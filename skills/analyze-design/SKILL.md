---
name: analyze-design
description: >
  Analyze UI/UX designs from Jira tickets and/or Figma wireframes.
  Fetches Jira ticket info, resolves linked functional scenarios,
  extracts visual descriptions from Figma, and generates design graph
  nodes (UserJourney, Flow, Page, Component). Use when: user shares a
  Jira ticket, a Figma URL, or both; "analyze this design", "design
  from Jira", "map Figma to design graph".
---

## Resources

- For design graph rules (component types, supportingComponents,
  reuse, payload structure), read
  [../generate-design-from-ui/references/rules.md](../generate-design-from-ui/references/rules.md)
- For shared design ontology guide (API tools, payload schemas), read
  [../generate-design/references/guide.md](../generate-design/references/guide.md)
- For atomic design theory and component classification, read
  [../generate-design/references/atomic-design-theory.md](../generate-design/references/atomic-design-theory.md)

---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). Pass `.breeze.json`'s `projectUuid` value as `uuid`.
>
> **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter
> MUST be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or
> `scenario_id`).
>
> **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
> the node label as **`label`** (e.g., `label: "Component"`), NOT as
> `parameters0_Value`.

---

## Step 1: Gather Input

The user can provide **one or both** of the following:

**A. Jira ticket** (e.g., `https://...atlassian.net/browse/PROJ-123` or `PROJ-123`)
- Use `mcp__plugin_atlassian_atlassian__getJiraIssue` to fetch the ticket details (summary, description, acceptance criteria, comments)
- Extract requirement context from the ticket content

**B. Figma URL(s)** (e.g., `figma.com/design/:fileKey/:fileName?node-id=:nodeId`)
- One or more Figma frame links for the wireframes/designs
- Do NOT fetch Figma yet — these are used later in Step 3

If neither a Jira ticket nor a Figma URL is provided, ask the user for at least one.

---

## Step 2: Resolve Functional Scenarios

The goal is to identify which functional graph scenarios are relevant to this Jira ticket / design.

### 2a. Check Jira Ticket for Linked Scenarios

If a Jira ticket was provided, check whether it already has scenario references — look for Breeze scenario names, scenario IDs, or functional graph references in the ticket description, comments, or custom fields.

### 2b. Search Functional Graph

Regardless of whether the Jira ticket has scenario links:

1. Extract key terms from the Jira ticket (summary, description, acceptance criteria) and/or the Figma URL context
2. Call `Functional_Graph_Search(query: "<key terms>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")` to find matching scenarios
3. If the Jira ticket had linked scenarios, also search for those specifically to validate they exist in the graph

### 2c. Filter Non-Human Persona Scenarios

> **Only human persona scenarios are eligible for design generation.**
> System and External System personas have no UI — their scenarios MUST be excluded.

1. Call `Get_all_personas(uuid: "<projectUuid>")`
2. Identify non-human personas: `System`, `External System`
3. For each non-human persona, call `Get_all_outcomes_for_a_persona_id(uuid, personaId: "<id>")` and collect all outcome IDs into a `blockedOutcomeIds` set
4. From the scenarios discovered in Steps 2a–2b, remove any scenario whose `outcomeId` is in `blockedOutcomeIds`
5. Log excluded scenarios: `"Excluded N scenario(s) belonging to non-human personas (System / External System) — no UI to design"`

### 2d. Handle No Scenarios Found — HARD STOP

If no matching scenarios remain after filtering (neither from Jira links nor from search, or all were non-human):

> _"No functional graph scenarios found for this Jira ticket / design. The functional graph must exist before design generation can proceed. Please use `/breeze:analyze-functional` to generate the functional graph first, then re-run `/breeze:analyze-design`."_

**Stop here.** Do not proceed to any further steps.

### 2e. Present Scenarios to User for Selection

Display all remaining human-persona scenarios in a numbered list. For each scenario, show its `isDesignGenerated` status:

```
Found scenarios related to this ticket/design:

From Jira ticket links:
  1. ✓ Login with Email — Persona: End User (linked in ticket) [design: not generated]
  2. ✓ Login with SSO — Persona: End User (linked in ticket) [design: already generated]

From functional graph search:
  3. Reset Password — Persona: End User [design: not generated]

(N non-human persona scenarios excluded)

Select scenarios to process (e.g. "1,2,3"), "all", or "none" to skip:
```

