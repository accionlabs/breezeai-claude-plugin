# Functional Ontology — Universal Core

> **Single source of truth.** This file + `human-overlay.md` + `system-overlay.md` + `verbs.json` + `upsert.schema.json` + `validate.py` are the ONE rulebook for every functional-graph generator, validator, and consumer. Per-skill `references/rules.md` carries ONLY its source-extraction adapter (which files to read, how to map them) and then defers here. Do not re-state these rules inline — link to this file. (ADR 0001.)

The core holds what is true for **every** persona and **every** source. Persona-conditional rules live in the two overlays; never put a human-vs-system fork in this file.

---

## 1. The node model

A strict 5-level hierarchy, plus an API leaf:

**Persona → Outcome → Scenario → Step → Action → `apis[]`**

| Level | Question it answers | One-line definition |
|---|---|---|
| **Persona** | *Who* acts? | A distinct actor that interacts with the system (a human role, `System`, or `External System`). |
| **Outcome** | *What* high-level goal? | A high-level **business capability** the persona needs — never a technical function or endpoint. |
| **Scenario** | *Which* flow? | A **specific, testable user or system flow** under an Outcome, with a clear start and end. |
| **Step** | *What* sequential stage? | An **ordered stage** within a Scenario — a major phase of the flow. |
| **Action** | *What* atomic op / input? | An atomic operation the user provides/decides or the system processes. |

These definitions are **canonical and non-negotiable**. In particular:

- **A Step is a SEQUENTIAL STAGE, not a configuration variation.** Steps are ORDERED; they represent the phases a flow passes through. (This explicitly overrides the retired `visual-to-text` definition of Step-as-variation; capture variation as sibling **Scenarios**, never as Steps.)
- **A Scenario is a FLOW, not a variation layer.** Distinct interaction paths are distinct Scenarios.
- The only relationship below Action is **Action → `apis[]`**. There is **no** `Action TRIGGERED_BY Component` edge in the functional graph (that is a design-graph concern; do not leak it here).
- **Every Scenario AND every Action MUST carry a non-empty `description`** (HARD GATE — `validate.py descriptions`, both halves). A Scenario describes the flow; an Action describes what it accomplishes (field metadata / constraint / branch for human actions; the internal input→output / formula / table-or-SP for system actions). `null`/blank is never acceptable on a scenario or action. (Steps need no description.)

### Quantity guidance
- A Scenario typically has **3–8 Steps** (max 10).
- A Step holds **one Action per atomic operation or input** — there is **no upper cap**. A data-entry section with 15 editable fields correctly yields 15 `Enter`/`Select` actions under **one** Step; do **not** split a Step just to reduce its action count. The "1–5 actions" figure is a loose heuristic for Steps made of *distinct phases* (e.g. a review-then-confirm stage), **not** for field-entry Steps — atomicity (one action per editable field, see `human-overlay.md`) always wins. Split a Step only when it actually spans two different stages of the flow, never to hit a number.
- If more than 3–4 new Outcomes appear necessary for one source, re-evaluate for over-segmentation.

---

## 2. Reuse-first & dedup (every level)

**Always check the existing graph before creating a node.** The upsert merges by **name** at every level, so reuse is achieved by emitting the *exact existing name*.

- **Outcome:** prefer broader over narrower; capture variation as new Scenarios, not new Outcomes. Create a new Outcome ONLY if none can logically contain the intent without becoming misleading.
  - Good: `Manage Fund Allocations`, `Monitor Compliance Status`, `Generate Reports`.
  - Bad (anti-patterns): `Handle API Requests`, `Process Database Queries`, `Render Components`, one Outcome per endpoint, Outcome names matching a function/class/route/resolver, duplicate Outcomes with slightly different wording.
  - Quality bar: understandable by a non-technical stakeholder; stable across implementation changes; broad enough to absorb future Scenarios.
- **Scenario:** reuse if the flow is semantically similar; create new only for a genuinely distinct interaction path. If two Scenarios share **>70%** of their steps, consider merging.
  - Good: `Filter Dashboard by Date Range`, `Submit Compliance Report`, `Import code repository`.
  - Bad: `Use the System`, `Do Things with Data`.
