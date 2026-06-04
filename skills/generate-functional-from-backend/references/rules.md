## Backend Pass Rules Reference

---

## Functional Graph Definitions

### Outcome

A high-level goal or capability a persona needs to accomplish.
Outcomes are **business capabilities**, not technical functions or
API endpoints.

- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent

**Good:** "Manage Fund Allocations", "Monitor Compliance Status"
**Bad:** "Handle API Requests", "Process Database Queries", "Render Components"

**Quality checks:** understandable by non-technical stakeholders,
stable across implementation changes, broad enough to absorb future
Scenarios. If more than 3-4 new Outcomes appear necessary,
re-evaluate for over-segmentation.

### Scenario

A **specific user or system flow** under an Outcome. Testable — you
can write acceptance criteria. Clear start and end.

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging
- Each Scenario must include a brief description

**Good:** "Filter Dashboard by Date Range", "Submit Compliance Report"
**Bad:** "Use the System", "Do Things with Data"

For System Persona scenarios, the description MUST describe the
internal processing behavior, NOT the UI that triggers it.

### Step

**Sequential stages** within a Scenario — the major phases to
complete the flow.

- Each Step is a distinct stage, ORDERED in sequence
- Step name = short verb phrase
- Steps do NOT require descriptions (the name is sufficient)
- A Scenario typically has 3-8 Steps (max 10)

### Action

**Atomic operations or user inputs** within a Step. Rules differ
by persona type:

**HUMAN PERSONA actions** (User, Admin, or any named role):
- Describe what the user PROVIDES, DECIDES, or OBSERVES
- MUST be platform-agnostic (web, mobile, CLI, voice)
- FORBIDDEN words: click, tap, swipe, hover, scroll, drag, drop,
  toggle, button, dropdown, modal, dialog, popup, panel, checkbox,
  radio, slider, tooltip, menu, sidebar, navbar, tab, icon
- USE instead: Provide, Choose, Confirm, Review, Dismiss, Open,
  Close, Submit, Cancel, Specify, Indicate, Acknowledge, Request
- description = null, unless a real user-facing constraint exists

**SYSTEM PERSONA actions:**
- Single atomic internal operations
- description REQUIRED: formula, threshold, field names, condition,
  error message, data format, or input/output contract
- null only for trivial glue (e.g. "Log completion")

**EXTERNAL SYSTEM PERSONA actions:**
- Single atomic API/integration operations
- description = endpoint, payload shape, or auth mechanism when known

**Quantity:** 1-5 Actions per Step. If more than 5, split the Step.

---

## Backend Pass Specific Rules

---

### Source-of-truth hierarchy

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the backend folder | **Primary** — controllers, resolvers, services, DTOs, decorators | Filesystem has literal `@Post(...)` strings, `@Resolver`, full handler body, injection chain |
| `Code_Graph_Search` on the backend repo | **Optional accelerator** — locate controllers or trace call chains | Faster than blind globbing, but always confirm by `Read`ing the actual file |
| `Get_Code_File_Details` | **Allowed for backend** — extracting decorator strings + class structure | Backend route extraction is what this tool was designed for |
| `Functional_Graph_Search` | **Dedup check only** — never as a source of code knowledge | See Step 1 |

---

### Backend repo detection

A valid backend repo has one of: `package.json` (Node) / `pom.xml` /
`build.gradle` (JVM) / `requirements.txt` / `pyproject.toml`
(Python) / `go.mod` (Go) / `composer.json` (PHP), AND at least one
of: `src/controllers/`, `src/routes/`, `app/controllers/`, `cmd/`,
`internal/handlers/`, `*.controller.ts`, `routes.py`, GraphQL schema
files (`*.graphql`, `schema.gql`, `*.resolver.ts`).

If the path looks like a frontend repo, stop and suggest
`/breeze:generate-functional-from-ui`.

---

### Persona rules (backend pass specific)

The backend pass uses **only** two personas — assignment is mechanical:

