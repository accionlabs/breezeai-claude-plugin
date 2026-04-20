---
name: generate-functional-from-ui
description: >
  Generate User-persona functional graph from a frontend UI repo.
  Produces human-persona scenarios + actions with API endpoints in
  apis[]. Use when: generate functional from UI, ui to functional,
  frontend functional pass.
argument-hint: "[repo-path]"
---

## What this skill does

Transforms a frontend UI repo into the **User-persona** half of the
functional graph (Persona > Outcome > Scenario > Step > Action),
with API calls captured structurally in `action.apis[]`.

```
generate-functional-from-ui      -> User-persona scenarios   (this skill)
generate-functional-from-backend -> System-persona scenarios
```

The two passes are fully independent — they share the functional
graph as the only common surface (idempotent merge by outcome name).

## Resources

- For all rules (functional graph definitions, UI-pass-specific rules, validation, pitfalls), read [references/rules.md](references/rules.md)

## Inputs

- **UI repo path** — if provided as argument (`$ARGUMENTS`), use it
  directly; otherwise resolved in Phase -1
- **`.breeze.json`** — for `projectUuid`
- **Existing functional graph** — queried for dedup, not assumed empty
- **Optional: `entrypoints.json`** if resuming from a prior session
  (looked up inside the UI repo directory)

## Outputs

- **Functional graph** updated with User-persona scenarios + actions
- **`entrypoints.json`** — inventory + running checkpoint (written
  inside the user-provided UI repo directory, e.g.
  `<uiRepo>/entrypoints.json`)

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing or incomplete, tell the user to run `/breeze:setup-project`
3. Extract `projectUuid`
4. Call `Call_Get_Project_Details_` with `uuid=<projectUuid>` once, cache the returned project `name` — required by the bulk upsert in Step 7
5. Confirm the project has at least one code ontology indexed

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
6. If path has no frontend router file, stop and suggest
   `/breeze:generate-functional-from-backend`

> **Rules:** see [rules.md](references/rules.md) → "Frontend repo detection"

---

## Phase 0 — Discover entry points

If `entrypoints.json` already exists in the UI repo directory:
1. Read it and display a resume summary: completed EPs, remaining
   EPs, next EP to process
2. If user specified a specific EP (e.g., "start with EP 4"), jump
   to that EP
3. Otherwise, pick the next EP from `remaining[]`
4. Skip all sub-steps below and go directly to the per-EP loop

Do not overwrite an existing `entrypoints.json`.

---

### Sub-step 0.1 — Detect framework

1. Look for framework signals in the repo:
   - React Router: `<Route`, `createBrowserRouter`, `useRoutes`
   - Vue 2/3: `src/router/index.{js,ts}`
   - Next.js: `pages/` or `app/` directory
   - Angular: `*-routing.module.ts` or `app.routes.ts`
   - Nuxt: `pages/` with `.vue` files
   - SvelteKit: `src/routes/`
2. Record the detected framework and router file path

---

### Sub-step 0.2 — Discover and confirm personas ⛔ HARD GATE

**First check if personas already exist in the graph:**

1. Call `Get_all_personas(projectUuid)`
2. **If personas exist (≥1):**
   - Present them to the user
   - Ask: _"These personas are already in the graph. Want to use
     them, or should I re-detect from code using `/breeze:detect-personas`?"_
   - If user accepts → use existing personas, skip to step 6
   - If user wants recheck → proceed to step 3
3. **If no personas exist, or user requested recheck:**
   - Run `/breeze:detect-personas` against the target UI repo
   - `/breeze:detect-personas` will output an analysis-only persona
     matrix (it does NOT write to the graph)
   - Use its output as the candidate list
4. Present the detected personas to the user with source locations
5. Wait for user confirmation
6. Record confirmed set in `entrypoints.json` under `personas[]`
7. Personas are created in the graph as part of the first EP
   upsert payload (the upsert endpoint creates personas by name
   if they don't exist yet — idempotent merge). The
   `entrypoints.json` carries persona data across sessions.

> **Rules:** see [rules.md](references/rules.md) → "Persona rules (UI pass
> specific)". This is a **closed set** — do not proceed until user
> confirms.

---

### Sub-step 0.3 — Discover routes

1. Optionally `Code_Graph_Search` to locate the routes definition
2. Also query for sidebar/navbar structure to surface panel triggers
3. `Read` the router file locally
4. `Read` the sidebar/navbar component for non-routed features

---

### Sub-step 0.4 — Extract route details

For each route capture: `path`, `component`, `title`, `params`,
`queryParams`, `auth` guards, `variants`.

