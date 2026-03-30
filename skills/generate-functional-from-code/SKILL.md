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
  "generate functional graph from code graph",
  "generate functional ontology", "generate functional from ui".
---

## Purpose

Transforms a codebase's code graph (files, functions, classes, clusters) into
a functional graph (Persona → Outcome → Scenario → Step → Action). This is
the brownfield path — when code exists but the functional graph is empty.

## Two Modes

This skill supports two generation modes. Ask the user which mode to use,
or auto-detect based on the project:

### Mode A: Cluster Pipeline (default)
Best for: backend-heavy repos, repos without a UI, or when speed is preferred
over UI-level accuracy. Uses the Python pipeline script with LLM-based intent
extraction from code clusters.

### Mode B: UI-Driven Generation
Best for: frontend repos with a router/navigation system (Vue, React, Angular,
Next.js, etc.). Produces more accurate ontology by tracing UI entry points →
form fields → API calls → backend handlers. Generates both User and System
personas with API linking.

**Auto-detection:** If the working directory contains a frontend router file
(`src/router/index.js`, `app/routes.tsx`, `pages/` directory, etc.), suggest
Mode B. Otherwise, default to Mode A.

---

# Mode A: Cluster Pipeline

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

## Post-Generation (Both Modes)

After generation completes, consider running:
- `/breeze:validate-functional-graph` — check for duplicates, gaps, quality issues
- `/breeze:analyze-functional` — analyze specific requirements against the generated graph
- `/breeze:generate-spec` — generate a functional specification document from the graph

---

# Mode B: UI-Driven Generation

Generates the functional graph by tracing frontend UI entry points (routes) through
to backend API handlers. Produces both User and System personas with API linking
on actions.

## When to Use Mode B

- The project has a **frontend with a router** (Vue Router, React Router, Angular Router, Next.js pages, etc.)
- You need **UI-accurate ontology** — every form field, conditional rendering, and user flow captured
- You want **API linking** — each action that calls an API has it linked with method, URL, request/response shapes
- You want **System persona grounded in actual backend code** — not inferred, but traced through the code graph

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `apiKey`, `projectUuid`, and `apiBase`.

The project must have at least one code ontology indexed. If the code graph returns no results,
the repository has not been uploaded yet — follow the upload instructions in Mode A's Guard section.

## Phase 0: Discover Entry Points

If `entrypoints.json` does NOT exist in the working directory, create it:

### Step 1: Detect the framework
- Vue 2/3: look for `src/router/index.js` or `src/router/index.ts`
- React Router: look for `<Route`, `createBrowserRouter`, `useRoutes` in App/routes files
- Next.js: check for `pages/` or `app/` directory (file-based routing)
- Angular: look for `*-routing.module.ts` or `app.routes.ts`
- Nuxt: check for `pages/` directory with `.vue` files
- SvelteKit: check for `src/routes/` directory

### Step 2: Use code graph as primary source for route discovery
- Use specific queries per framework:
  - Vue: `"src/router/index.js vue router route definitions"`
  - React: `"routes.tsx react router createBrowserRouter Route"`
  - Angular: `"app-routing.module.ts angular routes"`
- The File node's `statements` field often contains full route definitions
- Use a second query for navigation structure (sidebar, navbar)
- Fall back to reading the router file directly if code graph is incomplete

### Step 3: Extract route details
For each route, extract: path, component, title, params, query params, auth guards, variants.

### Step 4: Categorize
Group by: Transaction, Accounting, Inventory, Reports, Users, Settings, Contacts, etc.

### Step 5: Discover orphaned views
Compare all view files against extracted routes. For views with NO route:
1. **Check imports** — is it a sub-component? Grep for `import.*from.*<ViewName>`
2. **Check git history** — was the route removed? `git log --all -p -- <router-file> | grep -i "<ViewName>"`
3. **Check for API calls** — does it have real functionality (axios/fetch calls)?

Classify as: sub-component (add to parent), dead code (flag for user), or truly unused (exclude).

### Step 6: Cross-reference backend API routes
If the backend repo is indexed in the code graph:
- Search for the routes definition file (e.g., `routes.py`)
- List all backend API endpoints
- Flag endpoints not called from any frontend code

### Step 7: Generate `entrypoints.json`
```json
{
  "project": "<name>",
  "framework": "<detected>",
  "routerFile": "<path>",
  "totalEntryPoints": "<count>",
  "entryPoints": [
    {
      "id": 1,
      "route": "/path",
      "title": "Page Title",
      "component": "src/views/Component.vue",
      "auth": true,
      "params": [],
      "queryParams": [],
      "variants": [],
      "category": "Category",
      "status": "pending"
    }
  ]
}
```