| EP type | Persona |
|---|---|
| REST controller (any auth) | **System** |
| GraphQL query / mutation / subscription resolver | **System** |
| Internal-only routes (`/internal/*`, `/admin/*`, `/health`) | **System** |
| Webhook receiver (HMAC-validated, partner-pushes-data-in) | **External System** |
| Payment gateway / partner API callback route | **External System** |
| Queue consumer / event handler (internal bus, same system's producer) | **System** |
| Scheduled job / cron handler | **System** |
| Queue consumer for a 3rd-party provider's event stream | **External System** |

**The backend pass NEVER:**
- Reads JWT decoders, role guards, or auth middleware to derive
  human role names
- Creates or proposes a human persona (`User`, `Admin`, `Subscriber`,
  etc.)
- Decides whether a controller "is or isn't called by the UI" — it
  doesn't matter; both cases are `System`

---

### `apis[]` type reference

| Backend surface | `type` | `method` | `url` pattern |
|---|---|---|---|
| REST route | `"REST"` | `"GET"` / `"POST"` / etc. | `/v2/search/projects` |
| GraphQL query | `"GraphQL"` | `"query"` | `Query.projectById` |
| GraphQL mutation | `"GraphQL"` | `"mutation"` | `Mutation.createProject` |
| GraphQL subscription | `"GraphQL"` | `"subscription"` | `Subscription.projectUpdated` |
| gRPC method | `"gRPC"` | method name | service + method |
| WebSocket handler | `"WebSocket"` | event name | namespace/room |
| Queue publish/consume | `"Event"` | `"publish"` / `"consume"` | `sqs://${ENV_VAR}` / `kafka://${TOPIC}` |
| Cron handler | `"Event"` | `"trigger"` | `cron:0 0 * * *` |

---

### Queue / event EP discovery rules

**Transports recognized** (framework → signals):

| Transport | Detection signal | EP shape |
|---|---|---|
| **NestJS Bull / BullMQ** | `@Processor(queueName)` + `@Process(jobName?)` | One EP per `@Process` method |
| **NestJS microservices** | `@MessagePattern(pattern)` / `@EventPattern(pattern)` | One EP per pattern handler |
| **AWS SQS (nestjs-sqs)** | `@SqsMessageHandler(queueName)` | One EP per handler method |
| **AWS SQS (raw SDK)** | `Consumer.create({ queueUrl, handleMessage })` | One EP per consumer instance |
| **Kafka (kafkajs / NestJS)** | `@KafkaListener(topic)` / `@MessagePattern(topic, Transport.KAFKA)` | One EP per topic handler |
| **RabbitMQ (@golevelup/nestjs-rabbitmq)** | `@RabbitSubscribe({ exchange, routingKey, queue })`, `@RabbitHandler` | One EP per subscribe method |
| **RabbitMQ (amqplib)** | `channel.consume(queue, handler)` | One EP per consume call |
| **Google Pub/Sub** | `subscription.on('message', handler)` | One EP per subscription |
| **Azure Service Bus** | `receiver.subscribe({ processMessage })` | One EP per receiver |
| **Cron / scheduled** | `@Cron(expression)`, `@Scheduled` (Spring), `@shared_task` (Celery) | One EP per scheduled method |

**Required fields per queue EP:**
- `transport` — SQS / Kafka / RabbitMQ / Bull / PubSub / ServiceBus / Cron
- `queueName` / `topic` / `pattern` — resolved (no `${...}` placeholders)
- `handlerClass`, `methodName`, `file`, `line`
- `messageShape` — DTO or type of the consumed message
- `subType` — `queue-consumer`, `event-handler`, or `scheduled-job`

**Resolve template literals:** queue names / topics are frequently
constructed from env vars or config tokens. Always `Read` the config
file and resolve to the literal queue/topic name before recording.

**`apis[]` for queue handlers:** use `type: "Event"`, `method:
"consume"` (or `"trigger"` for scheduled), `url` as
`sqs://<queueName>` / `kafka://<topic>` / `rabbit://<exchange>:<routingKey>`
/ `cron:<expression>`.

**Persona assignment:** default is `System`. Use `External System`
only when the producer is a documented 3rd-party provider pushing
data into your bus (e.g. Stripe webhook → SQS → consumer).

---

### GraphQL EP granularity rules

| Granularity | When to use | EP shape |
|---|---|---|
| **per-operation** (default) | Most schemas with <100 operations | One EP per `@Query` / `@Mutation` / `@Subscription` method |
| **per-resolver-class** | Resolver classes group closely related operations | One EP per `@Resolver()` class; operations become scenarios |
| **per-type-field** | Federated schemas with heavy `@ResolveField` | One EP per top-level type + one per resolved field |

Default to **per-operation** unless the schema clearly favors another.

---

### Dedup decision matrix

| Score | Match type | Action |
|---|---|---|
| > 0.6 | Same scenario already in graph | **Reuse** the exact name (upsert overwrites via name merge) |
| > 0.6 | Different action shape, same outcome | **Differentiate** — sibling scenario under same outcome |
| > 0.6 | Outcome created by UI pass or another EP | **Attach** — use exact same outcome name; upsert merges |
| < 0.6 | No match | **Proceed fresh** |

Use `parameters3_Value` for project UUID — wrong slot fails silently.

---

### Side-effect coverage validator rules (agent Phase 6, check #6)

- >=90% of the side-effect inventory must be matched to an action
- Log/metric emission CAN be added to `trivialSideEffects[]` but
  must be justified in one line each
- **API-operation-name check:** actions starting with Receive,
  Publish, Consume, Send, Submit, Fetch, Query, Upload, Download,
  Forward, Invoke MUST have `apis[]` OR a DB/ES/S3 identifier in
  description. If missing, validator MUST fail.
- **Forbidden-persona check:** if any persona is not `System` or
  `External System`, validator MUST fail

---

### Pre-upsert validation rules (agent Phase 6, checks #1-2)

**Rule A — side-effect-verb actions must have `apis[]` or DB/ES/S3
identifiers in description.** If `action.action` contains any of:
Receive, Publish, Consume, Send, Submit, Persist, Save, Insert,
Update, Delete, Index, Upload, Download, Fetch, Query, Push, Pull,
Forward, Notify, Invoke, Call, Resolve — then either:
1. Read the source file again and add `apis[]`, OR
2. If pure DB op, leave `apis[]` empty BUT `description` MUST name
   repository class + table or ES index, OR
3. If no side effect, rename the action to remove the verb

**Rule B — every service / repository / client injected into the
handler's constructor (from Phase 1 discovery) must resolve to a `Read` of the
file.** If you have a reference you never followed, go back, read
the file, add the missing identifiers.

If either rule fails -> refuse to POST. Fix and re-validate.

---

### Component-import drill-down rule

For every service, repository, or client injected into the handler's
constructor, you MUST read the file before drafting scenarios. Record
in this EP's citation list. If skipped intentionally, justify in
`completed[]` under `skippedDependencies[]`.

---

### Orphan handler classification

| Classification | Action |
|---|---|
| wired elsewhere | Add to EP list with discovered route |
| dead code | Flag for user, exclude |
| test fixture | Exclude |

---

### Write protocol

**The backend pass writes to the functional graph EXCLUSIVELY via
the curl upsert endpoint** — one POST per EP. Never batch multiple
EPs.

**Forbidden write paths:**
- `Update_Functional_Node` MCP tool
- `Call_Create_Functional_Node_` MCP tool
- Any per-node MCP write that requires a parent UUID lookup first

**Payload schema rules:**
- `project.uuid` from `.breeze.json` — required
- `personas[]` must be an array — only `System` and `External System`
- A backend EP's payload may contain BOTH persona types in one upsert
- Each level matched by **name** at upsert time — idempotent
- Cross-pass merging: use the same outcome name as a prior UI pass —
  upsert merges automatically
- `actions[].apis[]` supports **REST / GraphQL / gRPC / WebSocket /
  Event**
- `citations[]` supported at persona and outcome level

---

### Boundary with the UI pass

The backend pass **never**:
- Reads frontend repos
- Creates human-persona scenarios
- Reads JWT decoders / role guards to derive human role names
- Cites frontend file paths
- Writes any handoff file for the UI pass

The two passes share the functional graph as the only common surface.
No file-based handoff.

---

### Framework detection table

| Framework | Detection signal | Route convention |
|---|---|---|
| **NestJS** | `@nestjs/core` in deps; `*.controller.ts`; `*.module.ts` | `@Controller('prefix')` + `@Get/@Post/@Put/@Delete('subpath')` |
| **LoopBack 4** | `@loopback/core` in deps; `src/controllers/*.controller.ts` | `@get/@post/@put/@del` decorators |
| **Express** | `express` in deps; `app.use(...)` registrations | Routes in router files |
| **Fastify** | `fastify` in deps | `fastify.get/post(...)` |
| **Spring Boot** | `spring-boot` in pom/gradle; `@RestController` | `@RequestMapping` / `@GetMapping` / `@PostMapping` |
| **FastAPI** | `fastapi` in requirements | `@app.get()` / `@router.post()` |
| **Django** | `django` in requirements | `urls.py` URL patterns |
| **Flask** | `flask` in requirements | `@app.route()` |
| **Go net/http / chi / gin** | `go.mod` | `router.HandleFunc` / `r.GET` |
| **Apollo Server / NestJS GraphQL** | `@apollo/server`, `@nestjs/graphql` | `@Resolver`, `@Query`, `@Mutation`, SDL `*.graphql` |
| **GraphQL Yoga / Mercurius** | `graphql-yoga`, `mercurius` | SDL + resolver maps |

---

### Route discovery recipes (per framework)

- **NestJS:** Glob `src/**/*.controller.ts`. Read `@Controller('prefix')` + `@Get/@Post/@Put/@Delete('subpath')`
- **LoopBack 4:** Glob `src/controllers/**/*.controller.ts`. Extract `@get/@post/@put/@del`. Resolve template literals by reading config
- **Express/Fastify:** Glob router files. Trace `app.use(...)` / `fastify.get(...)` chains
- **Spring Boot:** Glob `**/*Controller.java`. Extract `@RequestMapping` class prefix + method annotations
- **FastAPI:** Glob `**/*.py`. Extract `@app.get()` / `@router.post()` + `APIRouter(prefix=...)`
- **Django:** Read `urls.py` tree from root URLconf outward
- **Go:** Grep for `HandleFunc` / `.GET` / `.POST` registrations

---

### Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading code-graph summary instead of handler file | Hallucinated route strings, wrong call chains | Always `Read` the controller/resolver |
| Skipping GraphQL sub-step when repo has GraphQL | System persona missing query/mutation flows | Sub-step 0.7 is a HARD GATE |
| Skipping queue sub-step when repo has consumers | Async/background flows missing from graph | Sub-step 0.8 — scan for `@Processor`, `@MessagePattern`, `@SqsMessageHandler`, `@RabbitSubscribe`, `channel.consume` |
| Leaving `${QUEUE_URL}` unresolved | Queue name is a template variable instead of literal | Read the config module and resolve |
| Wrong GraphQL granularity | EP list explodes or collapses | Default per-operation |
| Inventing human personas from auth code | Conflicts with UI pass | Backend pass NEVER writes human personas |
| Not resolving template literals / route prefixes | Routes written as `${...}` | Resolve at Step 3 |
| Skipping constructor-injected service drill-down | Scenarios are just function signatures | Step 2 drill-down rule |
| Trusting code graph for literal strings | URL mismatches | Always `Read` the handler file |
| Batching multiple EPs in one upsert | Per-EP count low | One upsert per EP |
| Wrong `Functional_Graph_Search` slot | Schema error | Use `parameters3_Value` |
| Writing a handoff file for UI pass | Skill drift | No handoff needed |
| Skipping `apis[]` for GraphQL resolvers | GraphQL flows missing | Use `type:"GraphQL"` |
| Side-effect-verb action with no identifiers | Actions uninspectable | Rule A refuses to POST |
| Using MCP write tools | 10-50x slower | Writes EXCLUSIVELY via curl upsert |
| Naming outcomes after routes/resolvers | "Handle ProjectsController" | Business capabilities |
| Null description on System actions | Actions are opaque | System descriptions REQUIRED |
