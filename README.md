# Breeze Plugin for Claude Code

A Claude Code plugin that integrates with the Breeze AI platform for functional graph management, code analysis, design analysis, and requirement tracing.

## Quick Start

### 1. Add the marketplace

In Claude Code, run:

```
/plugin marketplace add accionlabs/breezeai-claude-plugin
```

This registers the marketplace but does **not** install the plugin yet.

### 2. Install the plugin

```
/plugin install breeze
```

Pick `breeze` from the list when prompted. Claude Code downloads the plugin into your local plugin directory.

### 3. Activate the plugin

```
/plugin enable breeze
```

(If installation auto-enables it, this step is a no-op.)

### 4. Restart Claude Code

Plugin skills, hooks, and MCP servers are loaded at startup. **Quit Claude Code and start it again** so the new skills appear under `/breeze:*` and the Breeze MCP server is registered.

You can confirm everything loaded by running:

```
/plugin list
```

`breeze` should show as installed and enabled.

### 5. Initialize the workspace

```
/breeze:project setup
```

This walks you through:
- Authenticating the Breeze MCP (browser-based Keycloak sign-in; no API key to paste)
- Linking to an existing Breeze project or creating a new one
- Checking ontology status
- Pointing you at the right follow-up skill (onboard-repository,
  generate-functional-from-*, etc.)

The Keycloak token lasts roughly **7 days** from the last sign-in; after that any
`/breeze:*` skill will prompt you to re-run `/breeze:project auth`.

No API key is required at this stage — MCP-based skills authenticate
via Keycloak OAuth automatically. `/breeze:onboard-repository` only
needs an API key if you pick its **automatic upload** mode; the
**manual upload** mode generates ndjson locally and you upload via
the Breeze UI at `<uiBaseUrl>/code-ontology/<projectUuid>`. The
retired `/breeze:deprecated-cluster-pipeline` still needs a key if
you're resuming a historical run. In all cases the relevant skill
prompts on-demand and points you at `<uiBaseUrl>/mcp/generate/key`
if you don't have a key yet.

`<uiBaseUrl>` resolves from `breeze.config.json` at the plugin root
(default `https://ai.accionbreeze.com`). Override per-project by
setting `uiBaseUrl` in `.breeze.json`.

Your project UUID (and, once collected, your API key) is saved to
`.breeze.json` in the project root (gitignored).

### Updating the plugin

When a new version is released:

```
/plugin marketplace update accionlabs/breezeai-claude-plugin
/plugin update breeze
```

Then **restart Claude Code** again so the updated skills/hooks/MCP definitions are picked up.

## Available Skills

### Project management & setup

| Skill | Command | Description |
|-------|---------|-------------|
| **Project** | `/breeze:project [show \| list \| use <name> \| create <name> \| auth \| status \| setup]` | Canonical home for all project management. Sub-modes: `show` (active project), `list` (all accessible), `use <name\|uuid>` (switch and persist), `create <name> [--desc "..."]` (create and link), `auth` (re-authenticate MCP), `status` (full metadata report), `setup` (full bootstrap = auth + link/create + ontology check). No API key collected here (MCP uses Keycloak OAuth); does **not** upload repos or documents. |
| **Onboard Repository** | `/breeze:onboard-repository [repo-path]` | Get a source repository into the Breeze code graph. Wraps `breeze-code-ontology-generator` with `--capture-statements`, verifies Node.js is **exactly v22.x** (Node 24+ fails silently due to a tree-sitter ESM/TLA issue), and resolves the target repo from an argument or the current directory. Supports two modes: automatic (CLI streams to backend with an API key) or manual (CLI writes ndjson locally and you upload via the Breeze UI). API key is optional. Run once per repo (frontend + each backend). |

### Search & analysis

