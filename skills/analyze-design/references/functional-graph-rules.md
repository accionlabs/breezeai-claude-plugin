## Functional Graph Rules Reference (for Analyze-Design)

---

## Functional Graph Definitions

### Outcome

A high-level goal or capability a persona needs to accomplish.
Outcomes are **business capabilities**, not technical functions or
API endpoints.

- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent

**Good:** "Manage Fund Allocations", "Monitor Compliance Status"
**Bad:** "Handle API Requests", "Process Database Queries", "Render Components"

**Quality checks:** understandable by non-technical stakeholders,
stable across implementation changes, broad enough to absorb future
Scenarios. If more than 3-4 new Outcomes appear necessary,
re-evaluate for over-segmentation.

### Scenario

A **specific user or system flow** under an Outcome. Testable — you
can write acceptance criteria. Clear start and end.

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging
- Each Scenario must include a brief description

**Good:** "Filter Dashboard by Date Range", "Submit Compliance Report"
**Bad:** "Use the System", "Do Things with Data"

### Step

**Sequential stages** within a Scenario — the major phases to
complete the flow.

- Each Step is a distinct stage, ORDERED in sequence
- Step name = short verb phrase
- Steps do NOT require descriptions (the name is sufficient)
- A Scenario typically has 3-8 Steps (max 10)

### Action

**Atomic operations or user inputs** within a Step. Rules differ
by persona type:

**HUMAN PERSONA actions** (User, Admin, or any named role):
- Describe what the user PROVIDES, DECIDES, or OBSERVES
- MUST be platform-agnostic (web, mobile, CLI, voice)
- FORBIDDEN words: click, tap, swipe, hover, scroll, drag, drop,
  toggle, button, dropdown, modal, dialog, popup, panel, checkbox,
  radio, slider, tooltip, menu, sidebar, navbar, tab, icon
- USE instead: Provide, Choose, Confirm, Review, Dismiss, Open,
  Close, Submit, Cancel, Specify, Indicate, Acknowledge, Request
- description = null, unless a real user-facing constraint exists

**Quantity:** 1-5 Actions per Step. If more than 5, split the Step.

---

## Persona Rules

**Only human persona scenarios are eligible for design generation.**

| Persona Type | Process? | Reason |
|---|---|---|
| Human roles (User, Admin, etc.) | **Yes** | Has UI to design |
| System | **No — skip** | Background jobs, no UI |
| External System | **No — skip** | Webhooks/integrations, no UI |

**How to filter (blocklist approach) — BLOCKING GATE:**

> You MUST NOT process any scenario until the blocklist is fully built.

The hierarchy is `Persona → Outcome → Scenario`.

1. `Get_all_personas(uuid)` — get all personas
2. Identify non-human personas: `System`, `External System`
3. For each non-human persona:
   `Get_all_outcomes_for_a_persona_id(uuid, personaId)` → collect
   outcome IDs
4. Store all collected outcome IDs in `blockedOutcomeIds` set
5. When processing any scenario, check its `outcomeId`:
   - `outcomeId` in `blockedOutcomeIds` → **skip**, show user:
     `"Skipping '{name}' — belongs to non-human persona (no UI)"`
   - `outcomeId` not in `blockedOutcomeIds` → **proceed**

---

## Dedup Decision Matrix

When searching the functional graph for matching scenarios, use this
to decide whether to reuse or create new:

| Score | Match type | Action |
|---|---|---|
| > 0.6 | Same interaction model (single vs bulk, header vs row, modal vs inline) | **Reuse** — link to existing scenario |
| > 0.6 | Different interaction model | **Differentiate** — sibling scenario with disambiguated name |
| < 0.6 | No match | **Proceed fresh** |

---

## Design Graph Hierarchy

```
Design Ontology
├── User Journey  (1:1 with functional Scenario)
│   └── Flow      (a distinct path/way to complete the journey)
│       └── Page   (screens needed to complete the flow — one or many)
│           └── Component (UI elements: atoms, molecules, organisms, templates)
```

### Hierarchy Rules

- **Scenario → UserJourney** — 1:1 mapping, always
- **UserJourney → Flow(s)** — one or many flows per journey
- **Flow → Page(s)** — one or many pages per flow
- **Page → Component(s)** — the UI elements that make up the page

### Functional → Design Linkage

| Design Node | Link Field | Source |
|---|---|---|
| UserJourney | `scenarioId` | Scenario UUID (always required) |
| Flow | `stepIds[]` | Steps that belong to this path |
| Page | `stepIds[]` | Steps rendered on this page |
| Page | `actionIds[]` | Page-level actions |
| Component | `actionIds[]` | Actions this component implements |

