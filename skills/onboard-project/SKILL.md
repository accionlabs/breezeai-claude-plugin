---
name: onboard-project
description: >
  End-to-end onboarding orchestrator for a brownfield estate — one repo, a
  monorepo, or hundreds of services. Builds a workspace plan, onboards every
  repo into the code graph (via onboard-repository), classifies the code into
  units (SPA, backend service, Web Forms app, MVC app, metadata app, shared
  library, schema, infra, unsupported), routes each unit to the right
  generation skill, and runs them in dependency order: personas once across
  all UIs → functional per unit → cross-unit join → validate → design for UI
  units → validate design, with architecture in parallel once the code graph
  exists. Interactive by default (approval gates for repos, ignore patterns,
  git integration + tokens, units, personas, functional and design
  validation); `--autonomous` decides every gate itself and logs it. Every step
  is recorded in `.breeze/plan.json` and `.breeze/plan.log.jsonl` via
  `scripts/plan.py`, so a stopped or stalled run resumes from the first
  unfinished step. Ships `scripts/join.py` for the UI ↔ System join. Use when:
  "onboard this project", "onboard all repos", "onboard the estate",
  "end-to-end onboarding", "build all graphs", "what's next for this project",
  "onboarding status", "resume onboarding".
argument-hint: "[start | status | next | resume | rerun <step-id>] [--autonomous] [--project <uuid>]"
---

## What this skill does

Plans and drives the whole onboarding. It does **not** reimplement any generation logic — every step
calls an existing skill, and those skills keep their own checkpoints (`entrypoints.json`,
`design-progress.json`, …). This skill adds what they lack: the order, the routing, the gates, one
project-level record of what is done, and checks between steps.

```
P0  preflight                  tools, keys, project context, missing inputs
P1  code graph           ⛔    /breeze:onboard-repository (all repos; git link or local) — gates G1–G3
P2  units + routing      ⛔    classify every unit, pick its skill — gate G4
P3  personas             ⛔    detected once across ALL UI units — gate G5
P4  functional per unit        routed skill per unit, units in parallel
P5  join + validate      ⛔    link units by URL / queue / topic; validate-functional-graph — gate G6
P6  architecture               generate-architecture (+ schema) — may start any time after P2
P7  design (UI units)     ⛔    page/component registry → generate-design-from-ui → validate-design-graph — gate G7
P8  report                     coverage, gaps, out-of-scope boundaries, next actions
```

⛔ = an approval gate (see **Interactive vs autonomous** below). Everything else runs without asking,
unless a step fails.

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

## Where it runs: the workspace

Run from a **workspace folder** — not inside one of the repos. The repos can live anywhere: local paths,
git URLs, or a monorepo plus sub-folders. Nothing is copied or moved.

```
<workspace>/
  .breeze.json                 project link (+ apiKey; gitignored)
  .breeze/plan.json            THE plan: sources, units, steps, status  (resume point)
  .breeze/plan.log.jsonl       append-only event log
  .breeze/onboarding/          state of onboard-repository (repos.json, log.jsonl, ignore/, trees/)
```

If the user is inside a repo, suggest creating a workspace folder next to it and re-running there.

## Modes

| Invocation | Does |
|---|---|
| `start` (default when no plan exists) | P0 onwards |
| `status` (default when a plan exists and the user only asks) | Summary of every step + the next action; no changes |
| `next` / `resume` (default when a plan exists and the user asks to continue) | Runs from the first step that is not `done` |
| `rerun <step-id>` | Marks that step and the steps that depend on it `pending`, then resumes |
| `--autonomous` (with any of the above) | No questions: every gate is decided by the skill and logged. Saved in the plan, so `resume` keeps the same mode unless the user passes `--interactive` |

## Interactive vs autonomous

The plan records `"mode": "interactive" | "autonomous"` (default **interactive**). Gates are the only
places the run stops for the user; between gates it runs on its own in both modes.