| Skill | Command | Description |
|-------|---------|-------------|
| **Search** | `/breeze:search <query>` | Smart-search across functional, design, code, and architecture graphs — routes to one graph, a subset, or all based on query intent. Default entry point for any question about the project. |
| **Impact Analysis** | `/breeze:impact-analysis [--detailed] <prompt>` | Structured cross-layer impact analysis (functional → design → code → architecture). Summary by default; `--detailed` emits a full document with Mermaid request-path / async-tail diagrams, per-ontology marker tables, a structured risk taxonomy, a QA test plan, schema-side (DDL) impact with a 🔴/🟡/🟢 verdict, and deploy-coordination notes. Accepts `--project <name\|uuid>`. |
| **Analyze Functional** | `/breeze:analyze-functional` | Analyze a requirement against the existing functional graph — coverage gaps, conflicts, dependencies, impact |
| **Analyze Architecture** | `/breeze:analyze-architecture` | Analyze a requirement against the architecture graph — impacted layers and components across 8 architecture layers |
| **Analyze Design** | `/breeze:analyze-design <Figma URL>` | Analyze UI/UX designs from Figma frames — functional summary, components, mapping to the functional graph, gap flags |

### Generate functional graph from a repo

The recommended approach is the **split pipeline** — one pass for the UI and one for each backend repo. The two passes are independent and merge automatically by outcome name in the functional graph.

| Skill | Command | Description |
|-------|---------|-------------|
| **Generate Functional from UI** | `/breeze:generate-functional-from-ui [repo-path]` | **Recommended for frontend repos.** Reads the UI codebase from the filesystem (Glob/Read/Grep), discovers routes + non-routed panels, and generates the **User-persona** side of the functional graph with full JSX coverage validation and API endpoints captured in `action.apis[]`. **Stack-aware:** SPA (React/Vue/Angular/Next) **and ASP.NET Web Forms (`.aspx`)** — for Web Forms it reads markup + code-behind + the SOAP service-proxy and captures the operation as the API (`type: SOAP`). Persona discovery and panel discovery are both hard gates with user confirmation. |
| **Generate Functional from Backend** | `/breeze:generate-functional-from-backend [repo-path]` | **Recommended for backend repos.** Detects the framework (LoopBack/NestJS/Express/Fastify/Spring/FastAPI/etc.) and discovers ALL entry-point types: REST routes, SQS/Kafka/RabbitMQ consumers and producers, cron workers, WebSocket handlers, webhook receivers, and internal service-to-service routes. Writes **System** / **External System** persona scenarios with side effects captured in `apis[]` (REST/GraphQL/gRPC/WebSocket/Event), plus a per-repo handoff log used for cross-repo producer/consumer correlation. Run once per backend repo. |
| **Deprecated Cluster Pipeline** *(do not use)* | `/breeze:deprecated-cluster-pipeline` | **Retired v1 cluster pipeline.** Kept only so historical in-progress runs can be resumed. The DBSCAN clustering step duplicates scenarios under realistic repo layouts, which is why this skill was retired. For all new work, use `/breeze:generate-functional-from-ui` and `/breeze:generate-functional-from-backend` above. |

Both new skills resolve their target repo in this order: explicit path arg → `targetRepos.frontend` / `targetRepos.backend.<name>` in `.breeze.json` → current working directory autodetect → prompt the user. Resolved paths are persisted to `.breeze.json` so re-runs do not re-prompt. Checkpoint files (`entrypoints.json`, `entrypoints_<repo>.json`, `backend_log_<repo>.json`) live next to `.breeze.json`, not inside the target repo.

### Generate from designs

| Skill | Command | Description |
|-------|---------|-------------|
| **Visual to Text** | `/breeze:visual-to-text` | Generate user stories from UI design visuals (Figma frames, PDF screens, images) — outputs structured stories in persona/outcome/scenario/step/action form |
| **Generate User Story from UI Design** | `/breeze:generate-userstory-from-uidesign` | Translate a UI design into user stories that describe functional intent |

### Update, validate, generate

| Skill | Command | Description |
|-------|---------|-------------|
| **Update Functional Graph** | `/breeze:update-functional-graph` | Create or update functional-graph nodes from code, documents, or Figma designs |
| **Validate Functional Graph** | `/breeze:validate-functional-graph` | Validate the functional graph against source documents — coverage, duplicates, persona quality, citation traceability |
| **Generate Code** | `/breeze:generate-code <feature>` | Generate code and test cases informed by the functional graph and code graph |
| **Generate Spec** | `/breeze:generate-spec` | Generate functional specification documents from the functional graph |

### Recommended pipelines

