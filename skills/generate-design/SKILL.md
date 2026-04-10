---
name: generate-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from
  functional graph. Maps Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "create design from functional", "generate UI structure",
  "map functional to design graph".
---

## Resources

- For API tools, mapping rules, payload structures, bulk upsert format, component types, supportingComponents array, reusability patterns, and designSystemRef lookup tables, read [references/guide.md](references/guide.md)
- For atomic design theory, component type decision rules, hierarchy examples, full page breakdowns, and common mistakes, read [references/atomic-design-theory.md](references/atomic-design-theory.md)

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

## Step 0: Select Target Modalities & Processing Mode

### 0a. Processing Mode

Ask user which processing mode to use:

| Mode       | Description                                                        |
| ---------- | ------------------------------------------------------------------ |
| `confirm`  | Show preview and ask for confirmation before each scenario (default) |
| `auto`     | Skip per-scenario confirmation; process all unprocessed scenarios automatically |

**Question:** "Do you want to confirm each scenario before creating design nodes, or process all automatically? (`confirm` / `auto`)"

- Default: `confirm` if user doesn't specify
- In `auto` mode:
  - Skip Step 5 (User Confirmation) entirely
  - Log a one-line progress update per scenario instead (e.g., `"[12/700] Processing: Login Scenario → 3 Flows, 5 Pages, 14 Components"`)
  - On error: log the failure, skip the scenario, and continue to the next one
  - Show a final summary at the end (Step 7)

### 0b. Modalities

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

## Step 1: Initialize Component Registry File

> **MANDATORY — DO NOT RELY ON CACHING FOR COMPONENT REUSABILITY.**
> At the start of every generate-design run, create (or overwrite) a local
> `existingcomponents.json` file in the project root. This file is the single
> source of truth for component reuse decisions across scenarios.

### 1a. Check if `existingcomponents.json` Exists

Look for `existingcomponents.json` in the project root. If it does **not**
exist, create it with the empty structure before proceeding:

```json
{
  "ATOM": {},
  "MOLECULE": {},
  "ORGANISM": {},
  "TEMPLATE": {}
}
```

### 1b. Query All Existing Components

Call `Get_all_Design_By_Label` (label=`Component`) to fetch all components
already in the design graph.

### 1c. Write `existingcomponents.json`

Populate (or overwrite) the file. The structure uses **component name as
key** for fast lookup. Each entry must have:

| Field                  | Description                                      |
| ---------------------- | ------------------------------------------------ |
| `designSystemRef`      | Design system reference key                      |
| `scope`                | `GLOBAL`, `DOMAIN`, or `PAGE`                    |
| `id`                   | Node UUID from the design graph                  |
| `supportingComponents` | Array of child component names (empty for ATOMs) |

**Example:**

```json
{
  "ATOM": {
    "Label": { "designSystemRef": "ds-label", "scope": "GLOBAL", "id": "uuid-1", "supportingComponents": [] },
    "TextInput": { "designSystemRef": "ds-text-input", "scope": "GLOBAL", "id": "uuid-2", "supportingComponents": [] },
    "SubmitButton": { "designSystemRef": "ds-submit-btn", "scope": "GLOBAL", "id": "uuid-3", "supportingComponents": [] },
    "ErrorMessage": { "designSystemRef": "ds-error-msg", "scope": "GLOBAL", "id": "uuid-4", "supportingComponents": [] }
  },
  "MOLECULE": {
    "TextInputField": { "designSystemRef": "ds-text-input-field", "scope": "GLOBAL", "id": "uuid-5", "supportingComponents": ["Label", "TextInput", "ErrorMessage"] },
    "SearchInput": { "designSystemRef": "ds-search-input", "scope": "GLOBAL", "id": "uuid-6", "supportingComponents": ["TextInput", "SearchButton"] }
  },
  "ORGANISM": {
    "RegistrationForm": { "designSystemRef": "ds-registration-form", "scope": "PAGE", "id": "uuid-7", "supportingComponents": ["TextInputField", "SelectField", "DatePickerField", "SubmitButton", "CancelButton"] }
  },
  "TEMPLATE": {
    "FormPageLayout": { "designSystemRef": "ds-form-page-layout", "scope": "GLOBAL", "id": "uuid-8", "supportingComponents": ["PageHeader", "FormSection", "FormActions"] }
  }
}
```

