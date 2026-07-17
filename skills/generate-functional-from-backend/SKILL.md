---
name: generate-functional-from-backend
description: >
  Generate the System / External System half of the functional graph from a
  backend repo (REST routes, GraphQL operations, queue / event / cron handlers)
  using a rooted per-entry-point sub-agent depth pass. The parent discovers
  entry points; an installed agent (breeze:backend-flow-structuring-agent)
  processes ONE EP per run — reads the handler + every injected service,
  enumerates DTO / enum / validation fields, runs a branch & error-path audit,
  traces side effects, self-validates (schema / rule-a / chain / persona /
  citations / coverage / polymorphic split), writes the payload to disk, and
  POSTs directly to /functional-graph/v2/upsert with an api-key header (no MCP
  argument-size clipping). Use when: generate functional from backend, backend
  to functional, backend functional pass.
argument-hint: "[repo-path]"
---

> ### ⚠️ Is this the right functional-generation skill?
> | Repo shape | Use |
> |---|---|
> | SPA frontend (React / Vue / Angular / Next) | `/breeze:generate-functional-from-ui` |
> | **◀ Headless backend API — REST / GraphQL / queue (incl. ASP.NET Core, Node, Java, Python) — THIS SKILL** | `/breeze:generate-functional-from-backend` |
> | ASP.NET **Web Forms** monolith (`.aspx`/`.ascx` + in-process backend, one repo) | `/breeze:generate-functional-from-aspnet-webforms` (single unified pass) |
> | ASP.NET **MVC / Razor Pages** full-stack (Razor views + controllers, one repo) | run **BOTH** `-from-ui` (views) **and** this skill (controllers) — they join by the action-route URL *(no unified skill yet)* |
> | Vert.x metadata-driven (MAPL / MSCR) | `/breeze:generate-functional-from-metadata` |
>
> This skill produces the **System / External System** half. For a headless API (like a .NET Core GraphQL/REST service) that's the whole graph from this repo; the **human** half comes from the consuming frontend's `-from-ui` run, joined by URL/operation. **Web Forms is the exception** — its in-process seam has no URL, so it uses the single unified `-from-aspnet-webforms` skill instead of this + `-from-ui`.

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

## What this skill does

Transforms a backend repo into the **System / External System** half of the
functional graph (Persona > Outcome > Scenario > Step > Action), with API calls
captured structurally in `action.apis[]`.

```
generate-functional-from-ui   -> User-persona scenarios
generate-functional-from-backend -> System-persona scenarios   (this skill)
```

The two passes are fully independent — they share the functional graph as the
only common surface (idempotent merge by outcome name).

**Architecture (delegated discovery + rooted per-EP sub-agents):** the parent
(this skill) only orchestrates and runs the user-facing gates. **Discovery** is
delegated to a single `breeze:backend-entrypoint-discovery-agent` that inventories
the repo and writes `entrypoints.json`. The deep **per-EP work** — reading the
handler, drilling into injected services, enumerating fields, tracing side
effects, building + self-validating the payload, and upserting — runs inside
`breeze:backend-flow-structuring-agent`, **one sub-agent per entry point, in
parallel batches of up to 3**. The parent never holds a payload or the raw file
inventory in context; it reads a single summary line back from each sub-agent.

