---
name: analyze-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from any
  input: Jira ticket, plain-text description, scenario references, or Figma
  wireframes. Builds requirement context, resolves matching functional graph
  scenarios/steps/actions, generates design nodes with component reuse, and
  optionally syncs results back to Jira. Use when: "analyze this design",
  "create design from this ticket", "generate design for these scenarios",
  user shares a Figma URL or Jira link, "design graph from requirement".
---

## Resources

- For functional graph node definitions (Outcome, Scenario, Step, Action), persona rules, action naming rules, and dedup decision matrix, read [references/functional-graph-rules.md](references/functional-graph-rules.md)
- For API tools, mapping rules, payload structures, bulk upsert format, component types, supportingComponents array, reusability patterns, and designSystemRef lookup tables, read [references/guide.md](../generate-design/references/guide.md)
- For atomic design theory, component type decision rules, hierarchy examples, full page breakdowns, and common mistakes, read [references/atomic-design-theory.md](../generate-design/references/atomic-design-theory.md)

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

## Step 0: Gather Input & Build Requirement Context

The user provides **any one (or more)** of the inputs below. A single input
is sufficient — do NOT ask for additional inputs if the user has already
provided one. Only ask if nothing was provided at all.

### 0a. Accepted Inputs

| Input | Example | How to Fetch |
| --- | --- | --- |
| **A. Jira ticket** (link or ID) | `PROJ-123` or `https://…/browse/PROJ-123` | `mcp__plugin_atlassian_atlassian__getJiraIssue` → extract summary, description, acceptance criteria, comments |
| **B. Plain-text description** | User types the requirement directly | Use as-is |
| **C. Scenario reference** | "create design for the login scenarios" | Noted — resolved in Step 1 |
| **D. Figma URL(s)** | `figma.com/design/:fileKey/…?node-id=:nodeId` | Fetch via Figma MCP, then run `/breeze:visual-to-text` to extract functional description |

If **none** of the above are provided, ask the user for at least one.
If the user provides just one input, proceed with that — do not prompt for others.

### 0b. Fetch Raw Content

For each input provided:

1. **Jira ticket →** call `getJiraIssue` and capture:
   - Summary & description
   - Acceptance criteria / definition of done
   - Comments (latest 10)
   - Linked issues (may reveal related scenarios)

2. **Figma URL(s) →** process wireframes to extract functional descriptions:
   1. Extract fileKey and nodeId from each URL (convert `-` to `:` in nodeId)
   2. Call `get_design_context` (Figma MCP) to fetch the screenshot and design data
   3. Run the **`/breeze:visual-to-text`** skill on the fetched frames — this
      produces structured user stories (personas, outcomes, scenarios, steps,
      actions) describing the functional intent behind the visual design
   4. Capture the visual-to-text output as part of the requirement context —
      this gives you both the UI elements identified AND the functional intent
      they represent

3. **Plain-text description →** use verbatim

4. **Scenario reference →** hold for Step 1

### 0c. Build Requirement Context

Synthesize all fetched content into a single **Requirement Context** document.
This is the lens through which you will search the functional graph and
generate design nodes.

```
REQUIREMENT CONTEXT
───────────────────
Source:        [Jira PROJ-123 | User description | Figma frame "Login" | …]

Summary:       <1-2 sentence description of what the user needs>

Key Capabilities:
  - <capability 1> (e.g., "User can log in with email and password")
  - <capability 2> (e.g., "User can reset password via email link")
  - …

From Figma / visual-to-text (if available):
  Personas identified:
    - <persona>: <description>
  Scenarios identified:
    - <scenario name>: <brief description>
  UI Elements:
    - <element>: <purpose> (e.g., "Email input: captures user email")
  Functional Intent:
    - <step → action mapping from visual-to-text output>

Acceptance Criteria (from Jira, if available):
  - <criterion 1>
  - …

Key Terms for Search:
  - <term 1>, <term 2>, <term 3>, …
```

Present this context to the user for confirmation:
**"Here's my understanding of the requirement. Does this look correct, or would you like to adjust anything?"**

---

## Step 1: Resolve Scenarios, Steps & Actions

