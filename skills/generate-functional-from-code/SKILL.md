---
name: generate-functional-from-code
description: >
  Generate a functional graph (Persona → Outcome → Scenario → Step → Action)
  from the code graph. Uses a multi-pass pipeline: extract intents from code
  clusters, deduplicate via embeddings + DBSCAN clustering, filter/merge/assign
  outcomes with Sonnet, then generate scenarios per outcome using intent-driven
  Code Graph Search for file discovery with citation tracking.
  Use when: "generate functional graph from code", "derive functional graph",
  "code to functional", "build functional graph from clusters",
  "generate functional graph from code graph".
---

## Purpose

Transforms a codebase's code graph (files, functions, classes, clusters) into
a functional graph (Persona → Outcome → Scenario → Step → Action). This is
the brownfield path — when code exists but the functional graph is empty.

The pipeline uses multiple passes:
1. **Extract intents** from each code cluster (descriptive, 5-15 words)
2. **Deduplicate intents** via keyword filter + normalization + embeddings + DBSCAN clustering
3. **Filter, merge, and assign outcomes** using cluster-based batching with Sonnet (filters non-functional intents, merges overlapping ones, assigns to outcomes)
4. **Generate scenarios** per outcome using intent-driven Code Graph Search for file discovery, with citation tracking at all graph levels

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
- Python 3.10+ with numpy and scikit-learn (`pip install numpy scikit-learn`)
- The `--capture-statements` flag ensures method-level statements are
  captured, which the pipeline needs for accurate steps/actions generation

Wait for the upload to complete (may take several minutes for large repos).
Once done, re-run the pipeline — clusters will now be available.

## Step 1 — Run the Pipeline

Run the generator script. **Always** pass `--auto-approve` since Claude Code
runs commands non-interactively (no TTY). The script also auto-detects
non-TTY environments and auto-approves, but the flag makes intent explicit.

Read all credentials from `.breeze.json` and pass them explicitly:

```bash
python3 {SKILL_DIR}/generate.py \
  --project-uuid {projectUuid} \
  --api-key {apiKey} \
  --api-base {apiBase} \
  --aws-access-key {awsAccessKey} \
  --aws-secret-key {awsSecretKey} \
  --aws-region {awsRegion} \
  --auto-approve
```

Where credentials and config are read from `.breeze.json` fields:
- `awsAccessKey` / `awsSecretKey` — AWS credentials
- `awsRegion` — AWS region (defaults to `us-west-2`)
- `bedrockHaikuModel` — custom Haiku model ID (optional)
- `bedrockSonnetModel` — custom Sonnet model ID (optional)

Config loading priority: CLI args > `.breeze.json` > env vars (`AWS_ACCESS_KEYID`, `AWS_SECRET_KEY`, `AWS_REGION`) > defaults.

If AWS credentials are missing from `.breeze.json`, ask the user and save them:
```json
{
  "awsAccessKey": "<ACCESS_KEY>",
  "awsSecretKey": "<SECRET_KEY>",
  "awsRegion": "us-west-2"
}
```

### Arguments

| Flag | Description |
|------|-------------|
| `--project-uuid` | Project UUID (defaults to `.breeze.json`) |
| `--api-key` | API key (defaults to `.breeze.json`) |
| `--api-base` | API base URL (defaults to `.breeze.json` or `https://isometric-backend.accionbreeze.com`) |
| `--aws-access-key` | AWS access key for Bedrock (defaults to `.breeze.json` or env) |
| `--aws-secret-key` | AWS secret key for Bedrock (defaults to `.breeze.json` or env) |
| `--aws-region` | AWS region for Bedrock (defaults to `.breeze.json` field `awsRegion`, env `AWS_REGION`, or `us-west-2`) |
| `--haiku-model` | Custom Haiku model ID (defaults to `.breeze.json` field `bedrockHaikuModel`) |
| `--sonnet-model` | Custom Sonnet model ID (defaults to `.breeze.json` field `bedrockSonnetModel`) |
| `--eps` | DBSCAN epsilon for intent clustering. 0.15=strict, 0.20=moderate, 0.30=loose (default: 0.20) |
| `--batch-clusters <N>` | Batch small clusters together (max N files per batch). Default 0 = process each cluster separately |
| `--cluster <id>` | Process only this cluster ID (for testing) |
| `--auto-approve` | Skip all approval prompts, auto-approve everything |
| `--skip-single-file-clusters` | Skip clusters with only 1 file |
| `--resume` | Auto-detect and resume from latest cached pass |
| `--resume-from <N>` | Resume from specific pass (1, 2, or 3) |

### Examples

```bash
# Standard run (auto-approve for non-interactive use)
/breeze:generate-functional-from-code

# With custom DBSCAN threshold (looser clustering)
/breeze:generate-functional-from-code --eps 0.30

# Resume from Pass 3 (skip intent extraction and outcome assignment)
/breeze:generate-functional-from-code --resume-from 3

# Test with a single cluster first
/breeze:generate-functional-from-code --cluster 45
```

## What Happens

### Pass 1 — Intent Extraction (automated)

Each cluster is processed individually by default. Large clusters (30+ files)
are split into file batches of 30. Use `--batch-clusters 15` to batch small
clusters together for faster processing (at the cost of less specific intents).

For each cluster:
- Fetches files with full hierarchy (classes, methods, route decorators,
  injected services, call targets)
