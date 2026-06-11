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
| Per-EP depth | **Installed agent `breeze:flow-structuring-agent`** invoked per (EP, persona); tool-scoped, model-pinned (sonnet), system prompt cached across calls |
| Persona-conditional visibility | **Mandatory Phase 2.5** — RBAC / role / permission / feature-flag / tier gate hunt inside the sub-agent, with explicit field-level scope |
| Multi-persona EPs | **One sub-agent run per persona** that can reach the EP |
| Field enumeration | **Mandatory Phase 2 inside sub-agent** with `{label, type, required, default, validation, options, visibleTo}` per field |
| Code_Graph_Search | **Hard floor: ≥1 mandatory hygiene sweep per run; no budget cap thereafter** |
| Step / Action quantity | **Guidance, not caps** — enumeration overrides |
| Output validation | **Self-validation inside the sub-agent** (Phase 6: schema / rule-a / chain / forbidden / citations) with in-place repair — parent runs NO validators |
| Upsert | **Sub-agent POSTs directly** to `/functional-graph/upsert` with `api-key:` header — no parent-side curl |
| Citations | `<repo_name>/<relative path>` enforced |

## Resources

- **Installed agent** — `agents/flow-structuring-agent.md` (plugin root). Invokable as `subagent_type: "breeze:flow-structuring-agent"`. The agent's full methodology — phases, rules, schema, self-check, self-validate, write-to-disk, upsert — lives in its system prompt.
- `references/flow-structuring-agent.prompt.md` — short **per-call input renderer** with `{{...}}` placeholders. The parent substitutes and passes the rendered text as the `prompt` argument.
- `references/rules.md` — functional graph semantics (also embedded in the agent's system prompt)
- `schemas/upsert.schema.json` — JSON-schema for the `/functional-graph/upsert` REST payload (mirrored from the n8n flow). Reference only; the agent self-validates against the rules in its system prompt.
- `validators/validate.py` — Standalone debugging helper (subcommands `schema | rule-a | forbidden | citations | coverage`). **Not invoked by the skill — the agent self-validates in Phase 6.** Useful only for manual inspection of `ui_ep{NN}_{persona}_*.json` files.
- `validators/requirements.txt` — Python dependency: `jsonschema`

## Inputs

- **UI repo path** — argument (`$ARGUMENTS`) or resolved in Phase -1
- **`.breeze.json`** — for `projectUuid` and `targetRepos.frontend`
- **Existing functional graph** — queried per (EP, persona) for dedup
- **Optional: `entrypoints.json`** if resuming from a prior session (looked up inside the UI repo directory)

## Outputs

- **Functional graph** updated with per-persona payloads (idempotent merge by name)
- **`entrypoints.json`** — full inventory + per-(EP, persona) checkpoint
- **Per-(EP, persona) payload files**: `<uiRepo>/ui_ep{NN}_{persona}_{slug}.json` (audit + replay)

---

# PHASES

## Bootstrap (run ONCE at skill start)

1. Resolve `projectUuid` per the **## Project** section above (defers to `CLAUDE.md`). Cache it.
2. **Resolve URLs** from `breeze.config.json` (plugin root), overridable per-project via `.breeze.json`:
   - `apiBase` — Breeze backend host (e.g. `https://isometric-backend.accionbreeze.com`)
   - `uiBaseUrl` — Breeze UI host (e.g. `https://app.accionbreeze.com`)

   See `/breeze:setup-project` → "URL resolution" for the canonical rule. Throughout this skill, `<apiBase>` and `<uiBaseUrl>` are placeholders the parent substitutes at runtime — never hardcode literal hosts.

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

---

## Phase 0 — Discover entry points

If `entrypoints.json` already exists in the UI repo directory:
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
2. Record the detected framework and router file path

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

### Sub-step 0.3 — Discover routes

1. Optionally `Code_Graph_Search` to locate the routes definition
2. Also query for sidebar/navbar structure to surface panel triggers
3. `Read` the router file locally
4. `Read` the sidebar/navbar component for non-routed features

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

1. Write the full inventory to disk with this schema (note the per-EP `personas[]` field):

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

## Step 1 — Dedup pre-query

```
Functional_Graph_Search(
  uuid  = projectUuid,
  query = f"{persona} {ep.title} {likely outcome name}",
  limit = 10
)
```

Group results into `EXISTING_NEIGHBORHOOD`:
```json
{
  "outcomes": [
    { "name": "<outcome>", "id": "...", "score": 0.78,
      "scenarios": [{ "name": "<scenario>", "id": "...", "score": 0.83 }] }
  ]
}
```

If empty, pass `{"outcomes": []}` — sub-agent will proceed fresh.

## Step 2 — Pre-compute OUTPUT_PATH and render the sub-agent prompt

**Pre-compute the output path** before spawning. The sub-agent writes its `{payload, audit}` JSON here; the parent reads from here for validators and upsert. This is how the parent avoids holding the full payload in its context:

```
OUTPUT_PATH = f"{uiRepo}/ui_ep{ep.id:02d}_{persona}_{slug}.json"
```

where `slug` is a kebab-cased form of `ep.title` (e.g. `code-ontology-list`).

Then load `references/flow-structuring-agent.prompt.md` and substitute the `{{...}}` placeholders:

| Placeholder | Value |
|---|---|
| `{{persona}}` | the persona for this run |
| `{{route}}` | `ep.route` |
| `{{kind}}` | `ep.type` (`route` / `panel` / `route-variant` / `backend-endpoint`) |
| `{{title}}` | `ep.title` |
| `{{seed_file_absolute_path}}` | absolute path to `ep.component` |
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
| `{{existing_neighborhood_json}}` | `json.dumps(EXISTING_NEIGHBORHOOD)` |

## Step 3 — Spawn sub-agent

```
Agent(
  subagent_type = "breeze:flow-structuring-agent",
  description   = f"Flow-structure EP {ep.id} ({persona}): {ep.title}",
  prompt        = <rendered per-call inputs from Step 2>
)
```

The agent's full methodology (phases, rules, schema, self-check) lives
in `agents/flow-structuring-agent.md` — installed by the breezeai-plugins
plugin. The `prompt` argument here is **only** the short variable input
block from Step 2; the agent's system prompt does the rest.

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

For 2-3 unique scenario descriptions from the upserted payload, call:
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
  "payloadPath":     "<uiRepo>/ui_ep12_Admin_project-settings.json",
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
- Up to 3 sub-agents in flight at once
- Group by EP — finish all personas of EP N before starting EP N+1 (so the EP's `remaining[]` entry is cleared atomically)

## Multi-session resume

When context budget hits ~75%, flush the current EP's checkpoint and stop.
Recommend the user resume with:
```
/breeze:generate-functional-from-ui continue from entrypoints.json in repo <uiRepo>
```

## Failure recovery

`entrypoints.failed[]` holds per-(EP, persona) failures with reasons mapped to the agent's summary-line prefixes (`FAIL_VALIDATE`, `FAIL_WRITE`, `FAIL_UPSERT`). For each:

- **`FAIL_UPSERT` only** — the payload is sound but the POST failed. Re-curl the same OUTPUT_PATH directly via `<API_BASE>/functional-graph/upsert` with `api-key:` header. No re-spawn needed.
- **`FAIL_VALIDATE` / `FAIL_WRITE`** — re-spawn the sub-agent with the same input block; the agent will regenerate from scratch. If the same failure repeats, inspect the OUTPUT_PATH on disk to understand the defect class, then patch the agent prompt.
- **Recovery loop**: clear matching entries from `failed[]`, re-add `(epId, persona)` to `remaining[]` (or pass explicitly via continue prompt), resume the skill.

## See also

- `/breeze:generate-functional-from-backend` — System / External System persona pass
- `/breeze:validate-functional-graph` — post-generation quality checks
- `/breeze:generate-spec` — export the graph as a spec document
