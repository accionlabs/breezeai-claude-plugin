---
name: generate-functional-from-metadata
description: >
  Generate the full functional graph (Persona → Outcome → Scenario → Step →
  Action → apis[]) from a Vert.x metadata-driven codebase (the kind where
  features are declared in MAPL/MSCR/MFID/MFLT/CRUD JSON, not imperative code).
  One run at the tree root discovers every application by parsing MAPL records,
  then a rooted per-application sub-agent reads each app's MAPL + referenced
  screens/filters/Java, enumerates 100% of declared fields (financial-grade
  coverage gate), and emits TWO linked subtrees — a Human-persona half (from
  ShowScreen steps) and a System/External-persona half (from DoFilter/WriteData
  steps) joined by a shared Outcome name (the app id is the deterministic
  UI↔backend link). Checkpoints to applications.json for safe resume. Use when:
  generate functional from a Vert.x webapp-engine, MAPL/MSCR metadata-driven
  metadata app, "generate functional from this metadata-driven codebase".
argument-hint: "[root-path]"
---

> ### ⚠️ Is this the right functional-generation skill?
> | Repo shape | Use |
> |---|---|
> | SPA frontend (React / Vue / Angular / Next) | `/breeze:generate-functional-from-ui` |
> | Headless backend API — REST / GraphQL / queue (incl. **ASP.NET Core**, Node, Java, Python) | `/breeze:generate-functional-from-backend` |
> | ASP.NET **Web Forms** monolith (`.aspx`/`.ascx` + in-process backend, one repo) | `/breeze:generate-functional-from-aspnet-webforms` (single unified pass) |
> | ASP.NET **MVC / Razor Pages** full-stack (Razor views + controllers, one repo) | run **BOTH** `-from-ui` (views) **and** `-from-backend` (controllers) — join by the action-route URL *(no unified skill yet)* |
> | **◀ Vert.x metadata-driven app (MAPL / MSCR / MFID JSON) — THIS SKILL** | `/breeze:generate-functional-from-metadata` |
>
> This skill is ONLY for **Vert.x metadata-driven** codebases (features declared in MAPL/MSCR/MFID/MFLT/CRUD JSON). If the repo is imperative code (any of the rows above), stop and use that row.

## Project

Project-bound — needs a `projectUuid`. Resolve per `CLAUDE.md` at the plugin root: a
`--project <name|uuid>` flag, a bare UUID, or a project hint in the prompt → otherwise the
`projectUuid` in `.breeze.json`. If none resolves, list projects via `Call_List_Project_` and ask
the user to pick (or run `/breeze:project setup`). Announce the active project on line 1:
`Project: <name> (<uuid>)`. Breeze MCP 401 handling is in `CLAUDE.md` (`/breeze:project auth`).

> **API key:** required — the per-app sub-agent POSTs upserts directly. Collected on-demand below.

## What this skill does

Features are declared in JSON metadata interpreted by a shared `webapp-engine`; the functional
flow is already written down in a `MAPL` record. So this skill **parses metadata** instead of
inferring from code — far higher fidelity, and the app id deterministically links the human and
system halves. See `references/rules.md` for the full record-type → functional mapping.

```
generate-functional-from-ui        → React/Vue/Angular route apps  (NOT this codebase)
generate-functional-from-backend   → REST/GraphQL/queue backends    (NOT this codebase)
generate-functional-from-metadata        → MAPL metadata apps             (this skill)
```

**Architecture (delegated discovery + rooted per-app sub-agents):** the parent only orchestrates
and runs the persona gate. **Discovery** is delegated to `breeze:metadata-application-discovery-agent`
(invoked ONCE; writes `applications.json`). The deep **per-app work** — reading the MAPL +
screens/filters/Java, enumerating fields, building + self-validating the two halves, and upserting
— runs inside `breeze:metadata-flow-structuring-agent`, **one sub-agent per application, in parallel
batches of up to 3**. The parent never holds a payload or raw file content; it reads one summary
line per sub-agent.

## Resources

