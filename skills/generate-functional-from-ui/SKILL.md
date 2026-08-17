---
name: generate-functional-from-ui
description: >
  Generate User-persona functional graph from a frontend UI repo with
  rooted per-(EP, persona) sub-agent depth pass, mandatory field
  enumeration, persona-conditional visibility audit, Code_Graph_Search
  escalation (no budget cap), and Python-helper validators
  (schema / rule-a / forbidden / citations / coverage). Produces
  upsert-ready payloads with apis[] capture. One sub-agent run per
  (EP, persona) pair.
argument-hint: "[repo-path]"
---

> ### ⚠️ Is this the right functional-generation skill?
> | Repo shape | Use |
> |---|---|
> | **◀ SPA frontend (React / Vue / Angular / Next) — THIS SKILL** | `/breeze:generate-functional-from-ui` |
> | Headless backend API — REST / GraphQL / queue (incl. **ASP.NET Core**, Node, Java, Python) | `/breeze:generate-functional-from-backend` |
> | ASP.NET **Web Forms** monolith (`.aspx`/`.ascx` + in-process backend, one repo) | `/breeze:generate-functional-from-aspnet-webforms` (single unified pass) |
> | ASP.NET **MVC / Razor Pages** full-stack (Razor views + controllers, one repo) | run **BOTH** this skill (views) **and** `-from-backend` (controllers) — they join by the action-route URL *(no unified skill yet; Razor `.cshtml` support here is limited — SPA is the primary target)* |
> | Vert.x metadata-driven (MAPL / MSCR) | `/breeze:generate-functional-from-metadata` |
>
> **Why Web Forms is one skill but MVC is two:** Web Forms' UI→backend seam is an *in-process method call* (no URL) → a single unified pass is required. MVC/Core expose the backend as a *URL* (the action/endpoint route) → the standard `-from-ui` + `-from-backend` passes join on that URL, same as a SPA + REST API.

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

> **API key:** this skill additionally needs a Breeze `apiKey` for its non-MCP REST upsert path. Collect it on-demand as described below — MCP calls themselves do not use it.

## What this skill does

Turn a frontend UI repo into the human-persona half of the functional graph
(Persona → Outcome → Scenario → Step → Action) with API calls captured
structurally in `action.apis[]`.

**How this skill works (per-(EP, persona) sub-agent depth pass):**

| Concern | Approach |
|---|---|
| Per-EP depth | **Installed agent `breeze:spa-flow-structuring-agent`** invoked per (EP, persona); tool-scoped, model-pinned (sonnet), system prompt cached across calls |
| Persona-conditional visibility | **Mandatory Phase 2.5** — RBAC / role / permission / feature-flag / tier gate hunt inside the sub-agent, with explicit field-level scope |
| Multi-persona EPs | **One sub-agent run per persona** that can reach the EP |
| Field enumeration | **Mandatory Phase 2 inside sub-agent** with `{label, type, required, default, validation, options, visibleTo}` per field |
| Code_Graph_Search | **OPTIONAL / conditional** — `Read`+`Grep` on local source is the backbone; use the graph only for a hard cross-file next-hop or a repo-wide inventory. Zero graph calls is a valid run. No cap when used. |
| Step / Action quantity | **Guidance, not caps** — enumeration overrides |
| Output validation | **Self-validation inside the sub-agent** (Phase 6: schema / rule-a / chain / forbidden / citations) with in-place repair — parent runs NO validators |
| Upsert | **Sub-agent POSTs directly** to `/functional-graph/v2/upsert` (queue-backed embedding, no inline CPU spike) with `api-key:` header — no parent-side curl |
| Citations | `<repo_name>/<relative path>` enforced |

## Resources

