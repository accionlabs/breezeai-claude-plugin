---
name: onboard-repository
description: >
  Get one repository, a list of repositories, a whole GitHub organisation /
  GitLab group, or a monorepo into the Breeze code graph for the current
  project. Default mode is GIT LINK: the repo is connected to Breeze
  (GitHub, GitLab, Bitbucket, Azure DevOps) and parsed server-side, with
  ignore patterns stored on the repo and applied on every sync — nothing is
  generated on disk. LOCAL mode runs the `breezeai-cog` parser via `uvx`
  (with template capture when needed) and uploads automatically or hands
  over an ndjson for manual upload. Every run proposes ignore patterns
  (vendored libraries, generated code, build output, …), polls the server
  ingest status until each repo is indexed or errored, retries failures,
  audits the result, and keeps a resumable state file + log under
  `.breeze/onboarding/` so a stopped run picks up where it left off. Scales
  to hundreds of repos (discover → triage → batch confirm → throttled
  connect). Use when: "onboard repo", "onboard repos", "connect github org",
  "add gitlab group", "upload repository", "index repo into breeze", "add repo
  to project", "ingest codebase", "register code graph", "clean up
  .repoignore", or whenever a Breeze skill reports the project has no code
  ontology yet.
argument-hint: "[repo path | repo URL | org/group URL | list file] [--local] [--autonomous] [--project <uuid>]"
---

## What this skill does

Gets source code into the Breeze **code graph** — files, classes, functions, routes,
call chains and method-level statements — which every downstream skill reads
(`generate-functional-from-*`, `generate-architecture`, `generate-design-from-ui`,
`search`, `impact-analysis`, `generate-code`).

It handles **one repo or hundreds** in the same flow:

```
Step 1  mode: git link (default) or local
Step 2  scope: one repo · list · org/group · monorepo  → state file
Step 3  triage (batches): pick what is in scope
Step 4  ignore patterns: propose per repo from its file list → confirm (one approval per batch)
Step 5  ingest: git link → connect + server sync · local → COG run + upload
Step 6  status: poll until every repo is indexed / errored; retry errored + stalled
Step 7  audit: counts, templates, unsupported languages, empty repos
Step 8  report + next steps
```

Everything is recorded in `.breeze/onboarding/` (in the current working directory,
which should be the workspace — not inside one of the repos):

| File | What it holds |
|---|---|
| `repos.json` | One entry per repo: url, branch, provider, `selected`, `status`, `codeOntologyId`, counts, last error, attempts |
| `log.jsonl` | Append-only event log: discover, connect, status changes, retries, failures |
| `ignore/<repo>.repoignore`, `ignore/_default.repoignore` | Confirmed patterns per repo / shared |
| `trees/<repo>.txt` | Remote file list used to propose patterns |

**Resume rule:** at the start of every run, if `.breeze/onboarding/repos.json` exists, show its summary
(counts by status, last 5 log events) and continue from it. Never re-connect a repo that already has a
`codeOntologyId` — re-sync it instead (Step 6).

The helper script `scripts/git_onboard.py` (stdlib Python) does all remote calls in git-link mode so the
logic is deterministic and resumable. Run it as
`python3 <skill dir>/scripts/git_onboard.py <cmd> --project <uuid>`.

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

URLs (`apiBase`, `uiBaseUrl`) come from `breeze.config.json`, overridable per project in `.breeze.json`
(see `CLAUDE.md` → "Service URLs"). `<apiBase>` / `<uiBaseUrl>` below are placeholders.

### Secrets

- **Breeze API key** (git link and local automatic upload): env `BREEZE_API_KEY`, else `apiKey` in
  `.breeze.json`. If neither exists, ask the user to generate one at `<uiBaseUrl>/mcp/generate/key` and
  save it to `.breeze.json` (reply only "API key saved"). `.breeze.json` must be gitignored.
- **Git token** (private repos): a token file (`--token-file`), env `GITHUB_TOKEN` / `GITLAB_TOKEN` /
  `BITBUCKET_TOKEN` / `AZURE_DEVOPS_TOKEN`, or the logged-in `gh` / `glab` CLI. **Never ask the user to
  paste a token into chat.** How to collect one is under gate G3 below. Recommend a read-only,
  fine-grained token. Breeze stores it on each connected repo to run later syncs.

### Interactive (default) vs `--autonomous`

Interactive runs stop at three gates; autonomous runs decide them and log the decision to
`log.jsonl` (`{"event":"gate", "gate", "decision", "detail"}`):

| Gate | Interactive: show and ask | Autonomous |
|---|---|---|
| **G1 Repos** (Step 3) | Repos found, the ones suggested for skipping and why | Take the suggestions (N = 24 months) |
| **G2 Ignore patterns** (Step 4) | Per-batch table of kept / excluded / biggest exclusions | Accept the proposals |
| **G3 Git integration** (Step 1, confirmed before Step 5) | Mode, provider, branch per repo, and that Breeze stores the token; then collect the token | Git link if every repo has a remote and a token is already available (or the repos are public); else local. Never prompts for a token; repos that need one are reported as `blocked: token` |

