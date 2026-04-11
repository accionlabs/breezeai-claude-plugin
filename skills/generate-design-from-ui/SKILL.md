---
name: generate-design-from-ui
description: >
  Generate design graph (UserJourney, Flow, Page, Component) from
  functional graph scenarios, enriched by reading the actual frontend UI
  codebase. Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "design from UI", "ui to design graph", "generate design
  from frontend", "map ui to user journeys".
argument-hint: "[repo-path]"
---

## What this skill does

Generates **design graph nodes** from functional graph scenarios,
using the **actual UI codebase** as the primary source for component
discovery, hierarchy, props, and states.

```
Design Ontology
├── User Journey  (1:1 with functional Scenario)
│   └── Flow      (a distinct path/way to complete the journey — detected from UI)
│       └── Page   (screens needed to complete the flow — one or many)
│           └── Component (UI elements: atoms, molecules, organisms, templates)
```

**Hierarchy rules:**
- **Scenario → UserJourney** — 1:1 mapping, always
- **UserJourney → Flow(s)** — one or many flows per journey, discovered
  from the UI code. The functional graph captures WHAT the user does;
  the UI code reveals HOW MANY WAYS they can do it. These don't always
  align. Each flow is also multiplied per selected modality.
- **Flow → Page(s)** — one or many pages per flow. A simple flow
  may complete on a single page; a complex flow requires navigating
  through multiple pages in sequence.
- **Page → Component(s)** — the actual UI elements (atoms, molecules,
  organisms, templates) that make up the page and enable the user to
  complete the flow.

**Functional graph linkage:**
- `scenarioId` on UserJourney
- `stepIds[]` on Flows and Pages (steps distribute across flows/pages)
- `actionIds[]` on Components and Pages (actions map to the components
  that implement them)

Unlike `generate-design` which infers components from action
descriptions, this skill **reads the actual JSX/TSX code** to discover
real components, their nesting, props, states, and flow structure.

## Resources

- For design graph rules (component types, supportingComponents,
  reuse, payload structure), read
  [references/rules.md](references/rules.md)
- For shared design ontology guide (API tools, payload schemas), read
  [../generate-design/references/guide.md](../generate-design/references/guide.md)
- For atomic design theory and component classification, read
  [../generate-design/references/atomic-design-theory.md](../generate-design/references/atomic-design-theory.md)

## Inputs

- **UI repo path** — if provided as argument (`$ARGUMENTS`), use it
  directly; otherwise resolved in Phase -1
- **`.breeze.json`** — for `apiKey`, `apiBase`, `projectUuid`
- **Functional graph** — scenarios, steps, actions (fetched
  incrementally per scenario)
- **Existing design graph** — queried for dedup, not assumed empty

## Outputs

- **Design graph** updated with UserJourney > Flow > Page > Component
  nodes via `Bulk_Update_Design_Nodes` MCP tool
- **`existingcomponents.json`** — component registry for dedup

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing or incomplete, tell the user to run `/breeze:setup-project`
3. Extract `apiKey`, `projectUuid`

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

## Phase -1 — Resolve the target UI repo

1. Check if user passed a path via `$ARGUMENTS` — validate it exists
   and looks like a frontend repo
2. Check `.breeze.json` field `targetRepos.frontend`
3. Check if cwd looks like a frontend repo
4. Ask the user — single prompt: "Which UI repo do you want me to
   read? Provide an absolute path."
5. Persist the chosen path to `.breeze.json`:
   ```json
   { "targetRepos": { "frontend": "/abs/path/to/ui-repo" } }
   ```
6. If path has no frontend router file, stop and inform user

> **Frontend repo detection:** A valid frontend repo has `package.json`
> AND at least one of: `src/router/`, `src/routes/`, `app/routes`,
> `pages/`, `src/pages/`, `app/`, or React/Vue/Angular Router imports.

---

## Phase 0 — Configuration

### 0a. Detect Framework

Look for framework signals in the UI repo:
- React Router: `<Route`, `createBrowserRouter`, `useRoutes`
- Vue 2/3: `src/router/index.{js,ts}`
- Next.js: `pages/` or `app/` directory
- Angular: `*-routing.module.ts` or `app.routes.ts`
- Nuxt: `pages/` with `.vue` files
- SvelteKit: `src/routes/`

Record the detected framework for use during component reading.

### 0b. Processing Mode

Ask user which processing mode to use:

| Mode      | Description                                                |
| --------- | ---------------------------------------------------------- |
| `confirm` | Show preview and ask for confirmation before each scenario |
| `auto`    | Skip per-scenario confirmation; process all automatically  |

Default: `confirm` if user doesn't specify.

### 0c. Detect & Confirm Modalities

**Auto-detect the primary modality from the repo:**

| Repo Signal | Detected Modality |
|---|---|
| React Router, Next.js, Nuxt, Vue Router, Angular Router, SvelteKit | `web` |
| React Native, `react-native` in package.json, `expo` | `mobile` |
| Electron, `electron` in package.json, Tauri | `desktop` |
| Ionic, Capacitor | `mobile` + `web` (hybrid) |
| Flutter web, responsive meta tags + mobile breakpoints | `web` + `mobile` |

