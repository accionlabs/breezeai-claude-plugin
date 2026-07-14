---
name: generate-functional-from-aspnet-webforms
description: >
  Generate the WHOLE functional graph (both the human/User half AND the System
  half) for a classic ASP.NET **Web Forms** monolith — UI and backend live in
  ONE repo, ONE process, with NO network boundary (a `.aspx`/`.ascx`
  presentation tier calls a `*Facade`/`*Service`/`SqlProcs` business tier
  in-process → repository → SQL). Per UI entry point it runs the human pass and
  the System pass in a SINGLE orchestration via
  `breeze:aspnet-webforms-flow-structuring-agent`, joined on a shared Outcome,
  folds each EP's runtime-mounted controls (subpanels/search) into the same
  pass, then does a tiny non-UI-triggered sweep (scheduled/cron/queue/webhook)
  for flows no human initiates. ONLY for ASP.NET **Web Forms** (C# code-behind,
  `.aspx`/`.ascx`). Use when: aspx/webforms monolith, SplendidCRM / KCE_CMS /
  KinderCare-style app, "UI and backend together in one repo". Do NOT use for
  ASP.NET **MVC / Core / Razor Pages / Blazor**, a headless REST/GraphQL API
  (e.g. a .NET Core service), or a SPA — those have a URL seam and are covered
  by generate-functional-from-ui + generate-functional-from-backend (see the
  router block below).
argument-hint: "[repo-path]"
---

