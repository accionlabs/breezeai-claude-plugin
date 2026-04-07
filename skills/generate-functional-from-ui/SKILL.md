---
name: generate-functional-from-ui
description: >
  Generate the User-persona side of the functional graph from a
  frontend UI repo. Reads the UI codebase from the filesystem
  (Glob/Read/Grep — NOT code graph as primary source) and produces
  human-persona scenarios + actions, with API endpoints captured in
  action.apis[]. NEVER writes the System persona — that is the
  generate-functional-from-backend skill's job. The UI pass and the
  backend pass are fully independent and share only the functional
  graph (idempotent merge by name).
  Use when: "generate functional from UI", "generate user persona
  from frontend", "ui to functional", "frontend functional pass",
  "run v2.1 frontend pass", "build user persona scenarios from UI".
---

## What this skill does

Transforms a frontend UI repo into the **User-persona** half of the
functional graph (Persona → Outcome → Scenario → Step → Action),
with API calls captured structurally in `action.apis[]`.

It is the **frontend half** of the recommended split pipeline:

```
generate-functional-from-ui   → User-persona scenarios   (this skill)
generate-functional-from-backend → System-persona scenarios
```

The two passes are fully independent — there is no file handoff
between them. They share the functional graph as the only common
surface; the upsert merges by **outcome name** so scenarios from
both passes land under the same outcome automatically.

The legacy `generate-functional-from-code` skill (Mode A cluster
pipeline) is **deprecated** but kept as a reference fallback for
backend-heavy or no-UI repos where running both passes is overkill.

## Guard

Read `.breeze.json` from the **plugin working directory**. If
missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `apiKey`, `projectUuid`, `apiBase`.

The project must already have at least one **code ontology**
indexed in Breeze (so `Functional_Graph_Search` and
`Code_Graph_Search` work). If not, run `/breeze:setup-project`
first.

## Phase -1 — Resolve the target UI repo

This skill operates on a **specific UI repo on the local filesystem**.
Resolve the path in this order:

1. **Explicit argument** — if the user provided a path
   (`/breeze:generate-functional-from-ui /path/to/repo`), validate
   that the path exists and looks like a frontend repo:
   - has a `package.json`, AND
   - has at least one of: `src/router/`, `src/routes/`, `app/routes`,
     `pages/`, `src/pages/`, `app/`, or React Router / Vue Router /
     Angular Router imports somewhere under `src/`
2. **`.breeze.json` field** — read `targetRepos.frontend` if present.
3. **Current working directory** — if the cwd looks like a frontend
   repo (same checks as 1), use it.
4. **Ask the user** — single prompt: "Which UI repo do you want me
   to read? Provide an absolute path." Do not guess across siblings.

After resolution, **persist the chosen path** to `.breeze.json` so
re-runs do not re-prompt:

```json
{
  "targetRepos": {
    "frontend": "/abs/path/to/ui-repo"
  }
}
```

If the resolved path does not contain a frontend router file at all,
**stop** with a clear message and suggest the user wanted
`/breeze:generate-functional-from-backend` instead.

All `Glob` / `Read` / `Grep` calls in the per-EP loop target this
resolved path. The code graph and functional graph are still queried
by `projectUuid` (no path scoping needed there).

## Why a separate frontend pass

A previous version of this skill mixed human-persona and System
persona generation in one per-EP loop. That caused:

- Backend coverage bounded by what the frontend touches
- Hallucinated route shapes when the agent got tired of repo-switching
- Workers and cron jobs completely invisible

The split pipeline fixes all three. The **frontend pass** (this
skill) is responsible for:

1. Every interactive widget on every UI page → captured as a
   human-persona scenario (`User`, or a domain-specific role like
   `Admin` / `Manager` / `Researcher` / `Subscriber` when the auth
   model has them)
2. Every API call the UI makes → captured in `action.apis[]` using
   the type enum **REST / GraphQL / gRPC / WebSocket / Event**

The frontend pass produces no handoff artifact for the backend pass.

## ★ Canonical rules — Persona / Outcome / Scenario / Step / Action ★

These are the rules from the official `analyze-functional` guide.
They apply to both the UI and backend passes. The skills adapt
**how** to discover the content, not **what shape** the content
takes.

### Persona — REUSE FIRST, then resolve in priority order

1. **Named human role** implied by the business domain
   (e.g. Admin, Fund Manager, Compliance Officer, Subscriber,
   Researcher, Lead Manager).
2. **Generic human role** when the domain role cannot be determined →
   `User`, `Customer`, `Visitor`.
3. **External System** — trigger originates outside the application
   boundary (webhooks, partner APIs, payment gateways, inbound
   integrations). Do NOT use for internal subsystems.
4. **System** — ONLY if the behavior is fully internal and automated
   with no human or external system initiating or consuming the
   outcome. **Reserved for the backend pass — never used here.**