- Sends compact summary to LLM (Haiku)
- Extracts descriptive functional intents (5-15 words with context)
- Format: `"Persona: Descriptive capability phrase with purpose and context"`
- No upper limit on intents per cluster — extracts as many as the code warrants

**No user interaction needed.** Progress is printed to console.

### Pass 1.5 — Intent Deduplication (automated)

Reduces raw intents to unique capabilities through a multi-step pipeline:
1. **Keyword filter** — removes test/mock/infrastructure intents
2. **Exact dedup** — removes identical strings
3. **Normalization dedup** — merges intents that differ only by case, articles, punctuation
4. **Embedding generation** — generates vector embeddings via AWS Bedrock Titan (cached)
5. **DBSCAN clustering** — groups semantically similar intents (configurable via `--eps`)

Displays clustering results and waits for user approval before proceeding.
Review the clusters to verify related intents are grouped together.

### Pass 2 — Outcome Assignment (user approval)

Processes intent clusters through Sonnet for deduplication and outcome assignment:

1. **Large DBSCAN clusters** (>= 13 intents) processed individually — chunked into
   batches of ~25 intents per Sonnet call if needed.
2. **Small DBSCAN clusters** (< 13 intents) batched together up to ~25 intents per call.
3. **Singletons** sorted by embedding similarity (greedy nearest-neighbor) so related
   ones batch together, then sent in groups of ~25.
4. Sonnet performs three tasks per batch: **filters** non-functional intents (infra, schemas,
   configs), **merges** overlapping intents into richer phrases, and **assigns outcomes**.
5. Each batch sees existing outcomes with sample intents (first 3 + last 2) to
   prevent duplicate outcomes and intents across batches.

Displays full outcome → intent mapping and supports an **edit loop**: user can provide
feedback to restructure outcomes via Sonnet before approving.
Review carefully — the outcome structure defines how the functional graph is organized.

### Pass 3 — Scenarios per Outcome (user approval)

For each outcome, a three-phase pipeline runs:

**Phase 1 — File Discovery:**
1. **Code Graph Search** — searches per intent for relevant files (File, Function, Class nodes, score >= 0.3)
2. **Fetches file details** once with children (deduplicated across all intents in the outcome)
3. **Generates enriched summaries** using `format_summary()` (classes, methods, params, call chains)

**Phase 2 — Scenario Extraction:**
4. Processes intents in batches of 5 (`INTENT_BATCH_SIZE`)
5. **Extracts scenarios** (Sonnet) — from enriched file context matched to each batch's intents
6. Cumulative dedup across batches (existing scenario names passed to each call)
7. Merges and deduplicates scenarios across all batches by scenario name

**Phase 3 — Steps & Actions:**
8. **Generates steps + actions** (Haiku) — processes 2 scenarios at a time using full code detail from relevant files
9. **Attaches citations** — maps file paths to code citations (type: "code") at outcome, scenario, step, and action levels
10. Prompts: `[A]pprove / [E]dit / [S]kip / [Q]uit` per outcome
11. If approved: upserts to BreezeAI API with 15s embedding wait

### Caching and Resume

Results are cached at each pass boundary:
- `llm_logs/cache_pass1.json` — extracted intents
- `llm_logs/cache_pass1.5.json` — dedup clustering results
- `llm_logs/cache_pass2.json` — outcome structure
- `llm_logs/intent_embeddings_v2.json` — embedding vectors (reused across runs)

Use `--resume` to auto-detect and resume from the latest cached pass, or
`--resume-from 2` to skip Pass 1, `--resume-from 3` to skip Pass 1+2.

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
- Do NOT invent Admin/Moderator unless code explicitly checks roles

## Dependencies

```bash
pip install boto3 requests numpy scikit-learn
```

Requires AWS Bedrock access with:
- Claude 3.5 Sonnet and Haiku models (LLM)
- Amazon Titan Embed Text v2 (embeddings)

**Note:** If `pip install` fails with an externally-managed-environment error
(PEP 668), use `pip install --break-system-packages boto3 requests numpy scikit-learn`.

## Models Used

| Pass | Model | Purpose |
|------|-------|---------|
| Pass 1 | Haiku 3.5 (configurable via `bedrockHaikuModel`) | Intent extraction (descriptive, per-cluster) |
| Pass 1.5 | Amazon Titan Embed Text v2 | Intent embedding for DBSCAN clustering |
| Pass 2 | Sonnet 3.5 (configurable via `bedrockSonnetModel`) | Intent filter + merge + dedup + outcome assignment |
| Pass 3a | Sonnet 3.5 (configurable via `bedrockSonnetModel`) | Scenario extraction (enriched file context, batches of 5 intents) |
| Pass 3b | Haiku 3.5 (configurable via `bedrockHaikuModel`) | Steps/actions generation (2 scenarios at a time, full code detail) |

## Estimated Cost (200K LOC codebase)

| Pass | Estimated Cost |
|------|---------------|
| Pass 1 (Haiku, ~130 calls) | ~$1.15 |
| Pass 1.5 (Embeddings, ~400 calls) | ~$0.04 |
| Pass 2 (Sonnet, ~20 calls) | ~$0.80 |
| Pass 3 (Sonnet + Haiku, ~130 calls) | ~$3.90 |
| **Total** | **~$5.90** |

## Post-Generation

After the pipeline completes, consider running:
- `/breeze:validate-functional-graph` — check for duplicates, gaps, quality issues
- `/breeze:analyze-functional` — analyze specific requirements against the generated graph
- `/breeze:generate-spec` — generate a functional specification document from the graph
