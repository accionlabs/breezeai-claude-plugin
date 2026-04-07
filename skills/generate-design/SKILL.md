---
name: generate-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from
  functional graph. Maps Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "create design from functional", "generate UI structure",
  "map functional to design graph".
---

## Reference

Consult `references/guide.md` for:

- API tools documentation (Query & Mutation tools)
- Detailed mapping rules and payload structures
- Component types and reusability patterns
- designSystemRef lookup tables

---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

> 💡 **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). When calling any Breeze MCP tool, pass the value from
> `.breeze.json`'s `projectUuid` field as the `uuid` argument. Using any other
> name will fail with `Required → at uuid`.

---

## Step 0: Select Target Modalities

Ask user which modalities to generate design nodes for:

| Modality  | Description               |
| --------- | ------------------------- |
| `web`     | Browser-based interface   |
| `mobile`  | Native mobile application |
| `desktop` | Desktop application       |
| `api`     | Backend/Integration layer |
| `voice`   | Voice-based interface     |
| `chatbot` | Conversational interface  |

**Question:** "Which modalities do you want to create design for? (Select one or more)"

- Allow multiple selection
- Default: `web` if user doesn't specify
- Store selected modalities for use in Step 4

---

## Step 1: Batch Process Scenarios

Process scenarios one at a time (incremental batch processing).

> ⛔ **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Functional graphs can be arbitrarily large and
> bulk fetching WILL blow the context window. You cannot know the size in
> advance, so always assume it is large and fetch incrementally per scenario
> using the loop below. This rule has no exceptions, even for "small" projects.

**Required incremental fetch sequence (per iteration):**

1. `Get_scenarios_by_uuid` — fetch ONE unprocessed scenario directly using:
   - `uuid`: projectUuid from `.breeze.json`
   - `limit`: 1
   - `page`: 1
   - `filters[isDesignGenerated][$eq]=false`
   This returns the next scenario whose design graph has not yet been generated.
   Do NOT walk personas → outcomes → scenarios; call this tool directly.
2. `Get_all_steps_actions_for_a_scenario_id` — fetch steps + actions for ONLY
   that one scenario
3. Generate design nodes for that scenario
4. Mark the scenario as processed by setting `isDesignGenerated=true` (this is
   what makes the next `Get_scenarios_by_uuid` call return the next one)
5. Drop the scenario's data from working memory and repeat

**Processing Loop:**

```
LOOP:
  1. Fetch ONE scenario where isDesignGenerated=false
     Get_scenarios_by_uuid(uuid, limit=1, page=1,
       filters[isDesignGenerated][$eq]=false)

  2. IF no scenario found:
       Show: "All scenarios processed. Design generation complete."
       EXIT

  3. Fetch steps and actions for THIS scenario ONLY
     (Get_all_steps_actions_for_a_scenario_id)

  4. Show progress:
       Processing scenario: "Patient Registration"
         ├── Found 4 steps, 12 actions
         └── Processing...

  5. Execute Steps 2-5 for this scenario

  6. Mark scenario as processed (isDesignGenerated=true)

  7. Show: "Completed scenario: Patient Registration"

  8. REPEAT from step 1
END LOOP
```

**Why incremental is mandatory:**

- Bulk fetches can exceed the context window on large projects
- You cannot determine graph size before fetching it
- Per-scenario fetching keeps memory bounded regardless of project size
- Allows resumption if interrupted
- Maintains data consistency per scenario

---

## Step 2: Check Existing Design Coverage

### 2a. Check Direct Mappings

Query existing design nodes to find what's already mapped:

| Functional Node | Design Node | Check Field   |
| --------------- | ----------- | ------------- |
| Scenario        | UserJourney | `scenarioId`  |
| Step            | Flow/Page   | `stepIds[]`   |
| Action          | Component   | `actionIds[]` |

### 2b. Build Reusable Component Registry

Analyze actions and identify reusable patterns:

| Level    | Scope              | Examples                   |
| -------- | ------------------ | -------------------------- |
| `GLOBAL` | Entire application | TextInput, Button, Select  |
| `DOMAIN` | Business domain    | PatientCard, VitalsDisplay |
| `PAGE`   | Single page        | Specific layout component  |