**Collecting a token at G3** — in order: (1) `gh auth status` / `glab auth status` already logged in;
(2) ask the user to run `! gh auth login` / `! glab auth login`; (3) ask the user to run
`! read -rs T && mkdir -p ~/.config/breeze && printf %s "$T" > ~/.config/breeze/<provider>_token && chmod 600 ~/.config/breeze/<provider>_token`
and pass `--token-file` to the script. Public repos need no token.
- Never print either secret, never write the git token to a file.

---

## Step 1 — Pick the mode

Ask once (skip if the prompt already says, e.g. a local path + "local"):

> How should Breeze get the code?
> **A. Git link (recommended)** — connect the repos from GitHub / GitLab / Bitbucket / Azure DevOps.
> Breeze parses them on the server, keeps the ignore patterns on each repo and can re-sync later.
> Nothing is generated on your machine.
> **B. Local** — run the parser here on a checked-out copy, then upload (automatic with an API key, or
> manual through the UI). Use this when the server can't reach the git host, there is no token, or the
> code isn't in git.

Record `mode` in `repos.json` (`"mode": "git" | "local"`).

**Templates.** UI repos with markup views (AngularJS/Angular `.html`, Razor `.cshtml`, Web Forms
`.aspx/.ascx`, Vue `.vue`) need them in the graph for the UI functional pass. Locally, pass
`--capture-templates`. On the server it is a deploy-time analyzer setting (`BREEZEAI_COG_CAPTURE_TEMPLATES`)
the API can't read; the dev deployment had it **on** (verified 2026-11-01: all 39 `.cshtml` views of a
git-linked repo were indexed). So don't warn up front — the Step 7 audit checks for template File nodes,
and only if they are missing re-onboard that repo locally with `--capture-templates`.

---

## Step 2 — Scope → state file

Accept any of these; several can be combined:

| Input | Git link | Local |
|---|---|---|
| One repo URL | `git_onboard.py add --url <url> [--branch B]` | — |
| List of URLs (file or pasted) | `add` once per line (`url[,branch]`) | — |
| GitHub org / user | `git_onboard.py discover --provider github --org <org>` | — |
| GitLab group (incl. subgroups, self-hosted via `--host`) | `git_onboard.py discover --provider gitlab --org <group path>` | — |
| Bitbucket workspace / Azure DevOps project | `add` per repo (no discovery API in the script yet) | — |
| Local path(s) | — | one entry per path |
| Monorepo | one repo entry; note its apps for `/breeze:onboard-project` | one entry |

Local paths must exist and look like source (`.git`, or a manifest such as `package.json`, `pom.xml`,
`*.csproj`, `pyproject.toml`, `go.mod`). If the path is the Breeze plugin repo itself, warn — the user
almost certainly means another folder.

---

## Step 3 — Triage (any time there are more than ~10 repos)

Show a table from `repos.json`: name, language, size, last push, archived, fork, empty. Suggest
**excluding** archived repos, forks, empty repos, and repos with no push in the last N months (ask N;
default 24). Group the rest so the user can decide quickly (by language, or by name prefix such as
`payroll-*`, `hr-*`). Set `selected: true/false` for every repo and save.

For one to a few repos, skip the table and just confirm the list.

