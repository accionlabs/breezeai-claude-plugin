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
/breeze:setup-project
```

This walks you through:
- Setting up your API key (generated at https://ai.accionbreeze.com/mcp/generate/key)
- Linking to an existing project or creating a new one
- Checking ontology status
- Optionally uploading your repository or documents

Your credentials are saved to `.breeze.json` in the project root (gitignored).

### Updating the plugin

When a new version is released:

```
/plugin marketplace update accionlabs/breezeai-claude-plugin
/plugin update breeze
```

Then **restart Claude Code** again so the updated skills/hooks/MCP definitions are picked up.

## Available Skills

### Setup

| Skill | Command | Description |
|-------|---------|-------------|
| **Setup Project** | `/breeze:setup-project` | Initialize the Breeze workspace — API key, project link, ontology status check, next-step guidance. Does **not** upload repos or documents. |
| **Onboard Repository** | `/breeze:onboard-repository [repo-path]` | Upload a source repository into the Breeze code graph. Wraps `breeze-code-ontology-generator` with `--capture-statements`, verifies Node.js 22+, and resolves the target repo from an argument or the current directory. Run once per repo (frontend + each backend). |

### Search & analysis

| Skill | Command | Description |
|-------|---------|-------------|
| **Search** | `/breeze:search <query>` | Search the functional graph or code graph for feature discovery, impact analysis, and cross-cutting queries |
| **Analyze Functional** | `/breeze:analyze-functional` | Analyze a requirement against the existing functional graph — coverage gaps, conflicts, dependencies, impact |
| **Analyze Architecture** | `/breeze:analyze-architecture` | Analyze a requirement against the architecture graph — impacted layers and components across 8 architecture layers |
| **Analyze Design** | `/breeze:analyze-design <Figma URL>` | Analyze UI/UX designs from Figma frames — functional summary, components, mapping to the functional graph, gap flags |

### Generate functional graph from a repo

The recommended approach is the **split pipeline** — one pass for the UI and one for each backend repo. The two passes are independent and merge automatically by outcome name in the functional graph.

| Skill | Command | Description |
|-------|---------|-------------|
| **Generate Functional from UI** | `/breeze:generate-functional-from-ui [repo-path]` | **Recommended for frontend repos.** Reads the UI codebase from the filesystem (Glob/Read/Grep), discovers routes + non-routed panels, and generates the **User-persona** side of the functional graph with full JSX coverage validation and API endpoints captured in `action.apis[]`. Persona discovery and panel discovery are both hard gates with user confirmation. |
| **Generate Functional from Backend** | `/breeze:generate-functional-from-backend [repo-path]` | **Recommended for backend repos.** Detects the framework (LoopBack/NestJS/Express/Fastify/Spring/FastAPI/etc.) and discovers ALL entry-point types: REST routes, SQS/Kafka/RabbitMQ consumers and producers, cron workers, WebSocket handlers, webhook receivers, and internal service-to-service routes. Writes **System** / **External System** persona scenarios with side effects captured in `apis[]` (REST/GraphQL/gRPC/WebSocket/Event), plus a per-repo handoff log used for cross-repo producer/consumer correlation. Run once per backend repo. |
| **Generate Functional from Code** *(deprecated)* | `/breeze:generate-functional-from-code` | **Legacy cluster pipeline.** Kept for reference and as a fallback for repos with no UI and no message queues / cron / WebSocket handlers. Uses a Python multi-pass pipeline (intent extraction → DBSCAN dedup → outcome assignment → scenario generation) driven by the code graph. For new work, use the two skills above instead. |

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
  /breeze:setup-project                               # API key + project link
  /breeze:onboard-repository <frontend repo>          # index code graph (once per repo)
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
  /breeze:setup-project
  /breeze:visual-to-text           # Figma / PDF / images → user stories
  /breeze:analyze-functional       # also ingests requirement documents

Adding a new requirement to an existing project:
  /breeze:analyze-functional
  /breeze:analyze-architecture
  /breeze:update-functional-graph
  /breeze:generate-code
```

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

- `.breeze.json` contains your API key — add it to `.gitignore`
- The **Design** skill requires a Figma MCP server to be configured separately
- All skills except `init` require a valid `.breeze.json` with `apiKey` and `projectUuid`
