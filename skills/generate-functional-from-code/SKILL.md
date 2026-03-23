---
name: generate-functional-from-code
description: >
  Generate a functional graph (Persona → Outcome → Scenario → Step → Action)
  from the code graph. Uses a three-pass pipeline: extract intents from code
  clusters, create global structure with user approval, then generate scenarios
  per outcome using Code Graph Search for file discovery.
  Use when: "generate functional graph from code", "derive functional graph",
  "code to functional", "build functional graph from clusters",
  "generate functional graph from code graph".
---

## Purpose

Transforms a codebase's code graph (files, functions, classes, clusters) into
a functional graph (Persona → Outcome → Scenario → Step → Action). This is
the brownfield path — when code exists but the functional graph is empty.

The pipeline uses three passes:
1. **Extract intents** from each code cluster (what does this code enable?)
2. **Create global structure** — Persona → Outcome skeleton (user reviews)
3. **Generate scenarios** per outcome using Code Graph Search for file discovery

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run
`/breeze:setup-project`. Extract `apiKey` and `projectUuid`.

The project must have at least one code ontology with clusters. If the
pipeline reports "No intents extracted" or "Total clusters: 0", the
repository has not been uploaded to the code graph yet.

**Upload the repository on behalf of the user:**

Ask the user for the path to their repository, then run:

```bash
npx github:accionlabs/breeze-code-ontology-generator repo-to-json-tree \
  --repo <repo-path> \
  --out breezeai \
  --upload \
  --capture-statements \
  --user-api-key {apiKey} \
  --uuid {projectUuid} \
  --baseurl {apiBase}
```

Where `{apiBase}` is read from `.breeze.json` field `apiBase`
(defaults to `https://isometric-backend.accionbreeze.com` if not set).

**Requirements:**
- Node.js 22+ must be available (`node --version` to check)
- The `--capture-statements` flag ensures method-level statements are
  captured, which the pipeline needs for accurate steps/actions generation

Wait for the upload to complete (may take several minutes for large repos).
Once done, re-run the pipeline — clusters will now be available.

## Step 1 — Run the Pipeline

Run the three-pass generator script:

```bash
python3 {SKILL_DIR}/generate.py \
  --project-uuid {projectUuid} \
  --api-key {apiKey}
```

### Arguments

| Flag | Description |
|------|-------------|
| `--project-uuid` | Project UUID (defaults to `.breeze.json`) |
| `--api-key` | API key (defaults to `.breeze.json`) |
| `--cluster <id>` | Process only this cluster ID (for testing) |
| `--auto-approve` | Skip all approval prompts, auto-approve everything |

### Examples

```bash
# Interactive — review and approve each step
/breeze:generate-functional-from-code

# Auto-approve everything (no prompts)
/breeze:generate-functional-from-code --auto-approve

# Test with a single cluster first
/breeze:generate-functional-from-code --cluster 45

# Different project
/breeze:generate-functional-from-code --project-uuid abc-123
```

## What Happens

### Pass 1 — Intent Extraction (automated)

For each code cluster:
- Fetches files with full hierarchy (classes, methods, route decorators,
  injected services, call targets)
- Sends compact summary to LLM (Haiku)
- Extracts 1-8 functional intents per cluster
- Format: `"Persona: Capability phrase"`

**No user interaction needed.** Progress is printed to console.

### Pass 2 — Global Structure (user approval)

Aggregates ALL intents from ALL clusters and sends to LLM (Sonnet) to create
the Persona → Outcome hierarchy.

The pipeline will:
1. Print the proposed structure (personas and outcomes)
2. Prompt: `[A]pprove / [E]dit / [S]kip / [Q]uit`
3. If `E` (edit): provide corrections, LLM revises and re-proposes
4. If `A` (approve): upserts personas + outcomes to BreezeAI API
5. Waits 15s for embedding generation

**This is the most important step.** Review carefully — the outcome structure
defines how the entire functional graph is organized. Use edit feedback to:
- Split over-merged outcomes
- Fix persona assignments (User vs System vs External System)
- Add missing capabilities
- Provide product domain context if the LLM misgroups

### Pass 3 — Scenarios per Outcome (user approval)

For each outcome:
1. **Code Graph Search** — finds relevant files across ALL clusters using
   the outcome name and mapped intents as search queries
2. **Fetches file details** — full code structure for discovered files
3. **Extracts scenarios** (Sonnet) — exhaustive, all distinct flows
4. **Generates steps + actions** (Haiku) — using only relevant files per scenario
5. **Adds citations** — each node cites its source code files
6. Prompts: `[A]pprove / [E]dit / [S]kip / [Q]uit`
7. If approved: upserts to BreezeAI API with 15s embedding wait

### LLM Logging

All LLM calls are logged to `./llm_logs/` in the current directory:
- `call_001.txt` — system prompt, user prompt, and response for each call
- `upsert_pass2.json` — the Pass 2 upsert payload

## Functional Graph Rules

The pipeline follows the BreezeAI functional graph specification defined in
`../shared/functional-graph-rules.md`. This includes:

- Persona resolution rules (priority order, forbidden names, tiebreakers)
- Outcome rules (reuse-first, business language, quality checks)
- Scenario rules (testable, 70% merge rule, System description rules)
- Step rules (sequential, verb phrases, 3-8 per scenario)
- Action rules (persona-aware: human/system/external system)
- Context type handling (documents, code, Figma)
- Data model and MCP tools mapping

### Code-to-Functional Mapping (additional rules for this skill)
- Frontend pages/components → Scenarios
- Backend controllers serving UI → Persona = human who triggers
- Pure backend (jobs, workers) → Persona = "System"
- Route decorators → business capabilities, not endpoint paths
- Never reproduce raw code in actions

## Dependencies

```bash
pip install langgraph langchain-aws langchain-core boto3 requests
```

Requires AWS Bedrock access with Claude 3.5 Sonnet and Haiku models.

## Models Used

| Pass | Model | Purpose |
|------|-------|---------|
| Pass 1 | Haiku 3.5 | Intent extraction (cheap, fast) |
| Pass 2 | Sonnet 3.5 | Structure creation (needs judgment) |
| Pass 3a | Sonnet 3.5 | Scenario extraction (needs judgment) |
| Pass 3b | Haiku 3.5 | Steps/actions generation (structured extraction) |

## Post-Generation

After the pipeline completes, consider running:
- `/breeze:validate-functional-graph` — check for duplicates, gaps, quality issues
- `/breeze:analyze-functional` — analyze specific requirements against the generated graph
