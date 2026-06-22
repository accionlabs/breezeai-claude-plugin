# Functional Ontology — System / External System Overlay

> Applies when the persona is **`System`** or **`External System`**. Read **after** `core.md`. Everything here is in addition to the core. For human personas use `human-overlay.md` instead.

---

## 1. Persona derivation (mechanical EP → persona)

The system half uses **exactly two** persona names — assignment is **mechanical**, never inferred from auth/role code:

| Entry point | Persona |
|---|---|
| REST controller (any auth) | **System** |
| GraphQL query / mutation / subscription resolver | **System** |
| Internal-only route (`/internal/*`, `/admin/*`, `/health`) | **System** |
| Queue consumer / event handler for the **same system's** producer (internal bus) | **System** |
| Scheduled job / cron handler | **System** |
| Internal automation / script-triggered pipeline | **System** |
| Webhook receiver (HMAC-validated, a partner pushes data in) | **External System** |
| Payment gateway / partner-API callback route | **External System** |
| Queue consumer for a **documented 3rd-party** provider's event stream (e.g. Stripe → SQS → consumer) | **External System** |
| Inbound integration: SOAP/Axis, file-ingest, partner callback | **External System** |

Decision aid: **"Does the trigger originate OUTSIDE this application's boundary?"** → YES → `External System`; NO → `System`. Default is `System`; use `External System` only for a documented external producer.

### The system pass NEVER
- Reads JWT decoders / role guards / auth middleware to derive **human** role names.
- Creates or proposes a human persona (`User`, `Admin`, …).
- Decides whether a controller "is or isn't called by the UI" — it does not matter; both are `System`.
- Reads frontend repos or cites frontend paths.

The `persona --kind system` gate requires exactly one persona whose name is in `verbs.json → system_personas` (`System` / `External System`).

> **Note on enum (C1):** `System` / `External System` is enforced by the **validator**, not the schema or the server. The backend's `PersonaDto.persona` is `@IsString @IsNotEmpty` — no enum. So a payload with a human persona is accepted by the server; persona-kind correctness is the validator's job.

---

## 2. Action language — describe internal processing

System actions describe a **single atomic internal operation** in functional-but-precise terms (not raw code).

- **`description` is REQUIRED on every System action.** Provide one of: a formula/calculation, a threshold/limit, the field names involved, a condition/branch, an error message, a data format/transformation, or the input→output contract of the operation.
  - When the context lacks a concrete value, describe the operation's **input → output contract** rather than setting `null`.
  - `null` is acceptable **only** for trivial glue (e.g. `Log completion`).
- **External System** actions describe a single API/integration operation: endpoint, payload shape, or auth mechanism when known; otherwise `null`.
- For a **System-persona Scenario**, the *description* must describe the **internal processing behaviour, NOT the UI** that triggers it.
  - Good: `System processes the embedding-generation request, calls the Bedrock API, stores vectors, and runs clustering.`
  - Bad: `Generate embeddings in the background.` (too vague, UI-framed)
- Worked example (good system descriptions carry real values): `Return = (NAV_D1 / NAV_D0) − 1`; `Divergence = |Return_ClassA − Return_ClassB| × 10,000 (bps)`; `> 20 bps = BREACH (Red), > 10 bps = WARNING (Amber)`.

> The human-overlay **forbidden-UI-word** check does **not** apply to system actions (system descriptions legitimately name tables, indices, queues). The `forbidden` validator skips system personas.

---

## 3. Atomicity — ONE operation = ONE action (per-field atomicity is EXEMPT)

A `DoFilter` / `WriteData` / query / publish / consume is **one atomic operation**, and its **field list is the request payload of that single call**. So:

- **Do NOT split a System operation into one-action-per-field.** Leave it as one action per filter / write / publish / consume.
- The advisory `atomicity` check **skips System / External personas entirely** (it emits a skip note and passes). Per-field atomicity is a human-overlay concern only.

Still capture, in the System action description, the operation's specifics: filter conditions (`==`, `~`, `>=`), status codes (e.g. `C05=101`), date windows (e.g. `C06 >= $hireDate`), join tables, sort order, repository class + table / ES index / bucket.

---

## 4. System `rule-a` (apis[] OR identifier)

First word of a System action in `verbs.json → side_effect_verbs` ⇒ either:

1. a **non-empty `apis[]`**, **OR**
2. a **data-store identifier in the `description`** — a `Repository`/`table`/`entity`/`index`/`bucket`/`collection`, an `s3://`/`sqs://`/`kafka://`/`rabbit://` URI, or an `->`/`→` transform (`verbs.json → identifier_patterns`).

This apis-OR-identifier fallback is **system-only** (the human half requires `apis[]` outright). It is what lets aspx **Case-B** (a side effect with no URL) pass: name the repository/table/stored-proc in the description instead of inventing a URL. If neither is present, add the source detail or rename the action to drop the verb. Refuse to upsert until it passes.

