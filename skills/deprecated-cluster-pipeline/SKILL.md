---
name: deprecated-cluster-pipeline
description: >
  DEPRECATED. Old Python multi-pass cluster pipeline that generated a
  functional graph from the code graph via intent extraction → DBSCAN
  clustering → outcome assignment → scenario generation. The DBSCAN
  clustering step produces duplicate scenarios under realistic repo
  layouts, which is why this skill was retired. Do NOT run unless you
  are explicitly resuming an in-progress historical run or are
  consciously reproducing the legacy behaviour for comparison.
  Replacements: /breeze:generate-functional-from-ui (frontend repos),
  /breeze:generate-functional-from-backend (backend repos). Should
  almost never auto-trigger on natural-language requests.
---

## ⚠ DEPRECATED — DO NOT USE FOR NEW WORK

This skill is the **retired v1 cluster pipeline**. It is **not
supported** and is kept in the tree only so that historical runs can
be resumed and the implementation remains available for reference.

### Why it was deprecated

The Pass 1.5 DBSCAN clustering step duplicates scenarios when intents
cluster non-deterministically across runs. The cumulative dedup logic
across batches in Pass 2 doesn't always catch these because the same
underlying capability shows up under slightly different intent
phrasings. Net effect: the functional graph ends up with multiple
near-identical scenarios under slightly-different outcome names, and
fixing it manually is more work than rerunning the modern skills.

### Use this only if

- You are **resuming an in-progress historical run** that already has
  cached passes on disk and you want to finish it for archival
  reasons.
- You are **consciously reproducing the legacy behaviour** for a
  bug-replay or comparison investigation.

For **all new functional-graph generation**, use one of:

- **`/breeze:generate-functional-from-ui`** — frontend repos.
  Produces the human-persona side with full JSX coverage, panel
  discovery, API linking, and per-EP verification.
- **`/breeze:generate-functional-from-backend`** — backend repos.
  Discovers REST controllers AND non-HTTP entry points (SQS/Kafka
  consumers, cron workers, WebSocket handlers, webhook receivers)
  and writes System / External System personas with side effects
  captured in `apis[]`.

The two skills are independent and merge automatically by outcome
name in the functional graph. Together they replace everything this
deprecated skill used to do — without the cluster duplication.

The rest of this file is preserved unchanged for reference and resume
of in-progress runs. Don't read it as a guide for new work.

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

Read `.breeze.json`. It must contain `projectUuid` — if it doesn't,
tell the user to run `/breeze:setup-project` first.

### Ensure the API key is available

This skill calls the Breeze REST upsert endpoint and the
`breeze-code-ontology-generator` CLI, both of which need an
`apiKey` (separate from your MCP login).

1. If `.breeze.json` already has `apiKey`, continue.
2. If `apiKey` is missing, tell the user:

   > This skill needs a Breeze API key for REST upserts and the
   > ontology-generator CLI. Generate one at:
   >
   >   **`<uiBaseUrl>/mcp/generate/key`**
   >
   > Then paste it here.

3. Save the pasted key to `.breeze.json` under `apiKey` (no echo back).

### Ensure AWS Bedrock credentials are available

This skill drives the pipeline through AWS Bedrock (Claude Sonnet +
Haiku for LLM passes, Titan for embeddings). It needs an AWS access
key / secret pair with Bedrock invoke permissions.

1. If `.breeze.json` already has both `awsAccessKey` and `awsSecretKey`
   (or the `AWS_ACCESS_KEYID` / `AWS_SECRET_KEY` env vars are set),
   continue.
2. If missing, tell the user:

   > This skill calls AWS Bedrock (Sonnet + Haiku + Titan embeddings)
   > and needs an AWS access key and secret with Bedrock permissions.
   >
   > Paste your AWS Access Key ID, then your Secret Access Key.
   > (If you don't have keys yet, create an IAM user with the
   > `AmazonBedrockFullAccess` policy and generate keys from the
   > AWS IAM console.)

3. Save to `.breeze.json`:

   ```json
   {
     "awsAccessKey": "<ACCESS_KEY>",
     "awsSecretKey": "<SECRET_KEY>",
     "awsRegion": "us-west-2"
   }
   ```

   `awsRegion` defaults to `us-west-2` if not specified. Override if
   your Bedrock models live elsewhere.

**Security:** Never print AWS credentials in output. Store only in
`.breeze.json` (gitignored). Do not commit.

Then extract `apiKey`, `projectUuid`, `awsAccessKey`, `awsSecretKey`,
and `awsRegion` for the rest of the run.

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
(read from `.breeze.json` → `breeze.config.json` → `https://isometric-backend.accionbreeze.com` fallback).

