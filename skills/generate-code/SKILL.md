---
name: generate-code
description: >
  Generate code and test cases informed by the functional graph and
  code graph. Ensures implementations align with requirements and
  existing patterns. Scoped by persona: a System (or External System)
  persona generates a backend; any non-System human persona generates
  the user-facing UI; a mixed selection generates fullstack. Re-engineers
  by deriving the most viable modern tech stack from the functional
  requirements (not the legacy stack), and lets the user override. Full
  builds run an orchestration mode
  that scaffolds a shared foundation once and fans out one module-builder
  sub-agent per feature domain with action-level coverage, then integrates
  + builds + smoke-tests. Use when: "generate code for X", "write tests
  for Y", "implement this scenario", "scaffold the API for Z", "generate
  frontend", "generate backend", "build the UI", "scaffold the full app",
  "build the whole app", "recreate the frontend for persona X end to end",
  "generate the backend for the System persona", "fan out agents to build
  each module". Supports both selective (single scenario) and full
  persona-scoped generation.
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

---

## Determine Generation Scope

Parse `$ARGUMENTS` for three things: **which persona(s)** to build for, **what to build**, and the
**tech stack**.

### Selective vs full build
- **Selective** (single scenario or feature) — "generate code for login", "implement VAL-001",
  "scaffold the upload page" → **Workflow A**. (Persona routing below doesn't apply.)
- **Full build** — "generate frontend / backend / the whole app", "recreate the frontend for persona
  X", "build everything" → choose the persona, then route per the rule below.

### Persona scope drives UI vs backend
Call `Get_all_personas`. Resolve the target persona(s):
- The prompt names a persona (e.g. *"for AAC-A"*, *"the Admin persona"*, *"the System persona"*) →
  match it. It names several or *"all personas"* → take those. **None given → list the personas and
  ask which to generate for** (don't guess).

Then route by **persona kind** — this is the default mapping:

| Persona kind | Target | Workflow |
|---|---|---|
| **`System`** | Backend (background jobs, pipelines, internal processing — no UI) | **Workflow C** |
| **`External System`** | Backend (API-key / integration surface, no user login) | **Workflow C** |
| **Any non-System (human) persona** | User-facing UI | **Workflow B** |
| **Mixed** (a human persona *and* `System`, or "full app / everything") | **Fullstack** — run B for the human persona(s) **and** C for `System`, linked on the shared `HAS_API` contracts | **B + C** |

### Explicit target override
A `ui` / `backend` / `fullstack` token in the prompt overrides the persona-kind default (e.g. force a
mock-backed UI for the System persona, or a stub backend for a human persona). If still ambiguous after
both signals, ask once.

### Tech stack — derive the most viable, let the user override
This skill **re-engineers** from the functional graph — it does **not** replicate the legacy stack by
default. Choose the **most viable modern stack from what the app needs functionally**:
- **Derive from the app's shape** (read it off the outcomes/scenarios): dashboards + data tables +
  filters + charts + forms + role-gated admin → an SPA; document/content-heavy or SEO-facing → SSR;
  a `System` persona with background jobs / queues / schedulers → a service with a worker;
  `External System` (integration-only) → an API surface; data-/ML-heavy domains → Python.
- **Map that to a sensible default** — UI: React + TypeScript + Vite + Tailwind + React Router
  (add a charts lib when there are dashboards); Backend: Node + Express + TypeScript, or FastAPI +
  Postgres for Python-leaning domains, adding a queue/worker when the graph implies async jobs.
- **User override always wins** — if the prompt names a stack ("in Next.js", "Vue + Pinia",
  "Spring Boot", "FastAPI + Postgres"), use it verbatim, no questions asked.
- **Matching an existing codebase is opt-in, not the default** — only when the user is *extending* a
  live repo (rather than re-engineering) should you detect its stack via `Code_Graph_Search` /
  `package.json` and match its conventions.
- **Announce** `Stack: <chosen> — <one-line why it fits the functional needs>` and proceed. The user can
  redirect at any time; don't block waiting for confirmation, and don't silently inherit the legacy stack.

---

## Orchestration mode — parallel module agents (recommended for full builds)

Workflows B and C can be run inline, but for a whole-app build the robust path is to **fan out one
sub-agent per feature domain** so the work parallelises and the parent never holds every file in
context. This plugin ships two module-builder agents for exactly this:
- `breeze:app-ui-module-agent` — builds one frontend feature module from a set of outcomes.
- `breeze:app-backend-module-agent` — builds one backend module (routes / services / validation / tests).

The loop (use the B/C step detail below to fill each phase):
1. **Traverse** the graph to the **action level** for the chosen persona(s) — every Outcome →
   Scenario → Step → Action. **Coverage is the acceptance gate: an Action with no UI behaviour /
   endpoint is a missing flow.**
2. **Plan domains** — group outcomes into ~5–12-outcome feature domains, each with its **own folder**
   and **non-overlapping route/prefix ownership** (so parallel agents never edit the same file), plus a
   curated nav (UI). Pair a UI domain with its backend domain on the shared Outcome + `HAS_API` url.
3. **Scaffold the shared foundation ONCE** (design system + app shell + route registry + data layer +
   persona gating for UI; framework skeleton + middleware + store + router-registry for backend), then
   render `references/agent-guide.template.md` → `<APP_DIR>/AGENT_GUIDE.md`.
4. **Pilot** one module agent to validate MCP access + conventions + that it builds, then **fan out**
   the rest in parallel — render `references/ui-module-agent.prompt.md` /
   `references/backend-module-agent.prompt.md` as each agent's `prompt`.
5. **Integrate & verify** — wire each module's exported routes/router into the registry (parent-only
   edit), install, build, **smoke-test it runs** (Playwright for UI, endpoint hits for backend), then
   **QA every outcome/action is covered exactly once** and patch any gap before reporting done.

Use orchestration mode for "build the whole app / recreate the frontend for persona X end to end"; use
inline Workflows A/B/C for smaller or single-feature work.

---

## Workflow A: Selective Generation

For generating code for a specific feature, scenario, or user story.

### A1. UNDERSTAND — Get the functional spec

- Call `Functional_Graph_Search` with the feature/scenario name
- Call `Get_all_steps_actions_for_a_scenario_id` for matched scenarios
- This gives you the WHAT: steps, actions, expected user interactions

### A2. DISCOVER — Find existing code patterns

- Call `Code_Graph_Search` with related terms
- Call `Get_Code_Nodes_By_Label(label="File", filters={"path": <path>, "codeOntologyId": <id>} OR {"id": <fileId>}, children=true)` on the most relevant files to inspect
  class structure, methods, and patterns
- Find existing files, functions, patterns, utilities
- This gives you the HOW: conventions, imports, patterns to follow

### A3. REFERENCE — Get business rules

- Call `Documents` for formulas, thresholds, validation rules
- This gives you the CONSTRAINTS: exact rules the code must enforce

### A4. GENERATE — Write code

- Follow existing code patterns found in step A2
- Align with functional steps from step A1
- Reuse existing utilities/components from code graph
- Apply business rules from step A3
- Add comments referencing functional graph node IDs for traceability

### A5. TEST — Generate test cases from scenarios

Map functional hierarchy to test structure:

    For each Scenario:
      describe("[Scenario Name]")
        For each Step:
          it("[Step Name]")
            For each Action:
              → Assert the expected behavior

- One test suite per scenario
- Test cases map 1:1 to steps
- Edge cases derived from action descriptions
- Include both happy path and error scenarios

---

## Workflow B: Full Frontend Generation

For generating an entire frontend application from the functional graph.
This follows the **Graph-to-UI pattern**: Persona → Auth, Outcome → Nav,
Scenario → Page sections, Step → Component interactions, Action → UI elements.

### B1. EXTRACT — Build the persona-to-UI map

Call `Get_all_personas` with the project UUID.

For each persona returned, call `Get_all_outcomes_for_a_persona_id`.
**Call all persona-outcome fetches in parallel** to minimize round-trips.

Build a **persona-outcome map** — this drives the entire UI structure:

```
Persona → Outcomes[]
  Fund Operations User → [Manage CSV File Uploads, ...]
  Fund Operations Analyst → [Review Validation Results, Generate Reports, ...]
  Admin → [Configure Settings, Manage Audit Log, ...]
  System → [internal processing — no UI needed]
```

**Skip the System persona** — it has no UI. Also skip External System
personas. Only human personas generate UI.

### B2. CONSOLIDATE — Map personas to auth roles

Multiple graph personas often map to fewer auth roles based on
**permission boundaries**, not 1:1 persona-to-login mapping.

Rules for consolidation:
- Group personas that share the same permission level
- The graph models WHO DOES WHAT (behavioral roles)
- Auth models WHO IS ALLOWED TO DO WHAT (permission boundaries)
- A single user may act as multiple personas (e.g., upload files as
  "Fund Operations User" and review dashboard as "Fund Operations Analyst")
- Check persona descriptions for sub-role hints (e.g., "may have roles:
  Admin, Manager, Operator" in a single persona → multiple auth roles)

Present the proposed mapping to the user for confirmation:

```
| Graph Persona           | Auth Role  | Why                                    |
|-------------------------|------------|----------------------------------------|
| Fund Operations User    | analyst    | Uploads files, triggers validation     |
| Fund Operations Analyst | analyst    | Reviews dashboard, adds comments       |
| Fund Controller         | analyst    | Reviews specific rule results           |
| Fund Reviewer           | reviewer   | Can approve/waive/reject exceptions    |
| Admin                   | admin      | System configuration, audit access     |
| Compliance Officer      | admin      | Audit log access (restricted view)     |
| System                  | (no UI)    | Backend automation                     |
```

### B3. DERIVE — Map outcomes to navigation and routes

Each outcome becomes a page or section in the navigation.
Group outcomes by auth role visibility:

```
Outcome → Route → Visible to roles
─────────────────────────────────────
"Manage CSV File Uploads"     → /upload           → [all roles]
"Review Validation Results"   → /dashboard        → [all roles]
"Generate Validation Reports" → button on dashboard → [all roles]
"Configure Validation Settings" → /admin/settings  → [admin]
"Manage Audit Log"            → /admin/audit-log   → [admin]
```

Present the proposed navigation structure to the user.

### B4. DETAIL — Get scenarios for each page

For each outcome that maps to a page, call
`Get_all_scenarios_for_a_outcome_id`.
**Call ALL outcome-scenario fetches in parallel** (batch all calls in one
message to maximize throughput).

This tells you what features each page must support. For example,
the Dashboard page might need:
- "View RAG Exception Summary Dashboard" → KPI cards + grid
- "Filter and sort exception grid" → filter bar
- "View exception details in drill-down panel" → slide-in panel
- "Add commentary to exceptions" → comment form
- "Change exception status" → status dropdown (reviewer/admin only)

### B5. DEEP DIVE — Get steps and actions for key scenarios

For the most complex scenarios (especially create/edit forms, dashboards,
and workflows), call `Get_all_steps_actions_for_a_scenario_id` to get
the exact UI interactions needed.
**Call 8-10 key scenarios in parallel** per batch.

This reveals:
- What form fields are needed (from "Provide..." actions)
- What displays are needed (from "Observe..." actions)
- What validation rules apply (from action descriptions)
- What role-gating is needed (from persona ownership)
- What error messages to show (from action descriptions)
- **What API endpoints exist** (from HAS_API children on actions:
  url, method, request schema, response schema)

### B5.1. EXTRACT API CONTRACTS from step/action data

Actions with `HAS_API` children contain the actual REST endpoints:
```
Action → Api { url, method, request, response }
```

Collect ALL API contracts discovered across scenarios into a centralized
reference. These drive:
- TypeScript API service stubs with correct request/response types
- Dummy data shape (must match response schemas)
- Form field names (must match request schemas)

### B6. DATA — Build dummy payloads from source documents

Call `Documents` with broad queries to find:
- Sample data values (prices, dates, amounts, names)
- Business rules (thresholds, formulas, materiality levels)
- Validation rules and error messages
- Acceptance criteria with expected values

Create a **single TypeScript dummy data file** (`src/data/dummy.ts`) that:
- Exports named constants for every entity type
- Uses realistic values from source documents (not lorem ipsum)
- Includes 5-10 records per entity for meaningful list/table views
- Matches the TypeScript interfaces exactly
- Marks every export with `// TODO: Replace with API call — GET /api/...`

### B7. SCAFFOLD — Generate the project

Use the stack resolved in *Determine Generation Scope* — derived from the functional needs (or the
user's explicit override). Don't re-ask here.

**Typical derived frontend stack:** React + TypeScript + Vite + Tailwind CSS (+ a charts lib for
dashboards) — unless the requirements point elsewhere (e.g. SSR → Next.js) or the user chose otherwise.

#### B7.1. Generation Order and Parallelization Strategy

> **Preferred for full apps: orchestration mode** (see the section above). Build the shared foundation
> yourself, then fan out **one `breeze:app-ui-module-agent` per feature domain** (one owner per folder,
> action-level coverage), and integrate. The layer-split below (foundation agents → page-group agents)
> is the lighter inline alternative for small apps where a full per-domain fan-out is overkill.

Generate in two phases to maximize speed:

**Phase 1 — Foundation (parallel agents):**
Launch 3 agents simultaneously:
1. **Types + Data agent**: TypeScript interfaces + dummy data file
2. **Auth + Utils agent**: AuthContext, useRoleGuard hook, formatters,
   main.tsx, index.css
3. **Components agent**: All shared UI components (see B7.2)

**Phase 2 — Pages and Routing (parallel agents):**
Once Phase 1 completes, launch 4-6 agents simultaneously:
1. **Layout + App.tsx agent**: Sidebar layout, route wiring
2. **Auth pages agent**: Login, Register, ForgotPassword, SelectOrg
3. **Core pages agent**: Dashboard, primary transaction pages
4. **Secondary pages agent**: Remaining list/create/detail pages
5. **Reports + Admin agent**: Report views, admin panels

Each agent gets a self-contained prompt with the relevant scenarios,
component API, and type definitions.

#### B7.2. Shared Component Library — Design Rules

Build these reusable components following these critical rules:

**FormField + Input components:**
- FormField must NOT have built-in margin (no `mb-4`). Parent controls
  spacing via grid `gap`. This prevents layout breakage in grids.
- All input sub-components (TextInput, NumberInput, DateInput,
  SelectInput, TextArea) must use `React.forwardRef` and MERGE
  incoming `className` with base classes:
  ```tsx
  export const TextInput = React.forwardRef<HTMLInputElement, Props>(
    ({ className, ...props }, ref) => (
      <input ref={ref} className={`${baseClasses} ${className ?? ''}`} {...props} />
    )
  );
  ```
  This prevents double-class conflicts when pages customize inputs.

**DataTable:**
- Wrap in a card container (`bg-white rounded-xl border shadow-sm overflow-hidden`)
- Toolbar row: search input (with search icon) on left, filter pills on right
- Footer: "Showing X of Y items" count
- No striped rows — use `hover:bg-gray-50` only (cleaner)

**DetailPanel (slide-in right panel):**
- z-index MUST be higher than sidebar: backdrop `z-50`, panel `z-[60]`
  (sidebar is typically `z-40`)
- Width: `w-full sm:w-[480px]` for mobile responsiveness
- Lock body scroll when open

**Modal:**
- Content must be scrollable: `max-h-[85vh]` with `overflow-y-auto`
- All interactive features (Create, Import, etc.) must be wired with
  real state and form logic — NEVER leave as placeholder buttons

**Layout (Sidebar + Header):**
- Sidebar: dark theme (`bg-slate-900`), nav items with rounded active
  indicators (not border-left which adds width shifts)
- Header: compact (56px), no shadow (border-b only for cleaner look)
- Content area: `max-w-7xl mx-auto` for ultra-wide screen containment
- Mobile: sidebar slides in with backdrop, swipe-to-close support

**CSS Utility Classes — define in index.css:**
```css
@layer components {
  .btn-primary { @apply inline-flex items-center justify-center gap-1.5
    rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white
    shadow-sm transition-all hover:bg-blue-700 focus:outline-none
    focus:ring-2 focus:ring-blue-500 focus:ring-offset-2; }
  .btn-secondary { @apply inline-flex items-center justify-center gap-1.5
    rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm
    font-medium text-gray-700 shadow-sm transition-all hover:bg-gray-50; }
  .btn-danger { @apply inline-flex items-center justify-center gap-1.5
    rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white
    shadow-sm transition-all hover:bg-red-700; }
}
```
Use these classes across all pages for button consistency.

**Badge:**
- Use `ring-1 ring-inset` borders for better definition:
  `bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-600/20`

#### B7.3. Page Generation Rules

For each page, use the scenarios as a checklist:
- Each scenario = a section or interaction on the page
- Each step = a sequential phase in the interaction
- Each action = a specific UI element or behavior

**List pages pattern:**
- PageHeader with "Create X" action button
- Tabs (if type variants exist, e.g., Sale/Purchase)
- Date filter row (plain labels + DateInput, NOT wrapped in FormField)
- DataTable with appropriate columns
- DetailPanel on row click with full details + action buttons

**Create/Edit form pages pattern:**
- Multi-section Card layout (one Card per functional step)
- Grid layout: `grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4`
- Toggle buttons for type selection (not plain radio buttons)
- Dynamic line item tables for invoice-like forms
- Totals summary in `bg-gray-50 rounded-lg p-4` box
- Footer with btn-primary (Submit) and btn-secondary (Cancel)

**Dashboard pattern:**
- StatCard grid: `grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5`
- Chart rows: `grid-cols-1 lg:grid-cols-2 gap-5`
- Use `recharts` with `ResponsiveContainer` — parent MUST have explicit height
- Pie chart labels: use `fontSize: 11` to prevent overlap

#### B7.4. Common Pitfalls to Avoid

1. **Never use FormField for inline filter controls** (date pickers in
   toolbars). Use plain `<span>` labels + input directly.
2. **Never pass className to input components that already style themselves**.
   The base component owns its styling; pages only override via the
   merged className prop when truly needed.
3. **Always set explicit height on chart containers** (e.g., `h-64`).
   `ResponsiveContainer` needs a sized parent to render.
4. **Use `tabular-nums` on columns with numbers/dates** for alignment.
5. **Use `truncate` on values that might overflow** (currency, long names).
6. **Every button/action must be wired** — no placeholder `onClick` handlers
   that do nothing. At minimum, show a modal or alert.
7. **Test the sidebar collapsed state** — all content must remain usable
   when sidebar is collapsed to icon-only width.

### B8. VERIFY — Build and test

Run **both** checks:
```bash
npx tsc --noEmit    # Type check — must produce zero output
npx vite build      # Production build — must succeed
```

If errors found, fix them and re-verify. Common issues:
- Missing imports (components used but not imported)
- Type mismatches between dummy data and interfaces
- Unused imports flagged by strict mode

Present the file manifest to the user with:
- Total file count and build output size
- Module breakdown (how many pages per section)
- How to run the dev server (`npm run dev`)

---

## Workflow C: Full Backend Generation

For generating an entire backend application from the functional graph.
This follows the **Graph-to-API pattern**: Persona → Auth middleware,
Outcome → Resource/Controller, Scenario → Endpoint, Step → Handler logic,
Action → Business rule implementation.

### C1. EXTRACT — Build the persona-to-API map

Same as B1: Call `Get_all_personas` then `Get_all_outcomes_for_a_persona_id`
for each persona. **Call all in parallel.**

Additionally, pay special attention to the **System persona** — its
scenarios define background jobs, cron tasks, and internal processing
pipelines that need backend implementation.

### C2. CONSOLIDATE — Map personas to auth middleware

Same consolidation as B2, but output as middleware/guard definitions:

```
Auth Role   → Middleware         → Allowed endpoints
analyst     → requireRole('analyst')  → GET /api/exceptions, POST /api/upload
reviewer    → requireRole('reviewer') → PATCH /api/exceptions/:id/status
admin       → requireRole('admin')    → ALL /api/admin/*
```

### C3. DERIVE — Map outcomes to API resources

Each outcome becomes an API resource or controller:

```
Outcome → Resource → Endpoints
──────────────────────────────
"Manage CSV File Uploads"       → /api/upload      → POST, GET /status
"Review Validation Results"     → /api/exceptions   → GET, GET/:id
"Configure Validation Settings" → /api/admin/config → GET, PUT
"Manage Audit Log"              → /api/admin/audit  → GET, GET/export
```

### C4. DETAIL — Get scenarios for each resource

For each outcome, call `Get_all_scenarios_for_a_outcome_id`.
**Call all in parallel.**

Map scenarios to HTTP endpoints:
- "Upload CSV files" → POST /api/upload
- "View exception details" → GET /api/exceptions/:id
- "Change exception status" → PATCH /api/exceptions/:id/status
- "Export PDF Validation Report" → GET /api/reports/pdf

### C5. DEEP DIVE — Get business logic from steps/actions

For System persona scenarios, call `Get_all_steps_actions_for_a_scenario_id`
to extract:
- Validation formulas (from action descriptions)
- Threshold values and business rules
- Error messages and status codes
- Data transformation logic
- Database query requirements
- **API contracts** (from HAS_API children: url, method, request, response)

### C6. REFERENCE — Get constraints from documents

Call `Documents` for:
- Database schema requirements
- API contract specifications
- Business rule formulas and thresholds
- Error handling requirements

### C7. SCAFFOLD — Generate the backend

Use the stack already confirmed in *Determine Generation Scope* (default: Node.js + Express + TypeScript;
FastAPI for Python repos).

> **Preferred for full backends: orchestration mode.** Scaffold the shared skeleton (bootstrap +
> middleware + store + router-registry) yourself, then fan out **one `breeze:app-backend-module-agent`
> per resource/domain** (one owner per folder; endpoints honour the `HAS_API` contracts so they match
> what the UI calls), and integrate. Generate inline (below) for small services.

Generate files in this order:

1. **Project setup** — package.json, tsconfig
2. **Types/Models** — From graph entity model + System persona actions
3. **Database schema** — From entity relationships in the graph
4. **Auth middleware** — From persona→role map (step C2)
5. **Routes** — From outcome→resource map (step C3)
6. **Controllers** — One per resource, with endpoint handlers from C4
7. **Services** — Business logic from System persona steps/actions (C5)
8. **Validators** — Input validation from action descriptions
9. **Dummy data/seeds** — From Documents (step C6)
10. **Tests** — Map scenarios to API test suites

### C8. VERIFY — Build and test

Run the build command and verify zero errors.

---

## Reference: Graph-to-Code Mapping Cheatsheet

```
FUNCTIONAL GRAPH          FRONTEND                BACKEND
─────────────────         ─────────────           ──────────────
Persona                   Auth role               Auth middleware
Outcome                   Nav section / Page      API resource / Controller
Scenario                  Page feature / Section  Endpoint handler
Step                      User interaction phase  Processing phase
Action (human)            UI element / Form field Request parameter
Action (system)           (not in UI)             Business logic / Service
Action (system desc)      (not in UI)             Formula / Threshold / Rule
Action → HAS_API          API service stub        Route handler implementation
```

## Reference: Dummy Data Pattern

When building dummy data files, always:

1. Shape data from source documents (real business values, not lorem ipsum)
2. Cover all entity types in the functional graph
3. Include edge cases (nulls, empty arrays, boundary values)
4. Add TODO comments for API replacement:
   ```typescript
   // TODO: Replace with API call — GET /api/exceptions
   const exceptions = await fetch('/api/exceptions').then(r => r.json());
   ```
5. Store in `/src/data/dummy.ts` (single file, named exports) for frontend
   or `/seeds/*.json` for backend
6. Match the TypeScript interfaces exactly
7. Use 5-10 records per entity for realistic list/table rendering
8. Include realistic domain-specific values (e.g., valid GSTIN formats for
   Indian accounting, proper date ranges within financial year)

## Reference: Auth Role Consolidation Rules

When mapping graph personas to auth roles:

1. **Permission boundaries drive roles, not persona count**
   - Multiple personas can share one role if permissions are identical
2. **System persona = no auth role** (backend automation)
3. **External System persona = API key auth** (not user login)
4. **Look for escalation patterns** in the graph:
   - "Can only view" → base role
   - "Can view + modify status" → elevated role
   - "Can configure system" → admin role
5. **Check persona descriptions for embedded sub-roles** — a single persona
   like "User" may describe multiple roles (Admin, Manager, Operator) in
   its description. These become separate auth roles.
6. **Present the mapping to the user** — they know the org structure

## Reference: UX Quality Checklist

Before delivering the frontend, verify:

- [ ] **No overflow**: Currency values use `truncate`, tables use `overflow-x-auto`
- [ ] **Consistent spacing**: All page sections use `space-y-5` or `space-y-6`
- [ ] **Grid alignment**: Form fields use `gap-x-6 gap-y-4`, never `mb-4` on FormField
- [ ] **Z-index layering**: Sidebar(40) < DetailPanel backdrop(50) < Panel(60) < Modal(50+)
- [ ] **Mobile responsive**: Sidebar collapses, tables scroll, grids stack to single column
- [ ] **All buttons wired**: Every Create/Import/Edit button opens a modal or navigates
- [ ] **Loading states**: Submit buttons show spinner during async operations
- [ ] **Error states**: Forms show validation errors, API failures show error banners
- [ ] **Empty states**: Tables show a helpful message when no data exists
- [ ] **Custom scrollbars**: Thin, subtle scrollbars in sidebar and panels
- [ ] **Build passes**: `npx tsc --noEmit` AND `npx vite build` both succeed with zero errors

## Reference: Parallelization Strategy for MCP Calls

To minimize latency when fetching the full functional graph:

```
Step 1: Get_all_personas (single call)
           ↓
Step 2: Get_all_outcomes_for_a_persona_id × N personas (ALL in parallel)
           ↓
Step 3: Get_all_scenarios_for_a_outcome_id × M outcomes (ALL in parallel)
           ↓
Step 4: Get_all_steps_actions_for_a_scenario_id × K key scenarios (batch 8-10 in parallel)
```

Each step depends on IDs from the previous step, so steps are sequential.
But within each step, ALL calls should be made in a single parallel batch.