```
First-time onboarding of a brownfield full-stack project:
  /breeze:project setup                               # MCP auth + project link (no API key needed yet)
  /breeze:onboard-repository <frontend repo>          # offers automatic (API key) or manual (UI upload) mode; indexes code graph (once per repo)
  /breeze:onboard-repository <backend repo 1>
  /breeze:onboard-repository <backend repo 2>
  ...
  /breeze:generate-functional-from-ui       <frontend repo>
  /breeze:generate-functional-from-backend  <backend repo 1>
  /breeze:generate-functional-from-backend  <backend repo 2>
  ...
  /breeze:validate-functional-graph
  /breeze:generate-spec

Greenfield project (no code yet):
  /breeze:project setup
  /breeze:visual-to-text           # Figma / PDF / images → user stories
  /breeze:analyze-functional       # also ingests requirement documents

Adding a new requirement to an existing project:
  /breeze:impact-analysis          # cross-layer blast radius first
  /breeze:analyze-functional
  /breeze:analyze-architecture
  /breeze:update-functional-graph
  /breeze:generate-code

Switching / comparing projects:
  /breeze:project list                                # see what's available
  /breeze:project use "Lead Manager V2"               # persist the switch
  /breeze:search --project v1 how does X work         # one-shot, no .breeze.json change
  /breeze:search --project v2 how does X work
```

## Project resolution

Every project-bound skill resolves the active project per invocation. The full
rule lives in `CLAUDE.md` at the plugin root — skills defer to it rather than
duplicating the logic.

1. **`--project <uuid|name>`** anywhere in the prompt (names resolved via
   `Call_List_Project_`, case-insensitive substring).
2. **Bare UUID** anywhere in the prompt (used directly).
3. **Natural-language hint** — `for <project>: ...`, `on <project>: ...`,
   `in the <project> project ...`.
4. **`.breeze.json` fallback** — the persisted default.
5. **If nothing matches** — the skill lists accessible projects and asks you to
   pick. No hard error.

For (1)–(3), an unambiguous match is used **for that invocation only** —
`.breeze.json` is not touched. `.breeze.json` is mutated **only** by
`/breeze:project setup`, `/breeze:project use`, and `/breeze:project create`.
This lets different terminals / Claude sessions target different projects in
parallel without re-linking.

## Auto-Loading (No Flag Needed)

To avoid passing `--plugin-dir` every time, add this to your project's `.claude/settings.json`:

```json
{
  "plugins": ["./breeze-claude-plugin"]
}
```

## Setup for Teams

### Option A: Plugin inside your project repo

Place the `breeze-claude-plugin/` folder in your project repo. Everyone who clones the repo has it.

### Option B: Separate shared repo

Clone the plugin repo alongside your project:

```bash
git clone git@github.com:accionlabs/breeze-claude-plugin.git
claude --plugin-dir ../breeze-claude-plugin
```

## Notes

- `.breeze.json` may contain a Breeze API key once you've used a skill that needs one (currently `/breeze:onboard-repository`, and the retired `/breeze:deprecated-cluster-pipeline` if you're resuming a historical run). Add `.breeze.json` to `.gitignore`.
- The Breeze MCP server uses Keycloak OAuth; Claude Code handles sign-in automatically on the first MCP tool call and does **not** read `apiKey` from `.breeze.json`. MCP-only workflows never need an API key.
- API keys are collected **on-demand** by the skills that actually use them, with a prompt pointing at `<uiBaseUrl>/mcp/generate/key` (default `https://ai.accionbreeze.com/mcp/generate/key`; see `breeze.config.json`). No upfront paste during setup.
- The Keycloak token expires after roughly **7 days**. Expect to re-authenticate periodically via `/breeze:project auth`; skills will tell you when an MCP call hits a 401.
- All Breeze service URLs live in `breeze.config.json` at the plugin root (`uiBaseUrl`, `apiBase`). To repoint every skill at a different Breeze deployment, edit that single file — or override `uiBaseUrl` / `apiBase` per-project in `.breeze.json`.
- The plugin ships a **`CLAUDE.md`** at the root. Claude Code auto-loads it and it centralizes the project-resolution flow, the exempt-skills list, the auth-on-401 rule, and the `.breeze.json` mutation policy. Individual `skills/*/SKILL.md` files defer to it rather than duplicating the rule.
- The **Design** skills require a Figma MCP server to be configured separately.
- All skills except `/breeze:project` (in `setup` / `auth` / `list` / `create` modes) and `/breeze:visual-to-text` (reads a design + writes local stories, no MCP calls) require a resolvable project (see **Project resolution** above).