- **All IDs come from `Get_all_steps_actions_for_a_scenario_id`**
- Shared steps can appear in multiple flows' `stepIds[]`
- Every `stepId` and `actionId` MUST appear in at least one design node
- `scenarioId` is ALWAYS required on UserJourney

---

## Component Atomic Design Levels

| Level | Definition | When to Use |
|---|---|---|
| **TEMPLATE** | Page-level layout skeleton | Defines WHERE things go, not WHAT they are |
| **ORGANISM** | Self-contained section with own logic | Forms, tables, nav bars, card grids |
| **MOLECULE** | Small group of atoms working as unit | Label + input + error, search with button |
| **ATOM** | Single indivisible UI element | Button, input, label, icon, badge |

---

## supportingComponents Array Rules

| Component Type | supportingComponents contains |
|---|---|
| TEMPLATE | ORGANISM names only |
| ORGANISM | MOLECULE and/or ATOM names |
| MOLECULE | ATOM names only |
| ATOM | `[]` (empty array) |

Order within `supportingComponents` reflects visual/logical order.

**NO `children` field** — composition is expressed solely through
`supportingComponents`.

---

## Component Reuse Resolution (Priority Order)

Before creating any component, search the design graph via
`Get_all_Design_By_Label` or `Design_Graph_Search`:

1. **Exact `designSystemRef` match** → REUSE
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope

**Hard rules:**
- Always search the design graph BEFORE creating
- ORGANISM containers are page-specific → always CREATE NEW
- Merge near-duplicates with same `designSystemRef`
- Never downgrade scope on reuse
- Ties: prefer higher scope and more linked nodes

**Scope levels:**

| Scope | Description | Examples |
|---|---|---|
| `GLOBAL` | Entire application | Button, TextInput, Label, Pagination |
| `DOMAIN` | Business domain | PatientCard, AppointmentSlot |
| `PAGE` | Single page only | DashboardHeader, ReportFooter |

---

## Template Generation Rules

Every Page MUST have a TEMPLATE.

| `pageType` | TEMPLATE Name |
|---|---|
| form / create / edit | `FormPageLayout` |
| list / table / search | `ListPageLayout` |
| detail / view / profile | `DetailPageLayout` |
| dashboard / overview | `DashboardLayout` |
| wizard / multi-step | `WizardLayout` |
| master-detail / split | `SplitPaneLayout` |
| login / signup / reset | `AuthPageLayout` |
| modal | `ModalLayout` |
| settings | `SettingsPageLayout` |

**Rules:**
- TEMPLATEs can ONLY contain ORGANISMs
- Define WHERE things go, not WHAT they are
- Named generically (`FormPageLayout`, NOT `PatientRegistrationTemplate`)
- One per layout pattern, reused across pages
- Always `GLOBAL` scope

---

## Flow Rules

A Flow represents a **distinct path/way to complete the journey**.

**Every UserJourney has at least one Flow.** If the requirement
describes a single path, create one default Flow.

**Naming:**
- Single flow: `"{Scenario Name}"`
- Multiple flows: `"{Path Description}"`
  (e.g. "Email Registration", "Social Login"). Do NOT add "Flow" suffix or modality — the node label and `modality` field already convey these.

**Multiply by modalities:**
- Each discovered flow × each selected modality = total flows
- modalities = `[web]`, 2 paths → 2 Flows
- modalities = `[web, mobile]`, 2 paths → 4 Flows

**Step distribution:**
- Each flow gets the stepIds for the steps it covers
- Shared steps can appear in multiple flows' `stepIds[]`

### Pages within a Flow

Each screen the user navigates through within a flow → one Page.

| Flow complexity | Pages |
|---|---|
| Simple (single screen) | 1 Page |
| Multi-step wizard | 1 Page per step |
| Navigation sequence | 1 Page per screen |

---

## Reusability Rules (LINK before CREATE)

Reusability is checked at **every level** of the design hierarchy.
The principle: **never create a duplicate — always link to existing
if semantically the same**.

### Reuse Decision per Level

**Flows — LINK before CREATE:**
1. Check existing Flows via `Get_all_Design_By_Label(label: "Flow")` for match by `(name, modality)`
2. Match found → `Update_Design_Node` to append `stepIds[]` → omit
   from bulk payload (flow + all its pages/components already exist)
3. No match → create in bulk payload