### Side-effect coverage (advisory)
Where the adapter supplies `audit.sideEffects[]`, ≥90% should be matched to an action (`coverage`). Log/metric emission may go in `trivialSideEffects[]` with a one-line justification. Actions starting with Receive/Publish/Consume/Send/Submit/Fetch/Query/Upload/Download/Forward/Invoke must have `apis[]` **or** a DB/ES/S3 identifier in the description.

---

## 5. `apis[]` typing (system surfaces)

See `core.md §4` for the full join-model table. System-relevant rows: backend REST routes → `REST`; GraphQL ops → `GraphQL`; queue/event consumers → `Event` (`sqs://`/`kafka://`/`rabbit://`); cron → `Event` (`cron:<expr>`); SOAP/WCF/ASMX → `SOAP`; P3 internal Vert.x bus / `DoFilter` / `WriteData` → `Event`. **Resolve all template literals to literal queue/topic/route values before recording.**

---

## 6. Inbound surface = its own action (served vs required interface)

This is the System-half mirror of `human-overlay.md §5` ("the backend call is its own action that owns the `apis[]`"). On the human side the persona **calls out**, so the call action owns the *outbound* `apis[]`. On the system side the persona **is the thing being called**, so the served endpoint/queue/schedule must be captured as its own **inbound** action.

**Rule.** The entry point's own surface — the endpoint it receives on — is modeled as a **dedicated action, the first action of the entry scenario**, and **that action owns the served `apis[]`**:

| EP kind | Inbound action (verb) | `apis[]` on that action |
|---|---|---|
| REST route | `Receive <METHOD> <url>` | `{type:REST, method, url, request: inbound DTO/query, response: returned DTO}` |
| GraphQL op | `Handle <Query\|Mutation>.<op>` | `{type:GraphQL, method, url}` |
| Queue consumer | `Consume <queue>` | `{type:Event, method:consume, url: sqs://… / kafka://… / rabbit://…}` |
| Cron / scheduled | `Handle scheduled <job>` | `{type:Event, method:trigger, url: cron:<expr>}` |
| Webhook / partner callback (**External System**) | `Receive <METHOD> <url>` | `{type:REST\|SOAP, …}` |

**Direction is read from the verb** (the schema has no `direction` field; `type`/`method` are free text):

- **Inbound / served interface** → `Receive` / `Consume` / `Handle`. There is **exactly one** per entry scenario, and its `apis[].url` equals the EP route. It appears **once** — never copy the served url onto internal actions.
- **Outbound / required interface** → `Call` / `Invoke` / `Publish` / `Send` (the handler calling *another* service, queue, or partner API). **Each such action carries its own `apis[]`** for the interface it exercises, with the URL resolved to a literal.
- Pure internal effects (DB / ES / S3 / SP) follow the §4 `rule-a` fallback: `apis[]` empty, the repository/table/index/stored-proc named in the action name or `description`.

**Polymorphic handlers** (a handler that dispatches on a discriminator — `switch(message.type)`, `if (eventType === …)`): each per-branch scenario repeats the `Receive`/`Consume` action with the **same** served `apis[].url` and the discriminator noted in `request` (e.g. `request: "body.type == 'CLOSE'"`), so every branch stays independently traceable to the surface.

**Why this matters (downstream meaning).** `apis[].url` is the join key across passes and layers, and **the join is persona-agnostic — it keys on the URL, not the persona.** A caller records an *outbound* call to a URL; the owner of that URL records an *inbound* `Receive`/`Consume` of the **same** URL; they reconcile on that string. This holds for **all four interaction quadrants**:

| Caller → Callee | Caller side | Callee side |
|---|---|---|
| **Human → System** | UI `Submit → POST /x` (outbound `apis[]`) | backend `Receive POST /x` (inbound `apis[]`) |
| **System → System** (internal, both ours) | service A `Call POST /b/x` (outbound `apis[]`) | service B `Receive POST /b/x` (inbound `apis[]`) |
| **System → External System** (we call a 3rd party) | our `Call`/`Invoke` with the external URL | — (not in our codebase) |
| **External System → System** (webhook/callback in) | — (not in our codebase) | our `Receive` under `External System` persona |

So **System → System is captured by the same mechanism as Human → System** — no new persona is needed; both endpoints stay `System` and link by `apis[].url`. `External System` is reserved for the *boundary* (a 3rd party we do not own), i.e. only the two dangling quadrants. A dangling outbound `Call` (no matching `Receive`) = a *required* external dependency; a dangling `Receive` under `External System` (no caller) = a surface we *provide* to the outside — both are intended signals (the mirror of `backendEndpointsWithNoFrontendCaller`). If the served surface is buried in prose instead of a structured `apis[]` node, every one of these joins silently breaks.
