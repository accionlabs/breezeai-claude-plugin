---
name: generate-architecture
description: >
  Generate the full Architecture Ontology (the 8-layer architecture graph) for a
  project from an architecture spec document. Reads the spec (PDF / markdown /
  image / diagram / text), maps every component to exactly ONE of the 8
  architectural layers (UserExperience, ApiGateway, ObservabilityMonitoring,
  Agents, Services, EventQueue, DataLake, Infrastructure), populates the
  layer-specific fields, dedups against the existing architecture graph via
  Architecture_Graph_Search, and commits each node via Create/Update_Architecture_Node
  in layer-hierarchy order. Runs in two grounding modes: doc-only (spec is the sole
  source) or code-grounded (when the project has onboarded repos — verifies claims
  and attaches code_ontology_id via the Code Graph). Can additionally ingest a
  Terraform / IaC repo (--iac <path>) to derive the deployed topology (services,
  gateways, queues, data stores, infra) by parsing HCL directly. Use when: generate
  architecture, generate architecture ontology, build the architecture graph, ingest
  an architecture spec / design document into Breeze, derive topology from Terraform,
  document the system topology.
argument-hint: "[spec-doc-path-or-url] [--project <name|uuid>] [--doc-only] [--iac <terraform-repo-path>]"
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

## What this skill does

Transforms an **architecture spec document** into the complete **Architecture Ontology** — the 8-layer architecture graph under a single root `Architectural` node:

```
Architectural
 ├─ UserExperience            (level 1)  client-side delivery modalities
 ├─ ApiGateway               (level 2)  routing / auth / rate-limit
 ├─ Services                 (level 3)  domain + platform business logic
 ├─ Agents                   (level 3)  AI workflows        [+ model_backend, tools_available]
 ├─ EventQueue               (level 4)  async messaging
 ├─ DataLake                 (level 5)  storage / analytics / AI-ML  [+ model_type, vector_db]
 ├─ ObservabilityMonitoring  (level 6)  metrics / traces / logs
 └─ Infrastructure           (level 7)  compute / network / deploy
```

**Every component belongs to exactly one layer.** The layer set is fixed — never invent a 9th layer. Full data model, per-layer fields, and placement rules: [references/architecture-ontology.md](references/architecture-ontology.md).

### How this differs from the neighbouring skills

| Skill | Input | Behaviour |
|---|---|---|
| `/breeze:analyze-architecture` | ONE requirement (Jira / doc / image) | Requirement-driven; maps the delta, runs impact/reuse/gap analysis, commits *selected* nodes. Analysis output is ephemeral. |
| **`/breeze:generate-architecture`** (this skill) | A full architecture **spec document** | Full-graph generation pass — produces the *entire* 8-layer ontology and commits it (idempotent merge). |
| `/breeze:search` | A question | Read-only; queries the architecture graph (`Architecture_Graph_Search`) among others. |

It is the architecture analogue of `/breeze:generate-functional-from-backend` and `/breeze:generate-design-from-ui`: a one-shot generation of a whole ontology, not an incremental analysis.

### Grounding modes (how nodes get verified/linked)

| Mode | When | What you get |
|---|---|---|
| **doc-only** | No onboarded repo, or `--doc-only` passed | Full structural graph from the spec. Nodes carry a doc citation but **no `code_ontology_id`** — downstream `impact-analysis` / `analyze-architecture` cannot anchor them to code. |
| **code-grounded** (default when repos are indexed) | Project has ≥1 repo onboarded via `/breeze:onboard-repository` | Everything doc-only gives, PLUS: tech claims verified against the Code Graph, `code_ontology_id` + `repositoryName` attached to code-backed nodes, and components the spec omitted surfaced from `Code_Graph_Search`. |

The spec document is **always the primary source**. Code-grounding verifies and enriches — it never overrides an explicit spec claim without flagging the divergence to the user.

### IaC input source (orthogonal — the best source for provisioned infra)

`--iac <terraform-repo-path>` adds a **Terraform / IaC ingestion pass** (Phase 1.5). Terraform is the *authoritative* source for the **Infrastructure, EventQueue, DataLake, and ApiGateway** layers — the spec doc is usually vaguer about them.

**This is a filesystem read, not code-grounding.** The Breeze code-ontology generator only parses *source languages* — it never indexes `.tf` / HCL, so `Code_Graph_Search` returns nothing structured for a Terraform repo. IaC nodes are derived by parsing `resource` / `module` blocks directly (Read/Glob/Grep). Provide the repo **path** — onboarding a Terraform repo does not help. Full resource→layer table: [references/iac-mapping.md](references/iac-mapping.md).