**Pages — LINK before CREATE:**
1. Check existing Pages via `Get_all_Design_By_Label(label: "Page")` for match by `(name, pageType, modality)`
2. Match found → `Update_Design_Node` to append `stepIds[]` /
   `actionIds[]` → omit from payload (page + components already exist)
3. No match → create in bulk payload

**Components — REUSE via design graph search:**
1. Check by `designSystemRef` (exact match)
2. Check by semantic + type match
3. Check by global atom/molecule name
4. No match → create new

### Reuse by Component Type

| Type | Reuse behavior | Scope |
|---|---|---|
| ATOM | Always reuse globally | GLOBAL |
| MOLECULE | Reuse globally or by domain | GLOBAL / DOMAIN |
| ORGANISM | Always create new, reuse children | PAGE |
| TEMPLATE | Reuse globally by layout pattern | GLOBAL |

### What Gets Linked vs Created

| Design Node | Same scenario | Across scenarios |
|---|---|---|
| UserJourney | Always new (1:1 with scenario) | Never reused |
| Flow | Unique within journey | **Reused** if same `(name, modality)` |
| Page | Unique within flow | **Reused** if same `(name, pageType, modality)` |
| Component (ATOM/MOLECULE) | Reused within page | **Reused** globally |
| Component (ORGANISM) | New per page | New per page (children reused) |
| Component (TEMPLATE) | Reused within page | **Reused** globally |

---

## MCP Tools Used

### Functional Graph Query Tools

| Tool | Purpose |
|---|---|
| `Get_scenarios_by_uuid` | Fetch scenarios with pagination and filtering |
| `Get_all_steps_actions_for_a_scenario_id` | Fetch steps + actions for one scenario |
| `Functional_Graph_Search` | Search for matching scenarios |
| `Get_all_personas` | Fetch all personas for filtering |
| `Get_all_outcomes_for_a_persona_id` | Fetch outcomes to build blocklist |

### Design Graph Query Tools

| Tool | Purpose |
|---|---|
| `Get_all_Design_By_Label` | Paginate existing design nodes by type |
| `Design_Graph_Search` | Semantic search for dedup |
| `Get_Design_Nodes_by_Ids` | Query nodes by relationships |

### Mutation Tools

| Tool | Purpose |
|---|---|
| `Bulk_Update_Design_Nodes` | **PRIMARY** — create entire UserJourney tree per scenario |
| `Update_Design_Node` | Link additional stepIds/actionIds to existing nodes |
| `Update_Functional_Node` | Mark scenario as processed (`isDesignGenerated=true`) |
| `Delete_Design_Node` | Remove nodes when replacing |

### Parameter Naming (CRITICAL)

| Tool | Parameter | Correct Name | Wrong Names |
|---|---|---|---|
| All Breeze MCP tools | Project ID | `uuid` | `projectId`, `projectUuid` |
| `Get_all_Design_By_Label` | Node label | `label` | `parameters0_Value` |
| `Get_all_steps_actions_for_a_scenario_id` | Scenario ID | `parameters0_Value` | `scenarioId`, `id` |

---

## Write Protocol

**This skill writes to the design graph EXCLUSIVELY via
`Bulk_Update_Design_Nodes`** — one call per scenario. Never batch
multiple scenarios in one call.

**Mark processed:** `Update_Functional_Node` with
`isDesignGenerated: true` after successful upsert.

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Missing TEMPLATE | Page has no layout structure | Mandatory for every Page |
| Batching multiple scenarios | Low per-scenario quality | One bulk call per scenario |
| Classifying all components as ORGANISM | Flat hierarchy | Use all atomic design levels |
| Naming templates after pages | Non-reusable templates | Name by layout pattern |
| Bulk-fetching functional graph | Memory overflow | Fetch incrementally per scenario |
| Mapping step to BOTH Flow and Page | Schema violation | Exclusive: Flow OR Page |
| Missing `scenarioId` link | Design graph disconnected from functional | Always include from fetched scenario |
| Not fetching steps/actions | Missing stepIds/actionIds in payload | Always call Get_all_steps_actions_for_a_scenario_id |
| Orphaned stepIds/actionIds | Functional IDs not linked to design | Every ID must appear in at least one design node |
| Skipping Flow dedup check | Duplicate flows across scenarios | LINK before CREATE — check (name, modality) |
| Skipping Page dedup check | Duplicate pages across flows | LINK before CREATE — check (name, pageType, modality) |
| Processing non-human persona scenarios | Design nodes for System/External personas | Build persona blocklist first |
| Forbidden words in action names | "Click button", "Toggle dropdown" | Use intent verbs: Provide, Choose, Confirm, etc. |