- **Installed agent** — `agents/spa-flow-structuring-agent.md` (plugin root). Invokable as `subagent_type: "breeze:spa-flow-structuring-agent"`. The agent's full methodology — phases, rules, schema, self-check, self-validate, write-to-disk, upsert — lives in its system prompt.
- `references/spa-flow-structuring-agent.prompt.md` — short **per-call input renderer** with `{{...}}` placeholders. The parent substitutes and passes the rendered text as the `prompt` argument.
- `references/rules.md` — functional graph semantics (also embedded in the agent's system prompt)
- Schema + word lists live in the **single source of truth** `../shared/functional/{upsert.schema.json, verbs.json}` (ADR 0001) — JSON-schema for the `/functional-graph/v2/upsert` payload; reference only, the agent self-validates.
- `validators/validate.py` — a thin **shim** that delegates to `../shared/functional/validate.py` (the one validator engine), injecting `--kind human` (the UI pass writes only human personas). Standalone debugging helper (subcommands `schema | rule-a | forbidden | citations | coverage | api-urls`). **Not invoked by the skill — the agent self-validates in Phase 6.** Useful for manual inspection of `ui_ep{NN}_{persona}_*.json` files.
- `validators/requirements.txt` — Python dependency: `jsonschema`

## Inputs

- **UI repo path** — argument (`$ARGUMENTS`) or resolved in Phase -1
- **`.breeze.json`** — for `projectUuid` and `targetRepos.frontend`
- **Existing functional graph** — queried per (EP, persona) for dedup
- **Optional: `entrypoints.json`** if resuming from a prior session (under `OUTPUT_BASE = <uiRepo>/.breeze-output/`)

## Outputs

> **All generated artifacts go under a SINGLE dedicated folder `OUTPUT_BASE = <uiRepo>/.breeze-output/`** — NEVER the repo root (that pollutes the target repo's git status). `mkdir -p` it on first write; add `.breeze-output/` to the **target repo's** `.gitignore`. `OUTPUT_BASE` (a folder) is distinct from `.breeze.json` (the config file).

- **Functional graph** updated with per-persona payloads (idempotent merge by name)
- **`OUTPUT_BASE/entrypoints.json`** — full inventory + per-(EP, persona) checkpoint
- **Per-(EP, persona) payload files**: `OUTPUT_BASE/ui_ep{NN}_{persona}_{slug}.json` (audit + replay)

---

# PHASES

## Bootstrap (run ONCE at skill start)

1. Resolve `projectUuid` per the **## Project** section above (defers to `CLAUDE.md`). Cache it.
2. **Resolve URLs** from `breeze.config.json` (plugin root), overridable per-project via `.breeze.json`:
   - `apiBase` — Breeze backend host (e.g. `https://isometric-backend.accionbreeze.com`)
   - `uiBaseUrl` — Breeze UI host (e.g. `https://app.accionbreeze.com`)

   See `CLAUDE.md` → "Service URLs" for the canonical rule. Throughout this skill, `<apiBase>` and `<uiBaseUrl>` are placeholders the parent substitutes at runtime — never hardcode literal hosts.

3. **Resolve `apiKey`** (required — the sub-agent POSTs the upsert directly):
   - Check `.breeze.json` for `apiKey`. If present → cache and continue.
   - If missing, prompt the user with this exact wording (mirrors `/breeze:onboard-repository` → Step 1 convention):

     > This skill upserts via REST directly (avoids MCP argument-size limits on large payloads). It needs a Breeze API key.
     >
     > Generate one at: `<uiBaseUrl>/mcp/generate/key`
     > Then paste it back here. I'll save it to `.breeze.json` for future runs.
     > (Make sure `.breeze.json` is in your `.gitignore`.)

   - Save the pasted key to `.breeze.json` under `apiKey`. Do NOT echo the key back; respond only with "API key saved." Continue.

   **Security:** Never print the key in output, logs, or commits. `.breeze.json` must be in `.gitignore`. The parent passes the key into the sub-agent's input block — both the parent and the agent must avoid echoing it.

4. Call `Call_Get_Project_Details_` with `uuid=<projectUuid>` once; cache the returned `name` — passed to the sub-agent as `PROJECT_NAME` and used in its upsert body.
5. **Resolve the frontend repo's `codeOntologyId`** (required for sub-agent's `Code_Graph_Search` scoping):
   - Check `.breeze.json` → `targetRepos.frontendCodeOntologyId`. If present and `targetRepos.frontendRepoName` is also present → cache both and continue.
   - Otherwise call `Call_List_Repositories_(projectUuid=<projectUuid>)`. The response has `data: [{ _id, name, fileCount, ... }]`.
   - Confirm at least one indexed repo exists with `fileCount > 0` and `status: "active"`. If none → stop and tell the user to run `/breeze:onboard-repository` first.
   - **Match the indexed repo to the on-disk frontend repo.** Strategy:
     1. Compare normalized basenames: lowercase + strip `.`/`-`/`_` from both `targetRepos.frontend`'s basename and each indexed `name`. Pick the first match.
     2. If no normalized match, and only ONE indexed repo exists, use it (sole-repo fast path).
     3. If multiple repos exist with no clear match, ask the user once: "Which indexed repo corresponds to `<basename>`?" with the indexed repo names as options.
   - Save `targetRepos.frontendCodeOntologyId = <_id>` and `targetRepos.frontendRepoName = <name>` to `.breeze.json` for future runs.
   - Cache both for the per-EP loop. The sub-agent receives them as `CODE_ONTOLOGY_ID` and `INDEXED_REPO_NAME`.

---

## Phase -1 — Resolve the target UI repo

Resolve in this order:
1. Check `$ARGUMENTS`
2. Check `.breeze.json` field `targetRepos.frontend`
3. Check if cwd looks like a frontend repo
4. Ask the user — single prompt for absolute path
5. Persist to `.breeze.json` under `targetRepos.frontend`
6. If path has no frontend router file, stop and suggest `/breeze:generate-functional-from-backend`

Then set **`OUTPUT_BASE = f"{uiRepo}/.breeze-output"`** and `mkdir -p` it — every artifact (`entrypoints.json` + per-(EP,persona) payloads) goes under `OUTPUT_BASE`, never the repo root. Ensure `.breeze-output/` is in the target repo's `.gitignore` (append if missing; do not touch the plugin's).

