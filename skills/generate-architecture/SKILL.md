---
name: generate-architecture
description: >
  Generate the complete Architecture Ontology for a project from ANY source — a codebase, a
  Terraform/IaC tree, SQL DDL or Elasticsearch mappings, an architecture spec document, a
  Confluence page, or any combination. Auto-detects what it is pointed at, maps every
  component to exactly ONE of the 8 architectural layers (UserExperience, ApiGateway,
  Services, Agents, EventQueue, DataLake, ObservabilityMonitoring, Infrastructure), and —
  when the tree contains .sql or ES mappings — also populates the DataLake schema layer
  (DDLTable/DDLColumn/DDLConstraint/DDLIndex/DDLView/DDLProcedure, ESIndex/ESField/ESAlias)
  using the bulk REST ingest path so foreign-key edges are built correctly. Dedups against
  the existing graph, commits in layer order, and verifies. Use when: generate architecture,
  generate architecture ontology, build the architecture graph, map this repo to the 8
  layers, ingest an architecture spec / Confluence page, derive topology from Terraform,
  load the database schema into the architecture graph, document the system topology.
argument-hint: "[repo-path | doc-path | confluence-url] [--project <name|uuid>] [--iac <path>] [--sql <path>] [--doc-only] [--no-schema]"
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

## What this skill does

Builds the **whole architecture picture** — the 8-layer topology **plus the data-layer schema
beneath it** — from whatever you point it at.

```
Architectural
 ├─ UserExperience            (level 1)  client-side delivery modalities
 ├─ ApiGateway                (level 2)  routing / auth / rate-limit
 ├─ Services                  (level 3)  domain + platform business logic
 ├─ Agents                    (level 3)  AI workflows      [+ model_backend, tools_available]
 ├─ EventQueue                (level 4)  async messaging
 ├─ DataLake                  (level 5)  one node per PHYSICAL database / store
 │    ├─ DDLTable → DDLColumn · DDLConstraint · DDLIndex   (+ FK REFERENCES edges)
 │    ├─ DDLView · DDLProcedure · DDLSequence
 │    └─ ESIndex → ESField · ESAlias
 ├─ ObservabilityMonitoring   (level 6)  metrics / traces / logs
 └─ Infrastructure            (level 7)  compute / network / deploy
```

**Every component belongs to exactly one layer.** The set is fixed — never invent a 9th.

### It accepts anything

| Point it at | It does |
|---|---|
| **A codebase** | Reads the tree (and the Code Graph if indexed), derives all 8 layers, attaches `code_ontology_id` |
| **Terraform / IaC** | Parses HCL for the provisioned topology — authoritative for Infrastructure / EventQueue / DataLake / ApiGateway |
| **`.sql` / ES mappings** | Bulk-ingests the full schema under the right DataLake |
| **A spec doc / PDF / diagram** | Extracts the described topology (multimodal for diagrams) |
| **A Confluence URL** | Fetches and treats it as the spec |
| **Any combination** | Merges them with an explicit precedence order |

Sources **compose**. A repo containing `terraform/` and `db/*.sql` runs all three passes and
merges into one graph — no flags needed.

### How this differs from the neighbouring skills

| Skill | Input | Behaviour |
|---|---|---|
| `/breeze:analyze-architecture` | ONE requirement | Requirement-driven delta + impact/reuse/gap analysis. Output ephemeral. |
| **`/breeze:generate-architecture`** (this) | A whole system — any source | Full-graph generation incl. DB schema; commits idempotently. |
| `/breeze:search` | A question | Read-only. |

## Resources

Read the reference for a pass **before** running it — they carry the failure modes.

- `references/source-discovery.md` — detecting source kinds, deriving layers from code / IaC / manifests / docs, the **per-layer probes** (so no layer is silently missed), and the precedence table. **Read in Phase 1.**
- `references/architecture-ontology.md` — the 8-layer data model, per-layer fields, placement rules, levels, and the ⚠ bare-`label` gotcha. **Read before Phase 4.**
- `references/db-schema-ingestion.md` — bulk vs per-object write paths, the O(n²) trap, T-SQL preprocessing, batching, procedure extraction, verification. **Read before Phase 5** whenever `.sql` / ES mappings exist.
- `references/iac-mapping.md` — resource→layer table (AWS / GCP / Azure / K8s+Helm) + spec↔IaC merge policy. **Read before the IaC pass.**
- Canonical per-layer field samples: `../analyze-architecture/references/guide.md` — single source of truth; extend there, don't fork.