### 1d. Usage Rules

- **Before creating any component** in Step 4c onward, read
  `existingcomponents.json` and check for a match — lookup by name is
  instant: `ATOM["Label"]`, `MOLECULE["TextInputField"]`, etc.
- **Check by `designSystemRef` too** for components that may have been
  renamed but share the same design system reference
- **Use `supportingComponents`** to know what's already inside a component
  when deciding whether to reuse it or create a variant
- **After each scenario's bulk upsert succeeds** (Step 6e), add all newly
  created components as new keys in the appropriate type object in
  `existingcomponents.json`
- This ensures every subsequent scenario sees components created by prior
  scenarios — no caching, no stale state

---

## Step 2: Batch Process Scenarios

Process scenarios one at a time (incremental batch processing).

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Always fetch incrementally per scenario.

**Required incremental fetch sequence (per iteration):**

1. `Get_scenarios_by_uuid(uuid: "<projectUuid>", page: "1", limit: "1", isDesignGenerated: "false")` — fetch ONE unprocessed scenario
2. `Get_all_steps_actions_for_a_scenario_id` — fetch steps + actions for
   ONLY that scenario
3. Generate design nodes for that scenario
4. Mark scenario as processed (`isDesignGenerated=true`)
5. Drop the scenario's data from working memory and repeat

**Processing Loop:**

Before entering the loop, fetch the total count of unprocessed scenarios
using `Get_scenarios_by_uuid(uuid, page: "1", limit: "1", isDesignGenerated: "false")`
and read the `total` from the response. Store as `totalScenarios` for
progress tracking.

```
counter = 0
LOOP:
  1. Fetch ONE scenario where isDesignGenerated=false
  2. IF no scenario found → EXIT
  3. counter += 1
  4. Fetch steps and actions for THIS scenario ONLY
  5. Show progress: "[counter/totalScenarios] Scenario: <name>"
  6. Execute Steps 3-6 for this scenario
     (In `auto` mode: skip Step 5 user confirmation)
  7. Mark scenario as processed
  8. Append newly created components to existingcomponents.json
  9. REPEAT from step 1
END LOOP
```

---

## Step 3: Check Existing Design Coverage

### 3a. Check Direct Mappings

Query existing design nodes to find what's already mapped:

| Functional Node | Design Node | Check Field   |
| --------------- | ----------- | ------------- |
| Scenario        | UserJourney | `scenarioId`  |
| Step            | Flow/Page   | `stepIds[]`   |
| Action          | Component   | `actionIds[]` |

### 3b. Build Reusable Registries

**Flow Registry:**

Query `Get_all_Design_By_Label` (label=`Flow`). Index by
`(name, modality)`. Used in Step 4b to avoid duplicating flows
across scenarios.

**Page Registry:**

Query `Get_all_Design_By_Label` (label=`Page`). Index by
`(name, pageType, modality)`. Used in Step 4b to avoid duplicating pages
across scenarios.

**Component Registry:**

> **DO NOT query the DB for components every iteration.**
> Read `existingcomponents.json` (created in Step 1) instead. This file is the
> single source of truth for component reuse. It was seeded from the DB at
> startup and is kept up-to-date after each scenario's bulk upsert.

Read `existingcomponents.json` and index by `designSystemRef` (level-1) and
by `(type, name, scope)` (level-2/3). Used in Step 4c for component reuse.

| Level    | Scope              |
| -------- | ------------------ |
| `GLOBAL` | Entire application |
| `DOMAIN` | Business domain    |
| `PAGE`   | Single page        |

### 3c. For Existing Mappings, Ask User

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

---

## Step 4: Generate Design Graph Nodes

### 4a. Scenario → UserJourney

One UserJourney per Scenario with `scenarioId` link.
Name MUST end with `Journey` suffix.

### 4b. Step → Flow OR Page (Exclusive)

A Step maps to Flow OR Page, never both.

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

Create separate Flow/Page for EACH selected modality.

**Flow Deduplication (LINK before CREATE):**

Before creating a Flow, check the flow registry from Step 3b for an existing
flow with the same `(name, modality)`. If a match is found:

- Do NOT create a new Flow or its child Pages
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing flow's `stepIds[]`
- In the bulk payload, omit this flow entirely (it and its pages/components
  already exist)