| Gate | When | Interactive: show and ask | Autonomous: decide and log |
|---|---|---|---|
| **G1 Repos** | P1, after discovery / local scan | Repos found, grouped; which are suggested for skipping (archived, forks, empty, inactive > N months, unsupported language) and why. Ask: in scope / skip / change N | Take the suggestions; N = 24 months |
| **G2 Ignore patterns** | P1, after file lists | One table per batch: repo · files kept · excluded · biggest exclusions (vendored libs, generated code, build output). Ask: accept / edit a repo / accept all | Accept the proposals |
| **G3 Git integration** | P1, before connecting | Mode (git link vs local), provider and branch per repo, and that Breeze will **store the token** on each connected repo for later syncs. Ask for approval, then collect the token (below) | Git link when every repo has a reachable remote and a token is already available (env, CLI login or token file); otherwise local. **Never** prompts for a token — repos needing one are marked `blocked: token` and reported |
| **G4 Units + routing** | P2 | Tree: source → units → skill → fold-ins; run groups; skipped / unsupported units; capability scope for large estates. Ask: confirm / change | Take the classification; scope = everything |
| **G5 Personas** | P3 | Merged persona matrix with evidence, rejected alternatives, comparison with existing graph personas. Ask: confirm / rename / merge / split | Take the smallest set with distinct feature sets |
| **G6 Validation** | P5 | Join report + validation score and top issues. Ask: continue / fix first | Continue when score ≥ 80%; otherwise stop the design phase, finish the rest, report |
| **G7 Design validation** | P7 | P0/P1/P2 counts, top issues, the skill's offered fixes | Continue with no P0; P1s listed as follow-ups |
| *Failures* | any step | Show the error; ask retry / skip / stop | Retry once if transient (5xx, timeout, 409); otherwise mark `failed`, continue with steps that don't depend on it |

Every gate writes `{gate, mode, decision, detail, ts}` to `plan.gates` and the log — in autonomous mode
this is the audit trail the user reviews afterwards (P8 lists every auto-decision).

Sub-skills: in autonomous mode tell each one to run unattended (processing mode `auto`, commit with
defaults, answer its own confirmations the way the gate table says) and to log its decisions. In
interactive mode let their own confirmations through only where they add information the gates above
did not already cover.

### Collecting git tokens (interactive G3)

Never ask the user to paste a token into the chat — the conversation is stored. Offer, in this order:

1. **Already logged in:** `gh auth status` / `glab auth status` succeeds → use the CLI's token.
2. **Log in now:** ask the user to run `! gh auth login` (or `! glab auth login`) in this session.
3. **Token file:** ask the user to run
   `! read -rs T && mkdir -p ~/.config/breeze && printf %s "$T" > ~/.config/breeze/<provider>_token && chmod 600 ~/.config/breeze/<provider>_token`
   then pass `--token-file ~/.config/breeze/<provider>_token` to `git_onboard.py`.

Recommend a read-only, fine-grained token scoped to the repos in scope. Public repos need no token.

---

## The plan file

`.breeze/plan.json` — never edit it by hand. All changes go through
`python3 <skill dir>/scripts/plan.py` (atomic write + one log line per change):

```bash
plan.py init --project <uuid> --name <name> [--mode autonomous]
plan.py source --key acme/payroll-api --url https://… --branch main
plan.py unit  --id payroll-ui --type spa --root apps/payroll-ui --skill generate-functional-from-ui --fold libs/widgets
plan.py group --id UI-payroll --skill generate-functional-from-ui --units payroll-ui,admin-ui --root <working copy>
plan.py set P4:UI-payroll running            # running | done | failed | skipped | blocked [detail]
plan.py gate G5 confirmed "Payroll Admin, Employee, System, External System"
plan.py status    # steps, next runnable step, recent gates
plan.py next      # first runnable step id
```

Shape:

```json
{
  "version": 1,
  "projectUuid": "…", "projectName": "…",
  "createdAt": "…", "updatedAt": "…",
  "scope": { "capabilities": ["payroll run", "tax"], "excludeUnits": [] },
  "sources": [ { "key": "acme/payroll-api", "url": "https://…", "path": null, "branch": "main" } ],
  "units": [
    { "id": "payroll-ui", "type": "spa", "framework": "angular", "source": "acme/payroll-web",
      "root": "apps/payroll-ui", "skill": "generate-functional-from-ui",
      "foldIn": ["acme/shared-widgets:libs/widgets"], "personas": ["Payroll Admin", "Employee"],
      "inScope": true, "notes": [] }
  ],
  "runGroups": [
    { "id": "UI-payroll", "skill": "generate-functional-from-ui", "units": ["payroll-ui", "admin-ui"],
      "root": ".breeze/src/acme__payroll-web", "outputDir": ".breeze/out/UI-payroll" }
  ],
  "personas": { "status": "confirmed", "list": ["Payroll Admin", "Employee", "System", "External System"] },
  "designExclusions": ["scenario names validation flagged as not real features"],
  "gates": [ { "gate": "G5", "mode": "interactive", "decision": "confirmed", "detail": "…", "ts": "…" } ],
  "steps": [
    { "id": "P4:payroll-ui", "phase": "P4", "unit": "payroll-ui", "skill": "generate-functional-from-ui",
      "dependsOn": ["P3"], "status": "running", "attempts": 1,
      "startedAt": "…", "finishedAt": null,
      "checkpoint": "<repo>/.breeze-output/entrypoints.json",
      "result": null, "error": null }
  ],
  "checks": [ { "after": "P4:payroll-ui", "name": "persona-descriptions", "ok": true, "detail": "" } ]
}
```