| Concern | Old inline pass | This skill |
|---|---|---|
| Discovery (Phase 0) | Parent reads every controller/resolver/consumer inline — eats the parent's context on large repos | **Installed agent `breeze:backend-entrypoint-discovery-agent`** invoked once; it does all the file reading and writes `entrypoints.json`, returning only a compact summary line |
| Per-EP depth | Inline parent-agent reasoning | **Installed agent `breeze:backend-flow-structuring-agent`** invoked per EP; tool-scoped, model-pinned (sonnet), system prompt cached across calls |
| Throughput | Serial, one EP at a time | **Parallel batches** — up to 3 per-EP sub-agents in flight per message |
| Field / enum enumeration | Step 5 suggestion | **Mandatory Phase 2 inside the sub-agent** (DTO / args / message-shape fields + full enum sets) |
| Branch & error paths | Implicit | **Mandatory Phase 2.5** — error/rejection branches, guard / transaction / idempotency / retry constraints captured |
| Side-effect coverage | Step 6.5 parent validator | **Self-validated inside the sub-agent** (Phase 6) with in-place repair |
| Output validation | Parent runs Rule A / Rule B / coverage | **Self-validation inside the sub-agent** (Phase 6: schema / rule-a / chain / persona / citations / coverage / polymorphic) — parent runs NO validators |
| Upsert | MCP `bulk_update_functional_nodes` (arg-size limit clips large payloads) | **Sub-agent POSTs directly** to `/functional-graph/v2/upsert` with `api-key:` header via `curl --data-binary @file` — payload never crosses a tool-call argument, so it is never truncated |
| Citations | File paths | `<repo_name>/<relative path>` enforced; backend paths only |

## Resources

- **Installed discovery agent** — `agents/backend-entrypoint-discovery-agent.md` (plugin root). Invokable as `subagent_type: "breeze:backend-entrypoint-discovery-agent"`. Inventories all entry points once and writes `entrypoints.json`; returns a compact summary line.
- `references/backend-entrypoint-discovery-agent.prompt.md` — per-call input renderer for the discovery agent.
- **Installed per-EP agent** — `agents/backend-flow-structuring-agent.md` (plugin root). Invokable as `subagent_type: "breeze:backend-flow-structuring-agent"`. Its full methodology — phases, rules, schema, self-check, self-validate, write-to-disk, upsert — lives in its system prompt.
- `references/backend-flow-structuring-agent.prompt.md` — short **per-call input renderer** with `{{...}}` placeholders. The parent substitutes and passes the rendered text as the `prompt` argument.
- `references/rules.md` — backend functional graph semantics (framework detection, route/GraphQL/queue discovery recipes, persona mechanical mapping, `apis[]` type reference, pitfalls). Carried over and also embedded in the agent's system prompt.
- Schema + word lists live in the **single source of truth** `../shared/functional/{upsert.schema.json, verbs.json}` (ADR 0001) — JSON-schema for the `/functional-graph/v2/upsert` payload; reference only, the agent self-validates.
- `validators/validate.py` — a thin **shim** that delegates to `../shared/functional/validate.py` (the one validator engine), injecting `--kind system` (the backend pass writes only System/External). Subcommands unchanged: `schema | rule-a | persona | citations | coverage`. **Invoked by the sub-agent in Phase 6** as a hard gate before write/upsert (the skill passes its absolute directory in as `VALIDATORS_PATH`). Falls back to prose-only checks if the script or its `jsonschema` dependency is unavailable (exit 3). Also runnable standalone for manual inspection of `be_ep{NN}_{name}.json` files.
- `validators/requirements.txt` — Python dependency: `jsonschema`

## Inputs

- **Backend repo path** — argument (`$ARGUMENTS`) or resolved in Phase -1
- **`.breeze.json`** — for `projectUuid`, `targetRepos.backend`, `apiKey`, and backend code-ontology id
- **Existing functional graph** — queried per EP for dedup AND cross-pass merge reference
- **Optional: `entrypoints.json`** if resuming from a prior session (under `OUTPUT_BASE = <backendRepo>/.breeze-output/`)

## Outputs

