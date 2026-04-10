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

| Modality        | Description                          |
| --------------- | ------------------------------------ |
| `web`           | Browser-based interface              |
| `mobile/tablet` | Native mobile & tablet application   |
| `desktop`       | Desktop application                  |

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

## Step 2: Select Scenarios & Process

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Always fetch incrementally per scenario.

### 2a. Scenario Selection Mode

Ask the user how they want to select scenarios for design generation:

**Question:** "How would you like to select scenarios?\n\n1. **Browse & Pick** — I'll show you 10 scenarios at a time, you pick which ones to process\n2. **Search & Generate** — Search for a scenario by name, then generate design for it\n3. **Process All** — Process all unprocessed scenarios one by one (batch mode)\n\nChoose 1, 2, or 3:"

---

#### Option 1: Browse & Pick

1. Fetch a page of scenarios:
   `Get_scenarios_by_uuid(uuid: "<projectUuid>", page: "<currentPage>", limit: "10", isDesignGenerated: "false")`
2. Display a numbered list with scenario name, outcome, and persona:

   ```
   Unprocessed Scenarios (Page 1 of N — showing 10 of <total>):

   1. Login with Email — Persona: End User
   2. Register New Account — Persona: End User
   3. Reset Password — Persona: End User
   ...
   10. View Dashboard — Persona: Admin

   Actions: Enter number(s) to select (e.g. "1,3,5"), "next" for next page, "all" to select all on this page
   ```

3. User selects scenarios by number (comma-separated), or:
   - `next` / `prev` — paginate through scenarios
   - `all` — select all scenarios on the current page
4. Collect selected scenarios into a `selectedScenarios` list
5. Ask: **"You selected {count} scenario(s). Proceed?"**
6. Process only the selected scenarios using the Processing Loop below

#### Option 2: Search & Generate

1. Ask: **"Enter scenario name (or keyword) to search:"**
2. Call `Functional_Graph_Search(query: "<userInput>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")` to find matching scenarios
3. If multiple matches found, display numbered list and let user pick one or more (same format as Option 1)
4. If exactly one match, confirm: **"Found: '{scenarioName}'. Generate design for this scenario?"**
5. If no matches, inform user and ask to try again or switch to another selection mode
6. Process selected scenario(s) using the Processing Loop below

#### Option 3: Process All (Default)

This is the batch mode. All unprocessed scenarios (`isDesignGenerated=false`) are processed one by one. This is the default if the user doesn't specify.

---

### 2b. Processing Loop

Process selected scenarios one at a time (incremental batch processing).

**Required incremental fetch sequence (per iteration):**

1. Fetch the scenario (for Option 3: `Get_scenarios_by_uuid(uuid, page: "1", limit: "1", isDesignGenerated: "false")`; for Options 1 & 2: use the already-fetched scenario from the selected list)
2. `Get_all_steps_actions_for_a_scenario_id` — fetch steps + actions for
   ONLY that scenario
3. Generate design nodes for that scenario
4. Mark scenario as processed (`isDesignGenerated=true`)
5. Drop the scenario's data from working memory and repeat

**Processing Loop:**

Before entering the loop, determine `totalScenarios`:
- **Option 1 & 2:** count of user-selected scenarios
- **Option 3:** fetch total using `Get_scenarios_by_uuid(uuid, page: "1", limit: "1", isDesignGenerated: "false")` and read `total` from response

```
counter = 0
LOOP:
  1. Get next scenario to process
     - Option 3: Fetch ONE scenario where isDesignGenerated=false
     - Option 1/2: Take next from selectedScenarios list
  2. IF no scenario remaining → EXIT
  3. counter += 1
  4. Fetch steps and actions for THIS scenario ONLY
  5. Show progress: "[counter/totalScenarios] Scenario: <name>"
  6. Execute Steps 3-4 for this scenario
     (In `auto` mode: skip Step 5 user confirmation)
  7. ⛔ BLOCKING: Update existingcomponents.json with new components (Step 6b)
  8. Call Bulk_Update_Design_Nodes (Step 6d) — ONLY after step 7 is done
  9. Mark scenario as processed (Step 6f)
  10. REPEAT from step 1
END LOOP
```

> **⛔ The loop order above is non-negotiable.** Step 7 (update
> `existingcomponents.json`) MUST happen before Step 8 (bulk upsert) on EVERY
> iteration. Do not reorder, batch, or skip these steps for any reason.

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
**Name MUST include modality** — format: `{Step} {Modality} Flow` / `{Step} {Modality} Page`
(e.g., "Sign Up Web Flow", "Sign Up Mobile Flow", "Registration Web Page", "Registration Mobile Page").

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

### 4d. Template Generation (Mandatory)

Every Page MUST be assigned a TEMPLATE. After generating all Pages in the
current scenario, apply this for each Page:

1. **Determine the layout pattern** from the Page's `pageType`:

   | `pageType`       | Standard TEMPLATE        |
   | ---------------- | ------------------------ |
   | form / create / edit / register | `FormPageLayout`   |
   | list / table / search           | `ListPageLayout`   |
   | detail / view / profile         | `DetailPageLayout` |
   | dashboard / overview            | `DashboardLayout`  |
   | wizard / multi-step             | `WizardLayout`     |
   | master-detail / split           | `SplitPaneLayout`  |
   | login / signup / reset          | `AuthPageLayout`   |

   If the page does not match any standard pattern, derive a generic layout
   name from its structure (e.g., `SettingsPageLayout`). Never name a template
   after a specific page — use the layout pattern name.

