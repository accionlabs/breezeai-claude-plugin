---
name: generate-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from
  functional graph. Maps Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "create design from functional", "generate UI structure",
  "map functional to design graph".
---

## Resources

- For API tools, mapping rules, payload structures, bulk upsert format, component types, children array, reusability patterns, and designSystemRef lookup tables, read [references/guide.md](references/guide.md)

---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). When calling any Breeze MCP tool, pass the value from
> `.breeze.json`'s `projectUuid` field as the `uuid` argument. Using any other
> name will fail with `Required → at uuid`.
>
> **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter MUST
> be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or `scenario_id`).
> It maps to `filters[id][$eq]` on the backend. Using any other name fails
> with `Required → at parameters0_Value`.
>
> **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
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

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Always fetch incrementally per scenario.

**Required incremental fetch sequence (per iteration):**

1. `Get_scenarios_by_uuid` — fetch ONE unprocessed scenario (`limit: 1`,
   `page: 1`, `filters[isDesignGenerated][$eq]=false`)
2. `Get_all_steps_actions_for_a_scenario_id` — fetch steps + actions for
   ONLY that scenario
3. Generate design nodes for that scenario
4. Mark scenario as processed (`isDesignGenerated=true`)
5. Drop the scenario's data from working memory and repeat

**Processing Loop:**

```
LOOP:
  1. Fetch ONE scenario where isDesignGenerated=false
  2. IF no scenario found → EXIT
  3. Fetch steps and actions for THIS scenario ONLY
  4. Show progress
  5. Execute Steps 2-5 for this scenario
  6. Mark scenario as processed
  7. REPEAT from step 1
END LOOP
```

---

## Step 2: Check Existing Design Coverage

### 2a. Check Direct Mappings

Query existing design nodes to find what's already mapped:

| Functional Node | Design Node | Check Field   |
| --------------- | ----------- | ------------- |
| Scenario        | UserJourney | `scenarioId`  |
| Step            | Flow/Page   | `stepIds[]`   |
| Action          | Component   | `actionIds[]` |

### 2b. Build Reusable Registries

Rebuild every iteration from DB (source of truth). Query fresh via
`Get_all_Design_By_Label` before generating nodes.

**Flow Registry:**

Query `Get_all_Design_By_Label` (label=`Flow`). Index by
`(name, modality)`. Used in Step 3b to avoid duplicating flows
across scenarios.

**Page Registry:**

Query `Get_all_Design_By_Label` (label=`Page`). Index by
`(name, pageType, modality)`. Used in Step 3b to avoid duplicating pages
across scenarios.

**Component Registry:**

Query `Get_all_Design_By_Label` (label=`Component`) or `Design_Graph_Search`.
Index by `designSystemRef` (level-1) and by `(type, semantic-name, domain)`
(level-2/3). Used in Step 3c for component reuse.

| Level    | Scope              |
| -------- | ------------------ |
| `GLOBAL` | Entire application |
| `DOMAIN` | Business domain    |
| `PAGE`   | Single page        |

### 2c. For Existing Mappings, Ask User

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

---

## Step 3: Generate Design Graph Nodes

### 3a. Scenario → UserJourney

One UserJourney per Scenario with `scenarioId` link.
Name MUST end with `Journey` suffix.

### 3b. Step → Flow OR Page (Exclusive)

A Step maps to Flow OR Page, never both.

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

Create separate Flow/Page for EACH selected modality.

**Flow Deduplication (LINK before CREATE):**

Before creating a Flow, check the flow registry from Step 2b for an existing
flow with the same `(name, modality)`. If a match is found:

- Do NOT create a new Flow or its child Pages
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing flow's `stepIds[]`
- In the bulk payload, omit this flow entirely (it and its pages/components
  already exist)
- In the preview (Step 4), show the flow under "REUSE EXISTING" rather than
  "NEW"

A flow contains multiple pages that together complete the flow. Reusing a
flow automatically reuses all its pages and their components.

**Page Deduplication (LINK before CREATE):**

Before creating a Page, check the page registry from Step 2b for an existing
page with the same `(name, pageType, modality)`. If a match is found:

- Do NOT create a new Page
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing page's `stepIds[]`
- In the bulk payload, omit this page (and its components — they already
  exist on the page)
- In the preview (Step 4), show the page under "REUSE EXISTING" rather than
  "NEW"

This prevents the same page (e.g., "Patient Dashboard") from being duplicated
when multiple scenarios reference it.

### 3c. Component Reuse Resolution (REUSE FIRST)

Walk this priority order, stop at the first match:

1. **Exact `designSystemRef` match** → REUSE (append `actionId`)
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (`GLOBAL` > `DOMAIN` > `PAGE`)

**Hard rules:**

- Always check registry from Step 2b BEFORE creating
- ORGANISM containers are page-specific — always CREATE NEW; children follow rules 1–3
- Merge near-duplicates with same `designSystemRef`
- Never downgrade scope on reuse
- Ties: prefer higher scope and more `actionIds[]` linked

### 3d. Template Generation (Optional)

Create TEMPLATE components for consistent page layouts based on pageType.

### 3e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 4: User Confirmation (Per Scenario)

Before creating nodes, show a preview for the current scenario covering:
UserJourneys, Flows, Pages, Components (new + reused). Include a summary
with total nodes to create and actions to link.

Ask: **"Proceed with creating these design nodes for this scenario?"**

| Option     | Action                                   |
| ---------- | ---------------------------------------- |
| **Yes**    | Create all nodes as shown                |
| **No**     | Skip this scenario, move to next         |
| **Modify** | Let user specify changes before creating |

If "Modify": allow removing nodes, changing names, reusability levels,
modality assignments. Show updated preview and re-confirm.

---

## Step 5: Create Design Nodes (Bulk Upsert)

Use `Bulk_Update_Design_Nodes` to create the entire UserJourney tree for the
current scenario in **one call**. See [references/guide.md](references/guide.md)
for the full payload structure, children array rules, and examples.

### 5a. Build the Bulk Payload

Assemble the nested tree from the confirmed preview: UserJourney → Flows →
Pages → Components (with `children`). One UserJourney per call (one scenario).

### 5b. Payload Rules

- **Nesting = hierarchy** — backend wires parent-child relationships
- **Component children** — ORGANISM → MOLECULE/ATOM, MOLECULE → ATOM, ATOM → `[]`
- **Reused components** — include with `designSystemRef`; backend deduplicates via upsert
- **Multi-modality** — separate Flow entries per modality under the same UserJourney

### 5c. Make the Call

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  data: <nested payload>
)
```

### 5d. Error Handling

| Failure Point              | Recovery Action                              |
| -------------------------- | -------------------------------------------- |
| Entire bulk call fails     | Retry once; if still fails, report to user   |
| Partial failure (returned) | Log failed nodes, report to user for review  |

### 5e. Mark Scenario as Processed

```
Update_Functional_Node(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true }
)
```

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