- **Discovery agent** `agents/metadata-application-discovery-agent.md` → `breeze:metadata-application-discovery-agent`. Inventories all apps once.
- `references/metadata-application-discovery-agent.prompt.md` — discovery input renderer.
- **Per-app agent** `agents/metadata-flow-structuring-agent.md` → `breeze:metadata-flow-structuring-agent`. Per-app depth, dual subtree, field-coverage gate, dual upsert.
- `references/metadata-flow-structuring-agent.prompt.md` — per-app input renderer.
- `references/rules.md` — metadata record types, MAPLQ verb mapping, apis[] typing, persona rules, field-capture gate.
- Schema + word lists live in the **single source of truth** `../shared/functional/{upsert.schema.json, verbs.json}` (ADR 0001). Persona = any string, one persona per payload.
- `validators/validate.py` — a thin **shim** that delegates to `../shared/functional/validate.py` (the one validator engine). Subcommands unchanged: `schema | rule-a | forbidden | persona --kind | citations --repo-name | field-coverage | citation-completeness | atomicity`. The sub-agent runs these in Phase 6; `field-coverage` is the 100%-field hard gate. `atomicity` is ADVISORY (human half only, skips System personas) — warns on clubbed input actions / input actions carrying apis[] / editable fields without a dedicated action; never blocks. (`rule-a`/`coverage` auto-detect human vs system from the half's single persona; the shim adds no static `--kind`.)
- `validators/requirements.txt` — `jsonschema`.

## Inputs / Outputs

- **Input:** metadata tree root (argument or `.breeze.json` `targetRepos.metadataRoot`), `.breeze.json` (`projectUuid`, `apiKey`).
- **Output:** functional graph updated (human + System halves, idempotent merge by name).
  All generated artifacts go to a SINGLE dedicated output base **`{metadataRoot}/.breeze-metadata-output/`**
  — NEVER inside the individual source repos (that pollutes ~340 module folders / their git
  status). Layout:
  - `{metadataRoot}/.breeze-metadata-output/applications.json` — inventory + resume checkpoint.
  - `{metadataRoot}/.breeze-metadata-output/{repo_name}/metadata_app{APP_ID}_{persona}.json` — per-app payload
    files (audit + replay), under a subfolder mirroring the source repo's name.

  Add `.breeze-metadata-output/` to the tree's `.gitignore` (or it lives outside any repo anyway). The
  source repos must stay clean — do NOT write `metadata_app*.json` into a module directory.

---

# PHASES

## Bootstrap (run ONCE)

1. Resolve `projectUuid` per **## Project**. Cache it. Print the `Project:` line.
2. **Resolve URLs** from `breeze.config.json` (plugin root), overridable via `.breeze.json`:
   `apiBase` (Breeze backend) and `uiBaseUrl` (Breeze UI). `<apiBase>`/`<uiBaseUrl>` are runtime placeholders — never hardcode.
3. **Resolve `apiKey`** (required): check `.breeze.json`. If missing, prompt:
   > This skill upserts via REST directly. It needs a Breeze API key.
   > Generate one at: `<uiBaseUrl>/mcp/generate/key` — paste it back; I'll save it to `.breeze.json` (keep it in `.gitignore`).

   Save under `apiKey`. Do NOT echo it; reply only "API key saved." **Never** print the key.
4. `Call_Get_Project_Details_(uuid=<projectUuid>)` once; cache `name` → passed as `PROJECT_NAME`.
5. **Upsert paths** (passed to the per-app agent): BOTH halves use v2 —
   `HUMAN_UPSERT_PATH = SYSTEM_UPSERT_PATH = /functional-graph/v2/upsert` with `embedding=true`.
   (v2 queues embeddings to the SQS worker fleet = scalable; v1 `/functional-graph/upsert` embeds
   in-process on the API node = slow. v2 puts no enum restriction on the persona name.)
   (Code-graph onboarding is OPTIONAL for metadata apps —
   the agent reads files directly; `Code_Graph_Search`/`Functional_Graph_Search` are used only as
   available. Skip `/breeze:onboard-repository` unless you want code-graph search.)

## Phase -1 — Resolve the metadata tree root

1. `$ARGUMENTS` → 2. `.breeze.json` `targetRepos.metadataRoot` → 3. cwd if it holds `**/json/MAPL(*).json`
→ 4. ask the user for the absolute path to the metadata tree root. Persist to `.breeze.json`
`targetRepos.metadataRoot`. Validate by globbing for at least one `MAPL(*)` record; if none, this is not
a metadata (Vert.x/MAPL) tree — suggest `/breeze:generate-functional-from-ui` or `-backend`.

## Phase 0 — Discover applications (delegated; ONCE)

`OUTPUT_BASE = f"{metadataRoot}/.breeze-metadata-output"` (create it; all artifacts live here, never in a
source repo). `OUTPUT_PATH = f"{OUTPUT_BASE}/applications.json"`. **If it already exists, read it
and skip to the per-app loop (resume) — do NOT re-discover.** Otherwise:

1. Load existing personas: `Get_all_personas(projectUuid)` → `EXISTING_PERSONAS`.
2. Render `references/metadata-application-discovery-agent.prompt.md` (`{{root_absolute_path}}`,
   `{{project_uuid}}`, `{{project_name}}`, `{{output_path}}`, `{{rules_path}}` = this skill's
   `references/rules.md` absolute path, `{{existing_personas_json}}`) and spawn:
   ```
   Agent(subagent_type="breeze:metadata-application-discovery-agent",
         description="Discover metadata applications", prompt=<rendered>)
   ```
3. The agent writes `applications.json` and returns ONE line
   (`OK · apps: N · flavorA … humanRawRole: N · path: …`). On `FAIL_DISCOVERY`, stop.

### Persona confirmation gate ⛔ (parent-side)

Read `personaCandidates` from `applications.json`. Present the human persona list (esp. any with
`confidence: "raw"` — unmapped role codes). Ask the user to confirm names / supply real names for
raw role codes / merge duplicates. Write confirmed names back into the relevant apps'
`personaHuman` fields in `applications.json`. System / External System need no confirmation. This is
a HARD GATE — do not enter the loop until human personas are confirmed.

---

# PER-APP LOOP (parallel batches of up to 3)

Process `remaining[]` (app ids) in **batches of up to 3**. EPs (apps) are independent — each is its
own pair of upserts. For each batch: run Step 1–2 per app (cheap, parent-side), spawn the batch
concurrently (Step 3), then Step 4–5 per app as each returns. Finish a batch before starting the
next so the checkpoint mutates atomically. Drop batch size to 1 near context budget.

## Step 1 — (removed) dedup is now agent-side

The parent no longer runs a dedup pre-query and does **not** pass `EXISTING_NEIGHBORHOOD`. The sub-agent builds its own dedup context from the **live** graph (`Functional_Graph_Search` + a persona-scoped `Get_all_personas`→`Get_all_outcomes_for_a_persona_id`→`Get_all_scenarios_for_a_outcome_id` read-back) right before writing — fresher and race-safe under parallel batches. Proceed to Step 2.

## Step 2 — Pre-compute output paths + render the prompt

```
OUTPUT_DIR         = f"{metadataRoot}/.breeze-metadata-output/{repo_name}"   # mirrors the source repo name; NOT inside the repo
OUTPUT_PATH_HUMAN  = f"{OUTPUT_DIR}/metadata_app{APP_ID}_{personaHuman_slug}.json"   # omit if personaHuman is null
OUTPUT_PATH_SYSTEM = f"{OUTPUT_DIR}/metadata_app{APP_ID}_System.json"
```
The agent's Phase 7 `mkdir -p`s the parent dir before writing, so `OUTPUT_DIR` is created on demand.
**Never** set these under `{repo_path}` — that writes into the source module and pollutes it.
Render `references/metadata-flow-structuring-agent.prompt.md`, substituting the app fields from
`applications.json` (`app_id`, `repo_name`, `repo_path`, `flavor`, `persona_human`, `persona_system`,
`mapl_path`, `steps_json`, `ajax_endpoints_json`), the Breeze coordinates (`project_uuid`,
`project_name`, `llm_platform="AWSBEDROCK"`, `api_base`, `api_key`, `human_upsert_path`,
`system_upsert_path`), the two output paths, `validators_path` (this skill's `validators/` absolute
dir), `shared_functional_path` (the shared SSOT dir `<pluginRoot>/skills/shared/functional` — the agent
reads `core.md` + `human-overlay.md` + `system-overlay.md` from here, same as the UI/backend passes),
and `rules_path` (this skill's `references/rules.md` absolute path = the metadata MAPL overlay). (No `existing_neighborhood_json` — the agent self-dedups against the live graph.)

## Step 3 — Spawn the batch (concurrently)

Emit up to 3 `Agent(subagent_type="breeze:metadata-flow-structuring-agent", …)` calls in ONE message.
Each self-validates (incl. `field-coverage`==1.0), writes both halves to disk, POSTs both upserts,
and returns ONE summary line:
```
OK · app: <id> · human: <http|skipped> · system: <http> · outcomes: 1 · scenarios: N · steps: N · actions: N · apis: N · fields: <declared>/<referenced> · cgs: N · pathH: … · pathS: …
```
Branch on prefix: `OK ·` → Step 4/5. `FAIL_VALIDATE` / `FAIL_WRITE` / `FAIL_UPSERT` → record in
`applications.failed[]` with the reason; the OUTPUT_PATH file is the replay artifact; continue.
**`fields: N/N` must be equal — that is the 100%-capture proof.** If a sub-agent reports
`fields: 10/9`, treat as `FAIL_VALIDATE` (coverage gate breached).

**The parent never runs validators and never POSTs — the agent owns both.**

## Step 4 — Verify (post-upsert)

For 2–3 scenario descriptions from the upserted halves, `Functional_Graph_Search` and confirm
`score > 0.4`. Confirm BOTH persona halves now resolve under the shared Outcome (the link worked).

## Step 5 — Checkpoint

Mark `app.status="done"`, pop the app id from `remaining[]`, append to `completed[]`
(`{appId, outcomeName, human:{persona,http}, system:{http}, scenarios, actions, apis, fieldsDeclared, fieldsReferenced, payloadPaths, completedAt}`).
Edit (do not rewrite) `applications.json` — only `status`, `completed[]`, `failed[]`, `remaining[]`
mutate. **This is the resume checkpoint: a mid-run stop leaves a clean state; re-invoking the skill
reads `applications.json` and continues from `remaining[]`.**

---

# REFERENCE

## Per-app cost
Small app (≤5 steps, few filters): ~30k tokens / ~60s. Medium: ~70k / ~120s. Large (many filters +
custom Java): ~150k+ / ~180s+. Plan multi-session for large trees (hundreds of apps).

## Multi-session resume
When context hits ~75%, finish the current batch (checkpoints flushed) and stop. Resume with:
```
/breeze:generate-functional-from-metadata continue from applications.json in <metadataRoot>
```
The skill reads `{metadataRoot}/.breeze-metadata-output/applications.json`, skips `completed[]`, and continues
`remaining[]`. Discovery is never re-run while that checkpoint exists.

## Failure recovery
`applications.failed[]` maps to the agent prefixes. `FAIL_UPSERT` only → re-curl the saved
`metadata_app*_*.json` `payload` to the right path with the `api-key:` header (no re-spawn).
`FAIL_VALIDATE` (incl. field-coverage) / `FAIL_WRITE` → re-spawn with the same input; if it repeats,
inspect the payload file on disk, then patch the agent prompt. Recovery loop: clear from `failed[]`,
re-add the app id to `remaining[]`, resume.

## When NOT to use
- Standard React/Vue/Angular UI repos → `/breeze:generate-functional-from-ui`
- Standard REST/GraphQL/queue backends → `/breeze:generate-functional-from-backend`

## See also
- `/breeze:validate-functional-graph` — post-generation quality checks
- `/breeze:generate-spec` — export the graph as a spec doc
