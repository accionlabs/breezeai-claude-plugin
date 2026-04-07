---
name: generate-functional-from-backend
description: >
  Generate the System-persona side of the functional graph from a
  backend repo. Detects framework, discovers ALL entry-point types
  (REST routes, SQS/Kafka consumers, cron workers, WebSocket
  handlers, webhook receivers, internal service-to-service handlers),
  and writes System / External System persona scenarios + a per-repo
  backend handoff log used for cross-repo producer/consumer
  correlation. Re-runnable per repo. Reads filesystem first, code
  graph second, functional graph for dedup only. NEVER writes human
  personas — that is the generate-functional-from-ui skill's job.
  Use when: "generate functional from backend", "backend to
  functional", "system persona pass", "discover backend entry points
  including non-HTTP", "run v2.1 backend pass on <repo>".
---

## What this skill does

Transforms a single backend repo into the **System / External
System** half of the functional graph. Discovers every entry-point
type — not just REST controllers — and grounds every scenario in
actual handler code.

It is the **backend half** of the recommended split pipeline:

```
generate-functional-from-ui      → User-persona scenarios
generate-functional-from-backend → System-persona scenarios   (this skill)
```

The two passes are fully independent — there is no file handoff
between them. They share the functional graph as the only common
surface; the upsert merges by **outcome name** so scenarios from
both passes land under the same outcome automatically.

## ★ The persona rule for the backend pass — read first ★

**The backend pass writes ONLY two persona types: `System` and
`External System`. It NEVER creates or proposes a human persona,
even when the REST controller it's looking at is clearly called by
a UI.**

Why: human personas are owned by the UI pass. When a UI pass exists
for the same project, it produces the human-persona scenarios for
the same business capabilities. The backend pass writes the System-
side scenarios — validation, persistence, side effects, queue
publishes, DB writes, ES indexing, S3 uploads — under the same
outcome name. The upsert merges them by outcome name, so the
outcome ends up with both human-persona scenarios (from the UI
pass) and System scenarios (from this pass) living side by side.

| Entry-point type | Persona |
|---|---|
| REST controller called by the UI | **System** (this pass) — the UI pass writes the human side under the same outcome name |
| REST controller called by another internal service | **System** |
| Internal-only REST routes (`/internal/*`, `/admin/*`, `/health`) | **System** |
| SQS / Kafka / RabbitMQ / SNS consumer | **System** |
| Cron / scheduled worker | **System** |
| WebSocket handler (any kind) | **System** |
| Webhook receiver (HMAC-validated, partner-pushes-data-in) | **External System** |
| Inbound Kafka topic from external source | **External System** |
| Payment gateway / partner API callback | **External System** |
| Worker that polls an external API | **System** for the poll itself; if you also want to model the external producer, use **External System** |

**The backend pass never reads JWT decoders, role guards, or auth
middleware to derive human role names.** Even if a controller has
`@UseGuards(JwtAuthGuard)`, treat the persona as `System` — the
human-side scenario lives in the UI pass's output.

This is a hard rule. If no UI pass has been run yet, the human-side
simply doesn't exist in the graph yet; that's fine, it will be added
when the UI pass runs later, and the upsert will merge it under the
same outcome name.

## Core principle

> **One backend repo at a time. Discover every entry-point type.
> Use only `System` and `External System` personas. Use both
> ontologies on every EP.**

## Guard

Read `.breeze.json` from the **plugin working directory**. If
missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `apiKey`, `projectUuid`, `apiBase`.

The project must already have at least one **code ontology** indexed
in Breeze (so `Functional_Graph_Search` and `Code_Graph_Search`
work). For best results the **target backend repo should also be
indexed** in Breeze — code-graph navigation across the repo's call
chains makes Step 4 dramatically faster. If it isn't indexed, the
skill still works but Step 4 falls back to filesystem-only traversal.

## Phase -1 — Resolve the target backend repo

This skill processes **one backend repo at a time**. Resolve the
repo path in this order:

1. **Explicit argument** — if the user provided a path
   (`/breeze:generate-functional-from-backend /path/to/repo`),
   validate it exists and looks like a backend repo:
   - has a `package.json` (Node) / `pom.xml` / `build.gradle` (JVM) /
     `requirements.txt` / `pyproject.toml` (Python) / `go.mod` (Go) /
     `composer.json` (PHP), AND
   - has at least one of: `src/controllers/`, `src/routes/`,
     `app/controllers/`, `cmd/`, `internal/handlers/`, `bin/worker*`,
     `*.controller.ts`, `routes.py`, etc.
2. **`.breeze.json` field** — read `targetRepos.backend.<repoName>`
   if the user named one, or `lastBackendRepo` for the most recent.
3. **Current working directory** — if cwd looks like a backend repo,
   use it.
4. **Ask the user** — single prompt: "Which backend repo do you want
   me to process? Provide an absolute path." Do not guess.

After resolution, **persist** to `.breeze.json`:

```json
{
  "targetRepos": {
    "backend": {
      "<repoName>": "/abs/path/to/backend-repo"
    },
    "lastBackendRepo": "<repoName>"
  }
}
```

If the resolved path looks like a frontend repo (has a router file
under `src/router/` or `src/routes/*.tsx` etc.), **stop** and suggest
the user wanted `/breeze:generate-functional-from-ui` instead.

The per-EP loop writes its checkpoint files to the **plugin working
directory** (next to `.breeze.json`), namespaced by repo name:
- `entrypoints_<repo>.json` — inventory + status checkpoint
- `backend_log_<repo>.json` — handoff log for cross-repo correlation

