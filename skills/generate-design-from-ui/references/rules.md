## Design-from-UI Rules Reference

---

## Design Graph Hierarchy

```
Design Ontology
├── User Journey  (1:1 with functional Scenario)
│   └── Flow      (a distinct path/way to complete the journey — detected from UI)
│       └── Page   (screens needed to complete the flow — one or many)
│           └── Component (UI elements: atoms, molecules, organisms, templates)
```

### Hierarchy Rules

- **Scenario → UserJourney** — 1:1 mapping, always
- **UserJourney → Flow(s)** — one or many flows per journey. Flows
  represent **different ways/paths to complete that journey**, discovered
  from the UI code (e.g. social login vs email registration, bulk edit
  vs single edit, wizard vs quick-form)
- **Flow → Page(s)** — one or many pages per flow. A simple flow may
  complete on a single page; a complex flow requires navigating through
  multiple pages in sequence
- **Page → Component(s)** — the actual UI elements that make up the
  page and enable the user to complete the flow

### Functional → Design Linkage

| Design Node | Link Field | Source |
|---|---|---|
| UserJourney | `scenarioId` | Scenario UUID (always required) |
| Flow | `stepIds[]` | Steps that belong to this path |
| Page | `stepIds[]` | Steps rendered on this page |
| Page | `actionIds[]` | Page-level actions |
| Component | `actionIds[]` | Actions this component implements |

- **All IDs come from `Get_all_steps_actions_for_a_scenario_id`** —
  fetch steps + actions per scenario, extract UUIDs, then wire them
  into the design payload
- Shared steps can appear in multiple flows' `stepIds[]`
- Every `stepId` and `actionId` MUST appear in at least one design node
- `scenarioId` is ALWAYS required on UserJourney

### How Flows Are Discovered from UI Code

Flows are NOT mapped 1:1 from functional steps. They are discovered by
reading the UI code and identifying distinct paths:

| UI Signal | Indicates | Example |
|---|---|---|
| Conditional rendering by auth method | Separate auth flows | Social login vs email/password |
| Tab groups / stepper variants | Alternative paths | Quick form vs wizard mode |
| Feature flags / A-B switches | Variant flows | New UI vs legacy UI |
| Different routes to same outcome | Navigation variants | Create from list vs create from detail |
| Modal vs full-page for same action | Interaction variants | Inline edit vs edit page |
| Bulk vs single operation | Scale variants | Bulk delete vs single delete |

If only one path exists in the UI → one Flow (the default/only way).
If multiple paths → multiple Flows under the same UserJourney.

---

## Component Atomic Design Levels

Components are nestable at any granularity. Classification follows
atomic design theory:

| Level | Definition | When to Use |
|---|---|---|
| **TEMPLATE** | Page-level layout skeleton | Defines WHERE things go, not WHAT they are |
| **ORGANISM** | Self-contained section with own logic | Forms, tables, nav bars, card grids |
| **MOLECULE** | Small group of atoms working as unit | Label + input + error, search with button |
| **ATOM** | Single indivisible UI element | Button, input, label, icon, badge |

---

## Source-of-Truth Hierarchy

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the UI folder | **Primary** — pages, widgets, services, components | Filesystem has literal JSX, component hierarchy, props |
| `Code_Graph_Search` on the UI repo | **Optional accelerator** — locate pages or trace imports | Faster than blind globbing, but always confirm by `Read` |
| `Design_Graph_Search` | **Dedup check only** — never as source of UI knowledge | Step 2 dedup |
| Functional graph tools | **Scenario/step/action structure** — the skeleton to enrich | Fetch incrementally per scenario |

---

## Frontend Repo Detection

A valid frontend repo has `package.json` AND at least one of:
`src/router/`, `src/routes/`, `app/routes`, `pages/`, `src/pages/`,
`app/`, or React/Vue/Angular Router imports under `src/`.

---

## Component Classification from UI Code

### From JSX to Atomic Design Level

When reading actual UI code, classify components by analyzing their
structure, not just their name:

**ATOM indicators:**
- Single HTML element or thin wrapper (`<button>`, `<input>`, `<img>`)
- No internal state management
- Props-only interface
- Examples: `Button`, `Input`, `Label`, `Icon`, `Badge`, `Avatar`,
  `Checkbox`, `Radio`, `Switch`, `Tooltip`

**MOLECULE indicators:**
- 2-4 atoms composed together as a functional unit
- Minimal internal state (e.g. input focus, dropdown open)
- Examples: `SearchBar` (input + button), `FormField` (label + input +
  error), `MenuItem` (icon + label + badge), `Pagination` (buttons +
  page numbers)

**ORGANISM indicators:**
- Self-contained section with own state management
- Uses hooks (`useState`, `useReducer`, `useQuery`, `useMutation`)
- Contains multiple molecules/atoms
- Examples: `LoginForm`, `DataTable`, `NavigationBar`, `UserCard`,
  `FilterPanel`, `CommentThread`

**TEMPLATE indicators:**
- Layout-only component — defines grid/flex structure
- No business logic, just slots for children
- Examples: `PageLayout`, `SplitPane`, `DashboardGrid`,
  `FormPageLayout`, `WizardLayout`

---

## Component Naming Conventions

**CRITICAL:** ATOMs and MOLECULEs must be named **generically**.

| Wrong (instance-specific) | Right (generic) |
|---|---|
| `PatientNameInput` | `TextInput` |
| `FundAllocationTable` | `DataTable` |
| `LoginSubmitButton` | `SubmitButton` |
| `DashboardHeading` | `Heading` |