1. Detect the primary modality from the framework identified in 0a
   and `package.json` dependencies
2. Present the detected modality to the user:

   ```
   Detected modality: **web** (React Router SPA)

   Do you also want to generate design nodes for other modalities?
   This creates separate Flows per modality under each UserJourney.

   Available: mobile, desktop

   Enter additional modalities (comma-separated), or press Enter to
   continue with web only:
   ```

3. If user adds modalities → each scenario gets duplicate Flows per
   modality (e.g. "Login Web Flow" + "Login Mobile Flow") with the
   same pages but modality-specific naming
4. Store confirmed modalities list for the per-scenario loop

---

## Step 1: Initialize Component Registry File

> **MANDATORY — DO NOT RELY ON CACHING FOR COMPONENT REUSABILITY.**
> At the start of every run, create (or overwrite) a local
> `existingcomponents.json` file in the project root.

### 1a. Check if `existingcomponents.json` Exists

Look for `existingcomponents.json` in the plugin working directory.
If it does **not** exist, create it with the empty structure:

```json
{
  "ATOM": {},
  "MOLECULE": {},
  "ORGANISM": {},
  "TEMPLATE": {}
}
```

### 1b. Query All Existing Components (Paginated)

Fetch **all** components already in the design graph by paginating
through `Get_all_Design_By_Label`:

```
allComponents = []
page = 1
limit = 50

LOOP:
  1. Call Get_all_Design_By_Label(
       uuid: <projectUuid>,
       label: "Component",
       page: "<page>",
       limit: "<limit>"
     )
  2. Append returned nodes to allComponents
  3. IF returned count < limit → EXIT (no more pages)
  4. page += 1
  5. REPEAT
END LOOP
```

### 1c. Write `existingcomponents.json`

Populate (or overwrite) the file. Structure uses **component name as
key** for fast lookup:

```json
{
  "ATOM": {
    "Label": {
      "designSystemRef": "ds-label",
      "scope": "GLOBAL",
      "supportingComponents": []
    }
  },
  "MOLECULE": {},
  "ORGANISM": {},
  "TEMPLATE": {}
}
```

### 1d. Build Flow & Page Registries

> **Flows and Pages are reusable across scenarios.** A "Login Web Flow"
> created for Scenario A can be reused when Scenario B also passes
> through login. Same for pages — a "Dashboard Web Page" can appear in
> many flows. These registries enable LINK-before-CREATE at every level.

Query existing Flows and Pages (paginate if > 50):

```
Get_all_Design_By_Label(uuid, label: "Flow", page: "1", limit: "50")
Get_all_Design_By_Label(uuid, label: "Page", page: "1", limit: "50")
```

**Flow Registry** — index by `(name, modality)`:
```json
{
  "Login Web Flow": { "id": "flow-uuid-1", "stepIds": ["step-1"], "modality": "WEB" },
  "Registration Web Flow": { "id": "flow-uuid-2", "stepIds": ["step-2"], "modality": "WEB" }
}
```

**Page Registry** — index by `(name, pageType, modality)`:
```json
{
  "Dashboard Web Page|dashboard|WEB": { "id": "page-uuid-1", "stepIds": ["step-3"], "pageType": "dashboard" },
  "Login Web Page|form|WEB": { "id": "page-uuid-2", "stepIds": ["step-1"], "pageType": "form" }
}
```

**After each scenario's upsert**, add newly created Flows and Pages
to these registries so subsequent scenarios can reuse them — same
pattern as `existingcomponents.json` for Components.

---

## Step 2: Select Scenarios & Process

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the
> entire functional graph in one shot. Always fetch incrementally per
> scenario.

> **SKIP SYSTEM PERSONA SCENARIOS.**
> This skill generates design nodes for UI — System and External System
> persona scenarios have no user interface and MUST be excluded.
> See Step 2a-pre below for how to build the blocklist.

### 2a-pre. Build non-human outcome blocklist ⛔ BLOCKING GATE

> **⛔ HARD STOP: You MUST NOT proceed to scenario selection or
> processing until the blocklist is fully built. This gate ensures no
> System/External System scenario is ever processed. There is NO valid
> reason to skip this step — even in `auto` mode, even to "save time".**

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
   zero personas, STOP and tell user to run
   `/breeze:generate-functional-from-ui` first
6. Log: `"Blocklist built: {N} non-human outcome(s) from {M} non-human persona(s) will be excluded"`

**⛔ Gate check:** `blockedOutcomeIds` must exist before ANY scenario
is fetched, displayed, or processed. If this step fails, do not
continue.

**Usage during scenario processing:**

When fetching scenarios (Browse & Pick, Search, or Process All),
each scenario has an `outcomeId`. Check it against `blockedOutcomeIds`:

- `outcomeId` **in** `blockedOutcomeIds` → **skip** — show user:
  `"Skipping '{scenarioName}' — belongs to non-human persona (no UI)"`
- `outcomeId` **not in** `blockedOutcomeIds` → **proceed** normally

### 2a. Scenario Selection Mode

