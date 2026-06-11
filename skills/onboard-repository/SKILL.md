---
name: onboard-repository
description: >
  Get a source repository into the Breeze code graph for the current
  project. Wraps the `breeze-code-ontology-generator` CLI with
  `--capture-statements` so method-level statements are available
  for downstream skills (generate-functional-from-ui,
  generate-functional-from-backend, generate-code, search). Supports
  two upload modes: automatic (CLI streams to the backend, needs an
  API key) or manual (CLI writes ndjson locally and the user uploads
  via the Breeze UI at /code-ontology/<projectUuid>). API key is
  optional — collected on-demand only if the user picks automatic
  mode. Verifies Node.js is exactly v22.x before running (Node 24
  fails silently due to a tree-sitter native-binding + ESM-TLA
  incompatibility) and resolves the target
  repo from a path argument or the current directory. Run once per
  repo. Re-run to re-index after large changes.
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

This skill runs the `breeze-code-ontology-generator` CLI to parse the
repo into an ndjson tree. There are **two ways** to get that tree
into the Breeze backend, and the user picks which one based on
whether they have an API key handy:

### Mode A — Automatic upload (CLI streams to backend)

Requires an `apiKey` in `.breeze.json`. The CLI does not authenticate
via Keycloak OAuth like the MCP tools — it needs an explicit key.

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
   > generate the ndjson locally in `./breezeai/`, and at the end
   > I'll give you the upload URL.

3. Based on the choice:
   - **A:** save the pasted key to `.breeze.json` under `apiKey` (no
     echo back, "API key saved" only) and set
     `uploadMode = "automatic"`.
   - **B:** set `uploadMode = "manual"` and continue without writing
     anything to `.breeze.json`.

### Mode B — Manual upload (UI)

When `uploadMode = "manual"`, this skill will run the CLI **without**
`--upload`, producing only the local ndjson tree under `./breezeai/`.
At the end (Step 6), it points the user at the Breeze UI to drop the
ndjson in:

```
<uiBaseUrl>/code-ontology/<projectUuid>?page=1
```

**Security (Mode A only):** Never print the key in output or commit
it. Make sure `.breeze.json` is in `.gitignore`.

## Step 2 — Activate Node.js v22.x

The CLI requires **Node.js 22 specifically**. Node 24+ fails with
`ERR_REQUIRE_ASYNC_MODULE` (or silently exits depending on stdout
buffering) because tree-sitter native bindings became ESM with
top-level await. Node 20 and older fail with syntax/ESM errors.

**Try to activate Node 22 automatically. STOP and ask the user only
if no version manager is installed.**

### 2a. Check what's on PATH

```bash
node --version
```

If the output is `v22.x.x`, the system default is already correct —
record an empty activation prefix and skip to Step 3.

### 2b. Try managers in order, capture an activation prefix

If `node` is missing or any other major, try each manager in this
order. **Each Bash tool call is a fresh shell**, so the manager's
init must be sourced *in the same command* as the `use 22`:

| Manager | Detect | Activate + verify |
|---|---|---|
| nvm | `[ -s "$HOME/.nvm/nvm.sh" ]` | `. "$HOME/.nvm/nvm.sh" && nvm use 22 && node --version` |
| fnm | `command -v fnm >/dev/null` | `eval "$(fnm env)" && fnm use 22 && node --version` |
| volta | `command -v volta >/dev/null` | `volta run --node 22 node --version` |

If a manager exists but reports `version "22" is not installed` (or
similar), install it first, then retry:

- nvm: `nvm install 22 && nvm use 22`
- fnm: `fnm install 22 && fnm use 22`
- volta: `volta install node@22`

Once one of them prints `v22.x.x`, **remember the exact activation
prefix that worked** — you'll prepend it to every CLI call in Step 5,
because fresh shells lose the activation. Examples:

- nvm → prefix is `. "$HOME/.nvm/nvm.sh" && nvm use 22 >/dev/null && `
- fnm → prefix is `eval "$(fnm env)" && fnm use 22 >/dev/null && `
- volta → wrap the whole CLI invocation in `volta run --node 22 …`
  instead of using a prefix

### 2c. STOP — no manager available

If none of nvm/fnm/volta is detected, surface this and stop:

> Your current Node is `<version>`. The CLI requires Node 22. I
> couldn't find nvm, fnm, or volta on your machine to switch
> automatically. Install one of them (recommended: nvm) and re-run
> this skill, or download Node 22 LTS from https://nodejs.org/.