**Rules:**
- Always check existing Personas FIRST before creating new ones
- Merge similar roles ("Admin User" + "Administrator" → reuse one)
- If ambiguous between User and System: "Does a human make a
  real-time decision that causes this to run?" YES → human persona
- If the triggering actor is truly ambiguous, default to **User**
- **Forbidden Persona names — NEVER use:** Developer, Engineer,
  Programmer, Architect, API, Service, Component, Module, Worker,
  Backend, Frontend, Database, Controller, Handler, Repository.

**For the UI pass specifically:** read the auth model (route guards,
JWT claims, role decorators) and use named human roles when present.
Fall back to `User` only when the repo's domain has no role
distinctions. **NEVER use `System` from the UI pass** — every UI
flow has a human triggering it.

### Outcome — high-level business capability, not a page or endpoint

- Outcomes are **business capabilities**, NOT technical functions or
  API endpoints
- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create a new Outcome ONLY if none can logically contain the intent

**Good:** "Manage Fund Allocations", "Monitor Compliance Status",
"Track Construction Project Opportunities"

**Bad (anti-patterns):** "Handle API Requests", "Open Dashboard",
"Use the Project Page" (page-named, technical, or trivial)

**Quality checks:**
- Understandable by non-technical stakeholders
- Stable across implementation changes
- Broad enough to absorb future Scenarios
- **If more than 3-4 new Outcomes appear necessary for an entire
  product, re-evaluate for over-segmentation.** Most products have
  5-10 outcomes total, not one per page.

### Scenario — a specific testable user flow

- Describes a specific user flow under an Outcome
- Testable — you can write acceptance criteria for it
- Clear start and end
- Reuse existing Scenario if semantically similar
- If two Scenarios share >70% of their steps, consider merging
- Each Scenario must include a brief description

### Step — sequential stages within a Scenario

- Each Step is a distinct stage in the Scenario's flow
- Steps are ORDERED — they represent a sequence
- Step name = short verb phrase
- **Steps do NOT require descriptions** — the name is sufficient
- A Scenario typically has 3-8 Steps (max 10)

### Action — atomic operation, human-persona rules

- Actions describe what the user **provides, decides, or observes**
- Actions MUST be **platform-agnostic** — must work for web, mobile,
  CLI, voice, or any future channel without rewriting
- **FORBIDDEN words in human-persona action names:**
  click, tap, swipe, hover, scroll, drag, drop, toggle, button,
  dropdown, modal, dialog, popup, panel, checkbox, radio, slider,
  tooltip, menu, sidebar, navbar, tab, icon
- Use intent verbs instead: **Provide, Choose, Confirm, Review,
  Dismiss, Open, Close, Submit, Cancel, Specify, Indicate,
  Acknowledge, Request**