> ### ⚠️ Is this the right functional-generation skill?
> | Repo shape | Use |
> |---|---|
> | SPA frontend (React / Vue / Angular / Next) | `/breeze:generate-functional-from-ui` |
> | Headless backend API — REST / GraphQL / queue (incl. **ASP.NET Core**, Node, Java, Python) | `/breeze:generate-functional-from-backend` |
> | **◀ ASP.NET Web Forms monolith (`.aspx`/`.ascx` + in-process backend, one repo) — THIS SKILL** | `/breeze:generate-functional-from-aspnet-webforms` (single unified pass) |
> | ASP.NET **MVC / Razor Pages** full-stack (Razor views + controllers, one repo) | run **BOTH** `-from-ui` (views) **and** `-from-backend` (controllers) — join by the action-route URL *(no unified skill yet; Razor UI support is limited)* |
> | P3 / Vert.x metadata (MAPL / MSCR) | `/breeze:generate-functional-from-metadata` |
>
> **Why Web Forms is one skill but MVC is two:** Web Forms' UI→backend seam is an *in-process method call* (no URL) → a single unified pass is required to join the halves. MVC/Core expose the backend as a *URL* (the action route) → the standard `-from-ui` + `-from-backend` passes join on that URL, same as a SPA + REST API.
>
> **This skill is ONLY for ASP.NET Web Forms** (C# `.aspx`/`.ascx` + code-behind, in-process business tier). Phase -1 verifies this and **stops** if the repo is MVC / Core / Razor Pages / Blazor / a headless API / a SPA. Rule of thumb: **no `.aspx`/`.ascx` ⇒ not this skill.**

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

> **API key:** required — the sub-agents POST the upsert directly via REST. Collect it on-demand (Bootstrap step 5).

## What this skill does

A classic ASP.NET **Web Forms monolith** is not two systems joined over HTTP — it is one repo where a `.aspx`/`.ascx` **presentation tier** calls a `*Facade`/`*Service`/`*Manager` **business tier in-process**, which calls **repositories → SQL**. Running `generate-functional-from-ui` and `generate-functional-from-backend` as two independent passes and hoping they line up on a `<Class>.<Method>` name is fragile for this shape (the join misses exactly when the code graph is incomplete). This skill keeps the **two-persona output model** but **unifies the orchestration**: it walks the whole chain **per UI entry point in one pass** and emits both halves under a **shared Outcome**, so the join is deterministic (same run, same Outcome name passed to both). It then sweeps the **non-UI** entry points (background/service flows) that have no human initiator.

```
per UI entry point ───────→ breeze:aspnet-webforms-flow-structuring-agent   (ONE agent, both halves)
(.aspx page / .ascx ctrl)    per (EP, persona): traces the WHOLE chain in one run —
                             .aspx/.ascx markup + code-behind → façade → WCF/in-process
                             service → repository → SQL — and emits BOTH the User subtree
                             AND the System subtree under ONE shared Outcome (join is
                             intrinsic: same run, verbatim Outcome name). Self-dedups
                             persona-scoped via the functional read tools.

NON-UI-triggered sweep ──→ breeze:backend-flow-structuring-agent   (System / External System)
(scheduled/cron, queue/     ONLY flows NO human/UI initiates. UI-reached procs + UI-triggered
 event, inbound webhook,     ASMX/WCF are already covered by the UI pass (do NOT re-model).
 server-push)               Another frontend's REST API (e.g. React Rest.svc) → that repo's
                            own UI pass, not here. Often tiny; empty is valid, not a gap.
```

**Persona model (deliberate — do NOT fold System into the human steps):**

| Trigger | Persona | Produced by |
|---|---|---|
| A user acting through a page/control | **User** (human) | `aspnet-webforms-flow-structuring-agent` (Phase 1 — human subtree) |
| The app's own backend logic invoked by that user action | **System** | `aspnet-webforms-flow-structuring-agent` (Phase 1 — joined System subtree, SAME run/Outcome) |
| Background/scheduled/queue/webhook work no human triggers | **System** | `backend-flow-structuring-agent` (Phase 2 sweep — System-only Outcome) |
| Inbound webhook / partner callback / 3rd-party event | **External System** | `backend-flow-structuring-agent` (Phase 2 sweep — External-only Outcome) |

Human actions stay platform-agnostic and user-observable (the forbidden-UI-word + per-field-atomicity rules still apply); backend side-effects (validations, DB writes, external calls) live in the **System** scenario, joined by Outcome — never melted into human steps. This preserves the backend lens, reuse (one façade method hit by many UI actions = one System scenario), and coverage of non-UI behavior.

**Join model (same as the agents already implement):**
- **In-process (the common case here):** the human action records the **façade/service method** `<Class>.<Method>` it invokes (e.g. `BillingFacade.CreateInvoice`); the System half is anchored on that same method. There is no URL — the method name IS the seam. This skill passes the human-half Outcome to the System agent as `EXISTING_NEIGHBORHOOD` so it **attaches** (upsert merges by Outcome name).
- **Network (rare in this app class):** if the action crosses a **SOAP** boundary (WCF `.svc` / ASMX `[WebMethod]`), the seam is the SOAP operation URL in `action.apis[]`.

**Runs on the LOCAL checkout.** The agents read the actual source off disk (`Read`/`Glob`/`Grep` over `.aspx`/`.ascx`/code-behind/façade/service). The code-ontology **graph is only an accelerator** (`Code_Graph_Search`/`Get_Code_File_Details` for following the `control→façade→service→repository→SQL` chain) — not the input. Extraction is therefore robust to code-graph gaps; a clean graph just makes the chain-following faster/more complete.

## Resources

- **Per-EP end-to-end agent (Phase 1)** — `agents/aspnet-webforms-flow-structuring-agent.md` (plugin root). Invokable as `subagent_type: "breeze:aspnet-webforms-flow-structuring-agent"`. Takes ONE (UI EP, persona) and traces the WHOLE chain in a single run — `.aspx`/`.ascx` markup + code-behind → façade → WCF/in-process service → repository → SQL — emitting BOTH the User subtree and the System subtree under ONE shared Outcome (the join is intrinsic: same run, verbatim Outcome name; no cross-agent hand-off). It **self-dedups persona-scoped** via the functional read tools (`Get_all_personas` / `Get_all_outcomes_for_a_persona_id` / `Get_all_scenarios_for_a_outcome_id` / `Get_all_steps_actions_for_a_scenario_id`): the Outcome is shared across personas by NAME (that is the join), but Scenario/Step/Action are scoped to the current persona and must never bleed across personas. The save/submit action links its real mechanism (`Postback` to the `.aspx`, or the ASMX/WCF SOAP op if AJAX-saved); empty `apis` only for pure input/selection. Self-validates and upserts; returns a one-line summary.
- **Installed System-only-sweep agent (Phase 2)** — `agents/backend-flow-structuring-agent.md` (plugin root). Invokable as `subagent_type: "breeze:backend-flow-structuring-agent"`. Used ONLY for the Phase-2 sweep of background entry points with no human trigger (WCF/ASMX SOAP operations, scheduled/service handlers). Reads the operation + injected repositories, traces side effects to SQL, self-validates, upserts. It **attaches to an existing Outcome** when `EXISTING_NEIGHBORHOOD` scores > 0.6 (verbatim name reuse).
- **Installed discovery agent (Phase 0.3)** — `agents/backend-entrypoint-discovery-agent.md` (plugin root). Invokable as `subagent_type: "breeze:backend-entrypoint-discovery-agent"`. Does the token-heavy repo globbing/reading and writes `entrypoints.json`, returning only a summary line — so the parent's context stays lean. It **already covers this app class**: its **monolith mode** enumerates `*Facade`/`*Service`/`*Manager` methods as `Internal` `service-operation` entry points (the façade seam), plus **WCF/ASMX** SOAP operations and **queue/cron** handlers, with mechanical persona routing. Phase 1 uses these entries to resolve each façade seam to `{seedFile, seedLine}`.
- This skill introduces the **`aspnet-webforms` end-to-end agent** for the per-EP pass and reuses the installed **discovery** + **backend-flow** agents for Phase 0.3 discovery and the Phase-2 System-only sweep.
- `detect-personas` skill — used at the persona gate (Phase 0.2).
- Shared functional SSOT — `../shared/functional/{upsert.schema.json, verbs.json, core.md, human-overlay.md, system-overlay.md}` (ADR 0001). The agents self-validate against it; pass its absolute dir to the System agent as `SHARED_FUNCTIONAL_PATH`.

## Inputs

- **Repo path** — argument (`$ARGUMENTS`) or resolved in Phase -1. Must be an ASP.NET Web Forms monolith (see Phase -1 guard).
- **`.breeze.json`** — `projectUuid`, `targetRepos.monolith` (this repo), `apiKey`, and the repo's code-ontology id.
- **Existing functional graph** — queried per EP for dedup + the cross-half Outcome join.
- **Optional: `entrypoints.json`** — resume checkpoint (written inside the repo dir).

## Outputs

- **Functional graph** updated with **both** User scenarios and joined System/External scenarios (idempotent merge by Outcome name).
- **`entrypoints.json`** — the UI reachability buckets from 0.1: **`primaryEntryPoints[]`** (own subagent run), **`foldedControls[]`** (passed to their parent EP as `MOUNTED_CONTROLS`, no own run), **`sharedControls[]`** (one run, reused via dedup), **`orphans[]`** (flagged for human review, never generated) — plus the discovery agent's `entryPoints[]` (Internal `service-operation` = façade seam, SOAP, queue/cron/service), `personas[]`, and per-EP checkpoint. Each `foldedControls[]` entry records its `parentEntryPoint` + `mountedVia`; each `orphans[]` entry records `why` (no route / no static ref / no metadata mount / not a template).
- **Per-EP payload files**: `<repo>/dm_ep{NN}_{persona}_{slug}.json` (human) and `<repo>/dm_sys_{Class}.{Method}.json` (System) — audit + replay.

---

# PHASES

## Bootstrap (run ONCE)

1. Resolve `projectUuid` (see **## Project**). Cache it.
2. **Resolve URLs** from `breeze.config.json` (plugin root), overridable per-project via `.breeze.json`: `apiBase` (Breeze backend), `uiBaseUrl` (Breeze UI). Placeholders `<apiBase>`/`<uiBaseUrl>` — never hardcode hosts.
3. `Call_Get_Project_Details_(uuid=<projectUuid>)` once; cache `name` → passed to agents as `PROJECT_NAME`.
4. **Resolve `apiKey`** (required — sub-agents upsert directly). Check `.breeze.json`; if missing, prompt with the standard wording:
   > This skill upserts via REST directly (avoids MCP argument-size limits). It needs a Breeze API key. Generate one at `<uiBaseUrl>/mcp/generate/key`, then paste it here. I'll save it to `.breeze.json` (make sure that's in `.gitignore`).

   Save under `apiKey`; respond only "API key saved." **Never echo/log the key.**
5. **Resolve the repo's `codeOntologyId`** (for `Code_Graph_Search` scoping): `.breeze.json` → `targetRepos.monolithCodeOntologyId`/`monolithRepoName`, else `Call_List_Repositories_(projectUuid)` and match the on-disk basename to an indexed repo with `fileCount > 0` and `status:"active"` (sole-repo fast path; ask once if ambiguous). Persist both. If none indexed → stop and tell the user to run `/breeze:onboard-repository` first. Cache `CODE_ONTOLOGY_ID` + `INDEXED_REPO_NAME`.
6. Resolve `SHARED_FUNCTIONAL_PATH` = `<pluginRoot>/skills/shared/functional` (absolute).

## Phase -1 — Resolve the repo & confirm it's a Web Forms monolith

Resolve the path (argument → `.breeze.json.targetRepos.monolith` → cwd → ask once; persist). Then **guard the stack** — this skill is only for the monolith shape:
- **Confirm Web Forms:** `Glob '**/*.aspx'` and `'**/*.ascx'` return hits, and code-behind imports `System.Web.UI`.
- **Confirm an in-process business tier:** classes named `*Facade`/`*Service`/`*Manager` (often `I*` interfaces with constructor-injected repositories).
- **If instead** it's a modern split (a SPA router + a separate REST/GraphQL API repo, no `.aspx`): **stop** and redirect the user to `generate-functional-from-ui` (+ `generate-functional-from-backend`). Don't force the monolith flow onto a split app.

## Phase 0 — Discover entry points & personas

If `entrypoints.json` already exists in the repo dir: read it, show a resume summary, and jump to the per-EP loop (do not overwrite).

### 0.1 — UI entry points + REACHABILITY classification (4 buckets)
`Glob '**/*.aspx'` **and** `'**/*.ascx'`, then **classify every control by how it is reached** — a control is a top-level EP only if it is independently reachable; otherwise it is *folded into the parent EP that mounts it*. Build the mount graph, then bucket:

- **`primaryEntryPoints[]`** — a `.aspx` page (`kind:page`), or a `.ascx` mounted 1:1 into its own route (EditView↔edit.aspx, DetailView↔view.aspx, ListView↔default.aspx, PopupView↔Popup.aspx, import↔import.aspx). Each gets **its own subagent run**.
- **`foldedControls[]`** — reachable **only through one parent** (a DetailView subpanel, a search control, an inline NewRecord). **NOT its own EP** — passed to the parent EP's subagent as `MOUNTED_CONTROLS` and captured in that same pass.
- **`sharedControls[]`** — mounted by **many** parents (`_controls/*` widgets, a related-list reused across modules, master-page/theme chrome). Model **once** as its own EP; other parents reference it via dedup (never re-capture per parent).
- **`orphans[]`** — reachable by **nothing** after ALL mount mechanisms are resolved → flag for human review; **never auto-drop, never auto-generate**.

⚠️ **Resolve dynamic mounts BEFORE bucketing — static `Register`/`LoadControl` references are NOT enough.** A metadata/convention-driven Web Forms app mounts most controls at runtime, so a naive "no static reference ⇒ orphan" check **over-reports orphans** (it will wrongly call live subpanels/dashlets dead, or wrongly promote them to their own EP). A control is *reachable* if ANY of these holds:
  1. **Static markup** — `<%@ Register Src="X.ascx">` / `LoadControl("…X.ascx")`.
  2. **Metadata mount** — `DETAILVIEWS_RELATIONSHIPS` (subpanels, via `AppendDetailViewRelationships(...)`), `GRIDVIEWS`/`EDITVIEWS`/search layouts, `DASHBOARDS` (dashlets, `MyX`/`MyRecentActivity`), `DYNAMIC_BUTTONS`. Check the append-call sites + the metadata tables/seed files.
  3. **Master-page / theme composition** — `App_MasterPages/**` fragments (toolbar/favorites/last-viewed) → **shared chrome**, not EPs.
  4. **Convention** — a host that `LoadControl`s by name (e.g. `Administration/*View.ascx`, module related-lists named after the related module).
  Also **exclude non-runtime files**: code-gen templates (`$placeholder$.ascx`, `*Template*.ascx`) are scaffolding, not EPs. Only a control failing **all** of 1–4 (and not a template) is a real orphan.

**Detect generic page hosts:** if a `.aspx` shell only `LoadControl(...)`s a control, the shell is a container and the mounted `.ascx` is the primary EP. Read `web.config` `<authorization>`/`<location>` and `.sitemap` `roles="…"` for per-EP persona reachability.

### 0.2 — Personas ⛔ HARD GATE
`Get_all_personas(projectUuid)`; if present, offer to reuse or re-detect. Otherwise run `/breeze:detect-personas` (analysis-only) against the repo. Present the candidate human personas + source locations, **wait for user confirmation**, record the closed set in `entrypoints.json.personas[]`. Do not proceed until confirmed. Per-EP `personas[]` from auth guards/roles/`web.config`; default to the full set where undeterminable (the per-(EP,persona) loop records `audit.skippedForVisibility[]`).

### 0.3 — Delegate backend + façade-seam discovery to the discovery agent  (context-lean)
Do **NOT** inventory the backend inline in the parent — a monolith is thousands of files/methods and would blow the parent's context. Spawn **`breeze:backend-entrypoint-discovery-agent`** ONCE (pass the repo path, `CODE_ONTOLOGY_ID`, `INDEXED_REPO_NAME`, `OUTPUT_PATH = <repo>/entrypoints.json`, `EXISTING_PERSONAS`). It does the token-heavy globbing/reading and writes `entrypoints.json`; the parent reads only its summary line. On a .NET Web Forms monolith it returns:
- **Internal façade/service methods (monolith mode)** — `*Facade`/`*Service`/`*Manager` public methods as `type:"Internal", subType:"service-operation", operation:"<Class>.<Method>", persona:"System"`, each with `{file,line,parameters,requestType,responseType}`. **This IS the façade seam** (the Phase-1 join targets) **and** the System side of the in-process join. It sets `internalEntryPointsNeedConfirmation: true`.
- **WCF / ASMX SOAP operations** — `[ServiceContract]`/`[OperationContract]`, `[WebMethod]` (incl. `[ScriptService]`) as System entry points (`type:"SOAP"`).
- **Queue / event / cron / Windows-service** handlers, and **webhook / partner** receivers → `External System`.
- Mechanical persona per EP. *(Its REST/GraphQL discovery will find little/nothing here — expected for Web Forms.)*

The parent merges the UI EPs (0.1) into the same `entrypoints.json` under `uiEntryPoints[]`; the discovery agent's `entryPoints[]` supply the façade seam + the non-UI System/External sweep set.

### 0.4 — Scope ⛔ HARD GATE (monolith can be huge)
The discovery agent flags `internalEntryPointsNeedConfirmation: true` because a monolith has thousands of façade methods — do NOT System-ify all of them. Confirm scope with the user:
- **Default (recommended):** System half = the façade/service methods **actually reached by UI actions** (resolved organically in Phase 1 from the join keys the human pass records) **plus** the non-UI background/SOAP/queue/cron entry points from 0.3. Bounds work to real flows.
- Alternatives: whole façade layer (heavier), or a named module subset (e.g. `Billing*`/`Enrollment*`).
Record the chosen scope in `entrypoints.json`.

## Phase 1 — Per-(UI EP, persona) UNIFIED pass  (human + joined System, one shot)

For each UI EP in `remaining[]`, and for each `persona` in `ep.personas[]`, in parallel batches of up to 3:

**1. Dedup pre-query.**
`Functional_Graph_Search(uuid, query=f"{persona} {ep.title} <likely outcome>", limit=10)` → group into `EXISTING_NEIGHBORHOOD` (`{outcomes:[{name,id,score,scenarios:[…]}]}`; `{"outcomes":[]}` if none). This is a *seed* — the agent also does its own persona-scoped read-back (below) before writing.

**2. Spawn the end-to-end agent** — `breeze:aspnet-webforms-flow-structuring-agent`. ONE call per (EP, persona) produces **both** halves (User subtree + joined System subtree) in a single run — there is no separate System spawn and no cross-agent hand-off. Pre-compute `OUTPUT_PATH_HUMAN = <repo>/dm_ep{NN}_{persona}_{slug}.json` and `OUTPUT_PATH_SYSTEM = <repo>/dm_ep{NN}_system_{slug}.json`. Resolve the façade seam(s) this EP calls to `{seedFile, seedLine}` from the discovery agent's `Internal` `service-operation` entries in `entrypoints.json` (fallback `Grep`/`Code_Graph_Search`), and pass them as hints. Render its input block:
```
PERSONA: <persona>            ENTRY_POINT: { route, kind(page|control|master), title }
SEED_FILE: <abs path to .aspx/.ascx markup>   CODE_BEHIND: <abs .aspx.cs/.ascx.cs>
REPO: { name: <basename>, root: <abs repo path> }
PROJECT_UUID / PROJECT_NAME / LLM_PLATFORM: AWSBEDROCK
OUTPUT_PATH_HUMAN / OUTPUT_PATH_SYSTEM
API_BASE / API_KEY (never echo)
CODE_ONTOLOGY_ID / INDEXED_REPO_NAME   SHARED_FUNCTIONAL_PATH
FACADE_SEAM_HINTS: [ { "op": "<Class>.<Method>", "seedFile": "...", "seedLine": N } ]
MOUNTED_CONTROLS: [ { "file": "<abs .ascx>", "codeBehind": "<abs .ascx.cs>", "mountedVia": "detailview-relationship|dashlet|search|inline-newrecord|register", "role": "subpanel|search|inline-create" } ]
SCOPE: <confirmed façade/service scope from Phase 0.5>
EXISTING_NEIGHBORHOOD: <json from step 1>
```
`MOUNTED_CONTROLS` = the `foldedControls[]` this EP hosts (from 0.1 reachability), resolved for this EP: a DetailView's subpanels (via `DETAILVIEWS_RELATIONSHIPS`), its search control, its inline-create control. The agent **reads each mounted control's code-behind and folds its flows into THIS EP's scenario** (extra Steps/Actions under the same Outcome) — they are NOT separate runs. `sharedControls[]` are NOT passed here (they get their own one-time run and are reused via dedup); `orphans[]` are never passed.

The agent: reads markup + code-behind **+ every `MOUNTED_CONTROLS` entry**, traces each action to its façade → service → repository → SQL, emits the **User** subtree (each action links its real mechanism — `Postback`/SOAP/none; folded-control flows appear as additional steps under the same Outcome) AND the **System** subtree under the **same Outcome name** (intrinsic join), self-dedups persona-scoped via the functional read tools (Outcome shared by name across personas; Scenario/Step/Action scoped to the current persona), self-validates, and upserts **both** payloads. Returns two summary lines (human + system HTTP status + functionalId).

**3. Read back both payloads** from `OUTPUT_PATH_HUMAN` / `OUTPUT_PATH_SYSTEM` for the checkpoint. Extract the **created Outcome name** (the join anchor) and the set of **façade/service seams** `<Class>.<Method>` the System half persisted.

**4. Checkpoint** the EP in `entrypoints.json` (`completed[]`); record which façade seams were System-ified under which Outcome (so a seam shared by a later EP in this run is *reused*, not re-created — the agent's own dedup read-back will find the existing System scenario and attach rather than duplicate).

## Phase 2 — Non-UI-triggered sweep ONLY  (usually tiny; often skippable)

**In an aspx monolith the UI pass already covers the backend end-to-end** (page → façade → `SqlProc` → SQL), so a separate backend pass is **redundant for anything a user can trigger** — do NOT re-model UI-reached procs or UI-triggered SOAP here (that just creates detached, human-less duplicates). Phase 2 exists ONLY for entry points **no human/UI initiates**. Decide per entry point:

| Discovery entry point | Phase 2? | Reason |
|---|---|---|
| `Internal` `service-operation` reached by a Phase-1 join key | ❌ skip | already modeled as the System half of that UI pass (dedup reuses it) |
| `Internal` `service-operation` NOT reached by any UI flow **and** in confirmed scope | ⚠️ optional | unreached façade — model only if the scope gate chose "whole layer"; else leave in the catalog |
| **ASMX/WCF SOAP op fired *from* a `.aspx`/`.ascx`** (autocomplete, AJAX save) | ❌ skip | UI-triggered → absorbed by the Phase-1 pass that calls it |
| **REST/SOAP that is another frontend's API** (e.g. `Rest.svc` for a React SPA) | ❌ skip | not an aspx flow — model via `generate-functional-from-ui` on **that** frontend's repo; it joins these served ops by URL |
| **Scheduled job / cron / Windows-service** | ✅ **yes** | timer-initiated, no UI path |
| **Queue / event consumer** (truly async) | ✅ **yes** | event-initiated |
| **Inbound webhook / partner callback** | ✅ yes (`External System`) | external-initiated |
| **Server-*initiated* push** (e.g. a SignalR broadcast from a job) | ✅ yes | not the client-called hub method (that's UI-triggered) |

For each entry point that qualifies (✅), spawn `breeze:backend-flow-structuring-agent` (parallel batches of 3) with `PERSONA = System` (or `External System` for inbound partner calls), `ENTRY_POINT = { url, operation, subType: scheduled-job|queue-consumer|event-handler|webhook }`, `SEED_FILE`/`SEED_LINE` from discovery, and a fresh dedup `EXISTING_NEIGHBORHOOD` (these own their Outcomes — no human half; but their `SqlProc` side effects still **dedup/attach** to System scenarios a UI pass already created).

> **If the app has no scheduler/queue/webhook, Phase 2 is empty — that's correct, not a gap.** The whole backend is then covered by the Phase-1 UI passes. Record the skipped-because-UI-triggered and other-frontend entry points in `entrypoints.json` (`backendDisposition`: `absorbed` / `other-frontend` / `unreached` / `phase2`) so nothing looks silently dropped.

## Phase 3 — Sign-off

Report: EPs processed, personas, human scenarios, System scenarios, join keys resolved (and any unresolved — a join key with no matching seam is an `audit` warning, not a silent drop). Suggest the §3.3 end-to-end trace check: *"what happens when a user does &lt;X&gt;?"* should now traverse User action → `<Class>.<Method>` → System scenario → repository → DB across the shared Outcome.

---

## Notes & guardrails

- **Local-first:** source on disk is the ground truth; the code graph is an accelerator only. You can run this before/independently of fixing code-graph coverage — but a cleaner graph (function/route completeness, `callresolve` depth) makes the System chain-following better.
- **Deterministic join:** because the same run feeds the human Outcome into the System agent, the halves join by construction — unlike two independent passes that merge only if they happen to name the Outcome identically.
- **No silent scope creep:** the monolith scope gate (0.5) bounds System work to UI-reached methods + background EPs; anything skipped is recorded, not dropped.
- **Reuses, never forks, the agents:** if the aspx/backend agents improve, this skill inherits it. It adds orchestration + the join wiring only.
- **VB Web Forms:** works the same once a `vb_webforms`-style human path exists; today the aspx agent targets C# code-behind.