> **All generated artifacts go under a SINGLE dedicated folder `OUTPUT_BASE = <backendRepo>/.breeze-output/`** — NEVER the repo root (that pollutes the target repo's git status). `mkdir -p` it on first write; add `.breeze-output/` to the **target repo's** `.gitignore`. `OUTPUT_BASE` (a folder) is distinct from `.breeze.json` (the config file).

- **Functional graph** updated with System / External System scenarios + actions (idempotent merge by name)
- **`OUTPUT_BASE/entrypoints.json`** — inventory + per-EP checkpoint
- **Per-EP payload files**: `OUTPUT_BASE/be_ep{NN}_{slug}.json` (audit + replay)

---

# PHASES

## Bootstrap (run ONCE at skill start)

1. Read `.breeze.json` from the plugin working directory.
2. If missing or incomplete → tell the user to run `/breeze:project setup`.
3. Extract `projectUuid`. Cache it.
4. **Resolve URLs** from `breeze.config.json` (plugin root), overridable per-project via `.breeze.json`:
   - `apiBase` — Breeze backend host (e.g. `https://isometric-backend.accionbreeze.com`)
   - `uiBaseUrl` — Breeze UI host (e.g. `https://ai.accionbreeze.com`)

   See `CLAUDE.md` → "Service URLs" for the canonical rule. Throughout this skill, `<apiBase>` and `<uiBaseUrl>` are placeholders the parent substitutes at runtime — never hardcode literal hosts.

5. **Resolve `apiKey`** (required — the sub-agent POSTs the upsert directly):
   - Check `.breeze.json` for `apiKey`. If present → cache and continue.
   - If missing, prompt the user with this exact wording (mirrors `/breeze:onboard-repository` → Step 1 convention):

     > This skill upserts via REST directly (avoids MCP argument-size limits that clip large backend payloads). It needs a Breeze API key.
     >
     > Generate one at: `<uiBaseUrl>/mcp/generate/key`
     > Then paste it back here. I'll save it to `.breeze.json` for future runs.
     > (Make sure `.breeze.json` is in your `.gitignore`.)

   - Save the pasted key to `.breeze.json` under `apiKey`. Do NOT echo the key back; respond only with "API key saved." Continue.

   **Security:** Never print the key in output, logs, or commits. `.breeze.json` must be in `.gitignore`. The parent passes the key into the sub-agent's input block — both the parent and the agent must avoid echoing it.

6. Call `Call_Get_Project_Details_` with `uuid=<projectUuid>` once; cache the returned `name` — passed to the sub-agent as `PROJECT_NAME` and used in its upsert body.
7. **Resolve the backend repo's `codeOntologyId`** (required for the sub-agent's `Code_Graph_Search` scoping):
   - Check `.breeze.json` → `targetRepos.backendCodeOntologyId`. If present and `targetRepos.backendRepoName` is also present → cache both and continue.
   - Otherwise call `Call_List_Repositories_(projectUuid=<projectUuid>)`. The response has `data: [{ _id, name, fileCount, ... }]`.
   - Confirm at least one indexed repo exists with `fileCount > 0` and `status: "active"`. If none → stop and tell the user to run `/breeze:onboard-repository` first.
   - **Match the indexed repo to the on-disk backend repo.** Strategy:
     1. Compare normalized basenames: lowercase + strip `.`/`-`/`_` from both `targetRepos.backend`'s basename and each indexed `name`. Pick the first match.
     2. If no normalized match and only ONE indexed repo exists, use it (sole-repo fast path).
     3. If multiple repos exist with no clear match, ask the user once: "Which indexed repo corresponds to `<basename>`?" with the indexed repo names as options.
   - Save `targetRepos.backendCodeOntologyId = <_id>` and `targetRepos.backendRepoName = <name>` to `.breeze.json` for future runs.
   - Cache both for the per-EP loop. The sub-agent receives them as `CODE_ONTOLOGY_ID` and `INDEXED_REPO_NAME`.

---

## Phase -1 — Resolve the target backend repo

1. Check `$ARGUMENTS` — validate it exists and looks like a backend repo.
2. Check `.breeze.json` field `targetRepos.backend`.
3. Check if cwd looks like a backend repo.
4. Ask the user — single prompt: "Which backend repo do you want me to read? Provide an absolute path."
5. Persist the chosen path to `.breeze.json` under `targetRepos.backend`.
6. If the path looks like a frontend repo, stop and suggest `/breeze:generate-functional-from-ui`.

Then set **`OUTPUT_BASE = f"{backendRepo}/.breeze-output"`** and `mkdir -p` it — every artifact (`entrypoints.json` + per-EP payloads) goes under `OUTPUT_BASE`, never the repo root. Ensure `.breeze-output/` is in the target repo's `.gitignore` (append if missing; do not touch the plugin's).