## ★ Canonical rules — Persona / Outcome / Scenario / Step / Action ★

### Persona resolution

The backend pass uses only two personas: `System` and `External
System`. Apply this mechanical mapping per EP (no auth-code reading):

| EP type | Persona |
|---|---|
| REST controller with auth guard (called by UI in real time) | **System** — the human-side is owned by the UI pass and lands under the same outcome name via the upsert merge |
| REST controller with no auth / `@Public()` | **System** |
| REST controller with internal-service auth | **System** |
| REST route under `/internal/*`, `/admin/*`, `/health`, `/metrics` | **System** |
| SQS / Kafka / RabbitMQ consumer | **System** |
| Cron / `@Cron(...)` / scheduled worker | **System** |
| WebSocket handler (any kind) | **System** |
| Webhook receiver (HMAC validation, partner-specific signature header) | **External System** |
| Inbound Kafka topic from external producer | **External System** |
| Payment gateway / partner API callback | **External System** |

**The backend pass NEVER:**
- Reads JWT decoders, role guards, or auth middleware to derive human role names
- Creates or proposes a human persona (`User`, `Admin`, `Subscriber`, etc.)
- Decides whether a controller "is or isn't called by the UI" — it doesn't matter; both cases are `System`

**Forbidden persona names — NEVER use:** Developer, Engineer,
Programmer, Architect, API, Service, Component, Module, Worker,
Backend, Frontend, Database, Controller, Handler, Repository, plus
any human role name (those are the UI pass's responsibility).

### Outcome — business capability

Same rules as the UI pass:
- Outcomes are business capabilities, NOT API endpoints or services
- ✅ "Track Construction Project Pipeline"
- ❌ "Handle ProjectsController POST endpoints"
- An entire backend repo usually contributes to 2-5 outcomes total,
  not one per controller method
- Re-evaluate if more than 3-4 new outcomes appear necessary

### Scenario — testable flow

- Has a clear start and end
- Reuse if semantically similar to existing
- For System persona scenarios, the description MUST describe the
  internal processing behavior (NOT the UI that triggers it)

### Step — sequential stage

- Short verb phrase
- No description required
- 3-8 per scenario (max 10)

### Action — rules for System and External System

#### System persona actions

- Single atomic internal operations
- `description` is **REQUIRED**. Provide one of:
  - Formula or calculation
  - Threshold or limit
  - Field names involved
  - Condition / branching logic
  - Error message
  - Data format / transformation
  - Input → output contract of the operation
- `null` is acceptable ONLY for trivial glue ("Log completion")
- `apis[]` is the structured side-effect capture using the
  REST / GraphQL / gRPC / WebSocket / Event enum:
  - REST controllers → `type: "REST"`
  - SQS / Kafka / RabbitMQ / SNS / EventBridge / cron handlers →
    `type: "Event"` with `method: "publish"|"consume"|"trigger"`
    and a transport-prefixed `url`
    (`sqs://${ENV_VAR}`, `kafka://${TOPIC}`, `cron:0 0 * * *`)
  - WebSocket handlers → `type: "WebSocket"`
  - GraphQL resolvers → `type: "GraphQL"`
  - gRPC service methods → `type: "gRPC"`

#### External System persona actions

- Single atomic API/integration operations representing the external
  side of an integration boundary
- `description` = endpoint, payload shape, auth mechanism, or HMAC
  signing scheme when known; otherwise null
- `apis[]` uses the same enum. Webhooks are typically `type: "REST"`
  with method=POST and the receiver URL.

**Quantity:** 1-5 actions per step. Split if more than 5.

### Cross-pass merge by outcome name

When the backend pass discovers a REST controller (or queue handler,
or webhook receiver) whose business capability matches an outcome
the UI pass already created, **use the exact same outcome name in
the payload**. The upsert merges by name automatically. The
backend-side System scenarios then live alongside the UI-side
human-persona scenarios under the same outcome — different
personas, same business capability.

If the UI pass hasn't run yet, the outcome may not exist. The
backend pass creates it and the UI pass attaches its human-persona
scenarios when it runs later. Order doesn't matter.

## Inputs

- **Backend repo path** — resolved in Phase -1 above
- **`.breeze.json`** — for `apiKey`, `apiBase`, `projectUuid`
- **Existing functional graph** — queried for dedup AND for cross-repo
  reference. If the UI pass already created an outcome with the same
  name, the System scenarios this pass creates will land under it via
  the upsert's idempotent merge by name. There is no file-based
  handoff from the UI pass — do not look for one.
- **Existing code graph** — queried for navigation, call chains,
  cross-repo handler discovery
- **Optional inputs that improve hand-off accuracy:**
  - Prior `backend_log_<previous_repo>.json` files — used to detect
    cross-repo SQS / Kafka producer-consumer pairs (e.g.
    `search_es_tnlm` publishes to `SQS_QUEUE_NAME_EXPORT`;
    `opensearch_tnlm` consumes from the same queue env var → link them)
- **Optional:** `entrypoints_<repo>.json` if resuming

## Outputs

- **Functional graph** updated with System and External System
  persona scenarios for the repo. Writes happen via the **curl
  upsert endpoint only** (one POST per EP, same as the UI pass).
- **`backend_log_<repo>.json`** — per-repo handoff file capturing
  every EP processed, message envelope schemas, queue/topic names,
  cron schedules, and the outcome/scenario names used. Consumed by
  subsequent backend pass runs to detect producer/consumer pairs
  across repos.
- **`entrypoints_<repo>.json`** — checkpoint for resume

## ★ Write protocol ★

**The backend pass writes to the functional graph EXCLUSIVELY via
the curl upsert endpoint** — one POST per EP. The upsert merges the
entire persona → outcome → scenario → step → action tree by name in
a single round trip and is idempotent.

**Forbidden write paths** (do not use even when they appear available):

- `Update_Functional_Node` MCP tool
- `Call_Create_Functional_Node_` MCP tool
- Any per-node MCP write that requires a parent UUID lookup first

These tools work but are 10–50× slower than the curl upsert because
they require a round trip per node and don't batch. They are also
unnecessary — the upsert handles existing-node detection via name
matching automatically.

**Allowed read paths:**

- `Functional_Graph_Search` (MCP) — for Step 1 dedup name discovery
- `Get_all_personas` / `Get_complete_functional_graph` (MCP) — for
  resume checkpoints, optional
- `Code_Graph_Search` / `Get_Code_File_Details` (MCP) — for
  cross-repo navigation in Phase 0 and Step 4

Reads via MCP are fine. Writes via MCP are forbidden.

## Source-of-truth hierarchy

Same philosophy as the UI pass: filesystem first, code graph as
accelerator, functional graph for dedup only.

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the backend repo | **Primary** — for reading controllers, services, workers, message handlers, decorator strings, env-var references | Filesystem has the literal `@post(...)` strings, the literal `process.env.SQS_QUEUE_NAME_EXPORT`, the literal cron expressions. |
| `Code_Graph_Search` on backend repos | **Required for cross-repo navigation** — find call chains, find handlers by name, find producer/consumer pairs | Faster than blind globbing across multiple repos. ALWAYS confirm by `Read`ing the actual file before citing. |
| `Functional_Graph_Search` | **Dedup check + cross-pass reference** | Step 1 (before write) and Step 8 (after write). Also used to find UI-created outcomes that this System scenario should attach to. |
| `Get_Code_File_Details` | **Allowed for backend** — useful for extracting decorator strings + class structure from one file | Backend route extraction is what this tool was designed for. |
| `Read` for the actual handler bodies | **Mandatory** for any handler being cited | Never trust code graph summary for the body — read the file. |

**Never** rely on a `Code_Graph_Search` summary as the source of a
route string, queue name, cron expression, or call chain. The
hallucination risk is exactly what earlier versions of this skill
got wrong.

---

## Phase 0 — Detect backend and discover entry points

### Sub-step 0.1 — Detect backend framework + entry-point conventions

Read the repo's `package.json` (or `pom.xml` / `pyproject.toml` /
`go.mod` etc.) and the top-level structure. Identify:

| Framework | Detection signal | Conventions |
|---|---|---|
| **LoopBack 4** | `@loopback/core` in dependencies; `src/controllers/*.controller.ts` | REST routes via `@get/@post/@put/@del` decorators on controller methods |
| **NestJS** | `@nestjs/core` in dependencies; `*.module.ts` files; `*.controller.ts` | REST routes via `@Get/@Post/@Put/@Delete` decorators; modules wire controllers + providers |
| **Express** | `express` in dependencies; `app.use(...)` route registration | REST routes registered in router files |
| **Fastify** | `fastify` in dependencies | Routes registered via `fastify.get/post(...)` |
| **Spring Boot** | `spring-boot` in pom/gradle; `@RestController` | `@RequestMapping` / `@GetMapping` / `@PostMapping` |
| **FastAPI** | `fastapi` in requirements | `@app.get()` / `@router.post()` |
| **Django** | `django` in requirements | `urls.py` URL patterns |
| **Pure worker (no HTTP)** | No web framework dependency; `bin/worker.ts` or `src/main.ts` runs a polling loop | All EPs are message handlers / cron jobs |

Record the framework name + the controller/handler glob pattern in
`entrypoints_<repo>.json`.

### Sub-step 0.2 — Discover REST routes

Use the framework conventions:

- **LoopBack:** Glob `src/controllers/**/*.controller.ts`. Read each
  file. Extract `@get/@post/@put/@del` decorator strings. Resolve
  template literals (`${appCfg.apiPathV2}/...`) by reading the
  imported config constant.
- **NestJS:** Glob `src/**/*.controller.ts`. Read each file. Extract
  `@Controller('prefix')` + `@Get/@Post/@Put/@Delete('subpath')`
  decorators. The full route is `prefix + subpath`.
- **Express/Fastify:** Glob router registration files. Trace
  `app.use(...)` chains.

For each REST route, capture: type, httpMethod, absoluteUrl,
controllerClass, methodName, file, line, parameters, requestType,
responseType, authGuards.

### Sub-step 0.3 — Discover SQS / message queue consumers

This is the step that v1 entirely missed.

1. **Grep for SQS imports:** `@aws-sdk/client-sqs`, `SQSClient`,
   `receiveMessage`, `ReceiveMessageCommand`, `DeleteMessageCommand`
2. **Grep for queue env vars:** `SQS_QUEUE_URL`, `SQS_QUEUE_NAME`,
   `QUEUE_URL`, `QUEUE_NAME`
3. **For each match, Read the file** and identify:
   - The queue name / env var consumed
   - The handler method (often `execute(msg, dataqueue)` or `handle(msg)`)
   - The expected message envelope (read the destructuring)
   - The polling loop / scheduler that invokes the handler
4. **Record as a non-REST EP** with `type: "SQS_CONSUMER"`.

### Sub-step 0.4 — Discover SQS / message queue producers

Producers are usually in REST controllers but the *act* of publishing
is what links them to consumers.

1. **Grep for `sendMessage` calls:** `sendMessage\(`,
   `SendMessageCommand`, `sqs.sendMessage`
