---
name: onboard-repository
description: >
  Get a source repository into the Breeze code graph for the current
  project. Wraps the Python `breezeai-cog` parser (run on demand via
  `uvx`) with `--capture-statements` so method-level statements are
  available for downstream skills (generate-functional-from-ui,
  generate-functional-from-backend, generate-code, search). Supports
  two upload modes: automatic (cog streams to the backend, needs an
  API key) or manual (cog writes a gzipped ndjson file locally and the
  user uploads it via the Breeze UI at /code-ontology/<projectUuid>).
  API key is optional — collected on-demand only if the user picks
  automatic mode. Requires Python 3.10+, uv (provides uvx), and git on
  PATH (on Windows, run under WSL); resolves the target repo from a
  path argument or the current directory. Run once per repo. Re-run to
  re-index after large changes.
  Use when: "onboard repo", "upload repository", "index repo into
  breeze", "add repo to project", "ingest codebase", "register code
  graph", or whenever a Breeze skill reports the project has no code
  ontology yet.
---

## What this skill does

Uploads a single source repository into the Breeze **code graph** for
the current project, capturing files, classes, functions, route
decorators, call chains, AND method-level statements (the
`--capture-statements` flag). The captured graph is what every
downstream Breeze skill reads from:

- `/breeze:generate-functional-from-ui`
- `/breeze:generate-functional-from-backend`
- `/breeze:deprecated-cluster-pipeline` *(retired — do not use)*
- `/breeze:generate-code`
- `/breeze:search`
- `/breeze:analyze-functional`

**Run this once per repo** that you want Breeze to know about. For a
multi-repo system (one frontend + N backends), invoke the skill once
per repo. Re-run after large refactors or new feature merges if the
graph has gone stale.

This skill **does not** upload documents. Document onboarding is
handled implicitly by `/breeze:analyze-functional` (which can ingest
PDFs, markdown, and other text inputs as part of the analysis flow)
and `/breeze:visual-to-text` (which converts UI design visuals into
structured user stories that feed into the same flow).

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

> **API key:** this skill additionally needs a Breeze `apiKey` only if you choose **automatic upload** mode (the CLI streams to the backend). Manual mode needs no key. Collect it on-demand as described below.

URLs (`apiBase`, `uiBaseUrl`) come from `breeze.config.json` at the
plugin root, overridable per-project via `.breeze.json`. See
`CLAUDE.md` → "Service URLs" for the full rule.
Throughout this skill, `<apiBase>` and `<uiBaseUrl>` are placeholders
the LLM substitutes at runtime — don't hardcode the literal hosts.

## Step 1 — Pick the upload mode

This skill runs the Python `breezeai-cog` parser (via `uvx`) to parse
the repo into a gzipped ndjson file. There are **two ways** to get
that data into the Breeze backend, and the user picks which one based
on whether they have an API key handy:

### Mode A — Automatic upload (cog streams to backend)

Requires an `apiKey` in `.breeze.json`. The parser does not
authenticate via Keycloak OAuth like the MCP tools — it needs an
explicit key (passed as `--user-api-key`, sent as the `api-key`
header).

1. Read `.breeze.json`. If `apiKey` is present → set
   `uploadMode = "automatic"` and continue to Step 2.
2. If `apiKey` is missing, prompt the user with **both options**:

   > This skill can either upload your code graph automatically (needs
   > a Breeze API key), or generate the ndjson locally so you can
   > upload it manually via the Breeze UI. Pick one:
   >
   > **A. Paste API key now (recommended for repeat onboardings)** —
   > generate one at **`<uiBaseUrl>/mcp/generate/key`** and paste it.
   > I'll save it to `.breeze.json` for next time.
   >
   > **B. Skip — I'll upload manually via the UI** — I'll just
   > generate the gzipped ndjson file locally, and at the end
   > I'll give you the upload URL.

3. Based on the choice:
   - **A:** save the pasted key to `.breeze.json` under `apiKey` (no
     echo back, "API key saved" only) and set
     `uploadMode = "automatic"`.
   - **B:** set `uploadMode = "manual"` and continue without writing
     anything to `.breeze.json`.

### Mode B — Manual upload (UI)

When `uploadMode = "manual"`, this skill will run the parser
**without** `--upload`, producing only the local
`<repo>-project-analysis.ndjson.gz` file. At the end (Step 6), it
points the user at the Breeze UI to upload it:

```
<uiBaseUrl>/code-ontology/<projectUuid>?page=1
```

**Security (Mode A only):** Never print the key in output or commit
it. Make sure `.breeze.json` is in `.gitignore`.

## Step 2 — Verify prerequisites (Python + uv + git)