> **Rules:** see [rules.md](references/rules.md) → "Backend repo detection"

---

## Phase 0 — Discover entry points (delegated to the discovery sub-agent)

If `OUTPUT_BASE/entrypoints.json` already exists, read it and skip to the per-EP loop (resuming). Do not overwrite. *(Also check the legacy repo-root path once for back-compat; if found there, move it into `OUTPUT_BASE`.)*

Otherwise the parent spawns ONE discovery sub-agent to inventory the repo, then handles only the two user-facing gates. The token-heavy file reading happens inside the sub-agent — the parent never globs/reads controllers itself.

### Step 0.1 — Gather inputs

- `OUTPUT_PATH = f"{OUTPUT_BASE}/entrypoints.json"` (`OUTPUT_BASE = {backendRepo}/.breeze-output`).
- Load existing personas: `Get_all_personas(projectUuid)` → keep the name list for `EXISTING_PERSONAS`.
- A `framework_hint` is optional — pass `null` and let the agent detect it, or a quick guess from `package.json`/`pom.xml` if you already know it.

### Step 0.2 — Spawn the discovery sub-agent

Render `references/backend-entrypoint-discovery-agent.prompt.md`, substituting:

| Placeholder | Value |
|---|---|
| `{{repo_name}}` | `backendRepoName` (indexed name; fallback to the on-disk basename) |
| `{{repo_root_absolute_path}}` | absolute path to the backend repo |
| `{{framework_hint}}` | optional framework guess, or `null` |
| `{{project_uuid}}` | `projectUuid` |
| `{{project_name}}` | project name cached in Bootstrap step 6 |
| `{{code_ontology_id}}` | `backendCodeOntologyId` |
| `{{indexed_repo_name}}` | `backendRepoName` |
| `{{output_path}}` | the `OUTPUT_PATH` above |
| `{{existing_personas_json}}` | `json.dumps(["System", ...])` from Step 0.1 |

```
Agent(
  subagent_type = "breeze:backend-entrypoint-discovery-agent",
  description   = "Discover backend entry points",
  prompt        = <rendered inputs>
)
```

The agent writes `entrypoints.json` and returns ONE line:
```
OK · framework: <name> · rest: <N> · graphql: <N> · queue: <N> · orphans: <N> · total: <N> · graphqlNeedsConfirm: <true|false> · path: <OUTPUT_PATH>
```
Failure prefixes: `FAIL_WRITE`, `FAIL_DISCOVERY` (no recognizable backend surface — stop and report; suggest `/breeze:generate-functional-from-ui` if it's actually a frontend repo).

### Step 0.3 — GraphQL confirmation gate ⛔ (parent-side; only if `graphqlNeedsConfirm: true`)

The agent has NOT added GraphQL EPs to `remaining[]` — they sit at `status: "needs_confirmation"`. Read `graphqlOperations[]` + `graphqlGranularity` from `entrypoints.json`, present the list and the agent's chosen granularity to the user, and let them confirm or adjust (`per-operation` / `per-resolver-class` / `per-type-field`). On confirmation, edit `entrypoints.json`: flip those EPs to `status: "pending"` and add their ids to `remaining[]`. (If the granularity changes, the agent's per-operation rows may need regrouping — re-spawn the discovery agent with the chosen granularity passed as `framework_hint` context, or adjust the rows directly for small schemas.) This remains a HARD GATE — no GraphQL EP enters the loop unconfirmed.

> **Rules:** see [rules.md](references/rules.md) → "GraphQL EP granularity rules"

### Step 0.4 — Exclusion gate (parent-side)

Read the `entryPoints[]` summary (group by `category` and `type`) from `entrypoints.json`, present it to the user, and ask if any EPs or categories should be excluded. Remove excluded ids from `remaining[]` (leave the records in `entryPoints[]` for the audit trail). Then proceed to the per-EP loop.

> The full `entrypoints.json` schema is documented in `agents/backend-entrypoint-discovery-agent.md` (Phase 6). Each EP carries a mechanical `persona` field used by the per-EP loop.

---