Ask the user how they want to select scenarios for design generation:

**Question:** "How would you like to select scenarios?\n\n1. **Browse & Pick** — I'll show you 10 scenarios at a time, you pick which ones to process\n2. **Search & Generate** — Search for a scenario by name, then generate design for it\n3. **Process All** — Process all unprocessed scenarios one by one (batch mode)\n\nChoose 1, 2, or 3:"

---

#### Option 1: Browse & Pick

1. Fetch a page of scenarios:
   `Get_scenarios_by_uuid(uuid: "<projectUuid>", page: "<currentPage>", limit: "10", isDesignGenerated: "false")`
2. For each scenario, check `outcomeId` against `blockedOutcomeIds`
   (from Step 2a-pre) — exclude matches from the display list
3. Display only human-persona scenarios:

   ```
   Unprocessed Scenarios (Page 1 of N — showing 10 of <total>):

   1. Login with Email — Persona: End User
   2. Register New Account — Persona: End User
   3. Reset Password — Persona: End User
   ...
   10. View Dashboard — Persona: Admin

   (N system persona scenarios excluded)

   Actions: Enter number(s) to select (e.g. "1,3,5"), "next" for next page, "all" to select all on this page
   ```

4. User selects scenarios by number (comma-separated), or:
   - `next` / `prev` — paginate through scenarios
   - `all` — select all scenarios on the current page
5. Collect selected scenarios into a `selectedScenarios` list
5. Ask: **"You selected {count} scenario(s). Proceed?"**
6. Process only the selected scenarios using the Processing Loop below

#### Option 2: Search & Generate

1. Ask: **"Enter scenario name (or keyword) to search:"**
2. Call `Functional_Graph_Search(query: "<userInput>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")` to find matching scenarios
3. Filter results: exclude any scenario whose `outcomeId` is in
   `blockedOutcomeIds`
4. If multiple matches found, display numbered list and let user pick
   one or more (same format as Option 1)
5. If exactly one match, confirm: **"Found: '{scenarioName}'. Generate design for this scenario?"**
6. If no matches, inform user and ask to try again or switch to another
   selection mode
7. Process selected scenario(s) using the Processing Loop below

#### Option 3: Process All (Default)

Batch mode. All unprocessed scenarios (`isDesignGenerated=false`) are
processed one by one, **skipping any whose `outcomeId` is in
`blockedOutcomeIds`**. This is the default if the user doesn't specify.

---

### 2b. Processing Loop

Process selected scenarios one at a time (incremental batch processing).

Before entering the loop, determine `totalScenarios`:
- **Option 1 & 2:** count of user-selected scenarios
- **Option 3:** fetch total using `Get_scenarios_by_uuid(uuid, page: "1", limit: "1", isDesignGenerated: "false")` and read `total` from response

```
counter = 0
skippedSystem = 0
LOOP:
  1. Get next scenario to process
     - Option 3: Fetch ONE scenario where isDesignGenerated=false
     - Option 1/2: Take next from selectedScenarios list
  2. IF no scenario remaining → EXIT
  3. Check scenario's outcomeId against blockedOutcomeIds:
     - IF outcomeId IN blockedOutcomeIds →
       Show: "Skipping '{scenarioName}' — belongs to non-human persona (no UI)"
       skippedSystem += 1
       REPEAT from step 1
  4. counter += 1
  5. Fetch steps and actions for THIS scenario ONLY
     → Get_all_steps_actions_for_a_scenario_id(uuid, parameters0_Value: <scenarioId>)
     → Extract and store:
        - scenarioId (the scenario UUID)
        - For each step: stepId (UUID), step name, step order
        - For each action under each step: actionId (UUID), action name, action description
     → These IDs are REQUIRED for linking design nodes to functional nodes
  6. Show progress: "[counter/totalScenarios] Scenario: <name>"
  7. Execute Steps 3-7 for this scenario
     (In `auto` mode: skip user confirmation in Step 6)
  8. ⛔ BLOCKING: Update existingcomponents.json with new components (Step 6d)
  9. Call Bulk_Update_Design_Nodes (Step 6f) — ONLY after step 8 is done
  10. Mark scenario as processed (Step 6i)
  11. REPEAT from step 1
END LOOP
```

> **⛔ The loop order above is non-negotiable.** Step 7 (update
> `existingcomponents.json`) MUST happen before Step 8 (bulk upsert) on
> EVERY iteration. Do not reorder, batch, or skip these steps.

### 2c. Extracted Data from `Get_all_steps_actions_for_a_scenario_id`

The response returns the full hierarchy. Extract and hold in memory
for the current scenario iteration:

```json
{
  "scenarioId": "scenario-uuid",
  "scenarioName": "Register New Account",
  "steps": [
    {
      "stepId": "step-uuid-1",
      "stepName": "Provide registration details",
      "order": 1,
      "actions": [
        {
          "actionId": "action-uuid-1",
          "actionName": "Provide email address",
          "description": null
        },
        {
          "actionId": "action-uuid-2",
          "actionName": "Provide password",
          "description": null
        }
      ]
    },
    {
      "stepId": "step-uuid-2",
      "stepName": "Submit registration",
      "order": 2,
      "actions": [
        {
          "actionId": "action-uuid-3",
          "actionName": "Submit registration form",
          "description": null
        }
      ]
    }
  ]
}
```