- In the preview (Step 5), show the flow under "REUSE EXISTING" rather than
  "NEW"

A flow contains multiple pages that together complete the flow. Reusing a
flow automatically reuses all its pages and their components.

**Page Deduplication (LINK before CREATE):**

Before creating a Page, check the page registry from Step 3b for an existing
page with the same `(name, pageType, modality)`. If a match is found:

- Do NOT create a new Page
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing page's `stepIds[]`
- In the bulk payload, omit this page (and its components — they already
  exist on the page)
- In the preview (Step 5), show the page under "REUSE EXISTING" rather than
  "NEW"

This prevents the same page (e.g., "Patient Dashboard") from being duplicated
when multiple scenarios reference it.

### 4c. Component Reuse Resolution (REUSE FIRST)

> **Always read `existingcomponents.json` before creating any component.**

Walk this priority order, stop at the first match:

1. **Exact `designSystemRef` match** in `existingcomponents.json` → REUSE (append `actionId`)
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (`GLOBAL` > `DOMAIN` > `PAGE`)

**Hard rules:**

- Always check `existingcomponents.json` BEFORE creating
- ORGANISM containers are page-specific — always CREATE NEW; supportingComponents follow rules 1–3
- Merge near-duplicates with same `designSystemRef`
- Never downgrade scope on reuse
- Ties: prefer higher scope and more `actionIds[]` linked

### 4d. Template Generation (Optional)

Create TEMPLATE components for consistent page layouts based on pageType.

### 4e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 5: User Confirmation (Per Scenario)

> **Skip this step entirely when processing mode is `auto`.**
> In `auto` mode, proceed directly to Step 6 after generating the design
> nodes. Print a single progress line instead:
>
> `"[{current}/{total}] Processing: {scenarioName} → {flowCount} Flows, {pageCount} Pages, {componentCount} Components"`

### `confirm` mode (default):

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

## Step 6: Create Design Nodes (Bulk Upsert)

Use `Bulk_Update_Design_Nodes` to create the entire UserJourney tree for the
current scenario in **one call**. See [references/guide.md](references/guide.md)
for the full payload structure, supportingComponents array rules, and examples.

### 6a. Build the Bulk Payload

Assemble the nested tree from the confirmed preview: UserJourney → Flows →
Pages → Components (with `supportingComponents`). One UserJourney per call (one scenario).

### 6b. Payload Rules

- **Nesting = hierarchy** — backend wires parent-child relationships
- **Component supportingComponents** — ORGANISM → MOLECULE/ATOM, MOLECULE → ATOM, ATOM → `[]`
- **Reused components** — include with `designSystemRef`; backend deduplicates via upsert
- **Multi-modality** — separate Flow entries per modality under the same UserJourney

### 6c. Make the Call

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  data: <nested payload>
)
```

### 6d. Error Handling

| Failure Point              | `confirm` mode                               | `auto` mode                                      |
| -------------------------- | -------------------------------------------- | ------------------------------------------------ |
| Entire bulk call fails     | Retry once; if still fails, report to user   | Retry once; if still fails, log error and skip scenario (continue loop) |
| Partial failure (returned) | Log failed nodes, report to user for review  | Log failed nodes, continue to next scenario      |

In `auto` mode, collect all errors in a `failedScenarios` list
(`{ scenarioId, scenarioName, error }`) and include them in the Step 7
summary.

### 6e. Update `existingcomponents.json`

After a successful bulk upsert, read `existingcomponents.json`, add all
**newly created** components as new keys in the appropriate type object,
and write the file back. Each new entry:

```json
"ComponentName": {
  "designSystemRef": "ds-ref",
  "scope": "SCOPE",
  "id": "uuid",
  "supportingComponents": ["ChildA", "ChildB"]
}
```

This ensures the next scenario iteration sees these components for reuse
without needing to re-query the DB.

### 6f. Mark Scenario as Processed

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

## Step 7: Output Summary

**Processing Summary** (`auto` mode only)

| Metric              | Count |
| ------------------- | ----- |
| Total scenarios     | N     |
| Processed           | N     |
| Skipped (errors)    | N     |

**Failed Scenarios** (`auto` mode, only if errors occurred)

| Scenario | Error |
| -------- | ----- |
| Name     | ...   |

> Failed scenarios remain `isDesignGenerated=false` and will be picked
> up on the next run.

---

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