---

## Phase 0 — Discover entry points

If `OUTPUT_BASE/entrypoints.json` already exists (also check the legacy repo-root path once for back-compat; if found there, move it into `OUTPUT_BASE`):
1. Read it and display a resume summary: completed EPs, remaining EPs, next EP to process
2. If the user specified a specific EP (e.g., "start with EP 4"), jump to that EP
3. Otherwise, pick the next EP from `remaining[]`
4. Skip all sub-steps below and go directly to the per-(EP, persona) loop

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
   - **ASP.NET Web Forms** (server-rendered): `*.aspx` + `*.aspx.cs`, `*.ascx`, `*.master`, `Global.asax`, a `*.csproj` referencing `System.Web.UI`
   - **ASP.NET MVC / Razor Pages** (server-rendered Razor): `*.cshtml` views, `*Controller.cs` returning `View(...)` (MVC), or `*.cshtml` + co-located `*.cshtml.cs` `PageModel` (Razor Pages); `_Layout.cshtml`, `_ViewImports.cshtml`, tag helpers / `@Html.*`
2. Record the detected framework and router/entry file path.
3. **Classify the stack** and record it in `entrypoints.json` as `stack`:
   - `webforms` — `*.aspx`/`*.ascx` present ⇒ **STOP (see below)**
   - `mvc` — Razor server-rendered: `*.cshtml` + controllers/PageModels, NO `*.aspx`
   - `spa` — otherwise (the default: React / Vue / Angular / Next / etc.)

   This `stack` value drives sub-steps 0.3–0.4 (client-route vs Razor-view discovery) and Step 3 (which per-EP agent to spawn). **All existing SPA behavior is unchanged when `stack = spa`.**