These IDs are used in Step 6 to populate:
- `scenarioId` on UserJourney
- `stepIds[]` on Flows and Pages
- `actionIds[]` on Components and Pages

---

## Step 3: Locate UI Code & Discover Flows for This Scenario

Using the step names and action names from the fetched functional data,
locate the corresponding UI code and discover how many distinct
paths/flows exist in the UI for completing this scenario.

### 3a. Map scenario to UI entry points

1. Use the scenario name and step names to grep the UI repo for
   matching routes, page titles, or component names
2. Use `Code_Graph_Search` as an accelerator, then confirm with `Read`
3. Identify the primary page directory for this scenario

### 3b. Discover flows (distinct paths) from UI code

Detect how many distinct ways a user can complete this journey.
There are **two types** of flow discovery:

- **Type A: Entry-point flows** — different navigation paths TO the
  target page (e.g. reaching `/ticket/:id` from project list vs
  dashboard vs sidebar)
- **Type B: On-page flows** — conditional rendering ON the target page
  that creates different component trees (e.g. social login vs email
  form)

---

#### Type A: Discover entry-point flows (different ways to reach the page)

**1. Identify the target route/page for this scenario** from Step 3a
(e.g. `/ticket/:id`, `/settings/profile`).

**2. Grep the ENTIRE UI repo for all navigation calls to that route:**

```
# React Router
grep -rn "navigate\(.*ticket\|<Link.*ticket\|to=.*ticket\|push\(.*ticket" --include="*.tsx" --include="*.jsx"

# Next.js
grep -rn "router\.push\(.*ticket\|<Link.*href=.*ticket" --include="*.tsx"

# Vue Router
grep -rn "router\.push\(.*ticket\|\$router\.push\(.*ticket\|<router-link.*ticket" --include="*.vue" --include="*.ts"

# Angular
grep -rn "routerLink=.*ticket\|router\.navigate\(.*ticket" --include="*.ts" --include="*.html"

# Generic
grep -rn "href=.*ticket\|window\.location.*ticket" --include="*.tsx" --include="*.ts"
```

**3. For each hit, identify the source page/component:**
- Which page/route does this `navigate()` or `<Link>` live in?
- Record: `{ sourcePage, sourceComponent, targetRoute }`

**4. Classify each entry point as a distinct flow or not:**

| Pattern | Separate Flow? | Why |
|---|---|---|
| Different source pages with different preceding steps | **Yes** | User navigates through different pages to get there |
| Same source page, different trigger components (sidebar vs card vs button) | **No** — same flow, different UI trigger | All start from the same page |
| Dashboard shortcut that skips listing page | **Yes** | Different page sequence (1 page vs 2 pages) |
| Breadcrumb/back navigation | **No** | Return path, not a forward flow |
| Deep link / direct URL | **Yes** — if the page behaves differently with no prior context | Different entry context |

**5. Check if target page behaves differently per entry point:**
- Grep the target page for `from`, `source`, `returnUrl`,
  `searchParams`, `location.state` — does it read where the user
  came from?