- **Dedup decision matrix** (run a `Functional_Graph_Search` dedup pre-query first — see §6):

  | Similarity | Match type | Action |
  |---|---|---|
  | > 0.6 | Same outcome/scenario already in graph (same interaction model) | **Reuse** — emit the exact existing name. |
  | > 0.6 | Different interaction model (single vs bulk, header vs row, modal vs inline) | **Differentiate** — sibling under the same Outcome, disambiguated name. |
  | > 0.6 | Outcome created by another pass/EP | **Attach** — reuse the exact Outcome name; upsert merges. |
  | < 0.6 | No match | **Proceed fresh.** |

> `Functional_Graph_Search` is a **dedup check only** — never a source of code knowledge. Pass the project UUID in `parameters3_Value` (wrong slot fails silently).

---

## 3. The dual human↔system subtree (the linking contract)

A complete feature has two halves that **share one Outcome name**:

- The **human** subtree answers *what the user wants* (the human-overlay persona, built from the UI/entry flow).
- The **system** subtree answers *how the system delivers it* (the System/External persona, built from the handlers/queries/side-effects).

Because the upsert merges by name, both halves attach to the **same Outcome** when they emit the **same Outcome name**. This is the cross-pass merge mechanism:

- The UI pass writes only the human half; the backend pass writes only the system half; **`generate-functional-from-metadata` is the reference implementation** — it builds BOTH halves from one `MAPL` and links them by a shared Outcome.
- The two passes share the functional graph as their **only** common surface — **no file-based handoff** between passes.

---

## 4. `apis[]` — the action↔interface leaf

`apis[]` is how an action declares the interface it exercises. Each entry: `{ type, method, url, request, response }`.

- **`type` is FREE TEXT** server-side (the backend stores a plain string — no enum is enforced). Recommended set: **REST / GraphQL / gRPC / WebSocket / Event / SOAP** (see `verbs.json → api_types`).
- An action carries `apis[]` only when it actually exercises an interface (see `rule-a`, §5). Pure user-input/selection actions carry **empty** `apis[]`.

### Per-stack join models (C5 — how an action maps to an interface)
| Stack / source | `type` | `method` | `url` |
|---|---|---|---|
| SPA fetch / axios / `useQuery` / `useMutation` | `REST` | HTTP verb | the literal endpoint path |
| GraphQL operation | `GraphQL` | `query` / `mutation` / `subscription` | `Query.x` / `Mutation.x` / `Subscription.x` |
| Real-time socket | `WebSocket` | event name | namespace / room |
| Server-Sent Events | `Event` | event name | stream path |
| gRPC | `gRPC` | method name | service + method |
| Backend REST route | `REST` | HTTP verb | route path (resolve prefixes/template literals to literals) |
| Queue / event consumer | `Event` | `consume` / `publish` | `sqs://<q>` / `kafka://<topic>` / `rabbit://<exch>:<key>` |
| Cron / scheduled | `Event` | `trigger` | `cron:<expression>` |
| ASP.NET / WCF / ASMX façade | `SOAP` | operation name | service endpoint + SOAPAction |
| **aspx Case-B** (side effect with no URL) | — | — | **no `apis[]`** — name the repository/table/SP in `description` instead (system-overlay rule-a fallback) |
| Vert.x internal event bus / `DoFilter` / `WriteData` | `Event` | the verb / address | filter id / handler name |
| Vert.x-app custom-HTML `$.ajax` | `REST` | HTTP verb | the endpoint path (`/apy-common-screen/...`) |

> **Resolve template literals to LITERAL values** before recording a `url` — never leave `${QUEUE_URL}` / `${TOPIC}` / route-prefix tokens unresolved (read the config module).

---

## 5. `rule-a` — side-effect actions must declare their interface (HARD GATE)

If an action's **first word** is a side-effect / network verb, it must declare where the effect goes. The verb set and the acceptable evidence are **persona-conditional** (see overlays), but the gate itself is universal:

- **Human half** — first word in `verbs.json → network_verbs` ⇒ **non-empty `apis[]` required** (no description fallback).
- **System half** — first word in `verbs.json → side_effect_verbs` ⇒ **non-empty `apis[]` OR** a data-store identifier in the `description` (a `Repository`/`table`/`entity`/`index`/`bucket`/`collection`, an `s3://`/`sqs://`/`kafka://`/`rabbit://` URI, or an `->`/`→` transform — `verbs.json → identifier_patterns`).

If `rule-a` fails: open the source file and add the `apis[]`/identifier, **or** rename the action to drop the verb if it is genuinely local-only (and say why in the description). **Refuse to upsert until it passes.**

---

## 6. Enumeration & source-fidelity discipline

- **The local source checkout is the SOURCE OF TRUTH; the code graph is an OPTIONAL accelerator, never required.** `Read` + `Grep` on disk are the backbone — a run that uses **zero** graph calls is completely valid. The code graph (`Code_Graph_Search` / `Get_Code_Nodes_By_Label`) earns its keep in only two situations: (a) resolving the concrete **next-hop** of a cross-file call (interface / DI / overload) that `Grep` can't disambiguate, and (b) **repo-wide inventories** (all routes / DB calls, via `Get_Code_Nodes_By_Label(label="Statement", …)`) — mostly a discovery-agent concern. Reach for it only then; otherwise `Grep`+`Read` is faster and always current.
- **⚠️ The code graph does NOT capture every statement — so it is NEVER the source of step/action detail.** It locates code; it does not define behaviour. **Every literal (route, URL, stored proc, table, field code, decorator, guard) and every Step/Action MUST be derived from `Read`ing the real file** — never from a graph summary. At **step/action granularity the local file is the ONLY source of truth.** A graph hit that lacks a statement you expect means "go Read the file," not "the statement doesn't exist."
- **⚠️ Scope EVERY graph query to THIS repo's `codeOntologyId`.** A Breeze project holds **multiple repos** (frontend + N backends), so an unscoped query bleeds across repos. Functional generation runs for **one repo at a time**: the skill resolves that repo's `codeOntologyId` **once at Bootstrap** via `Call_List_Repositories_(projectUuid)` (matching the on-disk repo to an indexed one) and passes it to the agent as `CODE_ONTOLOGY_ID`. Then:
  - `Code_Graph_Search(..., code_ontology_id=<id>)` — pass it as the param (fallback `repository_name=<INDEXED_REPO_NAME>` + a `cgs_unscoped` warning).
  - `Get_Code_Nodes_By_Label(..., filters={"codeOntologyId": <id>, …})` — pass it **inside `filters`**; `repositoryName` is **rejected** as a filter (mutable display name).
  A bad/missing `codeOntologyId` **fails loud** (`No repository with codeOntologyId … Available: …`), never a silent cross-repo or empty result — so never issue an unscoped graph query.
- **Enumerate, do not sample.** Every declared field / widget / injected dependency / side effect that the adapter discovers must be accounted for — either as its own action or folded into a `Review …` description (human) / the operation's payload (system). The adapter records what it found in `audit.declaredFields[]`, `audit.filesRead[]`, and (where relevant) `audit.sideEffects[]`; the validators check the graph against that audit.
- **Drill-down rule:** every dependency the adapter flags as significant (an imported stateful component for UI; a constructor-injected service/repository/client for backend; a referenced `MFLT`/`CRUD`/`.java` handler for a metadata app) **must be `Read`** before scenarios are drafted, and **cited**. If skipped, justify it in the audit's `skipped*` list.

---

## 7. Citations (HARD GATE on prefix AND placement)

A citation is `{ "type": "code", "name": <label>, "reference": <path> }` where `reference` **must** match `^[A-Za-z0-9_.\-]+/` — i.e. start with `<repo-name>/`. The `citations` validator enforces the prefix.

### 7.1 Placement (C3) — citations live ONLY on scenario / step / action
This is a fixed contract, **not** a judgement call — decide once, at authoring time. There are exactly **three** node levels that may carry a `citations[]`, and **two** that must never carry one:

| Node | `citations[]`? |
|---|---|
| **Action** | ✅ **author here by default** — the handler / field / widget the action came from (tightest, most useful link) |
| **Step** | ✅ allowed — the file(s) that define that stage |
| **Scenario** | ✅ allowed — a file that spans the whole flow (the route / page / `MAPL`), or the app-specific audit anchor |
| **Outcome** | ⛔ **forbidden — do NOT emit a `citations[]` key at all** |
| **Persona** | ⛔ **forbidden — do NOT emit a `citations[]` key at all** |

**Why Outcome/Persona are forbidden:** they are **shared and merged by name across many EPs**, so a file ref placed there accumulates on the shared node — hundreds of unrelated refs pile onto one Persona/Outcome = pollution. They are too high-level to carry file evidence. **Never author a `citations[]` on a persona or outcome node — omit the key entirely.** The `citations` validator **hard-fails (exit 2)** on any citation at outcome/persona level — cite the scenario/step/action it actually describes instead.

The `citation-completeness` gate treats citations at the three allowed levels as a **union**, so citing a file at the action (or step, or scenario) it came from fully satisfies completeness — there is never a reason to put a citation on a shared node.

### 7.2 Completeness (HARD GATE)
Every file the adapter `Read` (tracked in `audit.filesRead[]`) must appear — by **basename** — among the cited references. If you read a `.java` handler / service / `MFLT` / config to write a description, **cite it**. The `citation-completeness` check fails on any read-but-uncited file.

---

## 8. Write protocol

- **Write EXCLUSIVELY via the upsert endpoint**, one POST per entry point. **Never** batch multiple EPs into one upsert; never use the per-node MCP write tools (`Call_Create_Functional_Node_`, `Update_Functional_Node`) for generation — they are 10–50× slower and require parent-UUID lookups. (The MCP per-node tools remain valid for *targeted edits* by the update/merge skills, not for bulk generation.)
- **Endpoint:** `POST {apiBase}/functional-graph/v2/upsert?embedding=true&llmPlatform=AWSBEDROCK`. v2 is the scalable path (MERGE on composite keys = Neo4j idempotency authority, async SQS-queued embeddings); v1 generates embeddings in-process and is slow. Use v2 for **both** halves. Pass `embedding=true` explicitly (v2 queues embeddings unless `embedding=false`).
- **Body is a WRAPPER, not the bare payload:**
  ```json
  { "payload": { "personas": [ … ] }, "project": { "uuid": "<projectUuid>", "name": "<projectName>" }, "skipStepAndAction": false }
  ```
  A bare payload → 500; a bad key → 401.
- **Auth:** `api-key: <key>` header (lowercase). The key comes from `.breeze.json` and is never committed.
- **One persona per payload** (schema `minItems/maxItems 1`). Each level is matched by **name** at upsert time — idempotent; re-running is safe and overwrites by name.

---

## 9. Validation — where the gate actually is

- **The enforcement locus is the sub-agent's self-validate phase** (Phase 6 in the flow agents), which runs `validate.py` against the payload+audit it is about to POST. **Parent skills run no validators** — they orchestrate. Do not present `validate.py` as an orchestrator-level gate.
- **Hard gates (block the upsert):** `schema`, `rule-a`, `persona` (kind + count), `citations` (prefix), `field-coverage == 1.0`, `citation-completeness`. Plus `forbidden` on the human half.
- **Advisory (warn only, never block):** `atomicity` (human half only; skipped for System), `coverage` / `api-urls` (where the adapter supplies the inputs).
- All checks read the `{payload, audit}` object from **STDIN** and return `{ ok, errors, warnings }`. See `validate.py --help`.

---

## 10. Source-context handling (adapter-agnostic mapping)

Whatever the source, translate it into the node model — never reproduce raw code:

- **Document** (specs, user stories): extract business logic, acceptance criteria, formulas, thresholds directly from the text.
- **Source code** (Class → Method → Statements): classes → service boundaries, methods → processing phases, conditionals → business rules, queries → data operations. System action descriptions must carry **actual field names, thresholds, and error messages** from the code.
- **Figma / visual**: pages → Outcomes, screens → Scenarios, sections → Steps, user decision points → Actions. (Use the canonical Step/Scenario semantics from §1 — not the retired variation model.)

The *source-extraction adapter* (which files, which record types, which decorators) is the ONE thing that stays per-skill. Everything above is shared.