Present the list to the user for review. Ask if any should be excluded.

## Phase 1: Batch Entry Points by Category

1. Read `entrypoints.json`, group pending EPs by category or shared component
2. Plan which EPs share the same outcome (e.g., Invoice list + Create + Edit → "Manage Invoices")
3. Process one batch per upsert call

## Phase 2: Collate Context

Use **code graph + direct file reading** (both required):

### Code graph (for function logic and API calls)
- Search for the page component: `Code_Graph_Search` with `"<ComponentName>.vue <description>"`
- Extract: imports, functions, API calls from the `calls` field
- For child components, search code graph to understand their functions
- Use `Get_Code_File_Details` for deeper inspection when needed

### Direct file reading (for template details)
**Code graph does NOT capture `<template>` content.** Always read the actual file for:
- Use Grep for form fields (`v-model`, `@submit`, `@click`) first — skip inline SVGs
- Extract: form fields, `v-if`/`v-show` conditions, event handlers, slot templates
- Read script section for: `data()`, `computed`, `methods` (API calls), `mounted`

## Phase 3: Query Code Graph for Backend (System Persona)

Generate System persona **alongside** User persona:

1. From frontend code, identify all API endpoints (axios/fetch calls)
2. Search the backend code graph with descriptive queries: `"addInvoice invoice create post gkcore api handler"` (not just URL paths)
3. Code graph function results include call chains with SQL operations, helper functions, and line ranges
4. Build System persona scenarios describing actual backend processing

**System persona MUST be grounded in backend code graph — do NOT infer from frontend alone.**

## Phase 4: Generate Ontology

Follow the functional graph rules in `../shared/functional-graph-rules.md`, plus:

### UI-specific rules
- Group outcomes by primary ENTITY: "Manage Invoices" (not "Create Invoice")
- Each outcome should contain AT MOST 6 scenarios
- If two scenarios share >70% steps, MERGE with inline variant notes
- For conditional fields (`v-if`), note condition in plain English on the action
- FORBIDDEN action words: click, tap, button, dropdown, modal, checkbox, etc.
- USE intent verbs: Provide, Choose, Confirm, Review, Select, Submit

### API linking on actions
For each action that triggers an API call, attach an `apis` array:
```json
"apis": [{
  "method": "REST",
  "url": "POST /invoice",
  "request": "{payload shape}",
  "response": "{response shape}"
}]
```

## Phase 5: Self-Audit

Before presenting, verify:
1. No forbidden persona names
2. Outcomes are business capabilities, not technical
3. No scenario pairs with >70% step overlap
4. Steps: 3-10 per scenario, ordered
5. Actions: no forbidden words, system actions have descriptions, conditionals noted
6. Every form field from the template has a corresponding action

## Phase 6: Present for Review

Show the ontology with: personas, outcomes, scenarios with steps/actions, API summary table.
Ask user to approve, adjust, or skip.

## Phase 7: Write to Functional Graph via Upsert API

Build nested JSON payload and POST to the upsert endpoint:

```bash
curl -X POST "${API_BASE}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK" \
  -H "api-key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d @/tmp/upsert_payload.json
```

Upsert payload structure:
```json
{
  "project": {"uuid": "<projectUuid>", "name": "<projectName>"},
  "payload": {
    "personas": [{
      "persona": "User",
      "citations": [{"type": "code", "name": "<file>", "reference": "<file>"}],
      "outcomes": [{
        "outcome": "Manage Invoices",
        "scenarios": [{
          "scenario": "Create Invoice",
          "description": "...",
          "steps": [{
            "step": "Enter details",
            "actions": [{
              "action": "Select type",
              "description": "...",
              "apis": [{"method": "REST", "url": "POST /invoice", "request": "...", "response": "..."}]
            }]
          }]
        }]
      }]
    }]
  },
  "skipStepAndAction": false
}
```

The upsert is **idempotent** — match keys are string names. Re-running updates, not duplicates.
The upsert **merges across calls** — you can add scenarios to the same outcome in separate calls.

## Phase 8: Mark Complete

Update `entrypoints.json`: set processed EPs to `"status": "done"`.

## Phase 9: Coverage Validation

After all EPs are done:
1. Pull complete functional graph via `Get_complete_functional_graph`
2. Extract all APIs linked in the graph
3. Extract all backend routes from the backend repo
4. Compare and categorize gaps: missing flows, helper APIs, export variants, legacy
5. Generate coverage report with percentage
6. Upsert missing flows if user approves