Use the Requirement Context from Step 0 to find the functional graph nodes
that fulfil this requirement.

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Always fetch incrementally per scenario.

> **SKIP SYSTEM PERSONA SCENARIOS.**
> This skill generates design nodes for UI — System and External System
> persona scenarios have no user interface and MUST be excluded.
> See Step 1a-pre below for how to build the blocklist.

### 1a-pre. Build non-human outcome blocklist ⛔ BLOCKING GATE

> **⛔ HARD STOP: You MUST NOT proceed to scenario selection or
> processing until the blocklist is fully built. This gate ensures no
> System/External System scenario is ever processed. There is NO valid
> reason to skip this step.**

The functional graph hierarchy is **Persona → Outcome → Scenario**.
`Get_scenarios_by_uuid` does not have a persona filter, so we build
a blocklist of outcome IDs belonging to non-human personas and check
each scenario against it.

**Steps:**

1. Call `Get_all_personas(uuid: "<projectUuid>")`
2. From the response, identify non-human personas:
   - `System` → non-human
   - `External System` → non-human
   - Everything else (User, Admin, named roles) → human
3. For each **non-human persona**, call
   `Get_all_outcomes_for_a_persona_id(uuid, personaId: "<id>")`
4. Collect all outcome IDs from these calls into a
   `blockedOutcomeIds` set
5. **Verify** the set was built — if `Get_all_personas` returned
   zero personas, STOP and tell user to populate the functional graph first
6. Log: `"Blocklist built: {N} non-human outcome(s) from {M} non-human persona(s) will be excluded"`

**⛔ Gate check:** `blockedOutcomeIds` must exist before ANY scenario
is fetched, displayed, or processed. If this step fails, do not
continue.

**Usage during scenario processing:**

When resolving or processing scenarios, each scenario has an `outcomeId`.
Check it against `blockedOutcomeIds`:

- `outcomeId` **in** `blockedOutcomeIds` → **skip** — show user:
  `"Skipping '{scenarioName}' — belongs to non-human persona (no UI)"`
- `outcomeId` **not in** `blockedOutcomeIds` → **proceed** normally

### 1a. Resolve Scenarios

Scenarios can come from **three sources** — check each that applies and
merge into a single candidate list (deduplicate by scenario ID):

#### Source 1: Direct scenario reference (input C)