2. **For each match, Read the file** and identify the queue URL env
   var, the message body shape, and the calling method.
3. **Record as `type: "SQS_PRODUCER"`.**

This enables **producer/consumer pair detection** in the post-pass:
any consumer in any other repo that reads from the same env var is
the partner.

### Sub-step 0.5 — Discover cron / scheduled workers

1. **Grep for cron decorators / schedules:** `@Cron\(`,
   `cron\.schedule`, `node-cron`, `@Schedule`, `CronJob`,
   `setInterval`
2. **Grep for worker entry files:** `workers/`, `*worker*.ts`,
   `*worker*.js`, `bin/cron`
3. **Read each match.** Identify the cron expression, the handler
   method, what it does.
4. **Record as `type: "CRON_WORKER"`.**

### Sub-step 0.6 — Discover Kafka consumers / producers

Same pattern as SQS but with Kafka primitives. Grep: `kafkajs`,
`@nestjs/microservices.*Kafka`, `KafkaConsumer`, `@MessagePattern`,
`@EventPattern`, `subscribe.*topic`. Record `KAFKA_CONSUMER` /
`KAFKA_PRODUCER` entries.

### Sub-step 0.7 — Discover WebSocket / Socket.IO handlers

Grep: `socket.io`, `ws.*on\(`, `@SubscribeMessage` (NestJS),
`@WebSocketGateway`. Read each match. Identify the room/namespace,
event name, handler method. Record `WEBSOCKET_HANDLER` entries.

### Sub-step 0.8 — Discover webhook receivers

1. **Grep for webhook-style routes** — REST routes with paths like
   `/webhook`, `/callback`, `/hook`, `/incoming`. These are usually
   already captured in 0.2 but should be flagged as `webhook`.
2. **Grep for HMAC signature validation** — webhook receivers usually
   verify a header like `X-Hub-Signature`.
3. **Tag matching REST routes with `subType: "webhook"`** and persona
   `External System`.

### Sub-step 0.9 — Discover internal service-to-service handlers

REST routes whose auth guard is internal-only (not the public JWT
guard) are likely internal.

1. After 0.2, walk the REST route list.
2. For each route, read the auth guard. If it's
   `@intercept(InternalServiceAuth)`, `@UseGuards(InternalGuard)`, or
   similar, mark `subType: "internal"`. Path-based check: `/internal/*`
   or `/admin/*` also marks `subType: "internal"`.
3. Internal routes still get full System scenarios but are flagged so
   the cross-repo correlator can recognize service-to-service flows.

### Sub-step 0.10 — Categorize and write `entrypoints_<repo>.json`

Group all discovered EPs by category (Search / Pipeline /
Notifications / Account / Export / Import / Sync / Background-jobs /
Webhooks / etc.).

Schema:

```json
{
  "repo": "lmreborn-backend_nodejs_search_es_tnlm-477d12114364",
  "framework": "loopback4",
  "projectUuid": "f4c1ba07-...",
  "generatedAt": "<ISO>",
  "logFile": "backend_log_search_es_tnlm.json",
  "totalEntryPoints": 47,
  "entryPoints": [
    {
      "id": 1,
      "type": "REST",
      "httpMethod": "POST",
      "absoluteUrl": "/v2/search/projects/export-email/xls",
      "controllerClass": "ProjectsController",
      "methodName": "projectExportEmailToExcel",
      "file": "src/controllers/projects.controller.ts",
      "line": 262,
      "category": "Export",
      "subType": null,
      "status": "pending"
    },
    {
      "id": 18,
      "type": "SQS_CONSUMER",
      "queueName": "${SQS_QUEUE_NAME_EXPORT}",
      "queueEnvVar": "SQS_QUEUE_NAME_EXPORT",
      "handlerClass": "ExportExcelProjectService",
      "handlerMethod": "execute",
      "file": "src/services/export-excel/export-excel-project.service.ts",
      "line": 135,
      "category": "Export",
      "messageEnvelope": ["param", "filter", "userSession", "setting", "..."],
      "status": "pending"
    },
    {
      "id": 32,
      "type": "CRON_WORKER",
      "cronExpression": "0 0 * * *",
      "handlerClass": "PreAlertProjectPipelineDailyWorker",
      "handlerMethod": "run",
      "file": "src/pre-alert-project-pipeline/workers/daily-worker.service.ts",
      "line": 42,
      "category": "Alerts",
      "status": "pending"
    }
  ],
  "completed": [],
  "remaining": [1, 2, "...", 47],
  "discoveredQueues": {
    "produced": ["SQS_QUEUE_NAME_EXPORT"],
    "consumed": ["SQS_QUEUE_NAME_EXPORT"]
  }
}
```

**Hard gate:** present the EP list to the user, ask if any should be
excluded, before starting the per-EP loop.

---

## Per-EP loop (Steps 1–10)

### Step 1 — Dedup check via `Functional_Graph_Search`

`Functional_Graph_Search` for the likely outcome name and 2–3 likely
scenario names. Decision matrix:

| Score | Match type | Action |
|---|---|---|
| > 0.6 | Same scenario/controller already in graph | **REUSE the exact name** in the payload — the upsert overwrites in place via name merge |
| > 0.6 | Different action shape, same outcome | **DIFFERENTIATE** — sibling scenario name under the same outcome name |
| > 0.6 | Existing outcome (created by UI pass or another backend pass) | **ATTACH** — use the exact same outcome name; upsert merges by name |
| < 0.6 | No match | **PROCEED FRESH** — create new outcome name |