# PER-EP LOOP (parallel batches of per-EP sub-agents)

EPs are independent — each is its own upsert — so process `remaining[]` in **batches of up to 3**. For each batch:

1. Run **Step 2** (render prompt) for every EP in the batch — cheap parent-side string substitution (dedup is agent-side now).
2. **Spawn the whole batch concurrently** — emit all 3 `Agent(...)` calls in a SINGLE message (Step 3). They run in parallel; the Agent tool supports concurrent sub-agents.
3. As each returns, run **Step 4** (verify) and **Step 5** (checkpoint) for that EP.
4. Only start the next batch once the current batch's sub-agents have all returned (so `remaining[]` mutates atomically per batch and a mid-run stop leaves a clean checkpoint).

Tune the batch size down to 1 if you are near your context budget or hitting rate limits. The steps below describe the procedure for a single EP; apply them across the batch.

## Step 1 — (removed) dedup is now agent-side

The parent no longer runs a dedup pre-query and does **not** pass `EXISTING_NEIGHBORHOOD`. The sub-agent builds its own dedup context from the **live** graph (`Functional_Graph_Search` + a persona-scoped `Get_all_personas`→`Get_all_outcomes_for_a_persona_id`→`Get_all_scenarios_for_a_outcome_id` read-back) right before writing — fresher and race-safe under parallel batches. Proceed to Step 2.

## Step 2 — Pre-compute OUTPUT_PATH and render the sub-agent prompt

**Pre-compute the output path** before spawning. The sub-agent writes its `{payload, audit}` JSON here; the parent never holds the payload in context:

```
OUTPUT_PATH = f"{OUTPUT_BASE}/be_ep{ep.id:02d}_{slug}.json"   # OUTPUT_BASE = {backendRepo}/.breeze-output
```
where `slug` is a kebab-cased form of `ep.title` (e.g. `post-projects-export-email-xls`).

Load `references/backend-flow-structuring-agent.prompt.md` and substitute the `{{...}}` placeholders:

| Placeholder | Value |
|---|---|
| `{{persona}}` | `ep.persona` (mechanical: System / External System) |
| `{{kind}}` | `ep.type` (`REST` / `GraphQL` / `Queue`) |
| `{{http_method}}` | `ep.httpMethod` or `null` |
| `{{url}}` | `ep.absoluteUrl` or `null` |
| `{{operation}}` | `ep.operation` or `null` (GraphQL) |
| `{{graphql_kind}}` | `ep.kind` for GraphQL (`Query`/`Mutation`/`Subscription`) or `null` |
| `{{transport}}` | `ep.transport` or `null` (Queue) |
| `{{queue_name}}` | `ep.queueName` (resolved literal) or `null` |
| `{{title}}` | `ep.title` |
| `{{sub_type}}` | `ep.subType` or `null` |
| `{{seed_file_absolute_path}}` | absolute path to `ep.file` |
| `{{seed_line}}` | `ep.line` or `null` |
| `{{repo_name}}` | `backendRepoName` (the **indexed** repo name resolved in Bootstrap step 7) — so citation prefixes match how the code graph indexed the files and resolve in the Breeze UI. Fall back to the basename of the backend repo path only if `backendRepoName` is unresolved. |
| `{{repo_root_absolute_path}}` | absolute path to the backend repo (used only to strip into relative paths) |
| `{{project_uuid}}` | `projectUuid` from `.breeze.json` |
| `{{project_name}}` | project name cached in Bootstrap step 6 |
| `{{llm_platform}}` | `"AWSBEDROCK"` |
| `{{output_path}}` | the pre-computed `OUTPUT_PATH` above |
| `{{api_base}}` | `apiBase` from Bootstrap step 4 |
| `{{api_key}}` | `apiKey` from `.breeze.json` (NEVER echo, NEVER log) |
| `{{code_ontology_id}}` | `backendCodeOntologyId` resolved in Bootstrap step 7 |
| `{{indexed_repo_name}}` | `backendRepoName` resolved in Bootstrap step 7 |
| `{{shared_functional_path}}` | absolute path to the **shared functional SSOT** dir — `<pluginRoot>/skills/shared/functional` (sibling of this skill, i.e. `<this skill dir>/../shared/functional`). The agent reads `core.md` + `system-overlay.md` from here for the canonical rules (ADR 0001). Mirrors the UI pass's `{{shared_functional_path}}`. |
| `{{validators_path}}` | absolute path to **this skill's `validators/` directory** (e.g. `<pluginRoot>/skills/generate-functional-from-backend/validators`). The agent runs `validate.py` from here in Phase 6. |


