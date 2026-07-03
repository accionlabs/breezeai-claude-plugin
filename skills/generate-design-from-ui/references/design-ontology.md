# Design Ontology — Hierarchy, Linkage & Multi-Parent Model

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
- **UserJourney → Flow(s)** — one or many flows per journey, discovered
  from the UI code by grepping for conditional path indicators
  (branching component trees, tab workflows, auth method switches,
  modal-vs-page alternatives). Each flow is multiplied per modality
- **Flow → Page(s)** — one or many pages per flow. A simple flow may
  complete on a single page; a complex flow requires navigating through
  multiple pages in sequence
- **Page → Component(s)** — the actual UI elements that make up the
  page and enable the user to complete the flow

---

## Multi-Parent Reusability

Flows, Pages, and Components support **multi-parent relationships**:

- A **Flow** can be shared across multiple **UserJourneys** via
  `INCLUDES_FLOW` edges + `userJourneyIds[]` array
- A **Page** can be shared across multiple **Flows** via
  `CONTAINS_PAGE` edges + `flowIds[]` array
- A **Component** can be shared across multiple **Pages** via
  `CONTAINS` edges + `pageIds[]` array

### Backend Dedup Mechanism

**The backend deduplicates by `projectUuid + name` (case-insensitive).**
When a node with the same name already exists:
1. A new parent relationship edge is created (e.g. `INCLUDES_FLOW`)
2. The new parent ID is appended to the parent ID array
3. New `stepIds`/`actionIds` are appended to existing arrays
4. NO duplicate node is created

This means: **just include the node by name in the payload.** If it
exists, the backend links it. If not, the backend creates it.

### Deletion Behavior (Detach + Orphan Cleanup)

When a parent is deleted, shared children are NOT cascade-deleted:
1. The parent node is deleted (all its edges are detached)
2. The deleted parent's ID is removed from surviving children's arrays
3. Children with zero remaining parent edges are recursively deleted

---

## Functional → Design Linkage

| Design Node | Link Field | Source |
|---|---|---|
| UserJourney | `scenarioId` | Scenario UUID (always required) |
| Flow | `userJourneyIds[]` | Parent UserJourney IDs (multi-parent) |
| Flow | `stepIds[]` | Steps that belong to this path |
| Page | `flowIds[]` | Parent Flow IDs (multi-parent) |
| Page | `stepIds[]` | Steps rendered on this page |
| Component | `pageIds[]` | Parent Page IDs (multi-parent) |
| Component | `actionIds[]` | Actions this component implements |

- **All IDs come from `Get_all_steps_actions_for_a_scenario_id`** —
  fetch steps + actions per scenario, extract UUIDs, then wire them
  into the design payload
- Shared steps can appear in multiple flows' `stepIds[]`
- Every `stepId` and `actionId` MUST appear in at least one design node
- `scenarioId` is ALWAYS required on UserJourney

---

## Entity Field Reference

### UserJourney

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the user journey |
| `description` | string | No | Description |
| `scenarioId` | string | Yes | Linked functional Scenario ID |

### Flow

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the flow |
| `description` | string | No | Description |
| `modality` | string | Yes | `WEB`, `MOBILE`, `TABLET`, `DESKTOP`, `VOICE`, `API`, `KIOSK`, `WATCH`, `TV` |
| `entryPoint` | string | No | Page ID of the starting page |
| `exitPoint` | string | No | Page ID of the ending page |
| `userJourneyIds` | string[] | Yes | Parent UserJourney IDs (multi-parent) |
| `stepIds` | string[] | No | Linked functional Step IDs |

### Page

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the page |
| `description` | string | No | Description |
| `pageType` | string | No | `LIST`, `DETAIL`, `FORM`, `DASHBOARD` |
| `requiresAuth` | boolean | No | Requires authentication |
| `allowedRoles` | string[] | No | Roles allowed to access |
| `flowIds` | string[] | Yes | Parent Flow IDs (multi-parent) |
| `stepIds` | string[] | No | Linked functional Step IDs |

> **Page has NO `actionIds` field.** Actions map to Components only.

### Component

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Name of the component |
| `type` | string | Yes | `ORGANISM`, `MOLECULE`, `ATOM`, `TEMPLATE` |
| `description` | string | No | Description |
| `designSystemRef` | string | No | Design system reference (metadata, not dedup key) |
| `props` | string | No | JSON string of component properties |
| `states` | string[] | No | Component state definitions |
| `layoutType` | string | No | For TEMPLATEs: `GRID`, `FLEX`, `SIDEBAR`, `FULL` |
| `slots` | string[] | No | Named slot definitions for TEMPLATEs |
| `pageIds` | string[] | Yes | Parent Page IDs (multi-parent) |
| `actionIds` | string[] | No | Linked functional Action IDs |
| `supportingComponents` | string[] | No | Names of child components |

---

## Flow Rules

A Flow represents a **distinct path/way to complete the journey**,
discovered from the UI code.

**Every UserJourney has at least one Flow.** If no flow-splitting
signals are found in the UI code, create one default Flow.

**Naming:**
- Single flow: `"{Scenario Name}"`
- Multiple flows: `"{Path Description}"`
  (e.g. "Email Registration", "Social Login"). Do NOT add "Flow"
  suffix or modality — the node label and `modality` field already
  convey these.

**Multiply by modalities:**
- Each discovered flow × each selected modality = total flows
- modalities = `[WEB]`, 2 paths → 2 Flows
- modalities = `[WEB, MOBILE]`, 2 paths → 4 Flows

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

## Template Generation Rules

Every Page MUST have a TEMPLATE.

> **Valid `pageType` values:** `LIST`, `DETAIL`, `FORM`, `DASHBOARD`
> (uppercase only — these are the only values the backend accepts).

| `pageType`  | TEMPLATE Name      | `layoutType` |
|-------------|--------------------|--------------| 
| `FORM`      | `FormPageLayout`   | `FLEX`       |
| `LIST`      | `ListPageLayout`   | `FLEX`       |
| `DETAIL`    | `DetailPageLayout` | `FLEX`       |
| `DASHBOARD` | `DashboardLayout`  | `GRID`       |

> **Valid `layoutType` values:** `GRID`, `FLEX`, `SIDEBAR`, `FULL`

**Rules:**
- TEMPLATEs can ONLY contain ORGANISMs
- Define WHERE things go, not WHAT they are
- Named generically (`FormPageLayout`, NOT `PatientRegistrationTemplate`)
- One per layout pattern, reused across pages
- Always `GLOBAL` scope