- If the Jira ticket had scenario links, pre-validate them: show ✓ if found in graph, ✗ if not found
- Show `[design: already generated]` or `[design: not generated]` for each scenario
- Show count of excluded non-human scenarios
- Ask the user to confirm which scenarios to process
- If user says "none", inform the user and stop

### 2f. Handle Already-Generated Scenarios

If any of the user's selected scenarios have `isDesignGenerated: true`, ask the user how to proceed **before** fetching steps/actions:

> _"The following scenario(s) already have design nodes generated:
> - Login with SSO
> - Account Lockout
>
> How would you like to proceed?
> 1. **Skip** — exclude these scenarios and only process the ungenerated ones
> 2. **Regenerate** — delete existing design nodes and regenerate from scratch
> 3. **Continue anyway** — process all selected scenarios (may create duplicate design nodes)"_

Apply the user's choice:
- **Skip**: remove already-generated scenarios from the selected list
- **Regenerate**: keep them in the list; in Step 6, delete existing design nodes before bulk upsert
- **Continue anyway**: keep them in the list; proceed without deleting existing nodes

### 2g. Fetch Steps & Actions for Selected Scenarios

For each selected scenario, call `Get_all_steps_actions_for_a_scenario_id(uuid, parameters0_Value: <scenarioId>)` and extract:
- `scenarioId` (UUID)
- For each step: `stepId`, step name, step order
- For each action under each step: `actionId`, action name, action description

Hold this data for use in design graph generation.

---

## Step 3: Fetch & Analyze Figma Designs

This step runs **only** if Figma URL(s) were provided. If no Figma URLs, skip to Step 4 — design graph generation will rely solely on the functional graph data (scenario steps & actions).

### 3a. Fetch Figma Frames

For each Figma URL:
1. Extract fileKey and nodeId from the URL
2. Convert "-" to ":" in nodeId
3. Call `get_design_context` (Figma MCP) with fileKey and nodeId
4. Review the screenshot and generated code

### 3b. Extract Functional Description from Figma (Visual-to-Text)

For each fetched Figma frame, analyze the visual design and extract a functional text description. Focus on:

**Input Elements:**
- Text fields, dropdowns, selectors, checkboxes, radio buttons, date pickers, file uploads, text areas

**Interactive Elements:**
- Primary/secondary action buttons, links, navigation items, tabs, accordions, modals, dialogs, toggles, switches

**Display Elements:**
- Headers, titles, labels, data tables, lists, cards, charts, status indicators, error/success messages

**Navigation:**
- Navigation bars, breadcrumbs, pagination, menu items

**Layout & Structure:**
- Page sections, containers, grid layouts

### 3c. Map Figma Descriptions to Scenarios

From the extracted Figma descriptions, identify which scenarios, steps, and actions are represented:
- Match Figma elements to the steps/actions fetched in Step 2
- Note any UI elements in the Figma that don't map to existing actions (potential gaps)
- Note any actions from the functional graph that have no corresponding UI element in the Figma

This mapping informs the design graph generation — the Figma descriptions provide richer context about what components look like and how they're laid out.

---

## Step 4: Generate Design Graph Nodes (Per Scenario)

Process each selected scenario one at a time. For each scenario, generate design nodes using the functional graph data (steps, actions) enriched by Figma descriptions (if available).

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

Create separate Flow/Page for EACH modality (default: `web`).
**Name MUST include modality** — format: `{Step} {Modality} Flow` / `{Step} {Modality} Page`.

**Flow Deduplication (LINK before CREATE):**
Before creating a Flow, search existing Flows via `Design_Graph_Search` or `Get_all_Design_By_Label(label: "Flow")` for match by `(name, modality)`. Match found → LINK (append `stepIds[]` via `Update_Design_Node`) instead of creating.

**Page Deduplication (LINK before CREATE):**
Before creating a Page, search existing Pages via `Design_Graph_Search` or `Get_all_Design_By_Label(label: "Page")` for match by `(name, pageType, modality)`. Match found → LINK instead of creating.

### 4c. Action → Component (REUSE FIRST)

Since we don't have a repo to read actual code from, components are inferred from:
1. **Figma descriptions** (if available) — use the visual elements identified in Step 3b
2. **Action names and descriptions** from the functional graph
3. **Existing components** in the design graph — search to maximize reuse

**Component Reuse Resolution (priority order):**
1. **Search existing components** via `Design_Graph_Search` or `Get_all_Design_By_Label(label: "Component")` for matching components by name or `designSystemRef` → REUSE
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (`GLOBAL` > `DOMAIN` > `PAGE`)