The Step 1 search is read-only — its sole purpose is to discover
the right names to use in the Step 6 payload so the Step 7 upsert
merges into the existing structure.

### Step 2 — Read the handler file fully

`Read` the entire controller / service / worker file. Do not page-search.
The agent must see imports, class definition, constructor (for service
injection), and the full handler method body.

For non-REST EPs (SQS, cron, Kafka), also `Read`:
- The polling loop / scheduler that invokes the handler
- The module wiring that registers the handler

### Step 3 — Resolve template literals + env vars

For REST: resolve route prefix template literals (`${appCfg.apiPathV2}`)
by `Read`ing the imported config file.

For SQS / Kafka: resolve queue / topic env vars by `Read`ing the
deployment config or `.env` schema if present. Record both the env
var name AND any default value found in the code.

For cron: extract the literal cron expression.

### Step 4 — Trace the call chain

Walk one or two hops deep:

- **Constructor-injected services** are the call chain. List them with
  `Code_Graph_Search` if any are in other repos.
- **Internal calls** (the `calls` field from code graph) reveal what
  the handler does.
- **Repository injections** reveal which DB tables / ES indices are
  touched.
- **External clients** (`SQSClient`, `Kafka`, `HttpService`, S3) reveal
  what side effects happen.

### Step 5 — Identify side effects (the System persona's main job)

For each handler, enumerate side effects:

- **DB writes** — which repository, which table, what fields
- **DB reads** — same
- **ES index writes** — which index, what document shape
- **ES queries** — same
- **SQS publishes** — which queue, what message envelope
- **S3 uploads** — which bucket, what key pattern, what content
- **HTTP outbound** — which URL (often another internal service)
- **Email sends** — directly or via job
- **Logs / metrics** — only if non-trivial

This is what makes a System scenario useful for impact analysis. A
System scenario without side effects is just a function signature.

★ **Capture every side effect in `actions[].apis[]`** using the type
enum **REST / GraphQL / gRPC / WebSocket / Event**:

- **REST routes** the controller exposes → `type: "REST"`
- **gRPC service methods** → `type: "gRPC"`
- **GraphQL resolvers** → `type: "GraphQL"`
- **WebSocket / Socket.IO handlers** → `type: "WebSocket"`
- **SQS / Kafka / RabbitMQ / EventBridge / SNS publishes and
  consumes**, **cron-triggered handlers**, **internal pub-sub events**
  → `type: "Event"`

For an `Event` entry, populate the structured fields with the
identifying details:

```json
{
  "action": "Publish export job to SQS",
  "description": "Sends a message to the export queue so the opensearch_tnlm worker can pick it up.",
  "apis": [
    {
      "type": "Event",
      "method": "publish",
      "url": "sqs://${SQS_QUEUE_URL_EXPORT}",
      "request": "{templateId, subscriberId, projectVersionIds, param, filter, userSession, setting, allColumns, ...}",
      "response": "{messageId}"
    }
  ]
}
```

For consumers, mirror with `method: "consume"` and the same `url` so
the cross-repo correlator can match producer ↔ consumer by queue
identifier.

Other side effects that don't fit the API enum (DB writes, ES index
writes, S3 uploads) belong in the plain-text `action.description`. Be
specific — name the repository class, table, index, or bucket.

### Step 6 — Build payload

One outcome per related EP cluster. If Step 1 found an existing
outcome with the same business-capability name (typically created by
a prior UI pass run or a prior backend pass on a related repo), use
that exact outcome name in your payload — the upsert will merge under
it via name matching. Otherwise create a new outcome.

**Persona is always `System` or `External System` for the backend
pass.** The mapping is straightforward (see persona table above).

You may need to write multiple personas in the same payload if the EP
cluster spans types (e.g. a webhook receiver alongside a queue worker
that processes its events). That's fine — the upsert handles it.

Targets:
- 1–5 scenarios per EP
- 3–8 steps per scenario
- 1–5 actions per step
- Every action that touches state has its `apis[]` populated using
  the type enum **REST / GraphQL / gRPC / WebSocket / Event**

**Action description rules:**

- **System persona action:** description is REQUIRED. Provide a
  formula, threshold, field list, branching condition, error message,
  transformation, or input → output contract. The literal code-level
  details (queue name, table name, index name, ES query shape, S3
  bucket, file path) belong here.
- **External System persona action:** description = endpoint or
  payload shape when known.

**Example — REST controller (SYSTEM persona):**

```json
{
  "persona": "System",
  "outcomes": [{
    "outcome": "Track Construction Project Pipeline",
    "scenarios": [{
      "scenario": "Validate and enqueue project export",
      "description": "ProjectsController.projectExportEmailToExcel validates the request, snapshots the user context, inserts an idempotent_queue tracker row, and publishes an SQS message that the opensearch_tnlm worker will consume.",
      "steps": [
        {
          "step": "Receive export request",
          "actions": [
            {
              "action": "Receive POST /v2/search/projects/export-email/xls",
              "description": "Body: ParamExportProjects with exportTemplateId, projectVersionIds, isNewExport. Query param: filter (ProjectParams). Filter.toEmail flipped to true to indicate async mode.",
              "apis": [{
                "type": "REST",
                "method": "POST",
                "url": "/v2/search/projects/export-email/xls",
                "request": "ParamExportProjects + ProjectParams",
                "response": "ResponseApi<{queued:boolean}>"
              }]
            }
          ]
        },
        {
          "step": "Validate request",
          "actions": [
            {
              "action": "Check subscriber export quota",
              "description": "userSession.subscription.exportTypeLimit checked. Throws HttpErrors.NotAcceptable when value === 'DISABLED'."
            }
          ]
        },
        {
          "step": "Enqueue export job",
          "actions": [
            {
              "action": "Insert idempotent queue row",
              "description": "Repository: IdempotentQueueRepository. Table: idempotent_queue. Fields: uniqueId=subscriberId, queueName=SQS_QUEUE_NAME_EXPORT env value, statusQueue=0, retryCount=0, createdDate=now."
            },
            {
              "action": "Publish export job to SQS",
              "description": "Sends a message to SQS_QUEUE_URL_EXPORT containing the full processing context. Envelope keys: templateId, subscriberId, projectVersionIds, param, filter, userSession, setting, allColumns, checkFeatureBM, allColumnsProjectUdf, allColumnsCompanyUdf, getTimezone, settingProject.",
              "apis": [{
                "type": "Event",
                "method": "publish",
                "url": "sqs://${SQS_QUEUE_URL_EXPORT}",
                "request": "{templateId, subscriberId, projectVersionIds, param, filter, ...}",
                "response": "{messageId}"
              }]
            }
          ]
        }
      ]
    }]
  }]
}
```

