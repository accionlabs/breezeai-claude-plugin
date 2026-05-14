---
name: setup-project
description: >
  Initialize or validate the Breeze workspace. Links .breeze.json to a
  Breeze project (UUID) and checks ontology readiness. MCP access uses
  Keycloak OAuth (handled automatically by Claude Code on the first MCP
  tool call), so no API key is collected here — skills that talk to
  non-MCP consumers (the ontology-generator CLI, the deprecated REST
  upsert path) prompt for the API key on-demand. Does NOT upload repos
  or documents — use /breeze:onboard-repository for code uploads, and
  /breeze:analyze-functional or /breeze:visual-to-text for document
  and design ingestion. Use when: first time setup, "init breeze",
  "setup breeze", or when any Breeze tool fails with authorization
  errors.
---

## Scope

This skill is responsible for **workspace bootstrap only**:

- Project linking (select existing or create new)
- Ontology readiness check
- Pointing the user at the right next-step skill based on what they
  want to do

**No API key is collected here.** MCP access is authenticated via
Keycloak OAuth — Claude Code handles the sign-in automatically on the
first MCP tool call and does **not** read `apiKey` from `.breeze.json`.
Skills that hit the non-MCP REST surface prompt for the key locally,
at the point of need, with the generation URL:

- `/breeze:onboard-repository` — only if the user picks **automatic
  upload** mode. The **manual upload** mode generates ndjson locally
  and the user uploads it via the Breeze UI at
  `<uiBaseUrl>/code-ontology/<projectUuid>` — no key required.
- `/breeze:deprecated-cluster-pipeline` (retired) — needs the key for
  its REST upsert path if resuming a historical run.

Keeping the prompt out of bootstrap means MCP-only and manual-upload
workflows never have to paste a secret.

AWS Bedrock credentials needed by `/breeze:deprecated-cluster-pipeline`
are likewise collected on-demand by that skill and are not part of
this bootstrap. (You should almost never need to run that skill — see
its own SKILL.md for the deprecation rationale.)

This skill does **NOT** upload repositories or documents. That
responsibility now lives in dedicated skills:

| You want to… | Use this skill instead |
|---|---|
| Upload a source repo into the code graph | `/breeze:onboard-repository` |
| Ingest a PDF / markdown / text document | `/breeze:analyze-functional` (handles document input as part of the analysis flow) |
| Convert a UI design visual into user stories | `/breeze:visual-to-text` |

If the user asks for any of those during setup, finish the bootstrap
steps first and then point them at the right skill in Step 3.

## Prerequisites

Read `.breeze.json` from the project root. If it exists and contains
`projectUuid`, skip to **Step 2 — Ontology Status Check**.

If the file doesn't exist yet, create it with an empty object (`{}`)
so subsequent steps can append fields. `apiKey` is intentionally not
required at this stage — it's collected on-demand by the skills that
actually use it.

### URL resolution (shared across all Breeze skills)

Breeze service URLs come from `breeze.config.json` at the plugin
root. The fields used by the skills are:

- `uiBaseUrl` — the Breeze web UI base (default
  `https://ai.accionbreeze.com`). Used for API-key generation, the
  manual code-graph upload page, and the ontology console.
- `apiBase` — the Breeze REST backend base (default
  `https://isometric-backend.accionbreeze.com`). Used by the
  ontology-generator CLI and the deprecated cluster pipeline.

**Resolution order** (each skill follows this when it needs a URL):

1. Field on `.breeze.json` (per-project override, if set).
2. Field on `breeze.config.json` at the plugin root (canonical default).
3. Built-in fallback string in the SKILL.md (last-resort hardcoded
   value; matches whatever was in `breeze.config.json` when the plugin
   was authored).

To repoint every skill at a different Breeze deployment, you only
need to change `breeze.config.json` (plugin-wide) or set
`uiBaseUrl` / `apiBase` in `.breeze.json` (per-project). Do **not**
edit URLs inside individual SKILL.md files.

## Step 1 — Project Linking

If `projectUuid` is missing from `.breeze.json`:

Ask: "Would you like to:
1. Select an existing project
2. Create a new project"

**Option 1 — Select existing:**

- Call `Call_List_Project_`
- Display the project list (name + UUID)
- User selects one → save `projectUuid` to `.breeze.json`