## Inputs

- **Any source** — `$ARGUMENTS` as a repo path, doc path, or Confluence URL; or explicit `--iac <path>` / `--sql <path>`.
- **`.breeze.json`** — `projectUuid`, URL overrides, and **`apiKey`** (required for schema ingest — see Bootstrap 4).
- **Existing architecture graph** — for dedup and the root `architecturalId`.
- **Code graph** — for verification + `code_ontology_id` when repos are indexed.
- **Functional graph** *(optional)* — for `scenario[]` anchors on UX / ApiGateway / Services.

## Outputs

- **Architecture graph** — 8 layers, idempotent merge by node name within a layer.
- **DataLake schema nodes** — tables/columns/indexes/constraints/views/procedures, with FK edges.
- **`architecture-inventory.json`** — working artifact: inventory + per-node decision + checkpoint. Supports review, resume, re-runs.

## Flags

| Flag | Effect |
|---|---|
| `--iac <path>` | Force an IaC pass on a path outside the main tree |
| `--sql <path>` | Force a schema pass on a path outside the main tree |
| `--doc-only` | Skip code-grounding even if repos are indexed |
| `--no-schema` | Topology only — skip the DataLake schema pass |
| `--project <name\|uuid>` | Project override for this invocation |

---

# PHASES

## Bootstrap (ONCE)

1. Resolve `projectUuid` (see **## Project**). Cache it.
2. Resolve URLs from `breeze.config.json`, overridable via `.breeze.json` (`apiBase`, `uiBaseUrl`).
3. `Call_Get_Project_Details_(uuid)` once; cache `name`, `projectId`.
4. **API key — needed only for the schema pass.** The 8-layer nodes are written via MCP (session-authenticated). The **DataLake schema pass is REST** and needs `apiKey` from `.breeze.json`. Resolve it **lazily**: only when Phase 5 will actually run. If absent, prompt once:
   > Schema ingest uses the bulk REST endpoint (the only path that builds foreign-key edges). It needs a Breeze API key. Generate one at `<uiBaseUrl>/mcp/generate/key`, then paste it here. I'll save it to `.breeze.json` (make sure that's gitignored).

   Save under `apiKey`; reply only "API key saved." **Never echo or log it.**

## Phase 1 — Detect sources & build the inventory

Read `references/source-discovery.md` first.

1. **Classify the input** per §0 of that reference. A single path often yields several source kinds — detect them all. Announce in one line:
   `Sources: code (2 repos indexed) + IaC (terraform/) + DDL (412 .sql) + doc (Confluence 2482…)`
2. **If nothing resolves**, ask once — offering the options rather than assuming a doc:
   *"Point me at a repo, a Terraform tree, a spec doc, or a Confluence URL — or several."*
3. **Run each applicable pass**, appending rows to one shared inventory. Tag every row with
   `source: doc | code | iac | manifest | sql` and a `citation`.
   - **Document / Confluence** — §1. Primary source for *meaning*, weakest for topology.
   - **Code** — §2. Ground truth for what exists. Count connection strings → DataLake census.
   - **IaC** — §3 + `iac-mapping.md`. Authoritative for provisioned infra.
   - **Manifests** — §4. Fills `node_count`, `regions[]`, `deployment_model`.
4. **Run the layer probes (§5) for every layer with no rows yet.** This is the step that
   prevents a silently-missing layer — especially `ObservabilityMonitoring`, which is almost
   never in a doc and almost always in the code.
5. Write `architecture-inventory.json` so the run is resumable.

> Large sources: extract incrementally and checkpoint. Your context should hold the
> **inventory**, not the raw source text.

## Phase 2 — Read existing state (parallel)

