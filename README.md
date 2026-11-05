# Breeze Plugin for Claude Code

A Claude Code plugin that integrates with the Breeze AI platform for searching the functional, design, code, and architecture graphs and running cross-layer impact analysis.

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

The Keycloak token lasts roughly **7 days** from the last sign-in; after that any
`/breeze:*` skill will prompt you to re-run `/breeze:project auth`.

No API key is required — every skill in this plugin talks to Breeze over MCP and
authenticates via Keycloak OAuth automatically.

`<uiBaseUrl>` resolves from `breeze.config.json` at the plugin root
(default `https://ai.accionbreeze.com`). Override per-project by
setting `uiBaseUrl` in `.breeze.json`.

Your project UUID is saved to `.breeze.json` in the project root (gitignored).

### Updating the plugin

When a new version is released:

```
/plugin marketplace update accionlabs/breezeai-claude-plugin
/plugin update breeze
```

Then **restart Claude Code** again so the updated skills/hooks/MCP definitions are picked up.

## Available Skills

| Skill | Command | Description |
|-------|---------|-------------|
| **Project** | `/breeze:project [show \| list \| use <name> \| create <name> \| auth \| status \| setup]` | Canonical home for all project management. Sub-modes: `show` (active project), `list` (all accessible), `use <name\|uuid>` (switch and persist), `create <name> [--desc "..."]` (create and link), `auth` (re-authenticate MCP), `status` (full metadata report), `setup` (full bootstrap = auth + link/create + ontology check). No API key collected here — MCP uses Keycloak OAuth. |
| **Search** | `/breeze:search <query>` | Smart-search across functional, design, code, and architecture graphs — routes to one graph, a subset, or all based on query intent. Default entry point for any question about the project. |
| **Impact Analysis** | `/breeze:impact-analysis [--detailed] <prompt>` | Structured cross-layer impact analysis (functional → design → code → architecture). Summary by default; `--detailed` emits a full document with Mermaid request-path / async-tail diagrams, per-ontology marker tables, a structured risk taxonomy, a QA test plan, schema-side (DDL) impact with a 🔴/🟡/🟢 verdict, and deploy-coordination notes. Accepts `--project <name\|uuid>`. |

Both `search` and `impact-analysis` are read-only — they query the Breeze graphs
and never write nodes back.

### Typical usage

```
First run in a repo:
  /breeze:project setup                               # MCP auth + project link

Day to day:
  /breeze:search how does invoice approval work       # explore the graphs
  /breeze:impact-analysis what breaks if we drop the legacy payout endpoint
  /breeze:impact-analysis --detailed <prompt>         # full document on disk

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

- `.breeze.json` holds the project link (`projectUuid`) and any per-project URL overrides. Add it to `.gitignore`.
- The Breeze MCP server uses Keycloak OAuth; Claude Code handles sign-in automatically on the first MCP tool call and does **not** read `apiKey` from `.breeze.json`. No skill in this plugin needs an API key.
- The Keycloak token expires after roughly **7 days**. Expect to re-authenticate periodically via `/breeze:project auth`; skills will tell you when an MCP call hits a 401.
- All Breeze service URLs live in `breeze.config.json` at the plugin root (`uiBaseUrl`, `apiBase`). To repoint every skill at a different Breeze deployment, edit that single file — or override `uiBaseUrl` / `apiBase` per-project in `.breeze.json`.
- The plugin ships a **`CLAUDE.md`** at the root. Claude Code auto-loads it and it centralizes the project-resolution flow, the exempt-skills list, the auth-on-401 rule, and the `.breeze.json` mutation policy. Individual `skills/*/SKILL.md` files defer to it rather than duplicating the rule.
- `/breeze:search` and `/breeze:impact-analysis` require a resolvable project (see **Project resolution** above). `/breeze:project` in its `setup` / `auth` / `list` / `create` modes does not.