## Step 3 — Spawn the batch (concurrently)

Emit one `Agent(...)` call per EP in the batch, **all in a single message** so they run in parallel:

```
# up to 3 in one message
Agent(
  subagent_type = "breeze:backend-flow-structuring-agent",
  description   = f"Flow-structure EP {ep.id} ({ep.persona}): {ep.title}",
  prompt        = <rendered per-call inputs from Step 2 for ep>
)
Agent( ... next ep in batch ... )
Agent( ... next ep in batch ... )
```

The agent's full methodology lives in `agents/backend-flow-structuring-agent.md`. The `prompt` argument is ONLY the short variable input block from Step 2; the agent's system prompt does the rest. Tool scoping (Read, Glob, Grep, Bash, `Code_Graph_Search`, `Get_Code_Nodes_By_Label`), `model: sonnet`, and `maxTurns` are enforced by the agent definition. Anthropic prompt caching reuses the fixed system prompt across calls, so subsequent EPs pay only for the small variable input block.

**Sub-agent returns ONLY a short summary line.** It self-validates (Phase 6), writes to OUTPUT_PATH (Phase 7), POSTs the upsert (Phase 8), and reports HTTP status + functionalId:

```
# Success:
OK · outcomes: <N> · scenarios: <N> · steps: <N> · actions: <N> · apis: <N> · sideEffects: <N> · cgs: <N> · http: 200 · functionalId: <id> · path: <OUTPUT_PATH>

# Phase 6 (self-validate) failure — agent could not repair after 2 passes:
FAIL_VALIDATE · errors: <count> · last_check: <schema|rule-a|chain|persona|citations|coverage|polymorphic> · path: <OUTPUT_PATH>

# Phase 7 (write) failure:
FAIL_WRITE · could not write to <OUTPUT_PATH> · <reason>

# Phase 8 (upsert) failure:
FAIL_UPSERT · http: <status> · path: <OUTPUT_PATH> · note: <response excerpt>
```

Parse the summary; confirm `path` matches the OUTPUT_PATH you passed in. Branch on the prefix:

| Prefix | Action |
|---|---|
| `OK · ` | Continue to Step 4 (verify) and Step 5 (checkpoint) |
| `FAIL_VALIDATE` | Record in `entrypoints.failed[]` with `reason: "self-validation"`. Inspect the OUTPUT_PATH file if details are needed. Continue. |
| `FAIL_WRITE` | Record in `entrypoints.failed[]` with `reason: "write"`. Continue. |
| `FAIL_UPSERT` | Record in `entrypoints.failed[]` with `reason: "upsert"` and the HTTP status. The OUTPUT_PATH file IS the replay artifact — re-upserting later is a single curl. Continue. |

**The parent never runs validators and never POSTs. The agent owns both — that is the contract.**

## Step 4 — Verify (post-upsert sanity check)

For 2-3 unique scenario descriptions from the upserted payload, call:
```
Functional_Graph_Search(uuid=projectUuid, query=<first 80 chars of description>, limit=3)
```
Confirm `score > 0.4` and the `scenarioId` resolves. If the EP merged into an outcome with existing User scenarios, confirm both persona types now appear. Record verification scores in the checkpoint.

## Step 5 — Update checkpoint