- `Get_All_architecture_Graph(projectUuid)` — record root `architecturalId`; group existing
  nodes by layer for dedup. **< 3 nodes → first-time generation; otherwise merge mode.**
- `Call_List_Repositories_(projectUuid)` — a repo with `fileCount > 0` and `status: "active"`
  (and no `--doc-only`) enables **code-grounded** mode.

Announce: `Mode: code-grounded + IaC + schema (2 repos, terraform/, 412 .sql)`.

## Phase 3 — Merge sources

Collapse rows describing the same component into one, applying the **precedence table**
(source-discovery §6):

- existence → code / IaC beats doc
- name, description, `domain[]` → doc beats code
- technology, region, deployment → IaC > code > doc
- schema detail → the `.sql` / live DB

**Record every conflict as a `divergence` on the row — never silently overwrite.** A doc that
contradicts the code is a finding for the user, not a merge to resolve quietly.

Rows only a non-doc source found are tagged `code-discovered` / `iac-discovered` for the gate.

## Phase 4 — Classify into the 8 layers

Read `references/architecture-ontology.md`. Assign each row to **exactly one** layer, set
`level`, and populate that layer's fields. Non-negotiable rules:

- **UserExperience is modality-level** — one node per delivery channel, never per page. Pages/components are the Design ontology.
- **Auth / Search / Notifications → `Services`** (platform services), never ApiGateway, never Infrastructure.
- **AI agent / LLM workflow → `Agents`**, never Services. Set `model_backend`, `tools_available[]`.
- **ML / dbt / Spark / feature store / vector DB → `DataLake`**, never Services. Set `model_type`, `vector_db`.
- **A queue/topic → `EventQueue`**; its producers/consumers → `Services`. A database-backed polling queue still counts as EventQueue.
- **One DataLake per PHYSICAL database** — a second connection string means a second node.
- **`DataLake.type`** (`Relational` | `Elastic` | `Non-Relational`) is **required and immutable after create**.
- **Numeric fields are numbers** — `level`, `node_count`, `cpu_cores_total`, `storage_pb`. A descriptive string is rejected.
- **Every node needs a `citation`.** No citation → do not commit.
- **Fits no layer?** Do not force it, do not invent a layer — flag it in the gate.

## Phase 5 — DataLake schema pass (when `.sql` / ES mappings exist)

Skip if `--no-schema`, or if no schema sources were detected. **Read `references/db-schema-ingestion.md` before running this.**

The essentials, in order:

1. **The DataLake node must exist first** — commit it (Phase 7 order puts DataLake before this,
   or create it now) and capture its `id` as `dataLakeId`.
2. **Test one file as-is first** (§3). If it returns objects, no preprocessing needed. If it
   returns `tables=0` / `422`, apply the transforms — strip comments, unwrap guard blocks,
   drop procedural noise, normalise `;` separators — then re-test the same file before
   batching. The idioms differ by dialect; the rule (**bare, `;`-separated DDL**) does not.
3. **Batch ~110 files per upload** (§4) and POST to `/db-ontology/stream-ingest`. Add a
   per-batch fallback that retries files individually on non-202.
4. **Procedures/functions/triggers separately** (§5.2) via `POST /db-ontology/procedure` at
   concurrency 6–8 — the bulk parser drops them entirely. Slice `body` **from the `AS` keyword**
   so the 1000-char cap carries logic, not the signature.
5. **Verify** (§9) — the 202 is only a parse receipt; nodes land ~10 s later.

> ⛔ **Never loop `Create_DB_Schema_Column`.** Per-object column writes trigger a server-side
> re-embed of the table *and every column already on it* (O(n²)) — it stalls, and it cannot
> create FK edges at all. Bulk is the only correct path for tables/columns.

## Phase 6 — Dedup against the existing graph

1. `Architecture_Graph_Search(uuid, include_labels=[<layer>], query=<name + key tech>)`.
2. Semantic search silently drops non-matches — also consult the Phase-2 per-layer lists
   (`Get_Architecture_Nodes_By_Label`) for completeness.
3. Match on name (case-insensitive), then `technologies` + `domain`/`category` overlap.
   Confident match → `decision: "update"` + existing `id`; else `create`.