**Example — SQS consumer (SYSTEM persona):**

```json
{
  "persona": "System",
  "outcomes": [{
    "outcome": "Track Construction Project Pipeline",
    "scenarios": [{
      "scenario": "Worker generates project export xlsx",
      "description": "ExportExcelProjectService.execute polls the export queue, regenerates the user context, queries OpenSearch, renders the xlsx via exceljs, uploads to S3, and writes a notification row.",
      "steps": [
        {
          "step": "Consume export job from SQS",
          "actions": [
            {
              "action": "Receive message from export queue",
              "description": "Polls SQS_QUEUE_URL_EXPORT (default sqs://${SQS_QUEUE_URL_EXPORT}). ReceiveMessageCommand with WaitTimeSeconds=20.",
              "apis": [{
                "type": "Event",
                "method": "consume",
                "url": "sqs://${SQS_QUEUE_URL_EXPORT}",
                "request": "{templateId, subscriberId, ...}",
                "response": "msg.raw"
              }]
            }
          ]
        },
        {
          "step": "Generate xlsx",
          "actions": [
            {
              "action": "Query OpenSearch for project rows",
              "description": "Builds an ES query from msg.body.filter and pages through projects. Index: research_project_*. Page size: 1000. Cursor: scrollId."
            },
            {
              "action": "Render xlsx workbook",
              "description": "Uses exceljs Workbook + Worksheet. Columns derived from settingProject.columns. One row per project version."
            },
            {
              "action": "Upload xlsx to S3",
              "description": "Bucket: NotificationWorkerUploadS3Service.bucket (env: NOTIFICATION_S3_BUCKET). Key pattern: exports/{subscriberId}/{uuid}.xlsx. Returns presigned URL with 7-day expiry."
            }
          ]
        },
        {
          "step": "Notify user of completion",
          "actions": [
            {
              "action": "Insert PostAlertTracking row",
              "description": "Repository: PostAlertTrackingRepository. Table: post_alert_tracking. Fields: postAlertTrackingUuid, subscriberId, modules='ExportExcel', content=JSON({url, fileSize, fileName})."
            },
            {
              "action": "Delete SQS message",
              "description": "DeleteMessageCommand with QueueUrl + receiptHandle."
            }
          ]
        }
      ]
    }]
  }]
}
```

Both examples are under the **same outcome name** (`Track
Construction Project Pipeline`). When the UI pass runs (now or
later), it adds human-persona scenarios under the same outcome name.
The upsert merges everything by name.

**Example — webhook receiver (EXTERNAL SYSTEM persona):**

```json
{
  "persona": "External System",
  "outcomes": [{
    "outcome": "Sync Project Data from Partners",
    "scenarios": [{
      "scenario": "Receive project update from partner webhook",
      "description": "Partner system pushes a project update; the receiver validates the HMAC signature and forwards to the data sync pipeline.",
      "steps": [
        {
          "step": "Receive webhook payload",
          "actions": [
            {
              "action": "Receive partner webhook",
              "description": "Endpoint: POST /v2/webhook/partner/project-update. Auth: X-Hub-Signature HMAC-SHA256 with shared secret. Payload: {partnerId, projectExternalId, fields, eventType, timestamp}.",
              "apis": [{
                "type": "REST",
                "method": "POST",
                "url": "/v2/webhook/partner/project-update",
                "request": "PartnerProjectUpdate",
                "response": "{accepted:boolean}"
              }]
            }
          ]
        }
      ]
    }]
  }]
}
```

### Step 7 — Upsert (one EP at a time)

Write payload to `/tmp/be_<repo>_ep{NN}_{name}.json`, then POST it.

**Endpoint:**
```
POST {apiBase}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK
Headers: api-key: {apiKey}
         Content-Type: application/json
Body:    @<payload-file>
```

**Curl example:**
```bash
curl -X POST "${API_BASE}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK" \
  -H "api-key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d @/tmp/be_search_es_tnlm_ep01_export_email.json
```

**Payload schema (full nested tree, top-level keys are mandatory):**
```json
{
  "project": {
    "uuid": "<projectUuid from .breeze.json>",
    "name": "<repo or project name>"
  },
  "payload": {
    "personas": [
      {
        "persona": "System",
        "description": "...optional persona description...",
        "citations": [
          { "type": "code", "name": "<service file>", "reference": "<file path>" }
        ],
        "outcomes": [
          {
            "outcome": "Track Construction Project Pipeline",
            "description": "...business capability...",
            "citations": [
              { "type": "code", "name": "<file>", "reference": "<file path>" }
            ],
            "scenarios": []
          }
        ]
      }
    ]
  },
  "skipStepAndAction": false
}
```

