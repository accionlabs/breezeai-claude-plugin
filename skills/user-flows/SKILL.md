---
name: user-flows
description: >
  Generate user flow cluster documents from the code graph to produce
  richer functional graph coverage. Traces entry points (pages,
  controllers) through service hooks, controllers, services, and data
  layers — connecting pieces that Louvain clusters miss. Use when:
  "generate user flows", "generate flow clusters", "trace user flows
  from code", "create flow documents for functional graph".
---

## Purpose

The standard Louvain cluster approach groups files by code similarity
(shared imports, same module). This works well within a module but
**breaks when a user flow crosses module boundaries** — a frontend
page calling a service hook calling a backend controller calling a
service calling a database. These end up in different clusters, so
the LLM processing each cluster never sees the full flow.

This skill generates **flow-based clusters** that trace from entry
points (pages, controllers) through the entire call chain, bundling
all files involved in a single user flow into one document. This
produces a richer functional graph with:

- Connected frontend-to-backend scenarios (not fragmented)
- Async processing patterns captured (fire-and-forget, queues)
- Cross-repo call chains visible in one document
- Remaining files grouped by Louvain cluster ID (nothing lost)

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run
`/breeze:init`. Extract `apiKey` and `projectUuid`.

## Step 1 — Generate Raw Flow Clusters

Run the flow cluster generator script bundled in this skill's
directory:

```bash
python3 {SKILL_DIR}/flow_cluster_generator.py \
  --project-uuid {projectUuid} \
  --api-key {apiKey} \
  --output-dir ./flow-clusters
```

Where `{SKILL_DIR}` is the directory containing this SKILL.md file.

The script will:
1. Fetch all code ontologies for the project
2. Fetch all files with full hierarchy (functions, classes, statements)
3. Detect entry points using 3 layers:
   - **Layer 1:** Route decorators/annotations in statements (works for any language)
   - **Layer 2:** File path patterns (controllers/, pages/, handlers/)
   - **Layer 3:** Graph structure (high outbound calls, low inbound = entry point)
4. Trace call chains from each entry point following CALLS paths
5. Cross-match frontend hooks to backend controllers by entity name
6. Bundle files into flow cluster documents
7. Group remaining (uncovered) files by Louvain cluster ID (min 15 files per cluster)

Wait for the script to complete and note the output summary.

## Step 2 — AI Format Flow Clusters (markdown format only)

**Skip this step entirely if `--format raw` was used.**

For EACH flow cluster file (types: UI_TO_BACKEND or BACKEND_ONLY — NOT remaining-cluster-* files):

1. Read the raw markdown file
2. Reformat with AI-generated descriptions:

**For each FILE section, add:**
- **Role:** — One-line description of what this file does in the flow

**Group statements logically:**
- "Key State Declarations" — useState, useRef, computed values
- "Hook Bindings" — useMutation, useQuery wiring
- "Constants" — PAGE_SIZE, MAX_FILE_SIZE, config objects
- Format as: `[lineNum]` `code snippet` -- description

**For each function, add:**
- **Description:** — Brief explanation derived from function name, its calls, params, and statements

**For backend controllers, format routes clearly:**
```
#### @Post('/generate') → importJsonTree(req, res, next)
Lines: 73-186 | Auth: required | Role: all | DTO: ImportJsonTreeDto | fileUpload: true
```

**For classes with @Inject, list prominently:**
```
### Injected Services
- DocumentService → src/services/document.service.ts
- AWSService → src/services/aws.service.ts
```

**Rules:**
- Keep ALL data — don't remove any functions, calls, statements, imports
- Don't invent functionality not present in the data
- Don't summarize away details — only ADD descriptions and improve formatting

3. Write the polished version back to the same file

**Leave remaining-cluster-* files as-is** (raw format, no AI formatting).

## Step 3 — Report Summary

Print a summary showing:
- Number of flow clusters generated (with file counts and LOC)
- Number of remaining clusters
- Total files covered vs total files in codebase
- List of all generated files

## Step 4 — Upload (On User Request)

Ask the user: "Would you like to upload these flow clusters to BreezeAI as documents?"

**If yes:**

For each cluster file in `./flow-clusters/` (`.md` or `.json`):
1. Upload using multipart form POST:
   ```
   POST https://isometric-backend.accionbreeze.com/documents/upload
   Headers: api-key: {apiKey}
   Body (form-data):
     uuid: {projectUuid}
     file: {the markdown file}
   ```
2. Log success/failure for each upload
3. If any upload fails, continue with the rest and report failures at the end

**If no:** Skip upload, inform the user the files are available locally in `./flow-clusters/`.

## Arguments

`$ARGUMENTS` are passed directly to the Python script. Supported options:

- `--format <raw|markdown>` — Output format. `raw` outputs API JSON as-is (no formatting). `markdown` outputs formatted readable markdown (default). AI formatting in Step 2 only applies to `markdown` format.
- `--entry-point <name>` — Filter to a specific flow (e.g., "knowledge-management")
- `--output-dir <path>` — Custom output directory (default: ./flow-clusters)
- `--max-depth <n>` — Maximum call chain depth (default: 4)
- `--max-files <n>` — Maximum files per flow cluster (default: 20)

Examples:
```
/breeze:user-flows
/breeze:user-flows --format raw
/breeze:user-flows --entry-point knowledge-management
/breeze:user-flows --output-dir ./my-flows
```

## How It Differs from Cluster Approach

| Aspect | Louvain Clusters | User Flow Clusters |
|--------|-----------------|-------------------|
| Grouping | Code similarity (shared imports) | Call chain from entry point |
| Cross-repo | Never — each cluster is single repo | Yes — frontend + backend in one document |
| Entry points | Not identified | Pages, controllers, handlers detected |
| Async patterns | Not visible | Detected from call names (Async, Queue, Workflow) |
| Missing files | None — all files in some cluster | None — remaining files grouped by Louvain ID |
| Best for | Module-level understanding | User flow understanding, functional graph generation |