## Phase 7 — Confirmation gate ⛔

Render the full proposal **in the message** and wait. Do not commit first. Show:

1. **Sources & mode** — what was read, what grounded what.
2. **8-layer table** — every node with layer, `create`/`update`, key fields, `source`, `code_ontology_id`.
3. **Schema summary** (if Phase 5 will run) — DataLake(s), and counts of tables / columns / indexes / views / procedures to be ingested.
4. **Divergences** — doc-vs-code / doc-vs-IaC conflicts, for the user to arbitrate.
5. **Discovered nodes** — `code-discovered` / `iac-discovered`; accept or reject each.
6. **Empty layers with evidence** — e.g. "Agents: none — no LLM/agent SDK in either repo". Proven-empty, not assumed-empty.
7. **Unclassifiable components** — for placement or drop.
8. **Scenario anchors** *(optional)* — `Functional_Graph_Search` for UX / ApiGateway / Services. Non-blocking.

Loop until confirmed. Apply edits to the inventory.

## Phase 8 — Commit in layer order

1. Ensure the `Architectural` root exists; capture `architecturalId`.
2. Commit in data-flow order so levels land consistently:
   **UserExperience → ApiGateway → Services → Agents → EventQueue → DataLake → ObservabilityMonitoring → Infrastructure.**
3. `create` → `Create_Architecture_Node`; `update` → `Update_Architecture_Node` with the matched `id`
   (send only changed keys; **omit `type` on DataLake — immutable**).
4. **Then run the Phase-5 schema ingest** against the committed `dataLakeId`(s).

### ⚠ LABEL PARAMETER

`label` **must be the bare layer name**. The tool schema misleadingly lists `…Label`-suffixed
values; those return a generic **400**.

```
✓ label: "Services"        → success
✗ label: "ServicesLabel"   → 400 Bad Request
```

After each commit, mark the row `committed: true` with the returned `id` — a mid-run stop then
resumes cleanly.

## Phase 9 — Verify & report

1. Re-read per layer (`Get_Architecture_Nodes_By_Label`) — counts must match the inventory.
2. **If schema ran:** verify per `db-schema-ingestion.md` §9 — table/column/procedure totals,
   **FK count > 0**, a wide table's `columnCount` correct, and a known-nullable column reading
   `nullable: true`.
3. Spot-check 2–3 nodes via `Architecture_Graph_Search`.
4. Report: nodes per layer, schema objects ingested, divergences resolved, layers proven empty,
   anything deferred. **State what was NOT verified** rather than implying full coverage.
5. Point the user at `/breeze:analyze-architecture` (per-requirement deltas), `/breeze:impact-analysis`
   (blast radius, anchors on `code_ontology_id`), and `/breeze:search`.

---

# REFERENCE

## Accuracy rules (the ones that cause wrong graphs)

1. **Verify before asserting.** A doc claim you could not confirm is `verified: false`, not fact.
2. **Empty must be proven.** Run the §5 probes before reporting a layer as empty, and show the evidence.
3. **Never silently overwrite** across sources — record a divergence.
4. **A parse receipt is not an ingest.** `202` means queued; verify against the graph.
5. **Partial ingests leave wrong derived fields.** `columnCount` / `hasPrimaryKey` describe
   whatever landed. Prefer a **fresh DataLake** over reconciling a half-written one.
6. **Runtime-generated objects can't be captured statically** — audit/custom-field companion
   tables, dynamically built views. Ingest as stubs with a `comment`; don't call it a failure.

## Idempotency & re-runs

Safe to re-run: Phase 6 routes existing nodes to `Update`; `stream-ingest` and the schema
endpoints merge by name. The inventory checkpoint lets you resume (skip `committed: true`) or
diff a new source against a prior pass.

## When NOT to use

- **A single requirement / change** → `/breeze:analyze-architecture`.
- **Just querying** → `/breeze:search`.
- **Only the code graph** (no architecture layer wanted) → `/breeze:onboard-repository`.

## See also

`/breeze:analyze-architecture` · `/breeze:onboard-repository` · `/breeze:search` · `/breeze:impact-analysis`
