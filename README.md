# Breeze Plugin for Claude Code

A Claude Code plugin that integrates with the Breeze AI platform for functional graph management, code analysis, design analysis, and requirement tracing.

## Quick Start

### 1. Run Claude Code with the plugin

```bash
/plugin marketplace add accionlabs/breezeai-claude-plugin
```

### 2. Initialize Breeze

```
/breeze:setup-project
```

This will walk you through:
- Setting up your API key (generated at https://ai.accionbreeze.com/mcp/generate/key)
- Linking to an existing project or creating a new one
- Checking ontology status
- Optionally uploading your repository or documents

Your credentials are saved to `.breeze.json` in the project root (gitignored).

## Available Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **Init** | `/breeze:setup-project` | Set up API key, link project, check ontology status, optionally upload repo or documents |
| **Analyze Functional** | `/breeze:analyze-functional` | Analyze requirements against the existing functional graph — identifies coverage gaps, conflicts, dependencies, and impact |
| **Analyze Architecture** | `/breeze:analyze-architecture` | Analyze requirements against the existing architectural graph — identifies impacted layers and components across 8 architecture layers |
| **Analyze Design** | `/breeze:analyze-design <Figma URL>` | Analyze UI/UX designs from Figma frames — extracts functional summary, identifies components, maps to functional graph, flags gaps |
| **Search** | `/breeze:search <query>` | Search functional graph or code graph for feature discovery, impact analysis, and cross-cutting queries |
| **Generate Functional from Code** | `/breeze:generate-functional-from-code` | Generate a functional graph from the code graph using a three-pass pipeline — extracts intents, creates structure, generates scenarios |
| **Generate Code** | `/breeze:generate-code <feature>` | Generate code and test cases informed by the functional graph and code graph |
| **Generate Spec** | `/breeze:generate-spec` | Generate functional specification documents from the functional graph |
| **Update Functional Graph** | `/breeze:update-functional-graph` | Create/update nodes in the functional graph from documents, code, or Figma |
| **Validate Functional Graph** | `/breeze:validate-functional-graph` | Validate the functional graph for duplicates, gaps, quality issues |

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