---

### Sub-step 0.5 — Categorize

Group routes by domain category (e.g. Search, Pipeline,
Notifications, Insights, Settings, Auth).

---

### Sub-step 0.6 — Discover orphaned views

1. Compare every file under `src/pages/**` and `src/views/**` against
   routes from 0.3
2. For unmatched files, check imports and API calls
3. Classify each orphan as sub-component, dead code, or truly unused

> **Rules:** see [rules.md](references/rules.md) → "Orphan classification"

---

### Sub-step 0.7 — Discover non-routed feature surfaces ⛔ HARD GATE

1. Enumerate panel/drawer/modal type constants — grep for `TPanel`,
   `PanelType`, `DrawerType`, `ModalType`, setter calls, disclosure
   hooks, feature folders, `*-modal.tsx` / `*-drawer.tsx` etc.
2. Locate every renderer for each unique panel type string
3. Locate every trigger (`setPanelType("X")` call sites)
4. Read each renderer and classify as viewer or feature-rich
5. Present discovery list to user with classifications
6. Wait for user confirmation
7. Record confirmed list in `entrypoints.json` under `panels[]`

> **Rules:** see [rules.md](references/rules.md) → "Panel classification rules"

---

### Sub-step 0.8 — Cross-reference backend API routes (optional)

1. If backend repo is indexed in code graph, `Code_Graph_Search` for
   backend routes
2. Flag backend endpoints with no frontend caller
3. Do NOT modify the graph — just record for review

---

### Sub-step 0.9 — Write `entrypoints.json`

1. Write the full inventory to disk with this schema:

```json
{
  "project": "<repo name>",
  "projectUuid": "<from .breeze.json>",
  "framework": "react-router",
  "routerFile": "src/routes/routes.apac.tsx",
  "uiRepo": "<resolved target repo path>",
  "generatedAt": "<ISO timestamp>",
  "personas": [
    { "name": "Subscriber", "source": "src/features/auth/types.ts:14", "isExisting": false }
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

2. Present the EP list to the user and ask if any should be excluded

---

# PER-EP LOOP (repeat for each entry point)

---

## Step 1 — Dedup check

1. `Functional_Graph_Search` for the EP's likely outcome name + 2
   likely scenario names
2. Apply dedup decision matrix to decide: reuse, differentiate, or
   proceed fresh

> **Rules:** see [rules.md](references/rules.md) → "Dedup decision matrix"

---

## Step 2 — Read the page deeply

1. Glob the page directory and `Read` the meaningful files:
   - `index.{tsx,jsx}` entry component
   - All `widgets/*`, `components/*`
   - `queries.{ts,tsx}`, `store.{ts,tsx}`
   - Any `Form*`, `Popup*`, `Dialog*`, `Modal*`, `Sidebar*`,
     `Navigation*`
   - `hooks/*` if present
2. Skip leaf primitives (`Skeleton`, `LoadSkeleton`, `NoData`, `Empty`)
3. Follow every panel/drawer/modal trigger out of the page to its
   renderer
4. For every imported component matching the drill-down pattern, read
   the file

> **Rules:** see [rules.md](references/rules.md) → "Follow-the-trigger rule"
> and "Component-import drill-down rule". Target: name 10-20 distinct
> user flows after this step, not 2-3.

---

## Step 3 — JSX interactive-element inventory

1. Grep the page directory for interactive widget tags and form hooks:
   ```
   <Button       <IconButton    <Tab          <Tabs
   <Checkbox     <Switch        <Toggle       <Stepper
   <Select       <MenuItem      <Radio        <Autocomplete
   <Dialog       <Modal         <Popover      <Drawer
   <TextField    <Input         <DatePicker
   useState      useForm        zodResolver
   ```
2. Build a list: `{ widgetType, label, file, line }` for each unique
   interactive element
3. Strip leaf-primitive widgets and form scaffolding noise
4. This list is the **completeness checklist** for Step 6.5

---

## Step 4 — API inventory

1. Grep the page directory for:
   ```
   fetchGet|fetchPost|fetchPut|fetchDelete|fetchPatch
   useQuery|useMutation|useInfiniteQuery
   apiFetch|axios\.|api\.
   dispatch\(.*Api
   ```
2. For each hit, follow to the service/query file and `Read` it
3. Extract: literal URL string (resolve template literals), HTTP
   method, request shape, source location
4. If a Redux thunk wraps the call, trace one hop: thunk -> service ->
   URL

> **Rules:** see [rules.md](references/rules.md) → "`apis[]` type reference"

---

## Step 5 — Field enumeration for Review actions

1. For rendered data blocks (project header, overview, contact card,
   table row), enumerate fields by reading JSX render or response DTO
2. For enum dropdowns populated from master data, follow the hook to
   its query and find the value list
3. Put long field lists in the **Scenario description** (not action
   description)

---

## Step 6 — Build payload

1. Map EP to an outcome (one outcome per EP cluster or shared with
   closely-related EPs)
2. Build persona -> outcome -> scenario -> step -> action tree
3. Populate `apis[]` on every action that triggers an API call

**`data` payload** (top-level `personas` array, passed as the `data`
argument to `bulk_update_functional_nodes` in Step 7):

```json
{
  "personas": [
    {
      "persona": "User",
      "description": "...optional...",
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
                          "request": "ES query body",
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
}
```

The project `uuid`, `name`, `skip_step_and_action`, `embedding`, and
`llm_platform` are passed as sibling MCP arguments — they do NOT go
inside `data`.

> **Rules:** see [rules.md](references/rules.md) → "Persona rules", "Outcome
> rules", "Action rules", "Quantity targets", "Disambiguation rule",
> and `../shared/functional-graph-rules.md` for canonical rules.

---

## Step 6.5 — Pre-upsert JSX coverage validator

1. Take the Step 3 JSX widget inventory
2. For each widget, match to at least one action by label match,
   file+line citation, or `viewOnlyChrome[]` exclusion
3. Calculate coverage percentage
4. If >=90% -> proceed. If <90% -> fix payload or re-read missed files

> **Rules:** see [rules.md](references/rules.md) → "JSX coverage validator rules"

---

## Step 7 — Upsert ONE EP at a time

1. Write the Step 6 payload to `<uiRepo>/ui_ep{NN}_{name}.json` for
   audit/resume purposes
2. Call the `bulk_update_functional_nodes` MCP tool:
   ```
   bulk_update_functional_nodes(
     uuid: <projectUuid>,
     name: <project name from Call_Get_Project_Details_>,
     data: <payload from Step 6 — top-level personas array>,
     skip_step_and_action: false,
     embedding: true,
     llm_platform: "AWSBEDROCK"
   )
   ```
3. If Rule A or Rule B fails, refuse to call the tool — fix and
   re-validate

> **Rules:** see [rules.md](references/rules.md) → "Pre-upsert validation
> rules" and "Write protocol"

---

## Step 8 — Verify

1. `Functional_Graph_Search` for a unique phrase from each new
   scenario's description
2. Confirm: scenario appears, score > 0.4, `scenarioId` returned

---

## Step 9 — Update checkpoint

1. Mark EP's `status` from `in_progress` -> `done`
2. Pop the EP id from `remaining[]`
3. Append a `completed[]` record:

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
  "verificationScores": { "core project data": 0.71 },
  "payload": "<uiRepo>/ui_ep12_project_detail.json",
  "completedAt": "<ISO>"
}
```

4. Edit (do not rewrite) `entrypoints.json` — only `status`,
   `completed[]`, `remaining[]` mutate

---

# REFERENCE

## Cost per EP

~**10-14 tool calls per EP**. For 50 EPs: 500-700 calls. Plan for
multiple sessions.

## Multi-session resume

When context budget hits ~75%, or after completing 3-5 EPs: flush
current EP's checkpoint, stop, and report progress.

**Recommend the user to start a fresh session** with a ready-to-paste
command like:

```
/breeze:generate-functional-from-ui continue from entrypoints.json in repo <uiRepo path>
```

If complex EPs are next (e.g., project detail pages with many
sub-components), recommend starting those in a fresh session for
maximum quality:

_"EP N (Page Name) is a complex page with many sub-components.
I recommend processing it in a fresh session for best quality.
To resume, paste:"_

```
/breeze:generate-functional-from-ui continue from entrypoints.json in repo <path>, start with EP N
```

**Batching guidance to share with user:**
- Complex EPs (project detail, company detail): 1 per session
- Medium EPs (pipeline, search, key accounts): 2-3 per session
- Simple EPs (change password, settings, fair usage): 4-5 per session

## When NOT to use

- **Backend-only repos** — use `/breeze:generate-functional-from-backend`
- **Quick first-time exploration** — deprecated `generate-functional-from-code`

## See also

- `/breeze:generate-functional-from-backend` — the backend half
- `/breeze:generate-functional-from-code` — deprecated legacy pipeline
- `/breeze:validate-functional-graph` — quality checks after generation
- `/breeze:generate-spec` — export the graph as a spec doc