Build map: `{ designSystemRef → existingComponentId or "CREATE_NEW" }`

### 2c. For Existing Mappings, Ask User

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

---

## Step 3: Generate Design Graph Nodes

### 3a. Scenario → UserJourney

Create one UserJourney per Scenario with `scenarioId` link.

### 3b. Step → Flow OR Page (Exclusive)

> A Step maps to Flow OR Page, never both.

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

**Create separate Flow/Page for EACH selected modality.**

### 3c. Action → Component (Reuse-First)

```
For each Action:
    │
    ├─► 1. Determine designSystemRef from action content
    │
    ├─► 2. Check Registry: Does component exist?
    │       │
    │       ├─► YES → REUSE: Add actionId to existing component
    │       │
    │       └─► NO → CREATE NEW with reusability level
    │
    └─► 3. ORGANISM containers: Always create new (page-specific)
            But children (MOLECULE/ATOM) can be reused
```

**What gets REUSED vs CREATED NEW:**

| Component Type           | Reuse? | Reason                            |
| ------------------------ | ------ | --------------------------------- |
| ATOM (TextInput, Button) | REUSE  | Same UI element, different labels |
| MOLECULE (FormField)     | REUSE  | Same pattern, different config    |
| ORGANISM (PatientForm)   | NEW    | Page-specific containers          |

### 3d. Template Generation (Optional)

Create TEMPLATE components for consistent page layouts based on pageType.

### 3e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 4: User Confirmation (Per Scenario)

Before creating any nodes, show user a complete preview for the current scenario.

### Preview Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DESIGN NODES PREVIEW - Scenario: "Patient Registration"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 UserJourney (1 node)
┌─────────────────────────────────────────────────────────────────┐
│ Name                      │ Mapped From                         │
├───────────────────────────┼─────────────────────────────────────┤
│ Patient Registration      │ Scenario: Patient Registration      │
└─────────────────────────────────────────────────────────────────┘

🔹 Flows (2 nodes)
┌─────────────────────────────────────────────────────────────────┐
│ Name                      │ Modality │ Mapped From              │
├───────────────────────────┼──────────┼──────────────────────────┤
│ Registration Flow (web)   │ web      │ Step: Complete Registration│
│ Registration Flow (mobile)│ mobile   │ Step: Complete Registration│
└─────────────────────────────────────────────────────────────────┘

🔹 Pages (4 nodes)
┌─────────────────────────────────────────────────────────────────┐
│ Name                      │ Modality │ PageType │ Mapped From   │
├───────────────────────────┼──────────┼──────────┼───────────────┤
│ Patient Form (web)        │ web      │ form     │ Step: Enter Info│
│ Patient Form (mobile)     │ mobile   │ form     │ Step: Enter Info│
│ Confirmation (web)        │ web      │ detail   │ Step: Confirm   │
│ Confirmation (mobile)     │ mobile   │ detail   │ Step: Confirm   │
└─────────────────────────────────────────────────────────────────┘

🔹 Components - NEW (3 nodes)
┌─────────────────────────────────────────────────────────────────┐
│ Name                │ Type     │ Reuse  │ Mapped From           │
├─────────────────────┼──────────┼────────┼───────────────────────┤
│ PatientForm         │ ORGANISM │ PAGE   │ (container)           │
│ DatePickerField     │ MOLECULE │ GLOBAL │ Action: Select DOB    │
│ GenderSelect        │ ATOM     │ GLOBAL │ Action: Select Gender │
└─────────────────────────────────────────────────────────────────┘

🔹 Components - REUSE EXISTING (5 links)
┌─────────────────────────────────────────────────────────────────┐
│ Existing Component  │ Type     │ Action to Link                 │
├─────────────────────┼──────────┼────────────────────────────────┤
│ TextInputField      │ MOLECULE │ Action: Enter Name             │
│ TextInputField      │ MOLECULE │ Action: Enter Email            │
│ TextInputField      │ MOLECULE │ Action: Enter Phone            │
│ Button              │ ATOM     │ Action: Submit Form            │
│ Button              │ ATOM     │ Action: Cancel                 │
└─────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total nodes to CREATE: 10 (1 UserJourney + 2 Flows + 4 Pages + 3 Components)
Total actions to LINK: 5 (reusing existing components)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Confirmation Options

