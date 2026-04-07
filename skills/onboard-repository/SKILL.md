---
name: onboard-repository
description: >
  Upload a source repository into the Breeze code graph for the
  current project. Wraps the `breeze-code-ontology-generator`
  CLI with `--capture-statements` so method-level statements are
  available for downstream skills (generate-functional-from-ui,
  generate-functional-from-backend, generate-code, search). Verifies
  Node.js 22+ before running and resolves the target repo from a path
  argument or the current directory. Run once per repo. Re-run to
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
- `/breeze:generate-functional-from-code` *(deprecated)*
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

## Guard

Read `.breeze.json` from the **plugin working directory**. Required
fields:

- `apiKey`
- `projectUuid`
- `apiBase` (defaults to `https://isometric-backend.accionbreeze.com`)

If any are missing, tell the user to run `/breeze:setup-project`
first and stop.

## Step 1 — Verify Node.js 22+

The `breeze-code-ontology-generator` CLI requires Node.js 22 or
later. Check the installed version:

```bash
node --version
```

- If the output is `v22.x.x` or higher → continue.
- If the output is lower (e.g. `v20.x.x`, `v18.x.x`) → STOP and tell
  the user how to upgrade. Do not attempt to run the upload — it will
  fail with cryptic ESM/syntax errors. Suggested upgrade paths:
  - **nvm**: `nvm install 22 && nvm use 22`
  - **fnm**: `fnm install 22 && fnm use 22`
  - **volta**: `volta install node@22`
  - **System install**: download from https://nodejs.org/
- If `node` is not installed at all → STOP and ask the user to install
  Node.js 22+ before continuing.

After the user upgrades, ask them to confirm and re-run the skill.

Node 22+ is the only runtime this skill needs. (Python with numpy /
scikit-learn is only required by the deprecated
`/breeze:generate-functional-from-code` cluster pipeline — not by
this skill.)

## Step 2 — Resolve the target repo

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

## Step 3 — Suggest related repos (brownfield onboarding)

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

## Step 4 — Run the generator

Read `apiKey`, `projectUuid`, and `apiBase` from `.breeze.json`, then
run:

```bash
npx github:accionlabs/breeze-code-ontology-generator repo-to-json-tree \
  --repo <resolved-repo-path> \
  --out breezeai \
  --upload \
  --capture-statements \
  --user-api-key <apiKey> \
  --uuid <projectUuid> \
  --baseurl <apiBase>
```

**Flag rationale:**

- `--repo` — absolute path resolved in Step 2
- `--out breezeai` — local output directory for the intermediate JSON
  tree (kept for debugging)
- `--upload` — sends the parsed graph to the Breeze backend in
  addition to writing it locally
- `--capture-statements` — **mandatory**. Without this flag, the
  generator only captures method signatures, not their bodies.
  Downstream skills (especially `generate-functional-from-backend`)
  need statement-level data to extract route decorators, queue env
  vars, cron expressions, side effects, and call chains. Re-uploading
  without this flag silently degrades the graph.
- `--user-api-key`, `--uuid`, `--baseurl` — credentials and project
  link from `.breeze.json`

**Run it foregrounded so the user can see progress.** Large repos
(100K+ LOC) can take 5–15 minutes. If the command fails, surface the
error verbatim — don't paraphrase. Common failure modes:

| Symptom | Likely cause | Fix |
|---|---|---|
| `SyntaxError: Unexpected token` from npx | Node < 22 | Re-check Step 1 and upgrade |
| `401 Unauthorized` | Wrong / expired API key | Re-run `/breeze:setup-project` to refresh |
| `404 Project not found` | Wrong projectUuid in `.breeze.json` | Re-run `/breeze:setup-project` and re-link |
| `ECONNREFUSED` / DNS error on baseurl | Wrong `apiBase` | Check the value in `.breeze.json` |
| Hangs at "Uploading…" for many minutes | Large repo, slow link | Wait — uploads are streamed; cancel only if 30+ min with no progress |

## Step 5 — Verify the upload landed

After the command exits successfully, run a quick smoke test against
the code graph to confirm the repo is queryable:

```
Code_Graph_Search "<repo name>"   (via the Breeze MCP)
```

Expect at least one File node result. If the graph still appears
empty after a successful upload, ask the user to wait ~30 seconds
for indexing and try again — the upload returns when bytes land,
indexing finishes shortly after.

## Step 6 — Tell the user what to do next

After a successful upload, present a clear next-step menu based on
what kind of repo was just onboarded:

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

- `/breeze:setup-project` — must be run first to create
  `.breeze.json` and link the project
- `/breeze:generate-functional-from-ui` — next step after onboarding
  a frontend repo
- `/breeze:generate-functional-from-backend` — next step after
  onboarding a backend repo
- `/breeze:analyze-functional` — for ingesting documents and
  analyzing requirements against the existing graph
- `/breeze:visual-to-text` — for converting UI design visuals into
  user stories