**Schema rules the agent must obey:**
- `project.uuid` is the projectUuid from `.breeze.json`. Required.
- `personas[]` is mandatory. **The backend pass writes only `System`
  and `External System`. Never `User`, `Admin`, `Subscriber`, or any
  other human role name.**
- A backend repo's payload may contain BOTH `System` and `External
  System` persona objects in one upsert if the EP cluster spans both.
- The upsert is **idempotent by name** at every level (persona →
  outcome → scenario → step → action).
- **Cross-pass merging:** if a previous run (UI pass or another
  backend pass) created an outcome with the same name, use that exact
  outcome name in your payload — the upsert merges automatically by
  name.
- `actions[].apis[]` uses the enum **REST / GraphQL / gRPC /
  WebSocket / Event**:
  - REST → `type:"REST"` with method + url
  - SQS/Kafka/RabbitMQ/SNS/EventBridge publishes & consumes,
    cron-triggered handlers, internal pub-sub events →
    `type:"Event"` with `method:"publish"|"consume"|"trigger"` and
    `url` set to a transport-prefixed identifier like
    `sqs://${QUEUE_ENV_VAR}` / `kafka://${TOPIC}` / `cron:0 0 * * *`
- DB writes/reads, ES index writes/reads, S3 uploads, and other side
  effects that don't fit the API enum belong in `action.description`
  as plain text. Be specific — name the repository class, table,
  index, or bucket.

**⚠ Never batch multiple EPs into one upsert.**

**★ MANDATORY pre-upsert validation — refuse to POST until both
checks pass ★**

Walk every `action` in the tree and apply two refusal rules:

**Rule A — side-effect-verb actions must have `apis[]` or DB/ES/S3
identifiers in description.** If `action.action` contains any of:

```
Receive, Publish, Consume, Send, Submit, Persist, Save, Insert,
Update, Delete, Index, Upload, Download, Fetch, Query, Push, Pull,
Enqueue, Dequeue, Trigger, Invoke, Call, Forward, Notify
```

…the agent must STOP and:
1. Read the source file again and add the structured `apis[]` block
   with the right type from the enum, OR
2. If the verb refers to a pure DB operation that doesn't fit the API
   enum, leave `apis[]` empty BUT the `description` MUST name the
   repository class + table or ES index, OR
3. If after re-reading the source there is no side effect at all,
   rename the action to remove the verb.

**Rule B — every external client / repository / queue reference
discovered in Step 4 must resolve to a `Read` of the file that
contains it.** Track which files were opened during Step 4. If at
payload-build time you have a reference you never followed into, the
discovery is incomplete — go back, read the file, and add the missing
identifiers (queue env var, table name, ES index, S3 bucket key
pattern).

If either rule fails, refuse to POST. Fix and re-run validation.

### Step 8 — Verify via `Functional_Graph_Search`

Search for a unique phrase from each new System scenario description.
Confirm:
- Scenario appears in results
- Score > 0.4
- `scenarioId` returned

If the upsert merged into an outcome that already had User scenarios
(from a UI pass), search the outcome name and confirm both User and
System persona scenarios now appear under it.

### Step 9 — Append to `backend_log_<repo>.json`

This is the cross-repo handoff. Schema:

```json
{
  "repo": "...",
  "framework": "loopback4",
  "generatedAt": "<ISO>",
  "entryPoints": [
    {
      "epId": 18,
      "type": "SQS_CONSUMER",
      "queueEnvVar": "SQS_QUEUE_NAME_EXPORT",
      "handlerClass": "ExportExcelProjectService",
      "handlerMethod": "execute",
      "file": "src/services/export-excel/export-excel-project.service.ts",
      "line": 135,
      "messageEnvelope": ["param", "filter", "userSession", "..."],
      "outcome": { "name": "Track Construction Project Pipeline", "uuid": "..." },
      "scenarios": [
        { "name": "Worker generates xlsx", "uuid": "...", "steps": ["..."] }
      ],
      "sideEffects": [
        { "type": "es-write", "index": "notification.postAlertTracking" },
        { "type": "db-insert", "repository": "PostAlertTrackingRepository" },
        { "type": "s3-upload", "bucket": "...", "keyPattern": "..." }
      ]
    }
  ],
  "discoveredQueues": {
    "produced": ["SQS_QUEUE_NAME_EXPORT"],
    "consumed": ["SQS_QUEUE_NAME_EXPORT"]
  },
  "discoveredTopics": { "produced": [], "consumed": [] },
  "discoveredCronJobs": [
    { "expression": "0 0 * * *", "handler": "..." }
  ]
}
```

The `discoveredQueues` / `discoveredTopics` blocks are what the
**post-pass cross-repo correlation** uses: when the backend pass runs
on a second repo, the agent reads the prior repo's log and matches
queue/topic names. Producers in one repo + consumers in another with
the same env var name = a confirmed cross-repo flow.

### Step 10 — Update `entrypoints_<repo>.json` checkpoint

Same as the UI pass: flip status, pop from `remaining[]`, append to
`completed[]`.

---

## Post-pass — Cross-repo correlation report

After every backend pass run (or as a separate aggregator pass):

1. **Read all `backend_log_<repo>.json` files** from previous runs.
2. **Match producers to consumers** by queue env var, topic name,
   HTTP URL, or shared S3 bucket key pattern.