2. **Check `existingcomponents.json` → TEMPLATE section.** If a TEMPLATE
   with the matching `designSystemRef` already exists → REUSE it (do not
   create a duplicate). Add the Page's ORGANISMs to its `supportingComponents`
   if not already present.

3. **If no matching TEMPLATE exists → CREATE one** with:
   - `scope`: `GLOBAL` (templates are always reusable)
   - `designSystemRef`: the layout pattern name from the table above
   - `supportingComponents`: the ORGANISMs that slot into this layout

4. **Register** every new TEMPLATE in `existingcomponents.json` under the
   `TEMPLATE` key immediately after creation.

**Hard rules:**
- TEMPLATEs can ONLY contain ORGANISMs — never MOLECULEs or ATOMs directly
- TEMPLATEs define WHERE things go, not WHAT they are
- Name generically (`FormPageLayout`), never specifically (`PatientRegistrationTemplate`)
- One TEMPLATE per layout pattern, reused across all pages sharing that pattern

### 4e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 5: User Confirmation (Per Scenario)

> **Skip this step entirely when processing mode is `auto`.**
> In `auto` mode, proceed directly to Step 6 after generating the design
> nodes. Print a single progress line instead:
>
> `"[{current}/{total}] Processing: {scenarioName} → {flowCount} Flows, {pageCount} Pages, {componentCount} Components, {templateCount} Templates"`

### `confirm` mode (default):

Before creating nodes, show a preview for the current scenario covering:
UserJourneys, Flows, Pages, Components, Templates (new + reused). Include a
summary with total nodes to create and actions to link.

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
Pages → Components (with `supportingComponents`) + TEMPLATEs. One UserJourney per call (one scenario).

Include any new TEMPLATE nodes generated in Step 4d in the payload. TEMPLATEs
sit at the Page level with their ORGANISM `supportingComponents`. If the
TEMPLATE already exists (reused), omit it from the payload.

### 6b. Update `existingcomponents.json` (BLOCKING GATE — NEVER SKIP)

> **🚫 HARD STOP: You MUST NOT call `Bulk_Update_Design_Nodes` until
> `existingcomponents.json` has been updated for this scenario. This is a
> blocking prerequisite, not a suggestion. Skipping this step — even once,
> even to "save time", even in `auto` mode — breaks component reuse for ALL
> subsequent scenarios and causes duplicate components across the design graph.
> There is NO valid reason to skip this step.**

Before calling `Bulk_Update_Design_Nodes`, update `existingcomponents.json`
with ALL newly created components (ATOMs, MOLECULEs, ORGANISMs, TEMPLATEs)
from the current scenario.

1. Read `existingcomponents.json`
2. For each new component in the current scenario's payload, add it under
   the appropriate type key (`ATOM`, `MOLECULE`, `ORGANISM`, `TEMPLATE`):

   ```json
   "ComponentName": {
     "designSystemRef": "ds-ref",
     "scope": "SCOPE",
     "id": "<generated-unique-id>",
     "supportingComponents": ["ChildA", "ChildB"]
   }
   ```

3. Write the file back
4. **Verify** the file was written successfully before proceeding

**Why before bulk upsert:** If the bulk call fails or partially fails, the
next retry or the next scenario still sees these components for reuse and
avoids duplicates. The file is the single source of truth for deduplication
across scenarios.

**Consequences of skipping:** Molecules and organisms created in scenario N
will be invisibly duplicated in scenarios N+1, N+2, … resulting in a bloated,
inconsistent design graph that requires manual cleanup.

### 6c. Payload Rules

- **Nesting = hierarchy** — backend wires parent-child relationships
- **Component supportingComponents** — ORGANISM → MOLECULE/ATOM, MOLECULE → ATOM, ATOM → `[]`
- **Reused components** — include with `designSystemRef`; backend deduplicates via upsert
- **Multi-modality** — separate Flow entries per modality under the same UserJourney

### 6d. Make the Call

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  data: <nested payload>
)
```

### 6e. Error Handling

| Failure Point              | `confirm` mode                               | `auto` mode                                      |
| -------------------------- | -------------------------------------------- | ------------------------------------------------ |
| Entire bulk call fails     | Retry once; if still fails, report to user   | Retry once; if still fails, log error and skip scenario (continue loop) |
| Partial failure (returned) | Log failed nodes, report to user for review  | Log failed nodes, continue to next scenario      |

In `auto` mode, collect all errors in a `failedScenarios` list
(`{ scenarioId, scenarioName, error }`) and include them in the Step 7
summary.

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

| Modality  | UserJourneys | Flows | Pages | Templates (New/Reused) | Components (New) |
| --------- | ------------ | ----- | ----- | ---------------------- | ---------------- |
| web       | N            | N     | N     | N / N                  | N                |
| mobile    | N            | N     | N     | N / N                  | N                |
| **Total** | N            | N     | N     | N / N                  | N                |

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
