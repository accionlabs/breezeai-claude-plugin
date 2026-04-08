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
>
> 💡 **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter MUST
> be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or `scenario_id`).
> It maps to `filters[id][$eq]` on the backend. Using any other name fails
> with `Required → at parameters0_Value`.
>
> 💡 **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
> the node label as **`label`** (e.g., `label: "Component"`), NOT as
> `parameters0_Value`. The `parameters0_Value` naming is specific to
> `Get_all_steps_actions_for_a_scenario_id` — do not generalize it. Using
> the wrong name fails with `Required → at label`.

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

> ⚠️ **Registry must be rebuilt every iteration.** Do NOT cache the
> component registry across scenarios. At the start of each scenario
> iteration (after Step 1 fetches the scenario, before Step 3 generates
> nodes), query the design graph fresh via `Get_all_Design_By_Label`
> (label=`Component`) or, for large projects, `Design_Graph_Search`
> scoped to the current scenario's action vocabulary. The DB is the
> source of truth — this is what makes reuse work both across loop
> iterations within a run AND across separate runs of the skill
> (e.g., when a new scenario is added later). Index the result by
> `designSystemRef` (level-1 match) and by `(type, semantic-name,
domain)` (level-2/3 matches).

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

**Naming convention:** UserJourney `name` MUST end with the suffix
`Journey`. Derive it from the scenario name and append `Journey` if not
already present.

- Scenario `Patient Registration` → UserJourney `Patient Registration Journey`
- Scenario `Checkout` → UserJourney `Checkout Journey`
- Scenario `Onboarding Journey` → keep as-is (already ends in `Journey`)

### 3b. Step → Flow OR Page (Exclusive)

> A Step maps to Flow OR Page, never both.

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

**Create separate Flow/Page for EACH selected modality.**

### 3c. Component Reuse Resolution (REUSE FIRST)

Before creating any new Component, walk this priority order and stop at the
first match. Always prefer reuse over creation.

1. **Exact `designSystemRef` match** — a component already exists in the
   registry with the same `designSystemRef` (e.g., `ds://forms/TextInput@1.0`).
   REUSE: append the new `actionId` to its `actionIds[]`.
2. **Semantic + type match in same domain** — same component `type`
   (ATOM/MOLECULE) and semantically equivalent purpose within the same
   business domain (e.g., two "Patient name" inputs in the Patient domain).
   REUSE the existing DOMAIN-level component.
3. **Global atom/molecule match** — a `GLOBAL`-scoped ATOM or MOLECULE
   exists that satisfies the action regardless of domain (TextInput, Button,
   Select, Checkbox, DatePicker). REUSE the global component.
4. **Template/layout match** — for TEMPLATE-level reuse, an existing
   template matches the target `pageType` and modality. REUSE the template,
   only its slotted children differ.
5. **Create new** — no match above. Create with the narrowest reusability
   scope that is still correct: `GLOBAL` > `DOMAIN` > `PAGE`.

**Hard rules:**

- Always check the registry built in Step 2b BEFORE creating.
- ORGANISM containers are page-specific — always CREATE NEW at level 5,
  never reuse across pages. Their MOLECULE/ATOM children still follow
  rules 1–3.
- Merge near-duplicates (e.g., "Email Field" and "EmailInput" with same
  `designSystemRef`) — pick one canonical name and reuse it.
- Never downgrade scope on reuse: if a component is `GLOBAL`, do not
  create a `DOMAIN` copy of it for a new action — just append the
  `actionId`.
- If two candidates tie, prefer the one with the higher reusability scope
  (GLOBAL > DOMAIN > PAGE) and the more `actionIds[]` already linked.

### 3c-bis. Action → Component (mechanics)

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

| Option     | Action                                   |
| ---------- | ---------------------------------------- |
| **Yes**    | Create all nodes as shown                |
| **No**     | Skip this scenario, move to next         |
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

> ⛔ **MANDATORY — DO NOT BULK CREATE.** Bulk/nested create payloads are NOT
> allowed. Create each node with its own single Breeze MCP call. Walk the
> tree top-down (UserJourney → Flow → Page → Component → child Component)
> and issue one create call per node, passing the parent ID returned from
> the previous call as the explicit parent reference on the child.

### 5a. Per-Node Create Sequence

For the current scenario, in order:

1. Create the **UserJourney** (1 call) — pass `scenarioId`. Capture its
   returned `uuid`.
2. For each **Flow** under it: 1 call, passing `userJourneyId` = the
   UserJourney `uuid` from step 1, plus `stepIds[]` and `modality`.
3. For each **Page** under a Flow (or directly under the UserJourney if no
   Flow): 1 call, passing `flowId` (or `userJourneyId`), `pageType`,
   `stepIds[]`.
4. For each **Component** on a Page: 1 call, passing `pageId` and
   `actionIds[]`. For nested children (MOLECULE/ATOM inside an ORGANISM),
   pass `parentComponentId` = the parent component `uuid` from the prior
   call.

Each call is a single create — never combine multiple nodes into one
payload, and never use a nested `children`/`pages`/`flows` array on a
parent create.

### 5b. Link Actions to Existing Components

For components being reused (from Step 2b registry — created in this run or
a prior run), do NOT create a new component. Issue a single update call to
append the new action UUIDs to the existing component's `actionIds[]`.

### 5c. Hierarchy

Hierarchy is established **explicitly** via parent-id fields on each create
call (`userJourneyId`, `flowId`, `pageId`, `parentComponentId`). You must
wait for each parent create to return its `uuid` before issuing the child
create — these calls are sequential, not parallel.

### 5e. Error Handling

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