**Classify components using atomic design theory:**

| Level | When to Use |
|---|---|
| **TEMPLATE** | Page-level layout skeleton — defines WHERE things go |
| **ORGANISM** | Self-contained section (forms, tables, nav bars) — always CREATE NEW, reuse children |
| **MOLECULE** | Small group of atoms as unit (label + input + error) |
| **ATOM** | Single UI element (button, input, label, icon) |

**supportingComponents rules:**
- TEMPLATE → ORGANISM names only
- ORGANISM → MOLECULE and/or ATOM names
- MOLECULE → ATOM names only
- ATOM → `[]`

### 4d. Template Generation (Mandatory)

Every Page MUST have a TEMPLATE. Use the standard mapping:

| `pageType` | TEMPLATE Name |
|---|---|
| form / create / edit / register | `FormPageLayout` |
| list / table / search | `ListPageLayout` |
| detail / view / profile | `DetailPageLayout` |
| dashboard / overview | `DashboardLayout` |
| wizard / multi-step | `WizardLayout` |
| master-detail / split | `SplitPaneLayout` |
| login / signup / reset | `AuthPageLayout` |

Search existing TEMPLATEs via `Design_Graph_Search` or `Get_all_Design_By_Label(label: "Component")` for reuse. TEMPLATEs are always `GLOBAL` scope.

### 4e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 5: User Confirmation (Per Scenario)

Before creating nodes, show a preview for the current scenario:

```
Design Preview: [Scenario Name]

UserJourney: [Name] Journey
├── Flow: [Name] Web Flow (NEW / REUSE EXISTING)
│   ├── Page: [Name] Web Page — pageType: [type] (NEW / REUSE EXISTING)
│   │   ├── TEMPLATE: [LayoutName] (NEW / REUSE)
│   │   ├── ORGANISM: [Name] (NEW)
│   │   │   ├── MOLECULE: [Name] (REUSE)
│   │   │   └── ATOM: [Name] (REUSE)
│   │   └── ...
│   └── ...
└── ...

Summary: N new nodes, M reused | stepIds: [list] | actionIds: [list]
```

Ask: **"Proceed with creating these design nodes? (Yes / No / Modify)"**

If "Modify": allow removing nodes, changing names, reusability levels. Show updated preview and re-confirm.

---

## Step 6: Create Design Nodes (Bulk Upsert)

### 6a. Build & Send Bulk Payload

Assemble the nested tree: UserJourney → Flows → Pages → Components (with `supportingComponents`) + TEMPLATEs.

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  data: <nested payload>
)
```

One call per scenario. See [../generate-design/references/guide.md](../generate-design/references/guide.md) for payload structure.

### 6b. Mark Scenario as Design-Generated

```
Call_Update_Functional_Node_(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true }
)
```

### 6c. Repeat for Next Scenario

Return to Step 4 for the next selected scenario. Continue until all selected scenarios are processed.

---

## Step 7: Sync Analysis Back to Jira

This step runs **only** if the original input included a Jira ticket link/key. If no Jira ticket was provided, skip this step entirely.

1. Ask the user for explicit confirmation before touching Jira
2. On confirmation, fetch the current ticket via `mcp__plugin_atlassian_atlassian__getJiraIssue` and capture the existing `description` verbatim
3. Build the analysis block and **append** it to the existing description
4. Write the combined description back via `mcp__plugin_atlassian_atlassian__editJiraIssue` — never overwrite, never post as a comment, never edit any other field
5. Reply to the user with the Jira URL so they can verify

> **Rules:** see [jira-sync-rules.md](references/jira-sync-rules.md) → "When to Apply", "Confirmation Gate", "Write Protocol", "Description Format Preservation", "Analysis Block Template", and "Post-Write Confirmation".

---

## Step 8: Output Summary

**Design Analysis Summary: [Ticket Key / Frame Name]**

| Metric | Count |
|---|---|
| Scenarios processed | N |
| UserJourneys created | N |
| Flows (new / reused) | N / N |
| Pages (new / reused) | N / N |
| Components (new / reused) | N / N |
| Templates (new / reused) | N / N |

**Component Reuse Efficiency:** `(Reused / Total) × 100`%

**Gaps Identified:**
- Figma elements not mapped to functional actions
- Functional actions without Figma representation
- Acceptance criteria coverage (if Jira provided)

**Next Steps:**
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design refinement