IaC combines with either grounding mode: IaC supplies deployment/tech/region for infra nodes; code-grounding can still attach `code_ontology_id` to the *Service* workloads from the application repos.

## Resources

- `references/architecture-ontology.md` — the 8-layer data model: which fields each layer carries (including the extra fields — `model_backend`/`tools_available` on Agents, `model_type`/`vector_db` on DataLake), placement rules, layer levels, and the ⚠ bare-`label` gotcha. **Read this before Phase 3.**
- `references/iac-mapping.md` — how to read a Terraform repo and the resource→layer mapping (AWS / GCP / Azure / K8s+Helm) + the spec↔IaC merge policy. **Read this before Phase 1.5** (only when `--iac` is passed).
- Canonical field samples per layer live in `../analyze-architecture/references/guide.md` (single source of truth for the node data model — do not fork it; extend it there if a field is missing).

## Inputs

- **Architecture spec document** — argument (`$ARGUMENTS`), a path/URL, or pasted inline. Accepts PDF, markdown, plain text, and images/diagrams (routed through multimodal extraction).
- **Terraform / IaC repo** *(optional)* — `--iac <path>`. A filesystem path to `.tf` sources (state / plan output is even better if the user provides it). Read directly, not via the code graph.
- **`.breeze.json`** — for `projectUuid` and any URL overrides.
- **Existing architecture graph** — read for dedup + to resolve the root `architecturalId`.
- **Code graph (code-grounded mode only)** — queried per node for verification + `code_ontology_id`.
- **Functional graph (optional)** — queried for best-effort scenario anchoring on UX / ApiGateway / Services nodes.

## Outputs

- **Architecture graph** populated / updated with the 8 layers (idempotent merge by node name within a layer).
- **`architecture-inventory.json`** — local working artifact next to the spec doc: the extracted component inventory + per-node commit decision + checkpoint (supports review, resume, and re-runs). Never committed to the repo automatically.

---

# PHASES

## Bootstrap (run ONCE at skill start)

1. Read `.breeze.json` from the plugin working directory. If missing or `projectUuid` absent → resolve per `CLAUDE.md` (or tell the user to run `/breeze:project setup`). Cache `projectUuid`.
2. **Resolve URLs** from `breeze.config.json` (plugin root), overridable per-project via `.breeze.json` (`apiBase`, `uiBaseUrl`). See `CLAUDE.md` → "Service URLs".
3. Call `Call_Get_Project_Details_(uuid=<projectUuid>)` once; cache `name` and `projectId`.
4. **No API key is needed.** This skill writes through MCP tools (`Create_Architecture_Node` / `Update_Architecture_Node`), which are authenticated by the Claude Code session — there is no REST bulk-upsert path here (unlike `generate-functional-from-backend`). Never prompt for `apiKey`.

## Phase 1 — Load the architecture spec document

1. Resolve the spec source: `$ARGUMENTS` path/URL → else ask: *"Point me at the architecture spec document (path, URL, or paste it). I accept PDF, markdown, text, or a diagram/image."* **Exception:** if `--iac <path>` was passed and no doc is given, the spec doc is optional — you may proceed with IaC (Phase 1.5) + code-grounding as the sources; confirm with the user that they want an IaC-driven pass without a spec.
2. Read it. For PDFs use the Read `pages` parameter; for images/diagrams extract the topology multimodally (boxes = components, arrows = data flow, swimlanes/tiers often map to layers).
3. Build a raw **component inventory** — one row per component the doc names, with whatever the doc states: name, description, technologies, protocols, deployment, domain, and any layer-specific hints. Do not classify yet.
4. Write the raw inventory to `architecture-inventory.json` next to the doc (or in the cwd) so the run is resumable.

> If the doc is large, extract layer-by-layer and checkpoint after each. The parent's context should hold the inventory, not the full doc text.

## Phase 1.5 — Ingest Terraform / IaC (only if `--iac <path>` was passed)