Ask user: **"Proceed with creating these design nodes for this scenario?"**

| Option | Action |
|--------|--------|
| **Yes** | Create all nodes as shown |
| **No** | Skip this scenario, move to next |
| **Modify** | Let user specify changes before creating |

### If User Selects "Modify"

Allow user to:
- Remove specific nodes from creation
- Change node names
- Change component reusability level
- Skip certain mappings
- Change modality assignment

After modifications, show updated preview and ask for confirmation again.

---

## Step 5: Create Design Nodes

> ✅ **Use ONE bulk create call per scenario.** Do NOT create UserJourney,
> Flows, Pages, and Components with separate calls. The Breeze API accepts a
> single nested payload for an entire scenario's design subtree, which is
> dramatically faster and avoids partial-failure states.

### 5a. Bulk Create Payload (one call per scenario)

Send the entire scenario's design tree (UserJourney → Flows → Pages →
Components → nested children) in a single call. Payload shape:

```json
{
  "project": { "uuid": "<projectUuid>", "name": "<project name>" },
  "payload": {
    "userJourneys": [
      {
        "name": "Customer Onboarding",
        "description": "End-to-end signup and activation",
        "scenarioId": "<scenario-uuid>",
        "flows": [
          {
            "name": "Email Signup Flow",
            "description": "User signs up via email",
            "modality": "WEB",
            "entryPoint": "/signup",
            "exitPoint": "/dashboard",
            "stepIds": ["<step-uuid>"],
            "pages": [
              {
                "name": "Signup Page",
                "description": "Email/password signup form",
                "pageType": "FORM",
                "requiresAuth": false,
                "allowedRoles": ["guest"],
                "stepIds": ["<step-uuid>"],
                "components": [
                  {
                    "name": "SignupForm",
                    "type": "ORGANISM",
                    "description": "Signup form",
                    "designSystemRef": "ds://forms/SignupForm@1.2",
                    "props": "{\"variant\":\"default\"}",
                    "states": ["default", "loading", "error"],
                    "layoutType": "VERTICAL",
                    "slots": ["header", "body", "footer"],
                    "actionIds": ["<action-uuid>"],
                    "children": [
                      {
                        "name": "EmailInput",
                        "type": "ATOM",
                        "description": "Email text field",
                        "actionIds": []
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

Hierarchy is implicit via nesting — do NOT also pass `userJourneyId`,
`flowId`, `pageId`, or `parentComponentId` in the bulk payload; the server
infers them from the tree structure.

### 5b. Creation Order

Only one call is needed per scenario. After it succeeds, mark the scenario
processed (Step 5e).

### 5b. Link Actions to Existing Components

For reused components, update `actionIds[]` array.

### 5c. CONTAINS Relationships

Hierarchy is created automatically via parent ID fields:

- `userJourneyId` in Flow
- `flowId` in Page
- `pageId` in Component
- `parentComponentId` in nested Component

### 5d. Error Handling

| Failure Point        | Recovery Action                        |
| -------------------- | -------------------------------------- |
| UserJourney creation | Cannot proceed - critical failure      |
| Flow/Page creation   | Skip dependent components, log warning |
| Component creation   | Continue with other components         |
| Reuse update fails   | Create new component instead           |

### 5e. Mark Scenarios as Processed

After successful creation, update scenario with `isDesignGenerated: true`.

---

## Step 6: Output Summary

**Design Graph Generated (by Modality)**

| Modality  | UserJourneys | Flows | Pages | Components (New) |
| --------- | ------------ | ----- | ----- | ---------------- |
| web       | N            | N     | N     | N                |
| mobile    | N            | N     | N     | N                |
| **Total** | N            | N     | N     | N                |

**Component Reuse Statistics**

| Metric                        | Count |
| ----------------------------- | ----- |
| New GLOBAL components created | N     |
| New DOMAIN components created | N     |
| New PAGE components created   | N     |
| Existing components reused    | N     |

**Reuse Efficiency:** `(Reused / Total Actions) × 100`%

**Next Steps**

- Refine design nodes with additional properties
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design
