---
name: enrich-functional-from-confluence
description: >
  Enrich and validate the functional graph using a Confluence page (or page
  tree) as the source of truth. Performs a two-directional diff: finds
  requirements missing from the graph (doc → graph) and flags nodes that are
  wrongly mapped, contradicted, stale, or drifted relative to the doc
  (graph → doc). Presents categorised findings, collects user approval, then
  applies fixes — creating missing nodes and correcting existing ones via MCP.
  Use when: "enrich graph from confluence", "validate graph against confluence",
  "check graph against confluence page", "update functional graph from confluence",
  "what is missing from the functional graph", "wrong mappings in the graph",
  "sync functional graph with confluence".
argument-hint: "<confluence-url> [--project <name|uuid>] [--depth <1|2|3>]"
---

## Project

This skill is project-bound — resolve `projectUuid` per `CLAUDE.md`:
`--project` flag → bare UUID → natural-language hint → `.breeze.json` fallback →
list projects and ask. Announce: `Project: <name> (<uuid>)`.
Breeze MCP 401 handling: point the user at `/breeze:project auth`.

---

## Execution Flow

### 1. Authenticate and Fetch Confluence Page

Parse the `pageId` (and instance hostname) from the URL.
Authenticate with the Atlassian MCP server — follow the flow in
`references/atlassian-auth.md`. Then call `getConfluencePage` with
`contentFormat: "markdown"` and the `pageId` plus any fields the loaded
schema requires.

If `--depth 2` or `--depth 3` was passed (default: 1), ask the user before
fetching child pages — cap at 10. Save all content to `confluence-content.md`.

### 2. Extract Requirements Map

Parse `confluence-content.md` into a keyword map (`sources.json`) and a
full-text requirements list. See `references/sources-format.md` for the schema and
extraction rules.

### 3. Search the Functional Graph

Derive 5–10 domain query phrases from `sources.json`.
Call `Functional_Graph_Search` for each phrase.
Call `Get_all_personas` once for the persona landscape.
Deduplicate results by node ID → this is the **working subgraph** for this run.

If searches return no results, inform the user that all requirements will
appear as `missing` and continue.

### 4. Coverage Check (doc → graph)

For each requirement in `sources.json`, check the working subgraph:
collect keyword hits across node names and descriptions, then classify:
- **FULL** — ≥60% of keywords match AND a dedicated Scenario exists.
- **PARTIAL** — some keywords match but no clear Scenario.
- **MISSING** — no meaningful match.

Record FULL verdicts with their matching `Persona > Outcome > Scenario` path.

### 5. Semantic Diff (graph → doc)

Check each node in the working subgraph against the doc.
Classify findings using the taxonomy in `references/mismatch-taxonomy.md`.
Collect each finding with: `id`, `category`, `severity`, `location`,
`node_id`, `evidence`, `proposed_fix`.

State in the report which outcomes/scenarios were evaluated and which were not.

### 6. Present Findings and Collect Feedback

Display the validation report (see **Output Format** below).
Ask: *"Which findings should I fix? Reply with numbers (e.g. `1, 3, 5-7`),
`all`, `all P0`, `all P1`, or `none`. Add a note after a number to override
the proposed fix (e.g. `2: rename to "order" instead`)."*

Show a confirmation block listing each approved change before writing anything.
Wait for `yes / edit / cancel`.

### 7. Apply Fixes

Apply approved fixes in hierarchy order: Persona → Outcome → Scenario → Step → Action.
Follow the per-category protocols in `references/fix-protocols.md`.
Attach a `confluence` citation (`reference`: page URL, `inputText`: relevant excerpt)
to every node created or updated.

---

## Output Format

```
## Confluence ↔ Functional Graph Validation Report
Source: <page title> — <url>
Project: <name>

| Category            | Count | Severity |
| Missing             |   N   |    P0    |
| Wrong persona       |   N   |    P1    |
| Misplaced scenario  |   N   |    P1    |
| Contradicted        |   N   |    P1    |
| Stale               |   N   |    P1    |
| Terminology drift   |   N   |    P2    |

| # | Category | Location | Issue | Proposed Fix |
…rows…

Scope note: evaluated N outcomes / M scenarios; other areas not checked.
```

After fixes: print a `| Finding | Category | Change | Status |` summary table
and suggest re-running the skill to verify.