The parser is the Python **`breezeai-cog`**, run on demand via **`uvx`** — no Node.js, no global install, no runtime-version pinning. `uvx` fetches and runs `breezeai-cog` from GitHub in an ephemeral, isolated environment each time (cached per version after the first run). **Verify the toolchain is present; STOP and ask the user only if something is missing.**

> **Windows → run under WSL.** The parser and `uvx` expect a POSIX shell. If the user is on native Windows (PowerShell/cmd), tell them to re-run this skill from a **WSL** terminal.

### 2a. Check the toolchain

```bash
python3 --version   # need 3.10+
uvx --version       # uv provides uvx
git --version       # must be on PATH (uvx installs from git+https://…)
```

### 2b. If `uvx` is missing — install uv

`uvx` ships with **uv**. Install it, then re-check `uvx --version`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After install, `uvx` lives in `~/.local/bin` — ensure that's on `PATH` (open a new shell, or `source ~/.bashrc`). uv can also provision Python if needed: `uv python install 3.12`.

### 2c. STOP conditions

- **Python < 3.10 or missing** → ask the user to install Python 3.10+ (or `uv python install 3.12` once uv is present).
- **git missing** → ask the user to install git (uvx needs it to clone `git+https://github.com/accionlabs/breezeai-cog`).
- **native Windows, no WSL** → ask the user to re-run under WSL.

No runtime activation prefix is needed (unlike the old Node CLI) — `uvx` is self-contained, so Step 5's commands run as-is in any shell where `uvx` is on `PATH`.

## Step 3 — Resolve the target repo

Resolve the **absolute path of the repo to upload** in this order:

1. **Explicit argument** — if the user passed a path
   (`/breeze:onboard-repository /path/to/repo`), validate that the
   path exists and looks like a source repo:
   - has a `.git` directory, OR
   - has a recognizable manifest (`package.json`, `pom.xml`,
     `pyproject.toml`, `requirements.txt`, `go.mod`, `composer.json`,
     `Cargo.toml`, etc.)
2. **Current working directory** — if the cwd itself looks like a
   source repo (same checks as 1), confirm with the user:
   *"Onboard the current directory `<cwd>` as a Breeze repo?"*
3. **Ask the user** — single prompt: *"Provide the absolute path to
   the repo you want to onboard."* Do not guess across siblings.

If the resolved path is the **plugin working directory itself** (i.e.
the user is sitting in the Breeze plugin repo, not their target
project), warn them and ask them to re-confirm — they almost
certainly want a different path.

Before running, **show the user a one-line summary of what will
happen** and ask them to confirm:

> About to onboard repo `<resolved-path>` into Breeze project
> `<projectUuid>` using API base `<apiBase>`. This will index files,
> classes, functions, call chains, and method-level statements. Large
> repos can take several minutes. Proceed? [y/N]

Wait for confirmation before running the command.

## Step 4 — Suggest related repos (brownfield onboarding)

Brownfield projects almost always have **more than one repo** — a
frontend plus one or more backends, or a set of microservices. After
the user confirms the first repo, gently surface this:

> Most projects have a frontend + one or more backend repos. After
> this upload, you can onboard the others by re-running
> `/breeze:onboard-repository <other-repo-path>`. The
> `/breeze:generate-functional-from-ui` and
> `/breeze:generate-functional-from-backend` skills work best when
> every repo in the system is indexed.

This is informational — do not block on it. Continue with the upload.

## Step 4.5 — Configure exclusions (`.repoignore`)

The generator has **no `--exclude` CLI flag**. Exclusions are driven by a
gitignore-style **`.repoignore`** file at the repo root, which the generator
parses and merges with its **built-in** `.repoignore`. The built-in already
skips `.git/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `target/`,
`.gradle/`, `tests/`, `/docs/`, `*.csv`, images, `.env*`, etc. — so common
dependency/build/test noise is handled automatically.

The parser only handles its **supported source languages** — **C#** (+ ASP.NET, Web Forms, WCF, GraphQL), **Java** (+ Spring Boot, JAX-RS, Vert.x), **Python** (+ FastAPI), **TypeScript/JavaScript** (+ Angular, React, NestJS, Express, LoopBack, GraphQL), and **VB** (+ VB ASP.NET). Other languages (Go, PHP, Perl, Ruby, …) and non-source artifacts (`.json`, `.md`, PDFs) are never turned into code nodes even without an ignore entry. (Run `uvx --from git+https://github.com/accionlabs/breezeai-cog breezeai-cog capabilities` for the authoritative, live list.) You still want a `.repoignore` when:

- a folder contains **source files you don't want indexed** — generated code,
  vendored copies, scratch/planning dirs, sample apps, or a previous tool's
  output that happens to hold `.java`/`.js`/etc.;
- a large generated/output folder would needlessly slow the directory walk;
- the user explicitly names folders to skip.

**What to do before running:**