Node 22 is the only runtime this skill needs. (Python with numpy /
scikit-learn is only required by the retired
`/breeze:deprecated-cluster-pipeline` — not by this skill.)

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

## Step 5 — Run the generator

**Prepend the activation prefix from Step 2** to every command below.
If Step 2a succeeded (system default is already Node 22), the prefix
is empty and the command starts at `npx -y …`. Examples shown use the
nvm prefix.

The exact command depends on `uploadMode` from Step 1.

### Mode A — `uploadMode = "automatic"`

Read `apiKey`, `projectUuid`, and `apiBase` from `.breeze.json`, then
run:

```bash
. "$HOME/.nvm/nvm.sh" && nvm use 22 >/dev/null && \
  npx -y github:accionlabs/breeze-code-ontology-generator repo-to-json-tree \
  --repo <resolved-repo-path> \
  --out breezeai \
  --upload \
  --capture-statements \
  --user-api-key <apiKey> \
  --uuid <projectUuid> \
  --baseurl <apiBase>
```

### Mode B — `uploadMode = "manual"`

Omit the `--upload`, `--user-api-key`, `--uuid`, and `--baseurl`
flags. The CLI then only parses the repo and writes the ndjson tree
to `./breezeai/` — no network call:

```bash
. "$HOME/.nvm/nvm.sh" && nvm use 22 >/dev/null && \
  npx -y github:accionlabs/breeze-code-ontology-generator repo-to-json-tree \
  --repo <resolved-repo-path> \
  --out breezeai \
  --capture-statements
```

**Flag rationale:**

- `--repo` — absolute path resolved in Step 3
- `--out breezeai` — local output directory for the intermediate JSON
  tree (always written; this is what the user uploads in Mode B)
- `--upload` *(Mode A only)* — streams the parsed graph to the Breeze
  backend in addition to writing it locally
- `--capture-statements` — **mandatory in both modes**. Without this
  flag, the generator only captures method signatures, not their
  bodies. Downstream skills (especially
  `generate-functional-from-backend`) need statement-level data to
  extract route decorators, queue env vars, cron expressions, side
  effects, and call chains. Re-uploading without this flag silently
  degrades the graph.
- `--user-api-key`, `--uuid`, `--baseurl` *(Mode A only)* —
  credentials and project link from `.breeze.json`

**Run it foregrounded so the user can see progress.** Large repos
(100K+ LOC) can take 5–15 minutes. If the command fails, surface the
error verbatim — don't paraphrase. Common failure modes:

| Symptom | Likely cause | Fix | Mode |
|---|---|---|---|
| `SyntaxError: Unexpected token` from npx | Node < 22 | Switch to Node 22.x (Step 2) | both |
| Silent exit with no output beyond `npm warn …` lines | Node 24 or newer — tree-sitter native bindings can't be loaded via `require()` because the bindings are ESM with top-level await | Switch to Node 22.x (Step 2). Don't trust a "completed with exit 0" if no `./breezeai/` directory was created | both |
| `Error [ERR_REQUIRE_ASYNC_MODULE]: ... tree-sitter-c-sharp/bindings/node/index.js` | Same root cause — bindings use top-level await; surfaces visibly on some Node versions | Switch to Node 22.x | both |
| `401 Unauthorized` | Wrong / expired API key | Delete the `apiKey` field from `.breeze.json` and re-run this skill — Step 1 will prompt again (or pick Mode B) | A |
| `404 Project not found` | Wrong projectUuid in `.breeze.json` | Re-run `/breeze:project setup` and re-link | A |
| `ECONNREFUSED` / DNS error on baseurl | Wrong `apiBase` | Check the value in `.breeze.json` | A |
| Hangs at "Uploading…" for many minutes | Large repo, slow link | Wait — uploads are streamed; cancel only if 30+ min with no progress | A |
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

The CLI has finished writing `./breezeai/` but the backend doesn't
have the data yet. Tell the user:

> ✅ ndjson generated under `./breezeai/`. To finish onboarding,
> upload it via the Breeze UI:
>
>   **`<uiBaseUrl>/code-ontology/<projectUuid>?page=1`**
>
> Drop the contents of `./breezeai/` into the upload area on that
> page. Until you do this, downstream skills like
> `/breeze:generate-functional-from-ui` and `/breeze:search` will
> report "no code ontology" because the graph is still empty.

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