**Requirements:**
- Node.js **exactly v22.x** must be available (`node --version` to check). Node 24+ fails because of an ESM-with-TLA incompatibility in the bundled tree-sitter bindings.
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
- `awsAccessKey` / `awsSecretKey` — AWS credentials (collected
  on-demand in the Guard above if missing)
- `awsRegion` — AWS region (defaults to `us-west-2`)
- `bedrockHaikuModel` — custom Haiku model ID (optional)
- `bedrockSonnetModel` — custom Sonnet model ID (optional)

Config loading priority: CLI args > `.breeze.json` > env vars (`AWS_ACCESS_KEYID`, `AWS_SECRET_KEY`, `AWS_REGION`) > defaults.

If you reach this step without AWS credentials (e.g. the user
cancelled the Guard prompt), stop and re-run the Guard's "Ensure AWS
Bedrock credentials" step — do not silently fall back.

### Arguments

| Flag | Description |
|------|-------------|
| `--project-uuid` | Project UUID (defaults to `.breeze.json`) |
| `--api-key` | API key (defaults to `.breeze.json`) |
| `--api-base` | API base URL (resolves from `.breeze.json` → `breeze.config.json` → `https://isometric-backend.accionbreeze.com`) |
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
/breeze:deprecated-cluster-pipeline

# With custom DBSCAN threshold (looser clustering)
/breeze:deprecated-cluster-pipeline --eps 0.30

# Resume from Pass 3 (skip intent extraction and outcome assignment)
/breeze:deprecated-cluster-pipeline --resume-from 3

# Test with a single cluster first
/breeze:deprecated-cluster-pipeline --cluster 45
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

## Why Mode B Needs Both Code Graph AND Local File Access

Mode B uses **two complementary sources** for every entry point:

1. **Code Graph Search** (for BOTH frontend AND backend):
   - Frontend: function signatures, call chains, service hook dependencies, imports, class structures, route decorators
   - Backend: controller handlers, service methods, database queries, middleware chains, entity relationships
   - The code graph captures the **logic and data flow** across the full stack

2. **Local file reading** (for UI-specific details the code graph misses):
   - JSX/TSX return blocks, template markup, conditional rendering (`v-if`, ternaries)
   - Form fields, event handlers (`onClick`, `onSubmit`, `onChange`)
   - CSS/styling that implies UI structure (grids, tabs, modals)
   - The code graph does NOT index template/JSX content — only script-level declarations

**Rule: Always search the code graph FIRST for both frontend and backend files,
then supplement with local file reading for UI template details that the code graph cannot capture.**

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `projectUuid`. Call `Call_Get_Project_Details_` with `uuid=<projectUuid>` once
and cache the returned project `name` — required by the bulk upsert in Phase 7.

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

### Step 2: Use code graph AND local files for route discovery
- **Code graph first**: search with framework-specific queries:
  - Vue: `"src/router/index.js vue router route definitions"`
  - React: `"routes.tsx react router createBrowserRouter Route"`
  - Angular: `"app-routing.module.ts angular routes"`
- The File node's `statements` field often contains full route definitions
- Use a second query for navigation structure (sidebar, navbar)
- **Then read the router file locally** — code graph may not capture the full
  route config (lazy imports, nested routes, route guards). Local reading
  gives the complete picture including dynamic imports and component mappings
- Read the sidebar/navbar component locally to discover panel triggers and
  non-routed features (drawers, modals, overlay panels)

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

### Step 6: Discover non-routed feature surfaces (panels, drawers, modals)

**CRITICAL: Routes alone do NOT capture the full application.** Many significant feature
surfaces live as panels, drawers, or overlay components with no dedicated URL. These are
triggered by state changes (e.g., `setPanelType()`, `setIsOpen()`) from within routed pages.

**How to discover them:**
1. **Search for panel/drawer type constants** — look for panel type enums, constants, or
   union types (e.g., `TPanel`, `panelType`, `drawerType`) in constants or context files
2. **Read the panel/drawer renderer** — find the component that switches on panel type
   to render different layouts (e.g., `RightPanelLayout`, `PanelDrawer`)
3. **Identify feature-rich panels** — panels that have their own tabs, CRUD operations,
   sub-components, or API calls are significant feature surfaces (not just simple viewers)

**Classification rules:**
- **Simple viewer panels** (e.g., markdown render, Gherkin script display): capture as
  actions within the triggering page's scenarios (e.g., "View Gherkin script in side panel")
