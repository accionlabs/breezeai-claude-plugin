---
name: validate-functional-graph
description: >
  Validate the functional graph against source documents.
  Checks coverage, duplicates, persona quality, description completeness,
  action platform-agnosticism, and citation traceability.
  Use when: "validate graph", "check graph quality", "compare graph to docs",
  "audit functional graph", "graph health check".
---

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

---

## Step 1 — Collect Graph Data

Call `Get_complete_functional_graph` with the project UUID.
The response will be large and auto-saved to a file. This is expected.
Note the saved file path — you will pass it to the validation script.

---

## Step 2 — Collect Source Baseline (if available)

Determine the source baseline to validate against. The user may:

**A. Provide a folder path with source documents:**
- Read the files in the folder to extract requirements, user stories,
  features, and acceptance criteria
- Build a sources JSON mapping story IDs to keywords:
  ```json
  {
    "US-001 CSV Upload": ["upload", "csv", "fund", "valuation date"],
    "VAL-001 Share Class": ["share class", "divergence", "bps"]
  }
  ```
- Write this to `sources.json` in the project root

**B. Not provide source documents:**
- Use `Documents` MCP to search for the project's requirement structure
  with broad queries (e.g., "all epics user stories features requirements")
- Extract key terms and build the same `sources.json` format
- If `Documents` returns nothing useful, skip this step — the script
  will still run all structural checks

**C. Sources already exist:**
- If `sources.json` already exists from a previous run, reuse it

---

## Step 3 — Run Validation Script

Run the validation script against the saved graph file:

```bash
# Without source coverage check
python3 {SKILL_BASE_DIR}/scripts/validate-graph.py <saved-json-file> validation-report.json

# With source coverage check
python3 {SKILL_BASE_DIR}/scripts/validate-graph.py <saved-json-file> validation-report.json --sources sources.json
```

The script performs these checks automatically:

| Check | Severity | What it catches |
|-------|----------|-----------------|
| Empty nodes | P0 | Scenarios with 0 steps/actions |
| Duplicate scenarios | P1 | Same name across graph |
| Duplicate outcomes | P1/P2 | Same name, same or cross persona |
| Citation coverage | P1 | Nodes without source traceability |
| Description coverage | P1 | System actions missing business logic descriptions |
| Platform-agnostic | P1 | UI-specific words (click, button, etc.) in human actions |
| Persona quality | P0/P1 | Bloated (>40%), thin (<5 actions), forbidden names |
| Cross-persona overlap | P2 | Same keywords across 3+ personas |
| Source coverage | P0/P1 | Requirements not reflected in graph (when --sources provided) |

Read the output `validation-report.json` — it's structured JSON, small
enough to read directly (~10-20KB for most projects).

---

## Step 4 — Present Results

Present the validation report in this format:

```
## Functional Graph Validation Report

### Summary

| Metric | Value |
|---|---|
| Personas | {N} |
| Outcomes | {N} |
| Scenarios | {N} |
| Steps | {N} |
| Actions | {N} |
| Citation Coverage | {N}% |
| System Action Description Coverage | {N}% |
| Platform-Agnostic Compliance | {N}% |
| User Story Coverage | {N}/{M} FULL |

### P0 Issues (Must Fix)

{List each P0 issue with specific node names and locations}

### P1 Issues (Should Fix)

{List each P1 issue with specific node names and locations}

### P2 Issues (Consider)

{List each P2 issue}

### Detailed Results

#### Empty Nodes
{Table of empty scenarios}

#### Duplicate Names
{Tables of duplicate scenarios and outcomes}

#### Coverage Matrix
{Table mapping each user story to coverage status}

#### Platform-Agnostic Violations
{Table of actions with UI-specific words}

#### Persona Health
{Table with persona stats and quality flags}
```

---

## Step 5 — Recommend Actions

Based on the findings, provide a prioritized action list:

1. **P0 fixes** — specific nodes to populate, merge, or remove
2. **P1 fixes** — specific descriptions to add, duplicates to resolve,
   UI verbs to replace
3. **P2 improvements** — persona restructuring suggestions

---

## Step 6 — Optionally Fix Issues

Ask the user:
"Would you like me to fix any of these issues?"

If yes, for each fix type:

- **Empty nodes:** Ask whether to populate with steps/actions or remove
- **Duplicates:** Ask whether to merge or differentiate names
- **Missing descriptions:** Generate descriptions using `Documents` MCP
  for business logic detail, then `Call_Update_Functional_Node_`
- **UI-verb violations:** Propose platform-agnostic rewrites, then
  `Call_Update_Functional_Node_`
- **Forbidden personas:** Propose merge target, then update

Always confirm each batch of changes with the user before executing.

---

## Functional Graph Rules Reference

Refer to `../shared/functional-graph-rules.md` for the complete specification
of persona rules, outcome rules, scenario rules, step/action rules, and
forbidden names used during validation checks.