- If YES and renders differently → confirms separate flows
- If NO and renders identically → entry points share the same
  flow (different entry points don't create different page sequences)

---

#### Type B: Discover on-page flows (conditional paths on the target page)

**1. Grep the target page directory for branching patterns:**

```
# Conditional rendering / branching
grep -rn "? <\|: <\|&&\s*<" --include="*.tsx" --include="*.jsx"

# Tab/stepper variants
grep -rn "<Tab\|<Tabs\|<Stepper\|<Step\|activeStep\|activeTab\|TabPanel" --include="*.tsx"

# Auth method switches
grep -rn "authMethod\|loginType\|signInWith\|provider\|OAuth\|SSO\|socialLogin" --include="*.tsx"

# Feature flags / mode toggles
grep -rn "isAdvanced\|viewMode\|editMode\|quickMode\|expressMode\|isBulk" --include="*.tsx"

# Modal vs page alternatives
grep -rn "openModal\|showDrawer\|useDisclosure\|isInline\|isFullPage" --include="*.tsx"
```

**2. Read each hit and classify:**

| Pattern Found | Separate Flow? | Example |
|---|---|---|
| Ternary rendering different component trees | **Yes** | `isOAuth ? <SocialAuth/> : <EmailForm/>` |
| Tab group with self-contained workflows | **Yes** | `<Tab label="Import CSV">` / `<Tab label="Manual">` |
| Wizard with express/skip mode | **Yes** | `quickMode ? skipToStep3() : showAll()` |
| Modal vs full-page for same operation | **Yes** | `isInline ? <InlineEditor/> : navigate("/edit")` |
| Bulk vs single operation | **Yes** | `isBulk ? <BulkForm/> : <SingleConfirm/>` |
| Show/hide optional fields | **No** | `showAdvanced && <AdvancedOptions/>` |
| Loading/error states | **No** | `isLoading ? <Spinner/> : <Content/>` |
| Permission-gated sections | **No** | `canEdit && <EditButton/>` |
| Responsive layout switches | **No** | `isMobile ? <MobileLayout/> : <DesktopLayout/>` |

---

#### Combine Type A + Type B results

**Build the flow list:**

1. Start with discovered entry-point flows (Type A) — each distinct
   navigation path with different page sequences becomes a flow
2. Within each entry-point flow, check for on-page branching (Type B)
   — if found, split further
3. If no Type A or Type B signals → one default flow
4. Name each flow descriptively:
   - Type A: `"Generate User Stories from Dashboard Web Flow"`,
     `"Generate User Stories from Projects List Web Flow"`
   - Type B: `"Email Registration Web Flow"`,
     `"Social Login Web Flow"`
   - Combined: `"CSV Import via Settings Web Flow"`
5. Multiply all flows by each selected modality

**Record for each flow:**
- Flow name and description
- Entry point (which page the user starts from)
- Exit point (where the user ends up after completing the flow)
- Page sequence (which pages the user navigates through)
- Which UI components belong to this path
- Which steps/actions from the functional data map to this flow

### 3c. Map steps/actions to UI files per flow

For each discovered flow:
1. Identify which **steps** belong to this flow path
   - Record mapping: `stepId → page directory path`
   - Shared steps (e.g. "View confirmation page") can appear in
     multiple flows' `stepIds[]`
2. Identify which **actions** correspond to which UI components
   in this flow's component tree
   - Record mapping: `actionId → component file path`

### 3d. Build the file reading list

Collect all files that need to be read for this scenario (across
all discovered flows):
- Page entry components (`index.tsx`, `page.tsx`)
- Widget/component directories (`widgets/*`, `components/*`)
- Form components, modals, dialogs
- Shared components imported by the page
- Source pages for entry-point flows (the pages users navigate FROM)
- Flow-specific components (e.g. `SocialAuthPanel`, `EmailForm`,
  `BulkDeleteForm`, `WizardStepper`)

---

## Step 4: Deep-Read UI Code

### 4a. Read page files

For each file identified in Step 3b, `Read` the file and extract:
- Component hierarchy (JSX nesting)
- Props interface/type definitions
- State management (`useState`, `useReducer`, hooks)
- Interactive elements (forms, buttons, selects, tables)
- Layout structure (grid, flex, sidebar, header)

### 4b. Component-import drill-down

For every imported component matching
`/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/` AND
that has its own `useState`/`useReducer`/`useStore` hook, you MUST
read the file before drafting design nodes.

### 4c. Follow-the-trigger

For modals, drawers, panels triggered from this page:
- Viewer (read-only) → capture as components under this page
- Feature-rich (own forms/CRUD) → note for separate scenario processing

### 4d. Skip leaf primitives

Do NOT read: `Skeleton`, `LoadSkeleton`, `NoData`, `Empty`,
`Spinner`, `LoadingOverlay`. These are chrome, not functional
components.

---

## Step 5: Build Component Hierarchy from UI Code

### 5a. Classify components by atomic design level

Analyze the actual JSX structure to classify each component:

| UI Code Pattern | Design Level | Example |
|---|---|---|
| Page-level layout wrapper | TEMPLATE | `<PageLayout>`, `<DashboardGrid>` |
| Self-contained section with own state | ORGANISM | `<SearchForm>`, `<DataTable>` |
| Small group of elements as unit | MOLECULE | `<SearchBar>` (input + button) |
| Single UI element | ATOM | `<Button>`, `<Input>`, `<Label>` |

**ATOM indicators:** Single HTML element/thin wrapper, no internal
state, props-only interface.

**MOLECULE indicators:** 2-4 atoms composed together, minimal internal
state.

**ORGANISM indicators:** Self-contained section with own state
management (hooks), contains multiple molecules/atoms.

**TEMPLATE indicators:** Layout-only, no business logic, just slots
for children.

### 5b. Build `supportingComponents` from JSX nesting

Map actual JSX children to `supportingComponents` arrays:

| Component Type | `supportingComponents` contains |
|---|---|
| TEMPLATE | ORGANISM names only |
| ORGANISM | MOLECULE and/or ATOM names |
| MOLECULE | ATOM names only |
| ATOM | `[]` (empty) |

### 5c. Component naming (USE REPO NAMES)

> **CRITICAL: Use the actual component names from the codebase.**
> This is the key advantage of this skill over `generate-design` —
> design nodes should match the real code, not invented generic names.

**Naming priority:**

1. **Use the exact exported component name from the repo** — if the
   code has `export const SearchFilterPanel`, the design node name is
   `SearchFilterPanel`
2. **Use the file name** if the component is a default export with no
   explicit name — e.g. `search-filter-panel.tsx` → `SearchFilterPanel`
3. **Use PascalCase** — convert kebab-case or snake_case file names to
   PascalCase for the design node name

**Examples — repo name → design node name:**

| Code / File | Design Node Name | Type |
|---|---|---|
| `export const DataTable` | `DataTable` | ORGANISM |
| `export const SearchFilterPanel` | `SearchFilterPanel` | ORGANISM |
| `export const TextInputField` | `TextInputField` | MOLECULE |
| `export const IconButton` | `IconButton` | ATOM |
| `<Button>` from `ui/button.tsx` | `Button` | ATOM |
| `<DateRangePicker>` from `date-range-picker.tsx` | `DateRangePicker` | MOLECULE |
| `default export` in `project-card.tsx` | `ProjectCard` | MOLECULE |
| Layout in `page-layout.tsx` | `PageLayout` | TEMPLATE |

**When the repo doesn't have a named component:**
- HTML elements used directly (`<input>`, `<button>`, `<div>`) →
  use the design system name if from a library (e.g. MUI `TextField`
  → `TextField`), or standard name (`TextInput`, `Button`) if raw HTML
- Third-party library components → use the library's component name
  (e.g. `AgGridReact`, `ReactSelect`, `ChakraModal`)

**Reuse matching:**
When checking `existingcomponents.json` for reuse, match by the
**repo component name** first. Two scenarios using the same
`<SearchFilterPanel>` component should map to the same design node.

### 5d. Component reuse resolution

> **Always read `existingcomponents.json` before creating any component.**

Walk this priority order, stop at first match:

1. **Exact name match** in `existingcomponents.json` → REUSE
   (same repo component = same design node)
2. **Exact `designSystemRef` match** → REUSE
3. **Semantic + type match in same domain** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (GLOBAL > DOMAIN > PAGE)

**Scope rules:**
- ORGANISMs: page-specific → always CREATE NEW, reuse children
- TEMPLATEs: named by layout pattern (`FormPageLayout`), never by
  page name — this is the one exception where we use a generic name
  since templates are layout patterns, not code components

---

## Step 6: Build and Upsert Design Payload

### 6a. Assemble the design hierarchy (REUSE FIRST at every level)

Use the flows discovered in Step 3b and the step/action UUIDs from
Step 2c to build the design tree. At every level, **check for existing
nodes before creating new ones**.

---

**1. Scenario → UserJourney (1:1, always new)**
- `scenarioId` = scenario UUID (always required)
- UserJourneys are always unique per scenario — no reuse here

---

**2. Discovered paths → Flows (LINK before CREATE)**

For each flow discovered from UI code (Step 3b):

1. Check the **Flow Registry** (Step 1d) for a match by `(name, modality)`
2. **If match found → REUSE:**
   - Call `Update_Design_Node` to append current step UUIDs to the
     existing flow's `stepIds[]`
   - **Omit this flow from the bulk payload** — it already exists with
     all its pages and components
   - Show as "REUSE EXISTING" in the preview
   - The reused flow still appears under the UserJourney (backend links it)
3. **If no match → CREATE:**
   - Include as new flow in the bulk payload
   - `Flow.stepIds` = stepIds that belong to this path
   - After upsert, add to Flow Registry for future scenarios

**Example:** Scenario "Purchase Item" has a "Checkout Web Flow". If a
prior scenario already created "Checkout Web Flow", just link the new
stepIds — don't recreate all checkout pages and components.

---

**3. Pages within each flow (LINK before CREATE)**

For each page in a new flow (skip if flow was reused — pages already exist):

1. Check the **Page Registry** (Step 1d) for a match by
   `(name, pageType, modality)`
2. **If match found → REUSE:**
   - Call `Update_Design_Node` to append current step/action UUIDs to
     the existing page's `stepIds[]` / `actionIds[]`
   - **Omit this page from the bulk payload** — it and its components
     already exist
   - Show as "REUSE EXISTING" in the preview
3. **If no match → CREATE:**
   - Include as new page in the bulk payload
   - `Page.stepIds` = stepIds for steps rendered on this page
   - `Page.actionIds` = actionIds for page-level actions
   - After upsert, add to Page Registry for future scenarios

**Example:** Three different scenarios all end at the "Dashboard Web
Page". Only the first creates it; scenarios 2 and 3 just link their
stepIds to the existing page.

---

**4. Components on each page (REUSE via existingcomponents.json)**

For each component on a new page (skip if page was reused):

1. Check `existingcomponents.json` using the priority order from
   Step 5c (designSystemRef → semantic match → global match → create)
2. **If match found → REUSE:**
   - Include in payload with `designSystemRef` — backend appends
     `actionIds` automatically via upsert
3. **If no match → CREATE:**
   - Include as new component in payload
   - After upsert, add to `existingcomponents.json`

**Reusability by component type:**

| Type | Reuse behavior |
|---|---|
| ATOM | Always reuse globally (`TextInput`, `Button`, `Label`) |
| MOLECULE | Reuse globally or by domain (`TextInputField`, `SearchBar`) |
| ORGANISM | Always create new (page-specific), but reuse child molecules/atoms |
| TEMPLATE | Reuse globally by layout pattern (`FormPageLayout`) |

---

**Linking completeness rule:**
Every stepId and actionId from the fetched functional data MUST appear
in at least one design node — whether newly created or linked to an
existing node via `Update_Design_Node`.

### 6b. Determine page types from UI code

Derive `pageType` from actual UI analysis:

| UI Pattern | `pageType` |
|---|---|
| Form with inputs + submit | `form` |
| Table/list with rows | `list` |
| Detail view with data display | `detail` |
| Dashboard with widgets/cards | `dashboard` |
| Modal/dialog overlay | `modal` |
| Search with filters + results | `search` |
| Settings with sections | `settings` |
| Multi-step wizard/stepper | `wizard` |
| Report/chart view | `report` |

### 6c. Assign TEMPLATEs

Every Page MUST have a TEMPLATE. Map `pageType` to layout pattern:

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

Check `existingcomponents.json` → TEMPLATE section. If matching
TEMPLATE exists → REUSE. Otherwise → CREATE with scope `GLOBAL`.

### 6d. Update `existingcomponents.json` (BLOCKING GATE)

> **HARD STOP: You MUST NOT call `Bulk_Update_Design_Nodes` until
> `existingcomponents.json` has been updated for this scenario.**

1. Read `existingcomponents.json`
2. For each new component in the payload, add it under the appropriate
   type key (`ATOM`, `MOLECULE`, `ORGANISM`, `TEMPLATE`)
3. Write the file back
4. Verify the file was written successfully before proceeding

### 6e. Build the bulk payload

Assemble the nested tree: UserJourney → Flows → Pages → Components
(with `supportingComponents`) + TEMPLATEs.

**Payload structure (example with multiple flows):**

```json
{
  "userJourneys": [
    {
      "name": "User Registration Journey",
      "description": "End-to-end account registration",
      "scenarioId": "scenario-uuid",
      "flows": [
        {
          "name": "Email Registration Web Flow",
          "description": "Register with email and password form",
          "modality": "WEB",
          "entryPoint": "Registration page",
          "exitPoint": "Dashboard redirect",
          "stepIds": ["step-uuid-1", "step-uuid-2"],
          "pages": [
            {
              "name": "Registration Form Web Page",
              "description": "User fills in registration details",
              "pageType": "form",
              "requiresAuth": false,
              "allowedRoles": [],
              "stepIds": ["step-uuid-1"],
              "actionIds": ["action-uuid-1", "action-uuid-2"],
              "components": [
                {
                  "name": "FormPageLayout",
                  "type": "TEMPLATE",
                  "designSystemRef": "ds-form-page-layout",
                  "supportingComponents": ["RegistrationForm"]
                },
                {
                  "name": "RegistrationForm",
                  "type": "ORGANISM",
                  "description": "Email registration form with validation",
                  "designSystemRef": "ds-registration-form",
                  "props": "{\"onSubmit\": \"function\"}",
                  "states": ["idle", "loading", "error", "success"],
                  "actionIds": ["action-uuid-1"],
                  "supportingComponents": ["TextInputField", "PasswordInputField", "SubmitButton"]
                },
                {
                  "name": "TextInputField",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-text-input-field",
                  "actionIds": ["action-uuid-2"],
                  "supportingComponents": ["Label", "TextInput", "ErrorMessage"]
                },
                {
                  "name": "SubmitButton",
                  "type": "ATOM",
                  "designSystemRef": "ds-submit-button",
                  "supportingComponents": []
                }
              ]
            },
            {
              "name": "Email Verification Web Page",
              "description": "Confirm email address",
              "pageType": "detail",
              "stepIds": ["step-uuid-2"],
              "actionIds": ["action-uuid-3"],
              "components": [
                {
                  "name": "ConfirmationMessage",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-confirmation-msg",
                  "actionIds": ["action-uuid-3"],
                  "supportingComponents": ["Icon", "Heading", "Label"]
                }
              ]
            }
          ]
        },
        {
          "name": "Social Login Web Flow",
          "description": "Register via Google/GitHub OAuth",
          "modality": "WEB",
          "entryPoint": "Registration page",
          "exitPoint": "Dashboard redirect",
          "stepIds": ["step-uuid-1", "step-uuid-3"],
          "pages": [
            {
              "name": "Social Auth Web Page",
              "description": "Choose OAuth provider and authorize",
              "pageType": "form",
              "requiresAuth": false,
              "stepIds": ["step-uuid-1", "step-uuid-3"],
              "actionIds": ["action-uuid-4", "action-uuid-5"],
              "components": [
                {
                  "name": "SocialAuthPanel",
                  "type": "ORGANISM",
                  "description": "OAuth provider selection buttons",
                  "designSystemRef": "ds-social-auth-panel",
                  "actionIds": ["action-uuid-4"],
                  "supportingComponents": ["SocialLoginButton", "Divider", "Label"]
                },
                {
                  "name": "SocialLoginButton",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-social-login-btn",
                  "actionIds": ["action-uuid-5"],
                  "supportingComponents": ["Icon", "Label"]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Payload rules:**
- **One UserJourney per call** — one scenario per call
- **Nesting = hierarchy** — backend wires parent-child relationships
- **`scenarioId`** links UserJourney to functional scenario
- **`stepIds`** links Flows/Pages to functional steps
- **`actionIds`** links Components/Pages to functional actions
- **Multi-modality** — separate Flow entries per modality under same
  UserJourney
- **NO `children` field** — composition via `supportingComponents` only

### 6f. User confirmation (confirm mode only)

> **Skip in `auto` mode.** Print a progress line instead:
> `"[{current}/{total}] Processing: {scenarioName} → {flowCount} Flows, {pageCount} Pages, {componentCount} Components"`

Show preview covering: UserJourney, Flows, Pages, Components
(new + reused), Templates. Ask: **"Proceed with creating these
design nodes?"**

| Option | Action |
|---|---|
| **Yes** | Create all nodes as shown |
| **No** | Skip this scenario, move to next |
| **Modify** | Let user specify changes before creating |

### 6g. Make the bulk upsert call

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  data: <nested payload from 6e>
)
```

**One call per scenario.** Never batch multiple scenarios.

### 6h. Post-upsert: update Flow & Page registries

After `Bulk_Update_Design_Nodes` succeeds, update the **Flow and Page
registries** with real IDs so subsequent scenarios can LINK to them
via `Update_Design_Node(nodeId)`.

**Flow Registry:**
- For each new flow in the payload, fetch its real ID from the
  `Bulk_Update_Design_Nodes` response (or query
  `Design_Graph_Search` for the flow name)
- Add to registry:
  `{ name, modality, id: <real UUID>, stepIds }`

**Page Registry:**
- For each new page in the payload, fetch its real ID
- Add to registry:
  `{ name, pageType, modality, id: <real UUID>, stepIds }`

> **Why Flows/Pages need IDs but Components don't:**
> - **Flows/Pages** — when reused across scenarios, we call
>   `Update_Design_Node(nodeId, data: { stepIds: [...] })` to append
>   new stepIds. This requires the node's real UUID.
> - **Components** — reuse is handled by including the same
>   `designSystemRef` in the bulk payload. The backend deduplicates
>   automatically via upsert. No `Update_Design_Node` call needed,
>   so no ID needed in `existingcomponents.json`.

**`existingcomponents.json`** does NOT need a post-upsert ID sync.
It was already updated before the bulk call (Step 6d) with names and
designSystemRefs — that's all it needs for reuse resolution.

### 6i. Mark scenario as processed

```
Update_Functional_Node(
  uuid: <projectUuid>,
  apiKey: <apiKey>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true },
  citationId: [0],
  citations: [{ "type": "document", "name": "skip", "inputText": "skip" }]
)
```

### 6j. Error handling

| Failure Point | `confirm` mode | `auto` mode |
|---|---|---|
| Entire bulk call fails | Retry once; if still fails, report to user | Retry once; log error, skip scenario, continue |
| Partial failure | Log failed nodes, report to user | Log failed nodes, continue |

In `auto` mode, collect errors in `failedScenarios` list for the
final summary.

---

## Step 7: Output Summary

**Processing Summary** (`auto` mode only)

| Metric | Count |
|---|---|
| Total scenarios | N |
| Processed | N |
| Skipped (errors) | N |

**Failed Scenarios** (`auto` mode, only if errors)

| Scenario | Error |
|---|---|
| Name | ... |

> Failed scenarios remain `isDesignGenerated=false` and will be picked
> up on the next run.

---

**Design Graph Generated (by Modality)**

| Modality | UserJourneys | Flows | Pages | Templates (New/Reused) | Components (New) |
|---|---|---|---|---|---|
| web | N | N | N | N / N | N |
| **Total** | N | N | N | N / N | N |

**Component Reuse Statistics**

| Metric | Count |
|---|---|
| New GLOBAL components created | N |
| New DOMAIN components created | N |
| New PAGE components created | N |
| Existing components reused | N |

**Reuse Efficiency:** `(Reused / Total Components) x 100`%

**Next Steps**

- Refine design nodes with additional properties
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design

---

# REFERENCE

## What makes this skill different from `generate-design`

| Aspect | `generate-design` | `generate-design-from-ui` |
|---|---|---|
| Component source | Inferred from action descriptions | Read from actual JSX/TSX code |
| Component hierarchy | Guessed from action grouping | Derived from real import tree |
| Props & states | Inferred | Extracted from TypeScript interfaces |
| Realism | Approximate | Matches actual UI implementation |

Both skills share: scenario selection, component registry,
`Bulk_Update_Design_Nodes`, `existingcomponents.json` workflow.

## Cost per scenario

~**8-12 tool calls per scenario** (including UI code reading).
For 50 scenarios: 400-600 calls. Plan for multiple sessions.

## When NOT to use

- **No functional graph yet** — run `/breeze:generate-functional-from-ui`
  first to create scenarios
- **No UI repo available** — use `/breeze:generate-design` which works
  from functional graph alone
- **Backend-only repos** — this skill reads frontend UI code only
- **Figma-first workflow** — use `/breeze:analyze-design`

## See also

- `/breeze:generate-design` — design graph from functional graph (no UI code)
- `/breeze:generate-functional-from-ui` — functional graph from UI code
- `/breeze:create-page` — generate UI code from design nodes
- `/breeze:analyze-design` — analyze Figma designs