Step `status`: `pending → running → done | failed | skipped | blocked` (`blocked` = waiting on a user
gate or a missing input). The log gets one line per transition:
`{"ts","step","from","to","detail"}`.

### Resume rules (also after a stall or a crashed session)

1. Load the plan. Print `status` (counts per phase, failed steps with their error, next step).
2. For each step in `running`: it was interrupted. Inspect its `checkpoint`:
   - the sub-skill checkpoint shows it finished → mark `done`;
   - partly done → call the same skill again; it resumes from its own checkpoint (all generation skills
     do). Do **not** delete its outputs;
   - P1 (code graph) → re-run `git_onboard.py status`/`run`; connected repos are never re-created.
3. `failed` steps: show the error; retry once automatically if the error looks transient (HTTP 5xx,
   timeout, 409 "already running"), otherwise ask.
4. Never re-run a `done` step unless the user asks (`rerun`).
5. A step whose dependency is not `done` stays `pending`.

---

## P0 — Preflight

Record results in the plan; stop only on hard failures.

- **Project context:** `Call_Get_Project_Details_` (per `CLAUDE.md` Step 4).
- **API key** present (`BREEZE_API_KEY` or `.breeze.json`) — needed by onboarding and REST upserts.
- **Sub-agent graph access:** the generation sub-agents call Breeze MCP tools by the plugin server name
  (`mcp__plugin_breeze_breeze-mcp__*`). If that server is not connected (e.g. Breeze is configured under
  another name), the sub-agents silently run without graph tools: no live dedup, no code-graph lookups,
  design uploads fail. Check whether tools named `mcp__plugin_breeze_breeze-mcp__*` are available in this session; if not, tell the user to
  connect `plugin:breeze:breeze-mcp` via `/mcp`, and in P4 pass existing outcome names to every
  sub-agent as a dedup fallback.
- **Sub-agent types:** every routed skill delegates to a plugin agent type
  (`breeze:spa-flow-structuring-agent`, `breeze:aspnet-razor-flow-structuring-agent`,
  `breeze:backend-entrypoint-discovery-agent`, `breeze:backend-flow-structuring-agent`,
  `breeze:design-from-ui-structuring-agent`, …). Check the ones the plan needs are in this session's
  agent list. If one is missing, the fallback is a `general-purpose` sub-agent told to read the agent's
  `.md` file (plugin `agents/`) as its instructions, run in dry-run, and the orchestrator uploads its
  payload over REST. Record which steps use the fallback.
- **Missing inputs to flag now:** no UI code (design will be skipped); no DDL / migrations (schema will
  be derived from ORM mappings or missing); unsupported languages; pipelines/IaC not in any repo.
- **Documents (optional, P1b):** if the user has specs, BRDs or runbooks, upload them with
  `Upload_Document` and poll `Get_Document_Status` until indexed; record them in the plan so
  `analyze-functional` and `impact-analysis` can use them.

## P1 — Code graph

Invoke `/breeze:onboard-repository` with all sources (it handles git link vs local, triage, ignore
patterns, status polling, retries and audit, with its own state in `.breeze/onboarding/`). Mark P1
`done` when every selected repo is `indexed`, `unsupported` or explicitly skipped. Copy the repo list,
statuses, **indexed repo names** and code ontology ids into `sources` — P4 passes them to every skill
(citations must use the indexed repo name, not the folder name).