3. **For each matched pair, write the linkage back into the
   functional graph via the curl upsert** — NOT via MCP tools. The
   right shape is to add a new System scenario under the matched
   outcome name describing the linkage. Linkage types to look for:
   - `sqs-pair` — producer + consumer share queue env var
   - `kafka-pair` — producer + consumer share topic name
   - `http-internal` — internal REST caller + receiver share URL
   - `db-shared` — same table/index written by one and read by another
4. **Write `cross_repo_correlations.json`** with the full pair list
   for human review (this file is for the user, not for the graph).
5. **Flag mismatches:**
   - Producer with no consumer (orphan publish)
   - Consumer with no producer (orphan consume — possibly fed by an
     external system not in scope)

**No MCP write tools.** The correlator uses the same curl upsert as
the per-EP loop.

This is what surfaces overlap between competing implementations of
the same flow (e.g. a Gen-1 controller and a Gen-2 controller both
serving the same URL pattern, or two producers writing to the same
queue).

---

## Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading code-graph summary instead of opening the file | Hallucinated route strings, wrong call chains, fabricated method bodies | Always `Read` the controller/service/worker file |
| Skipping non-REST entry points | System persona missing async/scheduled flows | Phase 0 sub-steps 0.3–0.7 are mandatory |
| Treating SQS consumer as a function call from the producer | Wrong call chain in graph | They are decoupled — never draw a direct call edge between producer and consumer; link via shared queue env var |
| Method-name collision across repos confused with same call | Cross-repo "exportToExcel" treated as one node | Always check `repositoryName` in code-graph results |
| Looking for a `frontend_api_log.json` to consume | Skill drift — there is no such file | Cross-pass merging happens via outcome name in the upsert, not via file handoff |
| Not resolving env vars / template literals | Queue names like `${SQS_QUEUE_URL_EXPORT}` written as literals | Resolve at Step 3 |
| Skipping side-effect enumeration | System scenarios are just function signatures, useless for impact analysis | Step 5 is mandatory |
| Treating all repos as isolated | Cross-repo flows not surfaced | Always run the post-pass correlator |
| Skipping `actions[].apis[]` for non-REST side effects | SQS / Kafka / cron / WebSocket / pub-sub flows missing structured capture | Use `type:"Event"` with `method:"publish"\|"consume"\|"trigger"` and a transport-prefixed `url` |
| Inventing custom payload fields like `sideEffects[]` | Upsert silently ignores unknown fields under actions; data is lost | Use the supported `apis[]` enum for everything that fits, plain-text `description` for everything else |
| Inventing a human persona from auth-code reading | Conflicts with UI pass; merge produces duplicates | Backend pass NEVER writes human personas. All REST controllers — even those clearly called by the UI — are `System` |
| Skipping the follow-through from a Step 4 reference into the actual source file | Side-effect-verb actions end up with no identifiers | Step 4 mandates reading; Rule B refuses upsert |
| Side-effect-verb action with no `apis[]` and no identifiers in description | Actions are uninspectable; cross-repo correlator finds zero matches | Rule A refuses to POST |
| Using `Update_Functional_Node` / `Call_Create_Functional_Node_` MCP tools | Per-EP processing 10–50× slower than necessary | Writes are EXCLUSIVELY via the curl upsert in Step 7 |
| Reading JWT decoders / role guards in the backend | Wasted effort; risks creating invented role names | Skip auth-code reading entirely. Persona resolution is mechanical: webhook → External System; everything else → System |
| Naming outcomes after pages or endpoints | "Handle ProjectsController", "POST /v2/.../export" | Outcomes are business capabilities |

## Resume protocol

When context budget hits ~75%:
1. Flush current EP's log entry + checkpoint
2. Stop and report

To resume in a fresh session:

> "Continue backend pass on `<repo>` from `entrypoints_<repo>.json`"

Next agent reads the per-repo entrypoints + log, calls
`Get_all_personas` to confirm graph state, and picks up at
`remaining[0]`.

## Run order recommendation

For a multi-repo backend system:

1. **UI pass** (`/breeze:generate-functional-from-ui`) on the
   frontend repo(s) — produces human-persona outcomes.
2. **Backend pass on REST API repos first** (in any order). These
   produce most of the REST routes the frontend calls.
3. **Backend pass on worker repos** — these consume queues produced
   by the REST repos.
4. **Backend pass on duplicate/competing-implementation repos** — the
   cross-repo correlator will surface duplicates.
5. **Cross-repo correlation post-pass** — produces
   `cross_repo_correlations.json` with the full picture.

This order maximizes the chance that producer/consumer correlation
finds matches: REST (producer) repos run first so the consumer repos
have something to match against.

## Relationship to the UI pass

The UI pass and the backend pass are **fully independent**. The
backend pass takes no input from the UI pass — no log file, no
artifact, no handoff. The UI pass reads a UI repo and writes User
persona scenarios + its own `entrypoints.json`. The backend pass
reads a backend repo and writes System persona scenarios + its own
`entrypoints_<repo>.json` and `backend_log_<repo>.json`.

The two passes share the **functional graph** as their only common
surface. When both passes write under the same outcome name, the
upsert's idempotent merge by name lands them together. That's the
entire integration mechanism — no file-based handoff exists or is
needed.

## See also

- `/breeze:generate-functional-from-ui` — the frontend half of the
  split pipeline
- `/breeze:generate-functional-from-code` — **deprecated** legacy
  cluster pipeline. Kept as a reference for repos where running both
  passes is overkill.
- `/breeze:validate-functional-graph` — quality checks after generation
- `/breeze:generate-spec` — export the resulting graph as a spec doc