- `description = null` UNLESS the context specifies a real
  user-facing constraint (e.g. "Minimum 20 characters", "Blocked
  until all files uploaded")
- The structured `apis[]` block CAN be present on a human-persona
  action when the action triggers an API call. `apis[]` is the
  structured handoff for downstream tooling and is separate from
  the human-readable description constraint.

**Quantity:** A Step typically has 1-5 Actions. If more than 5,
consider splitting the parent Step.

## Inputs

- **UI repo path** — resolved in Phase -1 above
- **`.breeze.json`** — for `apiKey`, `apiBase`, `projectUuid`
- **Existing functional graph** — queried for dedup, not assumed empty
- **Optional: `entrypoints.json`** if resuming from a prior session

## Outputs

- **Functional graph** updated with User-persona scenarios + actions
- **`entrypoints.json`** — the inventory + running checkpoint (created
  in Phase 0, updated after every EP). Lives in the **plugin working
  directory** (next to `.breeze.json`), not in the target UI repo.

The frontend pass writes NO other files. There is no
`frontend_api_log.json` or any other handoff artifact. If you find
yourself wanting to write one, that's a smell — the backend pass is
designed to discover everything from the backend repos themselves.

## Source-of-truth hierarchy

**Filesystem first, code graph second, functional graph for dedup only.**

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the UI folder | **Primary** — for reading pages, widgets, services, queries, stores | Filesystem has the literal JSX, decorator strings, store fields, hook names. Code graph stores summarized/embedded versions and loses literal detail. |
| `Code_Graph_Search` on the UI repo | **Optional accelerator** — to locate entry-point pages or trace cross-file flows when you don't already know where to look | Faster than blind globbing for "where is the X feature implemented?" but always confirm by `Read`ing the actual file before citing. |
| `Functional_Graph_Search` | **Dedup check only** — never as a source of code knowledge | See Step 1. |
| `Get_Code_File_Details` | **Avoid** for frontend reading | Use raw `Read` on the JSX/TSX file. Code-file-details is structured for backend route extraction; for JSX it loses the visual element tree. |

## Phase 0 — Discover entry points (mandatory, runs once before the per-EP loop)

If `entrypoints.json` already exists in the working directory, **read
it and skip to the per-EP loop** — you are resuming a prior session.
Do not overwrite.

If it does not exist, run all 9 sub-steps below. Skipping any sub-step
leaves a major gap in the resulting graph.

### Sub-step 0.1 — Detect the framework

- React Router: look for `<Route`, `createBrowserRouter`, `useRoutes`
  in App or routes files
- Vue 2/3: `src/router/index.{js,ts}`
- Next.js: `pages/` or `app/` directory (file-based routing)
- Angular: `*-routing.module.ts` or `app.routes.ts`
- Nuxt: `pages/` directory with `.vue` files
- SvelteKit: `src/routes/` directory

Record the detected framework and router file path.

### Sub-step 0.2 — Discover and confirm personas (HARD GATE)

The UI pass writes only **human personas**. The set of personas used
by the per-EP loop must come from this sub-step's discovery + user
confirmation, NOT invented mid-loop.

**Discovery procedure:**

1. **Find the auth model** in the UI repo. Real signals only:
   - JWT decoder / claims extractor (e.g. `useAuthStore`,
     `userData.roles`, `parseJwt`, `decode(token)`)
   - Route guard components (`<ProtectedRoute requireRole="...">`,
     `<RequireAuth roles={[...]}>`)
   - Conditional rendering keyed off role flags
     (`isMaster && ...`, `isManager && ...`)
   - Auth feature directory (`src/features/auth/types.ts`,
     `src/store/reducers/user/`, `src/auth/...`)

2. **Extract literal role identifiers from those files** — do not
   synthesize or rename. If the code says `isMaster` and `isManager`,
   propose those literal names.

3. **Capture the source location for each candidate** so the user
   can verify (file:line plus what the flag gates).

4. **Distinguish roles from subscription tiers / feature flags.**
   Subscription tiers gate features but are NOT roles. Propose them
   in a separate "feature flags — not personas" list.

5. **Load existing personas from the functional graph:**
   `Get_all_personas(projectUuid)`. Anything already in the graph is
   reused.

6. **Present the discovered list to the user with source locations
   and your proposed mapping.** Wait for confirmation.

7. **★ HARD GATE ★** — do not proceed to sub-step 0.3 (route
   discovery) until the user confirms the persona set. Record the
   confirmed set in `entrypoints.json` under `personas[]`.

8. **The per-EP loop is then constrained to this closed set.** If
   the loop encounters an EP that needs a persona not in the set,
   it must STOP and ask the user — it cannot invent a new persona
   mid-loop.

★ **This sub-step never adds `System` to the persona set.** Even if
the agent finds polling, retries, background fetches, or
auto-refresh hooks, those are still part of a human-triggered flow.
System is reserved for the backend pass.

### Sub-step 0.3 — Discover routes (code graph + local files)

- **Code graph first** (optional accelerator):
  `Code_Graph_Search "routes.tsx react router createBrowserRouter Route"`
  (or framework-equivalent query). The File node's `statements` field
  often contains full route definitions.
- A second query for sidebar/navbar structure helps surface panel triggers.
- **Then `Read` the router file locally** — code graph may miss lazy
  imports, nested routes, route guards, or dynamic component mappings.
- `Read` the sidebar/navbar component locally to discover panel
  triggers and non-routed features (drawers, modals, overlay panels).

### Sub-step 0.4 — Extract route details

For each route capture: `path`, `component`, `title`, `params`,
`queryParams`, `auth` guards, `variants`.

### Sub-step 0.5 — Categorize

Group routes by domain category (e.g. Search, Pipeline, Notifications,
Insights, Settings, Auth). The category drives Phase 1 batching later.

### Sub-step 0.6 — Discover orphaned views

Compare every page/view file under `src/pages/**` and `src/views/**`
against the routes extracted in 0.3. For files with NO matching route:

1. **Check imports**: `Grep "import.*from.*<ViewName>"` — sub-component?
2. **Check git history** (only if needed): was the route removed?
3. **Check for API calls**: real functionality means it's still alive.

Classify each orphan as:
- **sub-component** → fold into the parent page's EP, do not create a new EP
- **dead code** → flag for the user, exclude from inventory
- **truly unused** → exclude

### Sub-step 0.7 — Discover non-routed feature surfaces (HARD GATE)

★ **This sub-step is a HARD GATE, equivalent in weight to persona
discovery.** Skipping or skimming this sub-step is the single largest
cause of "the panel is just a viewer" gaps.

**Discovery procedure (MANDATORY — run all five steps):**

1. **Enumerate panel/drawer/modal type constants.** Grep the repo for:
   - Type unions or enums: `TPanel`, `PanelType`, `DrawerType`,
     `ModalType`, `panelType`, `drawerType`, `modalType`
   - String literal panel keys passed to setters: `setPanelType("X")`,
     `setDrawerType("X")`, `setModalOpen("X")`
   - Disclosure / open-state hooks: `useDisclosure`, `useModalState`,
     `useDrawerStore`, `useSheetStore`
   - Feature folders: list every entry under `src/features/**` and
     every `*-modal.tsx` / `*-drawer.tsx` / `*-panel.tsx` /
     `*-sheet.tsx` / `*-dialog.tsx` under `src/components/**`

2. **Locate every renderer.** For each unique panel/drawer/modal type
   string found in step 1, find the component that switches on it
   (e.g. `RightPanelLayout`, `PanelDrawer`). Record the file path. If
   you cannot find the renderer for a type string, that is a finding —
   record it as `"renderer-not-found"`.

3. **Locate every trigger.** For each `setPanelType("X")` / equivalent
   call site, record `{ panelType, triggerFile, triggerLine,
   triggerContext }`. The same panel type can have multiple triggers.

4. **Read the renderer.** For each panel type, READ the renderer file
   (not just grep it) and decide:
   - **Simple viewer panel** (markdown render, read-only popup) → fold
     into the triggering page's scenarios as actions.
     `"classification": "viewer"`.
   - **Feature-rich panel** (own tabs, forms, CRUD, API calls,
     internal state machines) → SEPARATE EP with `"type": "panel"` and
     full Phase 2/3 processing. `"classification": "feature-rich"`.

5. **Present the discovery list to the user with classifications.**

★ **HARD GATE** — do not proceed to sub-step 0.8 until the user
confirms the panel inventory. Record the confirmed list in
`entrypoints.json` under `panels[]`.

If during the per-EP loop the agent encounters a `setPanelType("X")`
call where `X` is not in the confirmed `panels[]` list, the agent
must STOP and ask the user.

**Sub-tab workspaces inside pages** are handled differently — they
are NOT panels, they are inline tabbed content. Discover them by
grepping for `TabsContent`, `activeTab`, `<Tabs `, reading the parent
layout, and processing each significant tab as part of the parent
page's batch (same EP, multiple scenarios).

**Conditional layouts on parameterized routes.** A single route like
`/chat/:agent/:id` may render completely different layouts depending
on the param value. Read EVERY conditional branch — significant
branches become **variant EPs** with `"type": "route-variant"` and a
`paramValue` field.

### Sub-step 0.8 — Cross-reference backend API routes (optional)

If a backend repo is indexed in the code graph, run a
`Code_Graph_Search` for the routes definition file, list all backend
endpoints, and flag any endpoint that no frontend file calls. This
seeds orphan-detection that the backend pass will later verify.

The frontend pass does not modify the graph based on this — it just
records the result for the backend pass to consume via the functional
graph (no file handoff).

### Sub-step 0.9 — Write `entrypoints.json`

Schema:

```json
{
  "project": "<repo name>",
  "projectUuid": "<from .breeze.json>",
  "framework": "react-router",
  "routerFile": "src/routes/routes.apac.tsx",
  "uiRepo": "<resolved target repo path>",
  "generatedAt": "<ISO timestamp>",
  "personas": [
    { "name": "Subscriber", "source": "src/features/auth/types.ts:14",  "isExisting": false },
    { "name": "Master",     "source": "src/utils/constants.ts:42 (isMaster flag)", "isExisting": false }
  ],
  "personasConfirmedAt": "<ISO timestamp>",
  "panels": [],
  "totalEntryPoints": 47,
  "entryPoints": [
    {
      "id": 1,
      "route": "/main/dashboard",
      "title": "Dashboard",
      "component": "src/pages/Dashboard/index.tsx",
      "pageDir": "src/pages/Dashboard",
      "auth": true,
      "params": [],
      "queryParams": [],
      "variants": [],
      "type": "route",
      "category": "Search",
      "status": "pending"
    },
    {
      "id": 18,
      "route": null,
      "title": "Add to Project Pipeline (modal)",
      "component": "src/features/pipeline/widgets/add-to-pipeline-form.tsx",
      "pageDir": "src/features/pipeline",
      "auth": true,
      "type": "panel",
      "trigger": "useAddToPipelineStore.openForm()",
      "triggeredFrom": ["project-detail-header", "search-results-bulk-actions"],
      "category": "Pipeline",
      "status": "pending"
    }
  ],
  "completed": [],
  "remaining": [1, 2, "...", 47],
  "orphans": {
    "deadCode": [],
    "subComponentsFolded": [],
    "backendEndpointsWithNoFrontendCaller": []
  }
}
```

Field reference:
- `id` — sequential entry-point id
- `type` — `"route"` (default), `"panel"` for non-routed feature
  surfaces, or `"route-variant"` for conditional layouts
- `category` — domain group from sub-step 0.5
- `pageDir` — the directory the per-EP loop will glob (relative to
  the resolved UI repo)
- `status` — transitions `pending → in_progress → done`
- `completed[]` / `remaining[]` — resume tracking; `entryPoints[]`
  itself is immutable after Phase 0

After writing the file, **present the EP list to the user for review
and ask if any should be excluded** before starting the per-EP loop.

## The 9-step per-EP pipeline

For each entry point:

### Step 1 — Dedup check via `Functional_Graph_Search`

Search the existing graph for the EP's likely outcome name + 2 likely
scenario names. Decision rules:

- **Score > 0.6 AND same interaction model (single vs bulk, header vs
  row, modal vs inline)** → reuse: link new content to the existing
  scenario via the upsert under the same name.
- **Score > 0.6 BUT different interaction model** → differentiate:
  create a sibling scenario with disambiguated name (e.g. "Add to
  pipeline — single from detail header" vs "Add to pipeline — bulk
  from search results").
- **Score < 0.6** → proceed fresh.

Schema reminder: `Functional_Graph_Search` uses `parameters3_Value`
for the project UUID. Wrong slot fails silently.

### Step 2 — Read the page deeply (filesystem)

Glob the page directory and `Read` the meaningful files. For a typical
React page that means:

- The `index.{tsx,jsx}` entry component
- All `widgets/*.{tsx,jsx}`, `components/*.{tsx,jsx}`
- `queries.{ts,tsx}` (TanStack Query hooks)
- `store.{ts,tsx}` (Zustand stores)
- Any `Form*`, `Popup*`, `Dialog*`, `Modal*`, `Sidebar*`, `Navigation*`
- `hooks/*` if present

Skip leaf primitives (`Skeleton`, `LoadSkeleton`, `NoData`, `Empty`).

Read enough that you can name **10–20 distinct user flows**, not 2–3.
If you can only name 3, you haven't read enough.

**Follow-the-trigger rule (MANDATORY):**

In addition to the page directory glob, the agent MUST follow every
panel/drawer/modal trigger out of the page to the renderer file
confirmed in sub-step 0.7's `panels[]` list:

1. Grep the page (and every file you read in this EP) for
   `setPanelType\(`, `setDrawerType\(`, `setModalType\(`,
   `useDisclosure`, `openModal\(`, and any project-specific
   equivalents discovered in 0.7.
2. For each hit, look up the panel type string in the confirmed
   `panels[]` list:
   - If `classification === "feature-rich"` → that panel is its own
     EP; do NOT capture its internal scenarios here, but DO capture
     the "open panel X" action in the parent EP and link to the
     panel EP's id in the action description (`"opens panel EP <id>"`).
   - If `classification === "viewer"` → READ the renderer file now.
     Capture every interactive element inside it as an action under
     the parent EP's scenarios.
3. If you find a `setPanelType("X")` call where `X` is not in
   `panels[]`, STOP and surface it to the user.

**Component-import drill-down rule (MANDATORY):**

For every imported component referenced inside the page's JSX whose
name matches `/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/`
AND that has its own `useState`/`useReducer`/`useStore` hook, you
MUST read the component file before drafting scenarios.

After reading, record the file in this EP's citation list. If you
intentionally skip a matching component, justify it in the EP's
`completed[]` checkpoint under `skippedComponents[]`.

### Step 3 — JSX interactive-element inventory

After Step 2, grep the page directory for interactive widget tags and
form state hooks:

```
<Button       <IconButton    <Tab          <Tabs
<Checkbox     <Switch        <Toggle       <Stepper
<Select       <MenuItem      <Radio        <Autocomplete
<Dialog       <Modal         <Popover      <Drawer
<TextField    <Input         <DatePicker
useState      useForm        zodResolver
```

Build a list: `{ widgetType, label, file, line }` for each unique
interactive element. Strip leaf-primitive widgets and form scaffolding
noise. The remaining list is the **completeness checklist** — every
item must appear in the EP's scenarios as a step or action.

### Step 4 — API inventory

Grep the page directory for:

```
fetchGet|fetchPost|fetchPut|fetchDelete|fetchPatch
useQuery|useMutation|useInfiniteQuery
apiFetch|axios\.|api\.
dispatch\(.*Api
```

For each hit, follow to the service/query file and `Read` it. Extract:

- **Literal URL string** (after resolving template literals — read the
  const definition if needed)
- **HTTP method**
- **Request shape** (DTO type or zod schema)
- **Source location**: `{ calledFrom: "src/services/x.js:42",
  calledVia: "useFooQuery in src/pages/Foo/queries.ts:18" }`

If a Redux thunk wraps the API call, trace one hop: thunk → service → URL.

★ **Every URL discovered here must be captured in `action.apis[]`** in
the Step 6 payload as a structured entry (shown here as a fragment of
the action object):

```json
{
  "apis": [{
    "type": "REST",
    "method": "POST",
    "url": "/v2/search/projects2?filter={encoded}",
    "request": "ES query body (saved query payload)",
    "response": "{data:[ProjectRow], totalData}"
  }]
}
```

The `type` field supports the full enum:
**REST / GraphQL / gRPC / WebSocket / Event**.

For the UI pass you'll mostly use `"REST"`. If the UI subscribes to
GraphQL queries/mutations use `"GraphQL"`. If it opens a WebSocket
connection (Socket.IO, plain ws) use `"WebSocket"`. If it subscribes
to a Server-Sent Events stream use `"Event"`. gRPC-Web is `"gRPC"`.

It is also good practice (but not mandatory) to mention the URL in the
plain-text `action.description` so reviewers can see it inline.

### Step 5 — Field enumeration for Review actions

For any rendered data block (project header, overview, contact card,
table row), enumerate the **fields** by reading the JSX render or the
response DTO. The action name is a Review verb (e.g. "Review project
header"). For human-persona Review actions, prefer the field list in
the **Scenario description** (not action description) so the
per-action descriptions stay null per the canonical rules.

For enums and master-data-driven dropdowns: if a `<Select>` is
populated from `useGetMasterCategories()`, follow the hook to its
query, find the endpoint, and put the value list in the Scenario
description.

### Step 6 — Build payload

One outcome per EP cluster (or shared with closely-related EPs).

**Persona must come from the closed set in `entrypoints.json.personas[]`
that the user confirmed in Sub-step 0.2.** Do not invent. If you
encounter an EP that needs a persona not in the set, STOP, ask the
user to add it, and update `entrypoints.json` before proceeding.

**Never use `System` from the UI pass.** Even if the EP involves
polling, retries, background fetches, or auto-refresh, those are still
part of a human-triggered flow.

Aim for:
- 5–20 scenarios per EP
- 3–8 steps per scenario (max 10)
- 1–5 actions per step

**Mandatory rules from the canonical guide:**

1. **Outcome names are business capabilities, not page names.**
   - ❌ "Open Lead Manager Dashboard" / "Use the Project Detail Page"
   - ✅ "Discover Latest Project Opportunities" / "Investigate
     Construction Project Information"

2. **An entire product usually has 5-10 outcomes total**, not one
   per page. Re-evaluate if you're creating more than 3-4 new
   outcomes for the whole UI repo.

3. **Action names are intent verbs, not interaction verbs.** Forbidden:
   `click, tap, swipe, hover, scroll, drag, drop, toggle, button,
   dropdown, modal, dialog, popup, panel, checkbox, radio, slider,
   tooltip, menu, sidebar, navbar, tab, icon`. Use:
   `Provide, Choose, Confirm, Review, Dismiss, Open, Close, Submit,
   Cancel, Specify, Indicate, Acknowledge, Request`.

4. **Action descriptions are NULL for human persona** unless there's a
   real user-facing constraint. Backend-implementation prose is wrong
   here — that's code, not user-visible behavior.

5. **The structured `apis[]` block CAN coexist with a null
   description.**

6. **Step names are short verb phrases. Steps don't need
   descriptions.**

7. **Naming disambiguation:** for variants of the same capability
   across regional/tier flavors, use ONE shared outcome with
   disambiguated scenario names ("Search projects — APAC" vs "Search
   projects — Lite kanban") rather than separate outcomes.

### Step 6.5 — Pre-upsert JSX coverage validator (MANDATORY)

Before sending the payload to the upsert endpoint in Step 7, run an
automated coverage check against the JSX inventory built in Step 3.

**The check:**

1. Take the Step 3 JSX widget inventory: every interactive element
   found in every file read for this EP — including renderer files
   pulled in by the follow-the-trigger rule and component files
   pulled in by the component-import drill-down rule.

2. For each widget, attempt to match it to at least one action in
   the payload by:
   - Exact label match (case-insensitive) between the widget's text
     content and any action name OR
   - File+line proximity citation in any action's description OR
   - Explicit listing in the EP's `viewOnlyChrome[]` exclusion list.

3. **Coverage rule:** at least 90% of the inventory must be matched.
   Common chrome (close buttons, breadcrumb items, tooltip triggers,
   icon-only nav) can be added to `viewOnlyChrome[]` but the list
   must be present in the checkpoint and the agent must justify
   each entry in one line.

4. **Forbidden category check:** if any widget label contains an
   action verb (`Save`, `Submit`, `Generate`, `Delete`, `Upload`,
   `Download`, `Send`, `Confirm`, `Apply`, `Run`, `Create`,
   `Update`) and is NOT matched, the validator MUST FAIL — these
   widgets cannot be view-only chrome by definition.

5. **API-implying name check:** for every action whose name starts
   with `Submit`, `Generate`, `Upload`, `Delete`, `Send`, `Save`,
   `Fetch`, `Retrieve`, `Sync`, the action MUST have an `apis[]`
   block. If it doesn't, the validator MUST FAIL with the message
   *"action name implies network I/O but no API URL was extracted —
   re-run Step 4 and follow the hook to its service file."*

**On failure:** do NOT upsert. Either fix the payload (add missing
actions, add the missing `apis[]` block, justify exclusions in
`viewOnlyChrome[]`) or, if a renderer file was missed, return to
Step 2 and re-read.

**On success:** record the coverage report in the EP's `completed[]`
checkpoint.

### Step 7 — Upsert ONE EP at a time

Write payload to `/tmp/ui_ep{NN}_{name}.json`, then POST it.

**Endpoint:**
```
POST {apiBase}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK
Headers: api-key: {apiKey}
         Content-Type: application/json
Body:    @<payload-file>
```

**Curl example:**
```bash
curl -X POST "${API_BASE}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK" \
  -H "api-key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d @/tmp/ui_ep01_dashboard.json
```

**Payload schema (full nested tree, top-level keys are mandatory):**
```json
{
  "project": {
    "uuid": "<projectUuid from .breeze.json>",
    "name": "<repo or project name>"
  },
  "payload": {
    "personas": [
      {
        "persona": "User",
        "description": "...optional persona description...",
        "citations": [
          { "type": "code", "name": "<file>", "reference": "<file path>" }
        ],
        "outcomes": [
          {
            "outcome": "Manage X",
            "description": "...",
            "citations": [
              { "type": "code", "name": "<file>", "reference": "<file path>" }
            ],
            "scenarios": [
              {
                "scenario": "Submit project search with filters",
                "description": "User applies the project side-filter and submits a search.",
                "steps": [
                  {
                    "step": "Provide search criteria via project side filter",
                    "actions": [
                      {
                        "action": "Submit project search",
                        "description": null,
                        "apis": [
                          {
                            "type": "REST",
                            "method": "POST",
                            "url": "/v2/search/projects2?filter={encoded}",
                            "request": "ES query body (saved query payload)",
                            "response": "{data:[ProjectRow], totalData}"
                          }
                        ]
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  },
  "skipStepAndAction": false
}
```

**Schema rules the agent must obey:**
- `project.uuid` is the projectUuid from `.breeze.json`. Required.
- `personas[]` is mandatory and must be an array even with one persona.
- For the UI pass, use only **human personas** from the confirmed set.
  Never `System` (that's the backend pass).
- Each level (persona → outcome → scenario → step → action) is matched
  by **name** at upsert time. The upsert is **idempotent by name** —
  re-upserting with the same names overwrites content; with different
  names adds siblings.
- `actions[].apis[]` is the structured capture of any API call. The
  `type` field supports **REST / GraphQL / gRPC / WebSocket / Event**.
- `citations[]` is supported at outcome and persona level.

**⚠ Never batch multiple EPs into one upsert.** Even for seemingly
duplicate-feeling EPs, upsert each separately so verification works
per EP.

**★ MANDATORY pre-upsert validation — refuse to POST until both
checks pass ★**

Walk every `action` in the tree and apply two refusal rules:

**Rule A — network-verb actions must have `apis[]`.** If
`action.action` contains any of these verbs, the action MUST have a
non-empty `apis[]` block:

```
Submit, Generate, Upload, Download, Delete, Save, Send, Fetch,
Retrieve, Publish, Persist, Sync, Import, Export, Share, Subscribe,
Unsubscribe, Validate-against-server, Authenticate, Authorize,
Refresh, Poll
```

If a network-verb action has no `apis[]`, the agent must STOP and:
1. Open the corresponding service / query / mutation file in the UI
   repo, find the literal URL + HTTP method, and add the `apis[]`
   block, OR
2. Rename the action to remove the network verb if the operation is
   actually local-only, OR
3. Document why no `apis[]` exists in `action.description`
   (e.g. "Local-only — persists to localStorage").

**Rule B — every TanStack `useMutation` / `useQuery` / `mutateAsync`
call discovered in Step 4 must resolve to a `Read` of the service
file.** Track which service files were opened during Step 4. If at
payload-build time you have a hook reference that you never followed
into the file, the discovery is incomplete — go back, `Read` the
service file, and add the URL.

If either rule fails for any action, refuse to call the upsert
endpoint. Fix the payload and re-run validation.

### Step 8 — Verify via `Functional_Graph_Search`

Search for a unique phrase from each new scenario's description.
Confirm:
- Scenario appears in results
- Score > 0.4
- `scenarioId` returned

### Step 9 — Update `entrypoints.json` checkpoint

Edit (do not rewrite) `entrypoints.json`:

1. Mark the EP's `status` from `in_progress` → `done`.
2. Pop the EP id from `remaining[]`.
3. Append a `completed[]` record with verification metadata:

```json
{
  "epId": 12,
  "title": "Project Detail Page",
  "outcomeName": "Manage Project Detail",
  "outcomeUuid": "73f29538-...",
  "scenariosCreated": 14,
  "actionsCreated": 41,
  "apiCallsLogged": 9,
  "jsxAuditWidgets": 27,
  "verificationScores": { "core project data": 0.71, "express enquiry": 0.68 },
  "payload": "/tmp/ui_ep12_project_detail.json",
  "completedAt": "<ISO>"
}
```

The `entryPoints[]` block from Phase 0 stays put — only `status`,
`completed`, and `remaining` mutate.

## Cost per EP

- 1 dedup `Functional_Graph_Search`
- 4–8 page reads (filesystem)
- 1–2 grep passes (JSX widgets + API calls)
- 1–3 service/query file reads
- 0–1 optional `Code_Graph_Search` for navigation
- 1 payload write
- 1 curl upsert
- 1 verify `Functional_Graph_Search`
- 1 checkpoint write

≈ **10–14 tool calls per EP**. For 50 EPs: 500–700 calls. Plan for
multiple sessions.

## Multi-session resume

When context budget hits ~75%:
1. Flush current EP's log entry + checkpoint
2. Stop and report

To resume in a fresh session: **"continue UI pass from
entrypoints.json"**. Next agent reads the checkpoint, calls
`Get_all_personas` to confirm graph state, and picks up at
`remaining[0]`.

## Boundary with the backend pass

The frontend pass **never**:
- Reads backend repos
- Creates System persona scenarios
- Makes claims about controller files, routes, or handlers
- Cites backend file paths
- Writes any handoff file for the backend pass

The frontend pass and backend pass are fully independent. They share
the functional graph as the only common surface — both passes upsert
into the graph using idempotent merge by name. If the backend pass
discovers a REST handler whose business capability matches a User
outcome the frontend pass already created, it will land under the
same outcome via the name merge. **No file-based handoff is needed.**

Every action created here that touches an API has its `apis[]` block
populated with the URL the frontend believes it's calling — that's
useful as a cross-check during graph review, but the backend pass
does not consume it.

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading only `index.tsx` | < 5 scenarios per EP | Glob the page dir, read 4–10 files |
| Skipping the JSX audit | Steppers/toggles/tabs missing | Step 3 is mandatory |
| Opaque Display actions | No field enumeration | Step 5 is mandatory for any data-rendering action |
| Trusting code graph for literal strings | URL mismatches in payload | Always `Read` the service file and copy the literal |
| Batching multiple EPs into one upsert | Per-EP scenario count low | One upsert per EP |
| Wrong `Functional_Graph_Search` slot | Schema error, wasted call | Use `parameters3_Value` for project UUID |
| Writing a handoff file for the backend pass | Skill drift | The frontend pass produces no handoff |
| Skipping `actions[].apis[]` for non-REST API calls | GraphQL / WebSocket / gRPC / SSE flows missing | Use the matching enum value, don't omit `apis[]` |
| Skipping the follow-through from a TanStack hook to the service file | Network-verb actions end up with no `apis[]` | Step 4 mandates reading; Rule B refuses upsert |
| Network-verb action with no `apis[]` | "Submit X", "Generate Y" actions exist but have no URL | Rule A refuses to POST |
| Treating a side panel / drawer / modal as "just a viewer" | Panel exists in graph but its interactions are dropped | Sub-step 0.7 hard gate + follow-the-trigger rule + Step 6.5 validator |
| Component imports skipped | Wrapper components hide entire sub-flows | Step 2's component-import drill-down rule mandates reading them |
| Using `System` persona from the UI pass | Wrong persona ownership | Always use a human persona; System is for the backend pass only |
| Using forbidden words in action names | "Click stage tile", "Toggle tab" | Use intent verbs from the canonical list |
| Filling `description` on human-persona actions with code-level prose | "TNLMPaper card click invokes onStageClick(id, rules)" | `description` for human actions = null UNLESS there's a real user-facing constraint |
| Naming outcomes after pages | "Open Lead Manager Dashboard" | Outcomes are business capabilities; 5-10 total per UI repo |

## When NOT to use this skill

- **Backend-only repos** — use `/breeze:generate-functional-from-backend`
- **Quick first-time exploration** — the deprecated cluster pipeline
  in `generate-functional-from-code` is faster but lower fidelity

## See also

- `/breeze:generate-functional-from-backend` — the backend half of the
  split pipeline. Run after this skill (or before — order doesn't
  matter; merge happens by outcome name).
- `/breeze:generate-functional-from-code` — **deprecated** legacy
  cluster pipeline. Kept as a reference for backend-heavy/no-UI repos.
- `/breeze:validate-functional-graph` — quality checks after generation
- `/breeze:generate-spec` — export the resulting graph as a spec doc
