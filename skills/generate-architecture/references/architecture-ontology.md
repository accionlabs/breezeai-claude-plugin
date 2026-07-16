# Architecture Ontology — generation reference

The Architecture Graph is a fixed 8-layer model under a single root `Architectural`
node. **Every component belongs to exactly one layer.** Never invent a 9th layer;
if something fits none, flag it for the user (Phase 6) rather than forcing it.

Canonical per-layer field samples are in `../analyze-architecture/references/guide.md`
(single source of truth for the node data model). This file is the
generation-focused companion: which layer, which fields, and the gotchas.

## The 8 layers

| # | Layer (`label`) | Level | Owns | Typical tech |
|---|---|---|---|---|
| 1 | `UserExperience` | 1 | Client-side **delivery modalities** — one node per channel | React, Next.js, mobile, CLI; HTTP/WS |
| 2 | `ApiGateway` | 2 | Routing, auth delegation, rate limiting, request shaping | Kong, NGINX, Envoy, AWS API GW |
| 3 | `ObservabilityMonitoring` | 6 | Metrics, traces, logs, alerting | Prometheus, Grafana, OpenTelemetry, Jaeger |
| 4 | `Agents` | 3 | AI / LLM workflows & orchestration | LangChain, CrewAI |
| 5 | `Services` | 3 | Domain + platform business logic | FastAPI, Spring Boot, Go, Express |
| 6 | `EventQueue` | 4 | Async messaging / event streams | Kafka, RabbitMQ, SQS, Redis Streams |
| 7 | `DataLake` | 5 | Storage + analytics + AI-ML + vector search | Snowflake, Postgres, Pinecone, dbt, Spark |
| 8 | `Infrastructure` | 7 | Compute, network, deploy, scaling | Kubernetes, Docker, Terraform, VPC, CDN |

> The numbered list above follows the order the layers were specified. The
> **`level`** column is the data-flow level committed on each node (see
> "Layer levels" below) — it is NOT the same as the row number.

## Fields common to every layer

`architecturalId` (parent root id) · `projectUuid` · `name` · `level` ·
`category` · `technologies[]` · `pattern[]` · `protocols[]` · `description` ·
`emits_events` (bool) · `metrics[]` · `deployment` · `access_url` ·
`citation` (**mandatory** — spec ref or file hash) ·
`code_ontology_id` + `repositoryName` (**code-grounded mode only**, when the node maps to indexed code).

## Layer-specific fields

| Layer | Extra fields (beyond the common set) |
|---|---|
| **UserExperience** | `repository_url` |
| **ApiGateway** | `capabilities[]`, `auth_methods[]`, `rate_limit` |
| **Services** | `domain[]` |
| **Agents** | **`model_backend`**, **`tools_available[]`** |
| **EventQueue** | *(common set only)* |
| **DataLake** | **`model_type`** (relational / document / graph / warehouse / …), **`vector_db`** (engine name or "") |
| **ObservabilityMonitoring** | `pillers[]` (metrics/traces/logs), `alert_channels[]`, `self_monitored` (bool) |
| **Infrastructure** | `cloud_provider`, `regions[]`, `deployment_model`, `node_count`, `cpu_cores_total`, `storage_pb`, `scalability`, `backup_frequency` |

**Metadata priority:** prefer the fields above per layer first. Only add extra
metadata fields if the spec (or the user) explicitly provides them — do not
invent fields.

## Placement rules (resolve ambiguity here)

- **UserExperience is modality-level, not component-level.** One node per channel
  (web app, mobile app, voice, CLI, API client). Pages/components belong to the
  **Design Ontology**, not here. A typical product has 1–4 UX nodes total.
- **Services split into two sub-types** — *Custom Services* (Entity / Workflow /
  Integration, domain-specific) and *Platform Services* (cross-cutting: Auth,
  Search, Notifications, Logging, Audit).
- **Auth / Search / Notifications → `Services` (Platform Services)** — never
  `ApiGateway`, never `Infrastructure`.
- **AI agent / LLM workflow / assistant → `Agents`** — never `Services`. Set
  `model_backend` + `tools_available`.
- **ML training / dbt / Spark / feature store / vector DB → `DataLake`** — never
  `Services`. Set `model_type` + `vector_db`. This layer is broader than
  data-at-rest: "Data Lake, Analytics, AI/ML".
- **Message queue / topic / stream → `EventQueue`** — the queue itself lives here;
  the producing/consuming logic lives in `Services`.
- **No UX → DataLake direct calls; no reverse data flow** (Services calling UX).
  Flag boundary violations in the Phase 6 gate.

## Layer levels (data-flow order — commit `level` accordingly)

| `level` | Layer |
|---|---|
| 1 | UserExperience |
| 2 | ApiGateway |
| 3 | Services / Agents |
| 4 | EventQueue |
| 5 | DataLake |
| 6 | ObservabilityMonitoring |
| 7 | Infrastructure |

Commit order (parents/levels land consistently):
`UserExperience → ApiGateway → Services → Agents → EventQueue → DataLake → ObservabilityMonitoring → Infrastructure`.

## ⚠ The `label` gotcha

`Create_Architecture_Node` / `Update_Architecture_Node` take a `label` = the
**bare layer name**. The tool schema misleadingly documents `...Label`-suffixed
values; passing them returns a generic **400**.

```
✓ label: "DataLake"       → success
✗ label: "DataLakeLabel"  → 400 Bad Request
```

## MCP tools

| Operation | Tool |
|---|---|
| Read full graph | `Get_All_architecture_Graph` |
| Read one layer (no semantic filter) | `Get_Architecture_Nodes_By_Label` |
| Semantic search / dedup | `Architecture_Graph_Search` (`include_labels=[...]`) |
| Create node | `Create_Architecture_Node` |
| Update node | `Update_Architecture_Node` |
| Code grounding | `Code_Graph_Search`, `Call_List_Repositories_` |
| Scenario anchoring (optional) | `Functional_Graph_Search` |