1. Check for an existing `<repo>/.repoignore` — if present, honor it (the tool
   merges it automatically; just tell the user it's in effect).
2. Scan the repo root for obvious non-source / generated / output folders
   (e.g. a tool's output dir, `merge_plan/`, `*-output/`, a checkpoint folder)
   and any secrets file (`.breeze.json` holds the apiKey — never index it).
3. If you find any, **propose a `.repoignore`** listing them and write it after
   the user confirms (don't silently exclude — show the list). Use
   gitignore syntax: a trailing `/` means "directory, matched anywhere"
   (`merge_plan/` → skipped at any depth); a leading `/` anchors to repo root.

```
# example <repo>/.repoignore
.breeze-p3-output/      # generated functional-graph payloads (not source)
merge_plan/             # scratch / planning folder
.breeze.json            # contains apiKey — never index
```

Negation (`!pattern`) is **not** supported by the generator. Skipping this
step is fine for a clean single-module repo; it matters most for large
monorepos or trees that mix source with generated output.

## Step 5 — Run the parser

No activation prefix is needed — `uvx` runs `breezeai-cog` self-contained in any shell where `uvx` is on `PATH`. The exact command depends on `uploadMode` from Step 1. The parser writes a **single gzipped file** `<repo-name>-project-analysis.ndjson.gz` into `--out` (if `--out` is omitted it defaults to the repo's **parent** directory).

### Mode A — `uploadMode = "automatic"`

Read `apiKey`, `projectUuid`, and `apiBase` from `.breeze.json`, then run:

```bash
uvx --from git+https://github.com/accionlabs/breezeai-cog breezeai-cog repo-to-json-tree \
  --repo <resolved-repo-path> \
  --out <output-path> \
  --capture-statements \
  --upload \
  --user-api-key <apiKey> \
  --uuid <projectUuid> \
  --baseurl <apiBase>
```

### Mode B — `uploadMode = "manual"`

Omit the `--upload`, `--user-api-key`, `--uuid`, and `--baseurl` flags. The parser then only analyzes the repo and writes the gzipped ndjson locally — no network call:

```bash
uvx --from git+https://github.com/accionlabs/breezeai-cog breezeai-cog repo-to-json-tree \
  --repo <resolved-repo-path> \
  --out <output-path> \
  --capture-statements
```

**Flag rationale:**

- `--repo` — absolute path resolved in Step 3
- `--out <dir>` — directory for the gzipped ndjson (`<repo-name>-project-analysis.ndjson.gz`). Optional; defaults to the repo's **parent**. Pick a writable dir you can point the user at for Mode B (e.g. the repo's parent, or a scratch folder).
- `--upload` *(Mode A only)* — after writing the file locally, streams it to the Breeze backend
- `--capture-statements` — **mandatory in both modes**. Without it the parser captures method signatures only, not their bodies. Downstream skills (especially `generate-functional-from-backend`) need statement-level data to extract routes, queue env vars, cron expressions, side effects, and call chains. Re-indexing without this flag silently degrades the graph.
- `--user-api-key`, `--uuid`, `--baseurl` *(Mode A only)* — credentials + project link from `.breeze.json` (also readable from env `API_KEY` / `BREEZE_API_URL`).
- Optional: `--language <lang>` (repeatable) to restrict languages; `--jobs <N>` to cap worker processes; `--verbose` for DEBUG logs.

**Run it foregrounded so the user can see progress.** Large repos
(100K+ LOC) can take 5–15 minutes. If the command fails, surface the
error verbatim — don't paraphrase. Common failure modes:

| Symptom | Likely cause | Fix | Mode |
|---|---|---|---|
| `uvx: command not found` | uv not installed | Install uv (Step 2b: `curl -LsSf https://astral.sh/uv/install.sh \| sh`), then re-open the shell | both |
| `error: Python 3.10+ required` / version-related import errors | Python too old | Install Python 3.10+ (`uv python install 3.12`) | both |
| First run pauses on `Resolved … packages` / `Building breezeai-cog` | `uvx` cloning + building `breezeai-cog` from GitHub (one-time per version; cached after) | Wait — subsequent runs reuse the cache | both |
| `fatal: ... git ...` during `--from git+https://…` | git missing / no network | Install git; check connectivity to github.com | both |
| No `<repo>-project-analysis.ndjson.gz` produced despite exit 0 | Wrong `--out` path, or all files skipped (unsupported languages) | Check `--out` is writable; run `… breezeai-cog capabilities` to confirm the repo's languages are supported | both |
| `401 Unauthorized` / `upload failed` | Wrong / expired API key | Delete the `apiKey` field from `.breeze.json` and re-run this skill — Step 1 will prompt again (or pick Mode B) | A |
| `404 Project not found` | Wrong projectUuid in `.breeze.json` | Re-run `/breeze:project setup` and re-link | A |
| `ECONNREFUSED` / DNS error on baseurl | Wrong `apiBase` | Check the value in `.breeze.json` | A |
| Upload errors on ingest (`fileGraphStatus: error`) | Backend-side stale Neo4j constraint (a known DB migration issue), not a cog/file fault | Escalate to the Breeze backend team; the local `.ndjson.gz` is valid | A |
| Hangs at "Uploading…" for many minutes | Large repo, slow link | Wait — cancel only if 30+ min with no progress | A |
| Parser errors during walk | Unsupported language / encoding | Surface verbatim; the ndjson written so far still uploads in Mode B | both |

## Step 6 — Finalize (mode-dependent)

### Mode A — verify the upload landed

After the command exits successfully, run a quick smoke test against
the code graph to confirm the repo is queryable:

```
Code_Graph_Search "<repo name>"   (via the Breeze MCP)
```

Expect at least one File node result. If the graph still appears
empty after a successful upload, ask the user to wait ~30 seconds
for indexing and try again — the upload returns when bytes land,
indexing finishes shortly after.

### Mode B — hand off the ndjson for manual upload

The parser has finished writing `<output-path>/<repo-name>-project-analysis.ndjson.gz` but the backend doesn't have the data yet. Tell the user (substitute the real file path):

> ✅ Generated `<repo-name>-project-analysis.ndjson.gz` at `<output-path>`. To finish onboarding, upload it via the Breeze UI:
>
>   **`<uiBaseUrl>/code-ontology/<projectUuid>?page=1`**
>
> Drop that `.ndjson.gz` file into the upload area on that page. Until you do this, downstream skills like `/breeze:generate-functional-from-ui` and `/breeze:search` will report "no code ontology" because the graph is still empty.

Substitute the actual `uiBaseUrl` (from `.breeze.json` → `breeze.config.json`
→ `https://ai.accionbreeze.com`) and `projectUuid` (from
`.breeze.json`) into the URL before showing it — don't print the
placeholders verbatim.

After the user confirms they've uploaded, optionally run the same
`Code_Graph_Search` smoke test as Mode A to confirm the manual
upload landed.

## Step 7 — Tell the user what to do next

Present a clear next-step menu based on what kind of repo was just
onboarded. **In Mode B, gate this on the user having completed the
manual UI upload** — none of the downstream skills work until the
graph is populated.

> ✅ Repo `<name>` is now indexed in Breeze project `<projectUuid>`.
>
> **Next steps depend on the repo type:**
>
> - **Frontend repo** → run
>   `/breeze:generate-functional-from-ui <repo-path>` to generate the
>   User-persona side of the functional graph.
> - **Backend repo** → run
>   `/breeze:generate-functional-from-backend <repo-path>` to
>   generate the System-persona side (REST + queues + cron + WebSocket
>   + webhooks).
> - **More repos to onboard?** Re-run `/breeze:onboard-repository
>   <other-repo-path>` for each one.
> - **Exploring an existing graph?** Use `/breeze:search`,
>   `/breeze:analyze-functional`, or `/breeze:analyze-architecture`.

If the user has a multi-repo system, suggest the recommended order:

1. Onboard the frontend repo first (so the UI pass has it)
2. Onboard each backend repo
3. Run `/breeze:generate-functional-from-ui` on the frontend
4. Run `/breeze:generate-functional-from-backend` on each backend
5. Run `/breeze:validate-functional-graph` to check the result
6. Optionally run `/breeze:generate-spec` to export the graph

## What this skill does NOT do

- **Document upload** — PDFs, markdown specs, and other text inputs
  are handled by `/breeze:analyze-functional` (which ingests them as
  part of the analysis flow) and `/breeze:visual-to-text` (which
  converts design visuals into structured user stories that feed the
  analysis flow). Do not try to upload documents through this skill.
- **Functional graph generation** — this skill only populates the
  *code* graph. Use `/breeze:generate-functional-from-ui` /
  `/breeze:generate-functional-from-backend` to derive functional
  scenarios from the indexed code.
- **Multi-repo batch upload** — this skill processes one repo at a
  time. For a multi-repo system, invoke it once per repo. The
  per-invocation confirmation is intentional — uploads can be slow
  and we want the user to acknowledge each one.

## See also

- `/breeze:project setup` — must be run first to create `.breeze.json`
  and link a `projectUuid`. The API key is **not** collected there
  any more; this skill prompts for it in Step 1 when needed.
- `/breeze:generate-functional-from-ui` — next step after onboarding
  a frontend repo
- `/breeze:generate-functional-from-backend` — next step after
  onboarding a backend repo
- `/breeze:analyze-functional` — for ingesting documents and
  analyzing requirements against the existing graph
- `/breeze:visual-to-text` — for converting UI design visuals into
  user stories
