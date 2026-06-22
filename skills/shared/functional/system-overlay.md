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