> ⛔ **`stack = webforms` → STOP and redirect.** ASP.NET **Web Forms** needs the *unified* pass (its UI→backend seam is an in-process method call, no URL — a UI-only pass here can't join to the backend). Do NOT process it in this skill. Tell the user:
> _"This is an ASP.NET Web Forms app. Web Forms uses a single unified skill (UI + in-process backend in one pass) — run `/breeze:generate-functional-from-aspnet-webforms <repo-path>` instead."_ Then end the run.
>
> **`stack = mvc` is supported here** (human half) via `breeze:aspnet-razor-flow-structuring-agent`. The **System** half comes from `/breeze:generate-functional-from-backend` on the same repo (controllers/minimal-APIs as routes); the two join by the **action-route URL**. So a full-stack MVC/Razor monolith = this skill (views) + `-from-backend` (controllers) — two passes, URL-joined (unlike Web Forms).

---

### Sub-step 0.2 — Discover and confirm personas ⛔ HARD GATE

**First check if personas already exist in the graph:**

1. Call `Get_all_personas(projectUuid)`
2. **If personas exist (≥1):**
   - Present them to the user
   - Ask: _"These personas are already in the graph. Want to use them, or should I re-detect from code using `/breeze:detect-personas`?"_
   - If user accepts → use existing personas, skip to step 6
   - If user wants recheck → proceed to step 3
3. **If no personas exist, or user requested recheck:**
   - Run `/breeze:detect-personas` against the target UI repo
   - `/breeze:detect-personas` will output an analysis-only persona matrix (it does NOT write to the graph)
   - Use its output as the candidate list
4. Present the detected personas to the user with source locations
5. Wait for user confirmation
6. Record confirmed set in `entrypoints.json` under `personas[]`
7. Personas are created in the graph as part of the first EP upsert payload (the upsert endpoint creates personas by name if they don't exist yet — idempotent merge). The `entrypoints.json` carries persona data across sessions.

> **Rules:** see [rules.md](references/rules.md) → "Persona rules (UI pass specific)". This is a **closed set** — do not proceed until the user confirms.

---

### Sub-step 0.3 — Discover routes (or `.aspx` pages)

**If `stack = spa` (default):**
1. Optionally `Code_Graph_Search` to locate the routes definition
2. Also query for sidebar/navbar structure to surface panel triggers
3. `Read` the router file locally
4. `Read` the sidebar/navbar component for non-routed features

**If `stack = mvc`** (ASP.NET MVC / Razor Pages — Razor server-rendered): entry points are **Razor views**, each owned by a controller action or a Razor Page handler.
1. **MVC:** `Glob '**/Views/**/*.cshtml'` (skip `_Layout`, `_ViewStart`, `_ViewImports`, `Shared/EditorTemplates`/`DisplayTemplates`, partials `_*.cshtml`). Each feature view (`Views/Accounts/Edit.cshtml`) is an EP — `kind: mvc-action`, `route` = the controller action route (convention `/{controller}/{action}` or the `[Route]`/`[HttpX("…")]` attribute), `seed_file` = the `.cshtml`; the agent reads the matching controller action (GET+POST) + view-model.
2. **Razor Pages:** `Glob '**/Pages/**/*.cshtml'` with a co-located `.cshtml.cs`. Each page is an EP — `kind: razor-page`, `route` = the page route, `seed_file` = the `.cshtml`; the agent reads the `PageModel` (`OnGet*`/`OnPost*`).
3. **Fold, don't promote, composed views:** `_Layout.cshtml` (chrome), partials/editor-templates/display-templates, and `@await Component.InvokeAsync(...)` view-components are **not** standalone EPs — they're read *inside* the parent view's pass (the MVC analogue of subpanels). Only routed views are EPs.
4. `Read` `[Authorize]`/policies on controllers/PageModels + `_ViewImports` for per-EP persona reachability (sub-step 0.4).
> **The System half is a separate pass.** MVC controllers/actions are captured by `/breeze:generate-functional-from-backend` on the same repo; this skill emits the **human** half only, and the two join on the **action-route URL**. (Web Forms is different — it was redirected out in 0.1 because its seam has no URL.)

---

### Sub-step 0.3b — Route completeness cross-check ⛔ (ground-truth, mandatory when code graph is available)

Reading the router by hand can miss routes (conditional/nested routers, lazily-registered routes, routes defined outside the main router file). The code graph has a **deterministic, complete** route inventory — use it to catch anything the hand-read missed:

1. Call `Get_Code_Nodes_By_Label(project_uuid=<uuid>, label="Statement", filters={"codeOntologyId": <frontendCodeOntologyId>, "semanticType": "route"})` (pass `codeOntologyId` as an **integer**). If it returns empty, retry with `filters={"type": "route"}` (legacy parser).
2. **Diff** the returned `endpoint` list against the routes you discovered by reading the router.
3. Any route present in the graph but **missing** from your inventory → add it as an entry point (resolve its component via the `handler`/`path` fields or a follow-up `Code_Graph_Search`). Any route in your inventory but not in the graph → keep it (graph may be stale) but note it.
4. Record the reconciliation under `orphans.routeCrosscheck` in `entrypoints.json`: `{ graphRouteCount, inventoryRouteCount, addedFromGraph: [...], onlyInInventory: [...] }`.

If the code graph is unavailable (MCP down / repo not indexed), skip with a recorded note — do NOT block discovery.

---

### Sub-step 0.4 — Extract route details (+ per-EP `personas[]`)

For each route capture: `path`, `component`, `title`, `params`, `queryParams`, `auth` guards, `variants`.

**Every entry point also gains a `personas[]` field** listing which detected personas can reach this EP based on auth guards, route variants, RBAC, layouts, subscription gating, or feature flags. Populate it from the persona discovery in sub-step 0.2. If you cannot determine which personas reach an EP, default to the full confirmed persona set — the per-(EP, persona) loop uses `audit.skippedForVisibility[]` to record what each persona can/cannot see.

---

### Sub-step 0.5 — Categorize

Group routes by domain category (e.g. Search, Pipeline, Notifications, Insights, Settings, Auth).

---

### Sub-step 0.6 — Discover orphaned views

1. Compare every file under `src/pages/**` and `src/views/**` against routes from 0.3
2. For unmatched files, check imports and API calls
3. Classify each orphan as sub-component, dead code, or truly unused

> **Rules:** see [rules.md](references/rules.md) → "Orphan classification"

---

### Sub-step 0.7 — Discover non-routed feature surfaces ⛔ HARD GATE

1. Enumerate panel/drawer/modal type constants — grep for `TPanel`, `PanelType`, `DrawerType`, `ModalType`, setter calls, disclosure hooks, feature folders, `*-modal.tsx` / `*-drawer.tsx` etc.
2. Locate every renderer for each unique panel type string
3. Locate every trigger (`setPanelType("X")` call sites)
4. Read each renderer and classify as viewer or feature-rich
5. Present discovery list to user with classifications
6. Wait for user confirmation
7. Record confirmed list in `entrypoints.json` under `panels[]`

> **Rules:** see [rules.md](references/rules.md) → "Panel classification rules"

---

### Sub-step 0.8 — Cross-reference backend API routes (optional)

1. If backend repo is indexed in code graph, `Code_Graph_Search` for backend routes
2. Flag backend endpoints with no frontend caller
3. Do NOT modify the graph — just record for review

---

### Sub-step 0.9 — Write `entrypoints.json`

1. Write the full inventory to `OUTPUT_BASE/entrypoints.json` with this schema (note the per-EP `personas[]` field):

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
      "personas": ["Subscriber", "Admin"],
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
      "personas": ["Subscriber"],
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

# PER-EP LOOP (per (EP, persona) sub-agent)

For each entry point `ep` in `remaining[]`, **and for each `persona` in `ep.personas[]`**:

## Step 1 — (removed) dedup is now agent-side

The parent no longer runs a dedup pre-query and does **not** pass `EXISTING_NEIGHBORHOOD`. The sub-agent builds its own dedup context from the **live** graph (`Functional_Graph_Search` + a persona-scoped `Get_all_personas`→`Get_all_outcomes_for_a_persona_id`→`Get_all_scenarios_for_a_outcome_id` read-back) right before writing — fresher and race-safe under parallel batches. Proceed to Step 2.

## Step 2 — Pre-compute OUTPUT_PATH and render the sub-agent prompt

**Pre-compute the output path** before spawning. The sub-agent writes its `{payload, audit}` JSON here; the parent reads from here for validators and upsert. This is how the parent avoids holding the full payload in its context:

```
OUTPUT_PATH = f"{OUTPUT_BASE}/ui_ep{ep.id:02d}_{persona}_{slug}.json"   # OUTPUT_BASE = {uiRepo}/.breeze-output
```

where `slug` is a kebab-cased form of `ep.title` (e.g. `code-ontology-list`).

Then load `references/spa-flow-structuring-agent.prompt.md` and substitute the `{{...}}` placeholders:

| Placeholder | Value |
|---|---|
| `{{persona}}` | the persona for this run |
| `{{route}}` | `ep.route` |
| `{{kind}}` | `ep.type` (`route` / `panel` / `route-variant`) |
| `{{title}}` | `ep.title` |
| `{{seed_file_absolute_path}}` | absolute path to `ep.component` |
| `{{shared_functional_path}}` | absolute path to the **shared functional SSOT** dir — `<pluginRoot>/skills/shared/functional` (sibling of this skill, i.e. `<this skill dir>/../shared/functional`). The agent reads `core.md` + `human-overlay.md` from here for the canonical rules (ADR 0001). |
| `{{repo_name}}` | basename of the UI repo path |
| `{{repo_root_absolute_path}}` | absolute path to the UI repo |
| `{{project_uuid}}` | `projectUuid` from `.breeze.json` |
| `{{project_name}}` | project name cached in Bootstrap step 4 |
| `{{llm_platform}}` | `"AWSBEDROCK"` (passed to upsert URL) |
| `{{output_path}}` | the pre-computed `OUTPUT_PATH` above |
| `{{api_base}}` | `apiBase` from Bootstrap step 2 |
| `{{api_key}}` | `apiKey` from `.breeze.json` (NEVER echo, NEVER log) |
| `{{code_ontology_id}}` | `frontendCodeOntologyId` resolved in Bootstrap step 5 |
| `{{indexed_repo_name}}` | `frontendRepoName` resolved in Bootstrap step 5 (server-side name, may differ from on-disk basename) |


## Step 3 — Spawn sub-agent

Pick the per-EP agent by the `stack` detected in sub-step 0.1:
- `stack = spa` → `breeze:spa-flow-structuring-agent`
- `stack = mvc` → `breeze:aspnet-razor-flow-structuring-agent`
- `stack = webforms` → **never reaches here** — redirected to `/breeze:generate-functional-from-aspnet-webforms` in sub-step 0.1.

```
Agent(
  subagent_type = "breeze:spa-flow-structuring-agent",   # or "breeze:aspnet-razor-flow-structuring-agent" when stack == mvc
  description   = f"Flow-structure EP {ep.id} ({persona}): {ep.title}",
  prompt        = <rendered per-call inputs from Step 2>
)
```

Both agents take the **same** per-call input block (Step 2) and honour the **same** output contract (schema, self-validate, write, upsert) — they differ only in how they read the stack (SPA components + `fetch`/`axios` vs Razor `.cshtml` views + controllers/PageModels, joining on the action-route URL). The full methodology lives in `agents/spa-flow-structuring-agent.md` / `agents/aspnet-razor-flow-structuring-agent.md` respectively — installed by the breezeai-plugins plugin. The `prompt` argument here is **only** the short variable input block from Step 2; the agent's system prompt does the rest.

Tool scoping is enforced by the agent definition's `tools:` frontmatter
(Read, Glob, Grep, Bash, `mcp__plugin_breeze_breeze-mcp__Code_Graph_Search`).
Model is `sonnet`; `maxTurns: 30`. Anthropic prompt caching reuses the
fixed system prompt across calls, so subsequent (EP, persona) runs pay
only for the small variable input block.

**Sub-agent returns ONLY a short summary line.** It self-validates (Phase 6), writes to OUTPUT_PATH (Phase 7), POSTs the upsert (Phase 8), and reports the HTTP status + functionalId. Parse the summary line shape:

```
# Success:
OK · outcomes: <N> · scenarios: <N> · steps: <N> · actions: <N> · apis: <N> · cgs: <N> · http: 200 · functionalId: <id> · path: <OUTPUT_PATH>

# Phase 6 (self-validate) failure — agent could not repair after 2 passes:
FAIL_VALIDATE · errors: <count> · last_check: <schema|rule-a|chain|forbidden|citations> · path: <OUTPUT_PATH>

# Phase 7 (write) failure:
FAIL_WRITE · could not write to <OUTPUT_PATH> · <reason>

# Phase 8 (upsert) failure:
FAIL_UPSERT · http: <status> · path: <OUTPUT_PATH> · note: <response excerpt>
```

Parse the summary to confirm `path` matches the OUTPUT_PATH you passed in. Branch on the prefix:

| Prefix | Action |
|---|---|
| `OK · ` | Continue to Step 4 (verify) and Step 5 (checkpoint) |
| `FAIL_VALIDATE` | Record in `entrypoints.failed[]` with `reason: "self-validation"`. Inspect the OUTPUT_PATH file on disk if you need details. Continue to next persona/EP. |
| `FAIL_WRITE` | Record in `entrypoints.failed[]` with `reason: "write"`. Continue. |
| `FAIL_UPSERT` | Record in `entrypoints.failed[]` with `reason: "upsert"` and the HTTP status. The OUTPUT_PATH file IS the replay artifact — re-upserting later is a single curl. Continue. |

**The parent never runs validators and never POSTs. The agent owns both — that is this skill's contract.**

## Step 4 — Verify (post-upsert sanity check)

**Step 4a — Seed-fidelity assertion (cheap, do this FIRST).** Before the semantic check, confirm the payload the sub-agent wrote actually describes the EP you assigned. A sub-agent can return `OK · http 200` on a payload that was silently swapped by a concurrent sibling or padded from another route (the agent's own Phase-6 `seed-fidelity` gate is the primary guard; this is the parent-side backstop). Grep the OUTPUT_PATH for a citation to the EP's own seed basename:
```bash
python3 - "$OUTPUT_PATH" "$(basename "$ep_component")" "$persona" <<'PY'
import json,sys
d=json.load(open(sys.argv[1])); p=d.get("payload",d); seed,persona=sys.argv[2],sys.argv[3]
refs=[c.get("reference","") for pe in p.get("personas",[]) for o in pe.get("outcomes",[])
      for s in o.get("scenarios",[]) for lvl in (s,)+tuple(s.get("steps",[]))
      for c in lvl.get("citations",[])]
refs+=[c.get("reference","") for pe in p.get("personas",[]) for o in pe.get("outcomes",[])
       for s in o.get("scenarios",[]) for st in s.get("steps",[]) for a in st.get("actions",[]) for c in a.get("citations",[])]
pers=[pe.get("persona") for pe in p.get("personas",[])]
ok = any(seed in r for r in refs) and persona in pers
print("SEED_OK" if ok else f"SEED_MISMATCH persona={pers} seed={seed} cites_seed={any(seed in r for r in refs)}")
PY
```
If it prints `SEED_MISMATCH`, do **not** accept the `OK`: record it in `entrypoints.failed[]` with `reason: "seed-mismatch"`, re-add `(epId, persona)` to `remaining[]`, and re-spawn that one EP (serially — see Parallelism) with a corrective note. This is the single check that turns a silent content-swap into a caught failure.

**Step 4b — Semantic check.** For 2-3 unique scenario descriptions from the upserted payload, call:
```
Functional_Graph_Search(uuid=projectUuid, query=<first 80 chars of description>, limit=3)
```
Confirm `score > 0.4` and the `scenarioId` resolves. Record verification
scores in the checkpoint.

## Step 5 — Update checkpoint

Append to `entrypoints.completed[]`:
```json
{
  "epId":            12,
  "persona":         "Admin",
  "title":           "Project Settings",
  "outcomeName":     "Configure Project Settings",
  "scenariosCreated":  4,
  "actionsCreated":    18,
  "apiCallsLogged":    5,
  "fieldsEnumerated":  11,
  "codeGraphSearchCount":            3,
  "actionsSkippedForOtherPersonas":  2,
  "coverageRatio":   0.92,
  "skippedForVisibility": [...],
  "warnings":        [...],
  "payloadPath":     "<uiRepo>/.breeze-output/ui_ep12_Admin_project-settings.json",
  "completedAt":     "<ISO>"
}
```

**Only pop `ep.id` from `remaining[]` after all personas for this EP
have been processed** (successfully completed or marked failed).

---

# REFERENCE

## Per-(EP, persona) cost

- Small EP (≤200 lines): ~30k tokens, ~60s wall-clock
- Medium EP (~500 lines): ~70k tokens, ~120s
- Large EP (>1500 lines): ~150k+ tokens, ~180s+

For an EP with 3 personas, multiply by 3. Plan multi-session for >20 EPs.

## Parallelism

The Agent tool supports concurrent sub-agents in one message. Recommended:
- **Up to 3 sub-agents in flight at once — but never two runs that share the same seed component.** Two (EP, persona) pairs on the *same* seed file (e.g. the two personas of one EP, or an EP + its panel that render the same component) MUST run **serially**, one after the other. Same-seed siblings are the exact condition that produced content-swaps in practice (a concurrent run's scratch write clobbered its sibling's, so the file ended up with the wrong route's content). Different-seed EPs may run concurrently.
- Group by EP — finish all personas of EP N before starting EP N+1 (so the EP's `remaining[]` entry is cleared atomically). Within an EP, run its personas **serially** (they share the seed).
- Each sub-agent already writes to an EP-unique `OUTPUT_PATH` and keys its scratch files to that basename, and self-checks `seed-fidelity` in Phase 6; Step 4a re-asserts it parent-side. Serial same-seed execution is the belt to those suspenders — apply it, don't rely on the guards alone.

> ⚠️ **Two independent races — do not conflate them.**
> **(1) Content-swap race (severe, mitigated above):** concurrent same-seed siblings can end up with each other's *content* if any scratch file is shared. Mitigation: serialize same-seed runs (above) + the agent's EP-unique paths + the `seed-fidelity` gate + Step 4a. A swap that slips through surfaces as `SEED_MISMATCH` in Step 4a → re-spawn that EP serially.
> **(2) Parallel-dedup race (cosmetic):** each sub-agent builds its dedup neighborhood by reading the LIVE graph *before* it writes, so concurrent siblings can't see each other's about-to-be-created nodes. With the OUTCOME-ONLY inline dedup model (shared `core.md` §2), the only thing at risk is **Outcome-name convergence** — two siblings may mint slightly-different names for the same capability (e.g. "Monitor Project Progress" vs "Monitor Project Status"). Two mitigations, apply at least one:
> 1. **Serialize shared-Outcome work** — when several personas of one EP (or several EPs) will land on the same capability/Outcome, run them sequentially rather than concurrently so the later ones read the earlier one's Outcome.
> 2. **Rely on the mandatory reconciliation pass** (below) to merge near-duplicate Outcomes after the fan-out.
> Below-outcome nodes are intentionally NOT deduped (coverage-first) — the parallel race collides only at the Outcome, so reconciliation is Outcome-level only and leaves below-outcome nodes as distinct coverage.

## Reconciliation pass ⛔ (mandatory finalization — run after ALL EPs complete)

Coverage-first generation (shared `core.md` §2.3) and parallelism intentionally allow near-duplicate Outcomes. The parallel race collides **only at the Outcome** (siblings share it by name); everything below an Outcome came from a *different* EP/persona and is distinct coverage, not a duplicate. So reconciliation is **Outcome-level only** — a run is not "done" until it runs:

1. **Outcome convergence.** List every Outcome across all personas (`Get_all_personas` → `Get_all_outcomes_for_a_persona_id`). Within each persona, find Outcomes that denote the **same capability** under slightly different names; merge them with `Merge_Functional_Nodes` (keep the canonical/most-general name). Do NOT merge across personas — Outcome is shared by *name*, so once names converge the upsert already unifies them.
2. **Never merge distinct capabilities** to reduce node count — reconciliation removes *duplicates*, not *coverage* (respect the capability-level floor in `core.md` §2.2).
3. Record what was merged in `entrypoints.json` under `reconciliation: { outcomesMerged: [...] }`.

**Do NOT merge below the Outcome level.** Scenario / Step / Action are coverage-first — merging near-duplicate scenarios (which came from different EPs/personas) risks silently dropping distinct flows for no join benefit.

## Multi-session resume

When context budget hits ~75%, flush the current EP's checkpoint and stop.
Recommend the user resume with:
```
/breeze:generate-functional-from-ui continue from entrypoints.json in repo <uiRepo>
```

## Failure recovery

`entrypoints.failed[]` holds per-(EP, persona) failures with reasons mapped to the agent's summary-line prefixes (`FAIL_VALIDATE`, `FAIL_WRITE`, `FAIL_UPSERT`). For each:

- **`FAIL_UPSERT` only** — the payload is sound but the POST failed. Re-curl the same OUTPUT_PATH directly via `<API_BASE>/functional-graph/v2/upsert?embedding=true&llmPlatform=<LLM_PLATFORM>` with `api-key:` header. No re-spawn needed.
- **`FAIL_VALIDATE` / `FAIL_WRITE`** — re-spawn the sub-agent with the same input block; the agent will regenerate from scratch. If the same failure repeats, inspect the OUTPUT_PATH on disk to understand the defect class, then patch the agent prompt.
- **Recovery loop**: clear matching entries from `failed[]`, re-add `(epId, persona)` to `remaining[]` (or pass explicitly via continue prompt), resume the skill.

## See also

- `/breeze:generate-functional-from-backend` — System / External System persona pass
- `/breeze:validate-functional-graph` — post-generation quality checks
- `/breeze:generate-spec` — export the graph as a spec document