Skip entirely when `--iac` is absent. Read [references/iac-mapping.md](references/iac-mapping.md) first. This is a **filesystem read** — do NOT route it through the code graph (HCL isn't indexed).

1. `Glob` the IaC path for `**/*.tf`, `**/*.tf.json`, `**/*.hcl` (skip `.terraform/`, `.git/`). If the user provided `terraform plan`/`state` output, prefer that — it resolves interpolations and counts.
2. Parse each file's `resource "<type>" "<name>"` and `module "<name>"` blocks; capture type, local name, salient args (engine, instance_class, `name`/`bucket`/`queue`, `tags`), and read `provider` blocks + `*.tfvars`/`locals` for cloud provider + region(s) + environment. Resolve local `module` sources by reading their `.tf`.
3. Map each resource to its layer via the resource→layer table in the reference. Emit IaC-derived rows into the **same `architecture-inventory.json`**, tagged `source: "iac"`, with `citation` = the `.tf` path + resource address (e.g. `infra/modules/db/main.tf → aws_rds_instance.orders`). Fill deployment/tech/region/`access_url`; IaC nodes carry **no `code_ontology_id`** (expected).
4. Unmapped resource types → flag for the Phase 6 gate rather than guessing a layer.

> The **merge** with spec-doc rows happens in Phase 3 (dedup within the inventory): IaC is authoritative for provisioned infra (Infrastructure / EventQueue / DataLake / ApiGateway existence + tech + region); the spec doc is authoritative for business-facing meaning (Service domains, Agent purpose, UX modalities, descriptions). See the merge policy in the reference.

## Phase 2 — Read existing state & pick the mode (parallel)

Run these together:

- **Existing architecture graph** — `Get_All_architecture_Graph(projectUuid)`. Record the root `architecturalId` (create the root in Phase 7 if absent). Group existing nodes by layer for dedup. If the graph is empty/sparse (< 3 nodes) → **first-time generation** (mostly `Create`); if populated → **merge mode** (dedup → `Update` vs `Create`).
- **Repo inventory** — `Call_List_Repositories_(projectUuid)`. If ≥1 repo has `fileCount > 0` and `status: "active"` **and** the user did NOT pass `--doc-only` → **code-grounded mode**. Otherwise → **doc-only mode**. Announce the chosen grounding mode (and whether IaC ingestion ran) to the user in one line, e.g. `Mode: code-grounded + IaC (2 repos, terraform/)`.

## Phase 3 — Classify: map every component to exactly one layer

For each component in the inventory, assign it to **exactly one** of the 8 layers and populate that layer's fields. Follow [references/architecture-ontology.md](references/architecture-ontology.md) for the field list per layer and the placement rules. Key rules (do not deviate):

- **UserExperience is modality-level** — one node per delivery channel (web, mobile, voice, CLI, API client), NOT per page/component. Pages/components belong to the Design Ontology.
- **Auth / Search / Notifications → Services (Platform Services)**, never ApiGateway or Infrastructure.
- **ML training / dbt / Spark / feature store / vector DB → DataLake**, never Services. Set `model_type` and `vector_db`.
- **AI agent / LLM workflow → Agents**, never Services. Set `model_backend` and `tools_available`.
- **A component that fits no layer cleanly** → do NOT force it and do NOT invent a layer. Flag it for the user in the Phase 6 gate.
- Set `citation` on every node to the spec reference (doc name + page/section/heading, or file hash). A node with no citation must not be committed. IaC-derived rows keep their `.tf`-path citation from Phase 1.5.
- Assign the correct `level` per the layer-levels table in the reference.

**Merge spec ↔ IaC rows (only if Phase 1.5 ran):** when a spec row and an IaC row denote the same component (e.g. spec "Orders DB" ↔ `aws_rds_instance.orders`), collapse them into **one** node — spec supplies name/description/domain, IaC supplies technology/deployment/region/`access_url`. Match on name similarity + resource role. An IaC row with no spec counterpart becomes a node flagged `source: "iac-discovered"` (surfaced in the Phase 6 gate). Follow the merge policy in [references/iac-mapping.md](references/iac-mapping.md).

Update each inventory row with: `layer`, layer-specific fields, `citation`, and a provisional `decision: "create"`.

## Phase 4 — Code-grounding pass (code-grounded mode only)

Skip entirely in doc-only mode. For each node whose layer maps to code (UserExperience, ApiGateway, Services, Agents, EventQueue, DataLake):

1. Run `Code_Graph_Search` with 1–3 queries derived from the node (name, domain, key technology). Optionally scope with `repository_name=` when the node clearly maps to one repo (get names from the Phase 2 inventory).
2. **Attach grounding:** from the top hits, set `code_ontology_id` (the returned `codeOntologyId`) and `repositoryName` on the node.
3. **Verify:** if the code confirms the doc's technology/pattern → mark verified. If the code contradicts the doc (doc says Kafka, code shows SQS) → keep the doc value but record a `divergence` note for the Phase 6 gate; never silently overwrite.
4. **Gap-fill:** if `Code_Graph_Search` surfaces a clear component the spec omitted (an un-documented service, queue, or data store), add it to the inventory as a new node flagged `source: "code-discovered"` so the user can accept or reject it in the gate.

Nodes with no code correlation (often Infrastructure / ObservabilityMonitoring) simply carry no `code_ontology_id` — that is expected, not an error.

## Phase 5 — Dedup against the existing graph

For every proposed node, decide `create` vs `update`:

1. `Architecture_Graph_Search(uuid=projectUuid, include_labels=[<layer>], query=<node name + key tech>)` — semantic match within the layer.
2. For completeness (semantic search silently drops non-matches), also consult the per-layer lists from Phase 2 (`Get_Architecture_Nodes_By_Label` if not already loaded).
3. Match on name (case-insensitive) → then on `technologies` + `domain`/`category` overlap. On a confident match → set `decision: "update"` and record the existing node `id`; else `decision: "create"`.

Record the decision + matched id on each inventory row.

## Phase 6 — Confirmation gate ⛔ (parent-side)

Present the full proposed graph and **wait for the user**. Do not commit before confirmation. Show:

1. **Mode** — doc-only / code-grounded, whether IaC ingestion ran, and which repos / IaC path were used.
2. **8-layer table** — every proposed node with its layer, `create`/`update` decision, key fields, `source` (doc / iac / code), and `code_ontology_id` (or "— doc-only").
3. **Divergences** — doc-vs-code (Phase 4) and doc-vs-IaC (Phase 3 merge) conflicts for the user to arbitrate.
4. **Discovered nodes** — components not in the spec, from code (`code-discovered`) or IaC (`iac-discovered`); ask accept/reject each.
5. **Unclassifiable components** — anything that fit no layer, incl. unmapped IaC resource types (Phase 1.5 / Phase 3), for placement or drop.
6. **Best-effort scenario anchors** *(optional)* — for UX / ApiGateway / Services nodes, if a functional graph exists, run `Functional_Graph_Search` and propose `scenario` anchors. Unlike `analyze-architecture`, missing anchors here are **non-blocking** (a generation pass often precedes the functional graph) — offer them, don't require them.

Loop on this step until the user confirms. Apply their edits to the inventory.

## Phase 7 — Commit in layer-hierarchy order

1. **Root node** — ensure the `Architectural` root exists (from Phase 2). If absent, create it first and capture its `id` as `architecturalId` for every child.
2. Commit nodes in this order so parents/levels land consistently:
   **UserExperience → ApiGateway → Services → Agents → EventQueue → DataLake → ObservabilityMonitoring → Infrastructure.**
3. Per node: `decision: "create"` → `Create_Architecture_Node`; `decision: "update"` → `Update_Architecture_Node` with the matched `id`. Pass `architecturalId`, `projectUuid`, `name`, `level`, `citation`, the layer-specific fields, and (code-grounded) `code_ontology_id` + `repositoryName`.

### ⚠ LABEL PARAMETER — read before committing

The `label` argument **MUST be the bare layer name** — `UserExperience`, `ApiGateway`, `Services`, `Agents`, `EventQueue`, `DataLake`, `ObservabilityMonitoring`, `Infrastructure`. The tool's own schema *misleadingly* lists `...Label`-suffixed values; using them returns a generic **400**.

```
✓ label: "Services"       → success
✗ label: "ServicesLabel"  → 400 Bad Request
```

After each successful commit, mark the inventory row `committed: true` with the returned node `id` (checkpoint — a mid-run stop resumes cleanly).

## Phase 8 — Verify & report

1. Re-read with `Get_Architecture_Nodes_By_Label` per layer (or one `Get_All_architecture_Graph`); confirm counts match the committed inventory.
2. Spot-check 2–3 nodes via `Architecture_Graph_Search` and confirm they resolve.
3. Report a concise summary: nodes created / updated per layer, code-grounded vs doc-only counts, divergences resolved, and anything the user deferred. Point the user at `/breeze:analyze-architecture` (per-requirement deltas) and `/breeze:search` (querying the graph) as follow-ups.

---

# REFERENCE

## Idempotency & re-runs

Re-running against an updated spec is safe: Phase 5 dedup routes existing nodes to `Update`. The `architecture-inventory.json` checkpoint lets you resume a partial run (skip rows already `committed: true`) or diff a new spec against a prior pass.

## When NOT to use

- **A single new requirement / change** → use `/breeze:analyze-architecture` (delta + impact analysis).
- **Just querying the graph** → use `/breeze:search`.
- **No spec document at all** → run `/breeze:analyze-architecture` in ad-hoc current-state-capture mode instead, or produce a spec first.

## See also

- `/breeze:analyze-architecture` — per-requirement impact / reuse / gap analysis against this graph.
- `/breeze:onboard-repository` — index a repo so code-grounded mode can attach `code_ontology_id`.
- `/breeze:search` — read + synthesize across the architecture, functional, design, and code graphs.
- `/breeze:impact-analysis` — blast radius that anchors on the `code_ontology_id` this skill sets.