- **Feature-rich panels** (e.g., a panel with tabs, forms, CRUD, its own API calls):
  treat as a **separate entry point** in `entrypoints.json` with `"type": "panel"` and
  process it as its own batch with full context collation (Phase 2 + 3)

**Add feature-rich panels to `entrypoints.json`:**
```json
{
  "id": 18,
  "route": null,
  "title": "Semantic Model Panel",
  "component": "src/components/layout/unified-model-layout.tsx",
  "auth": true,
  "type": "panel",
  "trigger": "setPanelType('UNIFIED_MODEL')",
  "triggeredFrom": ["dashboard", "sidebar"],
  "category": "Semantic Model",
  "status": "pending"
}
```

**Why this matters:** A panel like the Semantic Model (with Functional, Architecture,
Design, Code, and History tabs — each with full CRUD, pagination, search, import/export,
clone, merge, and version history) is a larger feature surface than most routed pages.
Missing it would leave a major gap in the functional graph.

**Also check for sub-tab workspaces within pages.** Some pages contain tabbed
layouts where each tab is a full feature surface with its own CRUD operations,
service hooks, and backend controllers. These are NOT panels — they're rendered
inline within the page component. Discover them by:
1. Grepping for `TabsContent` or `activeTab` in page and layout components
2. Reading the parent layout to see what tabs exist and what components they render
3. Processing each significant tab as part of the parent page's batch

**Check for conditional layouts on parameterized routes.** A single route like
`/chat/:agent/:id` may render completely different layouts depending on the URL
parameter value. For example, one agent param might show a simple chat, while
another renders a full workspace with tabs, canvas, and CRUD operations. These
are easy to miss because the route looks like it was already processed.

**How to discover them:**
1. When processing a parameterized route, check if the component conditionally
   renders different layouts based on the param (e.g., `if (agent === "x") return <WorkspaceLayout />`)
2. Read EACH conditional branch — not just the default. Each branch that renders
   a different layout component is effectively a separate entry point
3. For significant branches, add them as variant entry points in `entrypoints.json`:
   ```json
   {
     "id": 19,
     "route": "/chat/:agent/:id",
     "title": "Architecture Workspace",
     "component": "src/components/layout/architecture-agent-layout.tsx",
     "auth": true,
     "type": "route-variant",
     "paramValue": {"agent": "architecture_agent"},
     "triggeredFrom": ["agents page"],
     "category": "Architecture",
     "status": "pending"
   }
   ```
4. Process each variant as its own batch with full context collation

### Step 7: Cross-reference backend API routes
If the backend repo is indexed in the code graph:
- Search for the routes definition file (e.g., `routes.py`)
- List all backend API endpoints
- Flag endpoints not called from any frontend code

### Step 8: Generate `entrypoints.json`
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
      "type": "route",
      "category": "Category",
      "status": "pending",
      "backendCodeGraphChecked": false,
      "backendControllersFound": []
    }
  ]
}
```

- `type`: `"route"` (default) or `"panel"` for non-routed feature surfaces
- `backendCodeGraphChecked`: updated to `true` after Phase 3 backend search
- `backendControllersFound`: populated with file paths of backend controllers found
```

Present the list to the user for review. Ask if any should be excluded.

## Phase 1: Batch Entry Points by Category

1. Read `entrypoints.json`, group pending EPs by category or shared component
2. Plan which EPs share the same outcome (e.g., Invoice list + Create + Edit → "Manage Invoices")
3. **Include panel-type entry points** — feature-rich panels (type: "panel") should be
   processed as their own batch, not folded into the pages that trigger them
4. Process one batch per upsert call

## Phase 2: Collate Context (Code Graph + Local Files)

For EVERY entry point batch, use **both** code graph search and direct file reading.
The code graph is the **primary source** for understanding logic; local files fill in
UI-specific details the code graph cannot capture.

### Step 1: Search code graph for frontend components
- Search for the page component: `Code_Graph_Search` with `"<ComponentName>.tsx <description>"`
- Search for service hooks used by the page: `Code_Graph_Search` with `"use<HookName> service hook"`
- Extract from code graph results: imports, function signatures, `calls` field (call chains),
  class structures, injected services, route decorators
- Use `Get_Code_Nodes_By_Label(label="File", filters={"id": <fileId>} OR {"path": <path>, "repositoryName": <repo>}, children=true)` for full hierarchy (classes → methods → statements)
- For child/sub-components referenced in the page, search code graph for those too