**When to create variants (distinct styling/behavior):**
- Button: `SubmitButton`, `CancelButton`, `DeleteButton`, `IconButton`
- Input: `TextInput`, `PasswordInput`, `EmailInput`, `NumberInput`,
  `TextArea`
- Label: Single generic reuse

**ORGANISM containers are page-specific** — always create new, but
reuse their children (molecules/atoms).

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

Before creating any component, read `existingcomponents.json`:

1. **Exact `designSystemRef` match** → REUSE
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope

**Hard rules:**
- Always check `existingcomponents.json` BEFORE creating
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

## Flow Discovery Rules

A Flow represents a **distinct path/way to complete the journey**.
Flows are discovered from UI code, not mapped from functional steps.

**Every UserJourney has at least one Flow.** If only one path exists,
create one Flow as the default path.

**When multiple Flows exist:**
- Each flow gets its own subset of stepIds (shared steps can repeat)
- Each flow has its own sequence of Pages
- Flows are named descriptively:
  `{Path Description} {Modality} Flow`
  (e.g. "Email Registration Web Flow", "Social Login Web Flow")

Create separate Flows for EACH selected modality.

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

### Three Registries

| Registry | Indexed by | Storage | Purpose |
|---|---|---|---|
| **Flow Registry** | `(name, modality)` | In-memory (rebuilt from DB at startup) | Reuse flows across scenarios |
| **Page Registry** | `(name, pageType, modality)` | In-memory (rebuilt from DB at startup) | Reuse pages across scenarios/flows |
| **Component Registry** | `(type, name)` + `designSystemRef` | `existingcomponents.json` on disk | Reuse components across pages |

### Reuse Decision per Level

**Flows — LINK before CREATE:**
1. Check Flow Registry for match by `(name, modality)`
2. Match found → `Update_Design_Node` to append `stepIds[]` → omit
   from bulk payload (flow + all its pages/components already exist)
3. No match → create in bulk payload → add to registry after upsert

**Pages — LINK before CREATE:**
1. Check Page Registry for match by `(name, pageType, modality)`
2. Match found → `Update_Design_Node` to append `stepIds[]` /
   `actionIds[]` → omit from payload (page + components already exist)
3. No match → create in bulk payload → add to registry after upsert

**Components — REUSE via existingcomponents.json:**
1. Check by `designSystemRef` (exact match)
2. Check by semantic + type match
3. Check by global atom/molecule name
4. No match → create new → add to registry before upsert (BLOCKING)

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

### Registry Update Timing

```
Before bulk upsert:
  ⛔ Update existingcomponents.json (BLOCKING GATE for components)

After bulk upsert:
  → Sync existingcomponents.json with real IDs from MCP
  → Add new Flows to Flow Registry (in-memory)
  → Add new Pages to Page Registry (in-memory)
```

### Flow & Page Deduplication

See **Reusability Rules** section above for the full LINK-before-CREATE
protocol at Flow and Page levels.

---

## Component-Import Drill-Down Rule

For every imported component matching
`/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/` AND
that has its own `useState`/`useReducer`/`useStore` hook, you MUST
read the file before drafting design nodes.

---

## MCP Tools Used

### Functional Graph Query Tools

| Tool | Purpose |
|---|---|
| `Get_scenarios_by_uuid` | Fetch scenarios with pagination and filtering |
| `Get_all_steps_actions_for_a_scenario_id` | Fetch steps + actions for one scenario |
| `Functional_Graph_Search` | Search for matching scenarios |

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

**`existingcomponents.json` update is a BLOCKING GATE** — must
complete before every `Bulk_Update_Design_Nodes` call.

**Post-upsert:** sync component registry from MCP to get real
node UUIDs.

**Mark processed:** `Update_Functional_Node` with
`isDesignGenerated: true` after successful upsert.

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading only `index.tsx` | < 3 components per page | Glob the page dir, read 4-10 files |
| Skipping component drill-down | Wrapper components hide sub-components | Follow import tree |
| Instance-specific atom names | Duplicate atoms across scenarios | Use generic names |
| Missing TEMPLATE | Page has no layout structure | Mandatory for every Page |
| Skipping existingcomponents.json update | Duplicate components | BLOCKING GATE |
| Batching multiple scenarios | Low per-scenario quality | One bulk call per scenario |
| Classifying all components as ORGANISM | Flat hierarchy | Use all atomic design levels |
| Naming templates after pages | Non-reusable templates | Name by layout pattern |
| Bulk-fetching functional graph | Memory overflow | Fetch incrementally per scenario |
| Mapping step to BOTH Flow and Page | Schema violation | Exclusive: Flow OR Page |
| Missing `scenarioId` link | Design graph disconnected from functional | Always include from fetched scenario |
| Guessing components from action names | Misses real UI structure | Read actual JSX code |
| Not fetching steps/actions | Missing stepIds/actionIds in payload | Always call Get_all_steps_actions_for_a_scenario_id |
| Orphaned stepIds/actionIds | Functional IDs not linked to design | Every ID must appear in at least one design node |
| Skipping Flow Registry check | Duplicate flows across scenarios | LINK before CREATE — check (name, modality) |
| Skipping Page Registry check | Duplicate pages across flows | LINK before CREATE — check (name, pageType, modality) |
| Not syncing registries post-upsert | Next scenario can't reuse | Update all 3 registries after every successful upsert |