Mark `ep.status` → `done`, pop `ep.id` from `remaining[]`, and append to `entrypoints.completed[]`:
```json
{
  "epId": 4,
  "type": "Queue",
  "persona": "System",
  "title": "SQS project-export-jobs consumer",
  "outcomeName": "Track Construction Project Pipeline",
  "scenariosCreated": 2,
  "actionsCreated": 11,
  "apiCallsLogged": 3,
  "fieldsEnumerated": 6,
  "sideEffectsLogged": 5,
  "codeGraphSearchCount": 2,
  "verificationScores": { "process export job": 0.71 },
  "payloadPath": "<backendRepo>/.breeze-output/be_ep04_sqs-project-export-jobs-consumer.json",
  "completedAt": "<ISO>"
}
```
Edit (do not rewrite) `entrypoints.json` — only `status`, `completed[]`, `failed[]`, `remaining[]` mutate.

---

# REFERENCE

## Per-EP cost

- Small EP (single handler, ≤200 lines + 1-2 services): ~30k tokens, ~60s wall-clock
- Medium EP (~500 lines, several injected services): ~70k tokens, ~120s
- Large EP (fat controller / dispatcher consumer): ~150k+ tokens, ~180s+

Plan multi-session for >20 EPs.

## Parallelism

The per-EP loop runs in **batches of up to 3** concurrent sub-agents (see the loop preamble). EPs are independent — each is its own upsert — so batching is safe; the only constraint is to finish a batch (all sub-agents returned, checkpoints written) before starting the next, so a mid-run stop leaves `remaining[]` consistent. Drop the batch size to 1 near your context budget or under rate limits. Discovery (Phase 0) is a separate single sub-agent that runs once before the loop.

> ⚠️ **Parallel-dedup race.** Each sub-agent reads the live graph for dedup *before* siblings write, so concurrent siblings can mint slightly-different names for the same Outcome. With Outcome-only inline dedup (shared `core.md` §2) that is the only exposure; it is resolved by the mandatory reconciliation pass below (or by serializing EPs known to share an Outcome).

## Reconciliation pass ⛔ (mandatory finalization — after ALL EPs complete)

Per shared `core.md` §2, below-outcome nodes are emitted coverage-first and Outcome names may diverge under parallelism. The parallel race collides **only at the Outcome** (siblings share it by name); everything below an Outcome came from a *different* EP/persona and is distinct coverage, not a duplicate. So this pass is **Outcome-level only**:
1. List all Outcomes (`Get_all_personas` → `Get_all_outcomes_for_a_persona_id`) and merge same-capability Outcomes to one canonical name via `Merge_Functional_Nodes` (System / External System scope; never across personas).
2. **Never merge distinct capabilities** — remove duplicates, not coverage.
3. Record merges under `reconciliation` in the checkpoint.

**Do NOT merge below the Outcome level.** Scenario / Step / Action are coverage-first — merging near-duplicate scenarios (which came from different EPs) risks silently dropping distinct flows for no join benefit.

## Multi-session resume

When context budget hits ~75%, flush the current checkpoint and stop. Resume with:
```
/breeze:generate-functional-from-backend continue from entrypoints.json in repo <backendRepo>
```

## Failure recovery

`entrypoints.failed[]` holds per-EP failures mapped to the agent's summary-line prefixes (`FAIL_VALIDATE`, `FAIL_WRITE`, `FAIL_UPSERT`). For each:

- **`FAIL_UPSERT` only** — the payload is sound but the POST failed. Re-curl the same OUTPUT_PATH directly via `<apiBase>/functional-graph/v2/upsert?embedding=true&llmPlatform=<LLM_PLATFORM>` with the `api-key:` header. No re-spawn needed.
- **`FAIL_VALIDATE` / `FAIL_WRITE`** — re-spawn the sub-agent with the same input block. If the same failure repeats, inspect the OUTPUT_PATH on disk to understand the defect class, then patch the agent prompt.
- **Recovery loop**: clear matching entries from `failed[]`, re-add `epId` to `remaining[]`, resume the skill.

## When NOT to use

- **Frontend-only repos** — use `/breeze:generate-functional-from-ui`

## See also

- `/breeze:generate-functional-from-ui` — the frontend half (User-persona pass)
- `/breeze:validate-functional-graph` — quality checks after generation
- `/breeze:generate-spec` — export the graph as a spec doc
