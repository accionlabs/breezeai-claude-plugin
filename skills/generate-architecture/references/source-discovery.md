# Source discovery — deriving the 8 layers from whatever you're pointed at

How to turn each input kind into inventory rows. Read this in Phase 1 once you know which
sources are present. Sources **compose** — a repo + IaC + a Confluence page all feed the same
inventory and are merged in Phase 4.

---

## 0. Detect what you've been given

Run this before asking the user anything. Point the skill at a path or URL and classify:

| Signal | Source kind |
|---|---|
| `*.tf` / `*.tf.json` / `*.hcl` (not under `.terraform/`) | **IaC** |
| `Dockerfile`, `docker-compose.y*ml`, `*.yaml` with `kind:` | **Deployment manifests** |
| `*.sql`, `*.ddl`, ES mapping `*.json` | **DB schema** |
| Source files in a supported language + `package.json` / `pom.xml` / `*.csproj` / `requirements.txt` | **Code** |
| `.md` / `.pdf` / image / pasted prose | **Document** |
| `atlassian.net/wiki/…` URL | **Confluence** |
| Project has repos with `fileCount > 0` (`Call_List_Repositories_`) | **Code graph** (indexed) |

A repo usually yields **several** of these at once. Announce what you found in one line
before proceeding — e.g. `Sources: code (2 repos indexed) + IaC (terraform/) + DDL (412 .sql)`.

---

## 1. Document / Confluence

The doc is the **primary source for meaning** — names, purpose, domains, business framing.
It is the **weakest source for topology** — it is usually stale, aspirational, or silent on
infrastructure.

**Confluence:** fetch with `getConfluencePage` (`contentFormat: "markdown"`). If it links to
child pages that look architectural, fetch those too — but keep the parent's framing.
Cite as `<page title> (<pageId>)`.

**PDF:** use the Read `pages` parameter, section by section — never load a large PDF whole.

**Diagram / image:** extract multimodally. Boxes = components, arrows = data flow,
swimlanes/tiers usually map to layers directly.

> ⚠ **Do not trust a document's layer count.** Docs routinely omit whole layers — especially
> `ObservabilityMonitoring` (logging/audit surfaces exist in nearly every system but are
> rarely written up) and `Agents`. Treat every layer the doc is silent on as *unverified*, not
> *empty*, and probe it in §5.

---

## 2. Code (repository on disk)

Read the tree directly — this is ground truth and it beats the doc on every factual claim.

| Look for | Yields |
|---|---|
| Frontend bundles (`package.json` + a router), SPA `src/`, server-rendered templates | **UserExperience** — one node per *delivery channel*, never per page |
| Route definitions, controllers, `*.svc`/`.asmx`, minimal-API registrations | **ApiGateway** — the entry surface, plus the auth/guard model |
| Service / manager / facade classes, business-logic modules, job runners | **Services** — split custom (domain) vs platform (auth, search, notify, log) |
| LLM/agent SDK usage, prompt orchestration | **Agents** — set `model_backend`, `tools_available[]` |
| Queue/topic clients, schedulers, timers, change-feed pollers | **EventQueue** |
| DB clients, ORMs, connection-string resolution | **DataLake** — one node per *physical database* |
| Log/metric/audit/error surfaces, admin diagnostic pages | **ObservabilityMonitoring** |
| Host config (`web.config`, `appsettings`, `Dockerfile`), cache setup | **Infrastructure** |

**Connection strings are the DataLake census.** A second connection string (archive, reporting,
read-replica-with-different-schema) means a **second DataLake node**. Read/write splits of the
same database do not.

**If the repo is indexed** (`code_ontology_id` exists), prefer `Code_Graph_Search` over
grepping for discovery — then confirm specifics on disk. Attach `code_ontology_id` +
`repositoryName` to every node the code backs.

---

## 3. IaC / Terraform

**Authoritative for provisioned infrastructure** — Infrastructure, EventQueue, DataLake, and
ApiGateway existence, technology, and region. The doc is usually vaguer here; prefer IaC.

This is a **filesystem read, not code-grounding** — HCL is not indexed, so `Code_Graph_Search`
returns nothing for a Terraform repo. Parse `resource` / `module` blocks directly. Full
resource→layer table: `iac-mapping.md`.

Prefer `terraform plan` / state output if the user has it — it resolves interpolations and
counts that raw HCL leaves symbolic.

---

## 4. Deployment manifests (k8s / compose / Dockerfile)

Fills the gap between "the code exists" and "how it runs":

- `Deployment` / `StatefulSet` → **Infrastructure** (replicas, resources, `deployment_model`)
- `Service` / `Ingress` → **ApiGateway** (routing, host)
- `ConfigMap` env → which external services a workload talks to (cross-check §2)
- `Dockerfile` base image + exposed port → `technologies`, `deployment`

Useful for `node_count`, `regions[]`, `scalability` — fields a doc rarely states and code never does.

---

## 5. Layer probes — run these before declaring a layer empty

The most common failure mode is a layer silently missing because nothing in the doc mentioned
it. For **each** of the 8 layers, if no row exists yet, actively search:

| Layer | Probe |
|---|---|
| `UserExperience` | Count distinct delivery channels. Multiple frontends (SPA + server-rendered + mobile) = multiple nodes. |
| `ApiGateway` | Route/controller definitions; also SOAP/RPC surfaces and **unauthenticated endpoints** (`AuthenticationRequired() == false`, `[AllowAnonymous]`, public webhooks). |
| `Services` | Cross-cutting platform services are the ones docs forget: auth, search, notification, export/import, localisation, scheduling. |
| `Agents` | LLM/agent SDKs. Legitimately empty in most non-AI systems — say so explicitly. |
| `EventQueue` | Brokers **and** database-backed queues (a `vwJobsDue`-style polling view *is* an EventQueue node). |
| `DataLake` | Every distinct connection string. Then run the schema pass — see `db-schema-ingestion.md`. |
| `ObservabilityMonitoring` | Log tables/viewers, audit trails, error-capture helpers, admin diagnostics. **Almost never in the doc; almost always in the code.** |
| `Infrastructure` | Host config, caching tier, deploy model, scale-out constraints. |

**Empty must be proven, not assumed.** If a layer genuinely has no components, state that in
the gate with the evidence (e.g. "Agents: no LLM/agent SDK found in either repo").

---

## 6. Precedence when sources disagree

| Concern | Winner |
|---|---|
| Component **exists** | Code / IaC over doc |
| Name, description, business **domain** | Doc over code |
| Technology, version, region, deployment | IaC > code > doc |
| Provisioned infra (queues, stores, gateways) | IaC |
| Schema detail (tables, columns, keys) | The `.sql` / live DB |
| Runtime-generated objects | Neither — flag as a stub |

**Never silently overwrite a doc claim.** When code or IaC contradicts the doc, keep both and
record a `divergence` on the row for the confirmation gate. A contradiction is a finding worth
showing the user, not a merge conflict to resolve quietly.

**Never assert something you did not verify.** If a claim came only from the doc and you could
not confirm it in code, mark the row `verified: false` rather than presenting it as fact.