Unsupported languages (see `uvx --from git+https://github.com/accionlabs/breezeai-cog breezeai-cog
capabilities`; today C#, Java, Python, TypeScript/JavaScript, VB) produce no code nodes. Flag repos whose
main language is unsupported (Go, PHP, Ruby, C/C++, RPG, COBOL, …) as **unsupported** in the state file
and tell the user now rather than after the sync.

---

## Step 4 — Ignore patterns

Follow [references/ignore-catalog.md](references/ignore-catalog.md):

1. Git link: `git_onboard.py tree` fetches each selected repo's file list (GitHub / GitLab) into
   `trees/`. Local: list the folder.
2. Propose patterns per repo — only for paths that exist, never repeating COG's built-in defaults.
   Patterns shared by every repo go to `ignore/_default.repoignore`.
3. Save the proposals to `ignore/`, then run `git_onboard.py preview`: it applies COG's built-in
   defaults plus your patterns to each file list with gitignore semantics and prints, per repo, files not
   parsed (unsupported type), excluded by built-ins, excluded by each of your patterns, kept, and any
   pattern that matched nothing. "Kept" counts parseable source only; the server's `fileCount` also
   includes config files, so it will be higher.
   Show **one table for the batch** from that output (gate **G2**). Let the user open any repo's detail.
   One confirmation per batch.
4. Local mode: write the confirmed patterns to `<repo>/.repoignore` (merged with an existing file).

Keep each repo's patterns under 10,000 characters (server limit); prefer `**/dir/` over long file lists.

---

## Step 5 — Ingest

### Git link

```bash
python3 <skill dir>/scripts/git_onboard.py run --project <uuid> --max-inflight 5 --interval 60
```

`run` loops until every selected repo is `indexed` or out of retries:

- connects repos (`POST <apiBase>/code-ontology/generate-from-git` with `projectUuid, name, repoUrl,
  gitBranch, gitProvider, gitToken?, ignorePatterns?`). The backend creates the code ontology and starts
  the first sync itself;
- keeps at most `--max-inflight` ingests running at once (start with 5; the analyzer and embedding queue
  are shared — raise it only if status keeps up);
- polls status and retries (Step 6).

Run it in the background for large batches and report progress from `log.jsonl`. If the session stops,
re-running the same command resumes: connected repos are never re-created.

### Local

Prerequisites: Python 3.10+, `uvx` (from uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`), git.
On Windows run under WSL. Then per repo:

```bash
uvx --from git+https://github.com/accionlabs/breezeai-cog breezeai-cog repo-to-json-tree \
  --repo <repo path> --out <output dir> [--capture-templates] \
  [--upload --uuid <projectUuid> --baseurl <apiBase>]      # automatic upload; key from env API_KEY
```

- Statements are captured by default (`--no-capture-statements` turns them off — don't).
- Add `--capture-templates` for UI repos with markup views (Step 1).
- Without `--upload` the parser writes `<repo>-project-analysis.ndjson.gz`; the user uploads it at
  `<uiBaseUrl>/code-ontology/<projectUuid>?page=1` (substitute real values).
- Pass the API key as env `API_KEY=…` for the command only; don't put it on the command line.
- After an automatic upload, the server still ingests asynchronously. Add the repo to the state file
  with `"status": "uploaded"` and `"displayName"` set to the name the parser used (the repo folder name);
  `git_onboard.py status` then matches it to its code ontology by name and tracks it like a git-linked
  repo (Step 6). Retries don't apply to local uploads — on `error`, re-run the parser.

Common local failures: `uvx: command not found` → install uv; Python too old → `uv python install 3.12`;
no ndjson produced → wrong `--out` or no supported files; `401` → bad API key; `404 Project not found` →
wrong project UUID. Surface errors verbatim.

---

## Step 6 — Status, stalls and retries

Status comes from `GET <apiBase>/code-ontology?filters[projectUuid][$eq]=<uuid>&selectFields=_id,name,fileGraphStatus,statusMessage,failedStep,fileCount,classCount,functionCount,updatedAt`
(`git_onboard.py status` wraps it and updates `repos.json`).

| `fileGraphStatus` | Meaning | State |
|---|---|---|
| `started`, `node_creation`, `relationship_creation`, `creating_embeddings`, `metadata_addition` | ingest running | `ingesting` |
| `active` | done | `indexed` |
| `error` | failed — read `failedStep` + `statusMessage` | `error` |

- **Errored** → retry: `GET /code-ontology/check-update/:id` for the latest commit, then
  `POST /code-ontology/sync/:id {incomingCommitId}`. Up to `--max-retries` (default 2), then leave it as
  `error` and report the reason.
- **Suspected stall** → a repo `ingesting` with no stage change for 30 minutes is probed with the same
  `POST /sync/:id`. The backend answers **409** while the ingest's heartbeat is fresh (it is just big) and
  starts a new sync only if the old one has died. So the probe is safe; the log records `still_running` or
  `retried`.
- `connect_failed` (HTTP error on connect, e.g. bad token or URL) → fix the cause, set the repo back to
  `discovered`, re-run.

Report progress as counts (`indexed=…, ingesting=…, error=…`) rather than per-repo lines once there are
more than ~10 repos.

---

## Step 7 — Audit

For every `indexed` repo (sample if there are many, but always list problems for all):

- **Counts:** files, classes, functions from the status row; flag zero classes/functions (unsupported
  language or everything ignored).
- **Expected vs. indexed files:** compare the tree / local file count minus excluded patterns with
  `fileCount`; explain large gaps.
- **Templates:** for UI repos, check `.html` / `.cshtml` / `.aspx` / `.vue` File nodes exist
  (`Get_Code_Nodes_By_Label` label `File`, filter on path). Missing → re-onboard that repo locally with
  `--capture-templates`.
- **Noise that got through:** large vendored files in the File list (library names, versions in names) →
  add patterns, `PUT <apiBase>/code-ontology/:id {"ignorePatterns": …}`, then re-sync (Step 6).

For a deep single-repo audit (ghost files after re-index, LOC deltas against an ndjson), run
`/breeze:code-ontology-audit-check <repo>`.

Record audit results per repo in `repos.json` (`audit: {ok, notes[]}`).

---

## Step 8 — Report and next steps

Summarise: repos indexed / errored / unsupported / skipped, files and LOC, any template or noise issues,
and where the state and log live. Then:

- One or two repos → the next skill per repo type (`generate-functional-from-ui` for a UI,
  `generate-functional-from-backend` for a service, …).
- Several repos, a monorepo, or a whole estate → `/breeze:onboard-project`, which classifies units,
  detects personas once, and runs the functional, design and architecture skills in order with its own
  resumable plan.

## What this skill does NOT do

- Functional, design or architecture graphs (see `/breeze:onboard-project`).
- Documents (use `/breeze:analyze-functional` or `/breeze:visual-to-text`).
- Store git tokens anywhere except the Breeze repo record the user asked to create.