If the user explicitly named scenarios (e.g., "create design for the login
scenarios"), fetch them directly:

- Call `Functional_Graph_Search(query: "<scenario name>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")`
- Or call `Get_scenarios_by_uuid` and match by name
- Add matched scenarios to the candidate list

#### Source 2: Jira ticket linked scenarios

If a Jira ticket was provided, check whether it already has scenario
references — look for Breeze scenario names, scenario IDs, or functional
graph references in the ticket description, comments, or custom fields.

If found:
- Fetch each referenced scenario via `Functional_Graph_Search` or
  `Get_scenarios_by_uuid` to validate it exists in the graph
- Add validated scenarios to the candidate list

#### Source 3: Search by requirement context

Using the **Key Terms** from the Requirement Context, search for additional
matching scenarios:

```
Functional_Graph_Search(
  query: "<key terms>",
  project_uuid: "<projectUuid>",
  includeLabels: "[\"Scenario\"]"
)
```

Run multiple searches if the requirement spans different domains (e.g., one
search for "login authentication", another for "password reset").

Add results to the candidate list (skip duplicates already found via
Source 1 or 2).

> **Priority:** If Source 1 or Source 2 already yielded scenarios, those are
> the primary candidates. Source 3 results are supplementary — present them
> separately so the user can decide whether to include them.

### 1b. Handle No Scenarios Found — HARD STOP

If no matching scenarios are found:

> _"No functional graph scenarios found matching your requirement. The
> functional graph must exist before design generation can proceed. Please use
> `/breeze:update-functional-graph` to create the functional graph first, then
> re-run `/breeze:analyze-design`."_

**Stop here.**

### 1c. Fetch Steps & Actions for Each Matched Scenario

For each scenario found, call
`Get_all_steps_actions_for_a_scenario_id(uuid, parameters0_Value: <scenarioId>)`
and extract:
- `scenarioId` (UUID), scenario name
- For each step: `stepId`, step name, step order
- For each action under each step: `actionId`, action name, action description

### 1d. Map Requirement Context → Scenarios → Steps → Actions

Cross-reference the Requirement Context against the fetched functional data.
For each **Key Capability** and **UI Element** from the context, identify which
scenario → step → action covers it.

Present a coverage summary to the user, grouped by source:

```
Requirement Coverage:

  From direct reference / Jira ticket:
    1. ✓ Login with Email — Persona: End User [design: not generated]
       ├── Step 1: Enter Credentials
       │   ├── Action: Display email input field
       │   ├── Action: Display password input field
       │   └── Action: Display login button
       └── Step 2: Validate & Redirect
           ├── Action: Show validation errors
           └── Action: Redirect to dashboard

  From functional graph search:
    2. Reset Password — Persona: End User [design: not generated]
       ├── Step 1: Request Reset
       │   └── Action: Display reset form
       └── Step 2: Confirm Reset
           └── Action: Display confirmation message

  Gaps (not covered by any scenario):
  - <UI element or capability with no matching action>

  Unmatched Actions (in graph but not in requirement):
  - <action that exists but isn't relevant to this requirement>

Scenarios to process: 2 | Steps: 4 | Actions: 7
```

### 1e. User Confirms Scope

Ask: **"These are the scenarios, steps, and actions I'll use to generate the
design graph. Proceed with all, or would you like to adjust the selection?"**

- User can exclude scenarios, add more via search, or accept all
- If user says "none", stop

### 1f. Handle Already-Generated Scenarios

If any selected scenarios have `isDesignGenerated: true`, ask:

> _"The following scenario(s) already have design nodes:
> - Login with SSO
>
> 1. **Skip** — exclude these
> 2. **Regenerate** — delete existing and regenerate
> 3. **Continue anyway** — may create duplicates"_

### 1g. Select Target Modalities

Ask which modalities to generate design nodes for:

| Modality        | Description                        |
| --------------- | ---------------------------------- |
| `web`           | Browser-based interface            |
| `mobile/tablet` | Native mobile & tablet application |
| `desktop`       | Desktop application                |

Default: `web` if user doesn't specify.

---

## Processing Loop

Process selected scenarios one at a time.

```
counter = 0
LOOP:
  1. Take next scenario from selected list
  2. IF no scenario remaining → EXIT
  3. counter += 1
  4. Show progress: "[counter/totalScenarios] Scenario: <name>"
  5. Execute Steps 2-3 for this scenario (check coverage, generate nodes)
  6. Step 4: User confirmation
  7. Step 5: Bulk upsert
  8. Step 5e: Mark scenario as processed
  9. REPEAT from step 1
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

**Flow Registry:**

Query `Get_all_Design_By_Label` (label=`Flow`). Index by
`(name, modality)`. Used in Step 3b to avoid duplicating flows
across scenarios.

**Page Registry:**

Query `Get_all_Design_By_Label` (label=`Page`). Index by
`(name, pageType, modality)`. Used in Step 3b to avoid duplicating pages
across scenarios.

**Component Registry:**

Query `Get_all_Design_By_Label` (label=`Component`). Search by name,
`designSystemRef`, or `componentType` to find existing components for reuse.
Used in Step 3c for component reuse decisions — reuse if found, create new
if not.

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
Use the scenario name directly as the UserJourney name. Do NOT add "Journey" suffix.

### 3b. Step → Flow OR Page (Exclusive)

A Step maps to Flow OR Page, never both.

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

Create separate Flow/Page for EACH selected modality.
**Name format:** Use the step name directly (e.g., "Sign Up", "Registration"). Do NOT add "Flow"/"Page" suffix or modality — the node label and `modality` field already convey these.

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

> **Always search existing components via `Get_all_Design_By_Label(label: "Component")`
> or `Design_Graph_Search` before creating any component.**

Walk this priority order, stop at the first match:

1. **Exact `designSystemRef` match** in existing design graph → REUSE (append `actionId`)
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (`GLOBAL` > `DOMAIN` > `PAGE`)

**Hard rules:**

- Always search the design graph BEFORE creating
- ORGANISM containers are page-specific — always CREATE NEW; supportingComponents follow rules 1–3
- Merge near-duplicates with same `designSystemRef`
- Never downgrade scope on reuse
- Ties: prefer higher scope and more `actionIds[]` linked

### 3d. Template Generation (Mandatory)

Every Page MUST be assigned a TEMPLATE. After generating all Pages in the
current scenario, apply this for each Page:

1. **Determine the layout pattern** from the Page's `pageType`:

   | `pageType`                      | Standard TEMPLATE  |
   | ------------------------------- | ------------------ |
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

2. **Search existing TEMPLATEs** via `Get_all_Design_By_Label(label: "Component")`
   or `Design_Graph_Search` for a TEMPLATE with the matching `designSystemRef`.
   If found → REUSE it (do not create a duplicate). Add the Page's ORGANISMs
   to its `supportingComponents` if not already present.

3. **If no matching TEMPLATE exists → CREATE one** with:
   - `scope`: `GLOBAL` (templates are always reusable)
   - `designSystemRef`: the layout pattern name from the table above
   - `supportingComponents`: the ORGANISMs that slot into this layout

**Hard rules:**

- TEMPLATEs can ONLY contain ORGANISMs — never MOLECULEs or ATOMs directly
- TEMPLATEs define WHERE things go, not WHAT they are
- Name generically (`FormPageLayout`), never specifically (`PatientRegistrationTemplate`)
- One TEMPLATE per layout pattern, reused across all pages sharing that pattern

### 3e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 4: User Confirmation (Per Scenario)

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

## Step 5: Create Design Nodes (Bulk Upsert)

Use `Bulk_Update_Design_Nodes` to create the entire UserJourney tree for the
current scenario in **one call**. See [references/guide.md](../generate-design/references/guide.md)
for the full payload structure, supportingComponents array rules, and examples.

### 5a. Build the Bulk Payload

Assemble the nested tree from the confirmed preview: UserJourney → Flows →
Pages → Components (with `supportingComponents`) + TEMPLATEs. One UserJourney per call (one scenario).

Include any new TEMPLATE nodes generated in Step 3d in the payload. TEMPLATEs
sit at the Page level with their ORGANISM `supportingComponents`. If the
TEMPLATE already exists (reused), omit it from the payload.

### 5b. Payload Rules

- **Nesting = hierarchy** — backend wires parent-child relationships
- **Component supportingComponents** — ORGANISM → MOLECULE/ATOM, MOLECULE → ATOM, ATOM → `[]`
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

| Failure Point              | Action                                      |
| -------------------------- | ------------------------------------------- |
| Entire bulk call fails     | Retry once; if still fails, report to user  |
| Partial failure (returned) | Log failed nodes, report to user for review |

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

## Step 6: Sync to Jira (Conditional)

This step runs **only** if the original input included a Jira ticket link or
key. If no Jira ticket was provided, skip to Step 7.

> **Rules:** see [references/jira-sync-rules.md](references/jira-sync-rules.md)
> for confirmation gate, write protocol, description format preservation,
> analysis block template, and post-write confirmation.

### 6a. Ask for Confirmation

> _"Would you like me to append this design analysis to the description of
> Jira ticket `<TICKET-KEY>`? The existing description will be preserved and
> this analysis will be appended at the end."_

If the user declines → skip to Step 7. Never write to Jira without explicit
confirmation.

### 6b. Build & Append Analysis Block

1. Fetch the current ticket via `mcp__plugin_atlassian_atlassian__getJiraIssue`
   and capture the existing `description` verbatim
2. Build the analysis block using the template in
   [jira-sync-rules.md](references/jira-sync-rules.md) — fill from Steps 0–5
   (requirement context, coverage mapping, design graph created, gaps)
3. **Append** the analysis block to the existing description (never overwrite)
4. Call `mcp__plugin_atlassian_atlassian__editJiraIssue` with the combined
   description — only modify the `description` field, nothing else

### 6c. Confirm to User

Reply with the Jira ticket URL so the user can verify the appended analysis.
If the edit failed, surface the error and ask the user how to proceed.

---

## Step 7: Output Summary

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