**Option 2 — Create new:**

- Ask for project name and description (optional)
- Call `Call_Create_Project_` with name and description
- Save returned `projectUuid` to `.breeze.json`

Confirm: "Project linked successfully."

## Step 2 — Ontology Status Check

With `projectUuid` in hand, check what the project already contains
so the user knows where to go next.

1. Call `Call_Get_Project_Details_` (or `Get_complete_functional_graph`
   via the Breeze MCP) to see what's already indexed.
2. Report the state plainly:

   - **Code ontology:** present or missing
   - **Functional graph:** populated (persona/outcome/scenario counts)
     or empty
   - **Design graph:** present or missing (if applicable)

**Do NOT attempt to upload anything from this skill.** Just report
what's there.

## Step 3 — Next-step guidance

Based on Step 2's findings, point the user at the right follow-up.

### Brownfield project (code exists, graph is empty)

If the user has an existing codebase they want Breeze to understand,
tell them explicitly:

> This looks like a brownfield project. To get value from Breeze you
> need to onboard your source repos into the code graph, then derive
> the functional graph from them.
>
> **Recommended flow:**
>
> 1. **Onboard each repo** with `/breeze:onboard-repository
>    <repo-path>`. Run this once per repo in your system — typically
>    one frontend plus one or more backends. It wraps the Breeze code
>    ontology generator with the required flags (including
>    `--capture-statements`) and verifies Node 22 (exactly v22.x —
>    not 24+) before running.
> 2. **Generate the functional graph from the UI repo** with
>    `/breeze:generate-functional-from-ui <frontend-path>` — produces
>    the User-persona side with full JSX coverage and API linking.
> 3. **Generate the functional graph from each backend repo** with
>    `/breeze:generate-functional-from-backend <backend-path>` —
>    produces the System / External System side, including REST
>    routes, SQS/Kafka consumers, cron workers, WebSocket handlers,
>    and webhooks. Run once per backend repo.
> 4. **Validate and export** with `/breeze:validate-functional-graph`
>    and `/breeze:generate-spec`.
>
> The two functional-from-* skills are independent — they merge by
> outcome name in the graph, so order between them doesn't matter.

Ask if the user wants to start onboarding a repo now. If yes, point
them at `/breeze:onboard-repository` — do NOT run the upload from
this skill.

### Greenfield project (no code yet)

If the user is starting from designs or documents instead of code:

> This looks like a greenfield project. To seed Breeze without code:
>
> - **UI designs** → use `/breeze:visual-to-text` to convert Figma
>   frames / PDFs / screenshots into structured user stories.
> - **Requirement documents** → use `/breeze:analyze-functional`,
>   which ingests documents as part of its analysis flow and can
>   upsert the extracted intent into the functional graph.
> - **Add code later** → when code starts to exist, come back and run
>   `/breeze:onboard-repository` followed by the
>   `generate-functional-from-ui` / `generate-functional-from-backend`
>   skills.

### Existing project with a populated graph

If the graph is already populated:

> Your project is ready. You can:
>
> - `/breeze:search` to explore the graph
> - `/breeze:analyze-functional` to analyze a new requirement
> - `/breeze:analyze-architecture` to check architecture impact
> - `/breeze:generate-code` to scaffold code for a feature
> - `/breeze:generate-spec` to export a functional specification

## What this skill does NOT do

- **Upload source code** — use `/breeze:onboard-repository`
- **Upload or ingest documents** — use `/breeze:analyze-functional`
- **Convert visuals to user stories** — use `/breeze:visual-to-text`
- **Generate the functional graph** — use
  `/breeze:generate-functional-from-ui` or
  `/breeze:generate-functional-from-backend`

Setup is intentionally narrow: bootstrap credentials, link the
project, tell the user where to go next. Every other responsibility
lives in its own skill.

## See also

- `/breeze:onboard-repository` — upload a source repo into the code
  graph (wraps the Breeze code ontology generator)
- `/breeze:generate-functional-from-ui` — generate User-persona
  scenarios from a frontend repo
- `/breeze:generate-functional-from-backend` — generate System-persona
  scenarios from a backend repo
- `/breeze:analyze-functional` — analyze requirements (including from
  documents) against the graph
- `/breeze:visual-to-text` — convert UI design visuals into user
  stories