**Working copies.** The generation skills write `.breeze-output/` (and a `.gitignore` line) into the repo
they read, and a git-linked repo may have no local clone. Give each source a working copy under the
workspace — `.breeze/src/<key with / as __>` (a `git clone --depth 1` of the branch, or a copy of the
user's folder) — and point every skill at that, never at the user's own checkout. Apply the confirmed
ignore patterns as its `.repoignore`.

## P2 — Units and routing ⛔

A **unit** is one thing that gets one generation run. One repo can hold many units (monorepo); one unit
can draw on several repos (an app plus its shared libraries).

Classify from evidence (code graph + file lists), not folder names:

| Evidence | Unit type | Skill (P4) |
|---|---|---|
| React / Angular / Vue / Svelte router, Next/Nuxt pages | `spa` | `generate-functional-from-ui` |
| REST / GraphQL / queue / cron / webhook handlers, no UI | `service` | `generate-functional-from-backend` |
| Console / batch program: `static void Main` (C#, `<OutputType>Exe</OutputType>`), `public static void main` (Java), `if __name__ == "__main__"` CLI, worker / hosted services, schedulers | `job` | `generate-functional-from-backend` — tell its discovery agent to add each `Main` / worker as an entry point (type `Job`, persona System); it does not inventory them on its own |
| `.aspx` / `.ascx` | `webforms` | `generate-functional-from-aspnet-webforms` (both halves) |
| Razor views + controllers (`Views/**/*.cshtml` that are not `_partials`, `*Controller.cs`, `App_Start/RouteConfig.cs`, `<OutputType>Library</OutputType>`) | `mvc` | `generate-functional-from-ui` **and** `generate-functional-from-backend` on the same unit |
| MAPL / MSCR / MFID metadata JSON | `metadata` | `generate-functional-from-metadata` |
| Library with no entry points (jar, npm widget lib, shared package) | `library` | **none** — added to `foldIn` of every unit that imports it |
| DDL, migrations, ORM entities only | `schema` | `generate-architecture` (schema ingest) |
| Terraform / Helm / k8s / pipelines | `infra` | `generate-architecture` |
| JD Edwards, SAP, mainframe, other unsupported stacks | `unsupported` | none — reported, needs a connector |

Monorepo frontends: use the workspace manifest (`nx.json`, `pnpm-workspace.yaml`, `turbo.json`,
`lerna.json`, `package.json` workspaces) to list apps — same discovery as `detect-personas-monorepo`.
Solutions with many projects (`.sln`, Maven multi-module, Gradle settings): one unit per project.

**Run groups.** One skill run per unit would re-discover the same repo many times (HotDocs: 7 web apps +
18 console programs = 32 runs). Group units that share a source **and** a routed skill into one run
(`plan.py group`); the skill's own entry-point list covers them, and the plan keeps per-unit records.
Give every run group its own `outputDir` — two groups writing the same `.breeze-output/` overwrite each
other's checkpoints.

**Several web apps in one solution** (each served from its own virtual directory) share routes like
`/Home/Index`. The canonical URL for every REST call, in both halves, is `/<app>/<controller>/<action>`
(the app = unit id / virtual directory). Pass the app to both skills; without it the human half and the
System half record different URLs and the P5 join fails.

Present the units as a tree (source → units → skill → fold-ins), the run order, and anything skipped.
For large estates, ask which **capabilities** are in scope for P4–P7 and set `inScope` per unit — the code
graph covers everything, the expensive steps cover the chosen slice. Write the steps for P3–P7 into the
plan only after gate G4.

## P3 — Personas ⛔

Run `/breeze:detect-personas` on each in-scope UI unit (`detect-personas-monorepo` for a monorepo) and
**merge into one list** — the same role found in two UIs is one persona; a separate app with its own
feature set used by different people is a persona candidate. Add `System` and `External System`.
For server-rendered stacks (MVC, Web Forms) the skill's guard and search patterns are SPA-only: tell it
to read `[Authorize]`, `Web.config` `<authorization>`/`<authentication mode>`, `Startup.Auth.cs`,
`_Layout`/`_LoginPartial`, and to treat scaffolded auth with no enforcement (no `[Authorize]`, missing
AccountController) as **no persona**. Write each persona with a 1–3 sentence description. Compare with
existing graph personas (`Get_all_personas`), then gate **G5**; record `personas.list` (names **and**
descriptions) and each unit's `personas`.

## P4 — Functional per unit

For every run group, run its routed skill on the group's working copy with an explicit context block:

- unit list (+ app / virtual-directory name per unit) and the canonical URL rule above;
- the indexed repo name, repo root and code ontology id from P1 (for citations);
- the confirmed personas **with descriptions** — the upsert clears a persona description unless the
  payload re-sends it;
- `foldIn` paths ("also read these shared libraries as depth");
- `EXISTING_OUTCOMES`: re-read live before **each batch** for every persona, including the other run
  groups' (UI and System groups running in parallel then share outcome names);
- the group's `outputDir`, and the instruction that every sub-agent derives its scratch file names from
  its own output path.

**Pass facts you derived as hints to verify, not as truth.** In the HotDocs test the orchestrator's brief
said "SOAP web service" and "no ORM"; the code had a REST client and EF Identity. Prefer file paths
over conclusions.

Groups are independent — run up to 3 at once. In autonomous mode tell each skill to answer its own
gates (processing `auto`, exclusions per the plan) and log the decisions.

**Checks after each unit** (record in `checks`; fix before moving on):
- every persona still has its description (the upsert can clear it — restore via
  `Call_Update_Functional_Node_` from the plan's persona list);
- no duplicate outcome names that differ only in wording (`Get_all_outcomes_for_a_persona_id`);
- the skill's own checkpoint shows no failed entry points left unexplained;
- the live node counts per persona equal the sum of the run's payloads minus dedup (a deploy or a
  timeout can drop writes silently).

## P5 — Join and validate ⛔

**Join.** Run `python3 <skill dir>/scripts/join.py [--verbless <paths>]`. It reads the live Api nodes
(never payload files — the upsert dedups) and classifies every human REST call: `matched` (method +
path), `verb-agnostic` (an MVC action with no `[HttpGet]`/`[HttpPost]` accepts any method — list those
paths in `--verbless`), `method-mismatch`, `NO HANDLER`, `external`, `relative-url`. A `NO HANDLER` call
is a finding about the **code** (the UI posts to an action that doesn't exist) — report it to the
customer, don't "fix" the graph. Then:
- service-to-service calls, queues and topics found in the code graph statements (HTTP clients, JMS /
  Kafka / SQS producers and consumers) should connect two in-scope units, or become an
  **External System** call marked "outside scope" when the other side is not onboarded.

Show the report; fix gaps with `/breeze:update-functional-graph` if the user wants.

**Validate.** Run `/breeze:validate-functional-graph` (read-only; skip its fix-offer step in autonomous
mode). Gate **G6** on its score. Scenarios it flags as not real features (e.g. built from unused
template code) go to `designExclusions` so P7 doesn't design them.

## P6 — Architecture

Can start as soon as P2 is confirmed; run it alongside P3–P5. `/breeze:generate-architecture` over the
in-scope sources, including schema units (DDL → stream ingest; ORM-only → derived stubs, labelled
approximate) and infra units. Point services at their repo names; add external services for
out-of-scope dependencies found in P5.

## P7 — Design (UI units only)

After G6, per in-scope UI run group: `/breeze:generate-page-registry` and
`/breeze:generate-component-registry` (one Page node per screen — without the registry the design pass
names pages per scenario and the same screen appears several times) → `/breeze:generate-design-from-ui`
(skip `designExclusions`; name pages after the view's title, not its route, when several apps share
routes) → `/breeze:validate-design-graph`.

Checks: every designed scenario has `isDesignGenerated: true`, excluded ones stay `false`; no two Page
nodes for the same screen; live UserJourney / Flow / Page / Component counts recorded.

**Gate G7 — design validation.** Interactive: show P0/P1/P2 counts and the top issues; offer the
skill's fixes (e.g. missing Flow/Page descriptions). Autonomous: continue when there are **no P0**
issues and list P1s in the report as follow-ups; with any P0, mark P7 `failed` with the issues.

Skip P7 with a note when there is no UI.

## P8 — Report

Write `.breeze/report.md`: per phase done/failed/skipped; counts per graph; units out of scope and
unsupported stacks; join results (including `NO HANDLER` code findings); functional and design
validation; known approximations (derived schema, missing templates); and — in autonomous mode — every
gate decision from `plan.gates`. Offer `/breeze:generate-spec`, `/breeze:impact-analysis`, or publishing
the report.

---

## Why this is a skill, not an agent

It needs the user at its gates (interactive mode), and it calls other skills (which may start their own sub-agents).
Sub-agents can't do either reliably, so the orchestration runs in the main session and delegates the
heavy per-unit work through the existing skills.