### Step 2: Read local files for UI template details
**Code graph does NOT capture JSX return blocks or template markup.** Read the actual file for:
- Form fields, input elements, select/dropdown options
- Conditional rendering (ternaries, `v-if`/`v-show`, `&&` guards)
- Event handlers (`onClick`, `onSubmit`, `onChange`, `@click`, `@submit`)
- Tab structures, modal triggers, panel openers (`setPanelType` calls)
- Use Grep for quick extraction of patterns (`v-model`, `@submit`, `onClick`) — skip inline SVGs
- For React: read the component's return/render block for UI structure
- For Vue: read `<template>` section separately from `<script>`

### Step 3: Identify API calls from frontend
- From service hooks and component code, extract all API endpoints (axios/fetch/apiFetch calls)
- Note the HTTP method, URL pattern, request payload shape, and response handling
- These become the bridge to backend code graph search in the next phase

## Phase 3: Search Code Graph for Backend (System Persona) — MANDATORY

**This phase is REQUIRED for every batch**, not optional. Generate System persona
**alongside** User persona for each outcome:

1. From Phase 2 Step 3, take each identified API endpoint
2. Search the **backend** code graph with descriptive queries:
   `"<controllerName> <httpMethod> <endpointDescription> handler"` (not just URL paths)
3. Use `Get_Code_Nodes_By_Label(label="File", filters={"path": <path>, "repositoryName": <repo>}, children=true)` on backend controller/service files to get:
   - Route decorators (e.g., `@Post('/login', ...)`) confirming the endpoint
   - Method call chains (what the handler calls: services, repositories, helpers)
   - Database queries (`query_statement` type in statements)
   - Injected services and their methods
4. Follow the call chain one level deeper: search for the service methods the controller calls
5. Build System persona scenarios describing actual backend processing with grounded evidence

**System persona MUST be grounded in backend code graph — do NOT infer from frontend alone.**
**If a backend repository is not indexed in the code graph, note this and skip System persona
for those APIs — do not fabricate backend behavior.**

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
  "type": "REST",
  "method": "POST",
  "url": "/invoice",
  "request": "{payload shape}",
  "response": "{response shape}"
}]
```

- `type`: protocol — `REST` (default), `GraphQL`, `gRPC`, `WebSocket`, `Event`
- `method`: operation verb for that protocol:
  - REST: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`
  - GraphQL: `QUERY`, `MUTATION`, `SUBSCRIPTION`
  - gRPC: `UNARY`, `SERVER_STREAM`, `CLIENT_STREAM`, `BIDI_STREAM`
  - WebSocket: `EMIT`, `ON`, `SUBSCRIBE`
  - Event: `PUBLISH`, `CONSUME`
- `url`: endpoint path, query name, service.method, or event name

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

## Phase 7: Write to Functional Graph via MCP Bulk Upsert

Build the nested `data` payload (top-level `personas` array) and call
the `bulk_update_functional_nodes` MCP tool:

```
bulk_update_functional_nodes(
  uuid: <projectUuid>,
  name: <project name from Call_Get_Project_Details_>,
  data: <payload below>,
  skip_step_and_action: false,
  embedding: true,
  llm_platform: "AWSBEDROCK"
)
```

`data` payload structure:
```json
{
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
            "apis": [{"type": "REST", "method": "POST", "url": "/invoice", "request": "...", "response": "..."}]
          }]
        }]
      }]
    }]
  }]
}
```

The project `uuid`, `name`, `skip_step_and_action`, `embedding`, and
`llm_platform` are passed as sibling MCP arguments — they do NOT go
inside `data`.

The upsert is **idempotent** — match keys are string names. Re-running updates, not duplicates.
The upsert **merges across calls** — you can add scenarios to the same outcome in separate calls.

## Phase 8: Mark Complete

Update `entrypoints.json` for each processed EP:
- Set `"status": "done"`
- Set `"backendCodeGraphChecked": true/false` — whether backend code graph was
  searched for this EP's API calls
- Set `"backendControllersFound": [...]` — list of backend controller/service file
  paths that were found and used for System persona generation
- If backend was NOT checked, add `"backendNote"` explaining why (e.g., "N8N
  integration only", "localStorage only", "no API calls from this page")

**This tracking is MANDATORY.** It ensures accountability — when reviewing results,
the user can verify which EPs have grounded System persona vs. frontend-only coverage.
If an EP has `backendCodeGraphChecked: false` without a valid reason, it should be
flagged for re-processing.

## Phase 9: Coverage Validation

After all EPs are done:
1. Pull complete functional graph via `Get_complete_functional_graph`
2. Extract all APIs linked in the graph
3. Extract all backend routes from the backend repo
4. Compare and categorize gaps: missing flows, helper APIs, export variants, legacy
5. Generate coverage report with percentage
6. Upsert missing flows if user approves
