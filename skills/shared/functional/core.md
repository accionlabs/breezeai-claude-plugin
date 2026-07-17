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

## 2. Reuse-first & dedup — OUTCOME-ONLY inline, coverage-first below

The upsert merges by **name** at every level, so reuse is achieved by emitting the *exact existing name*. Dedup effort is **concentrated at the Outcome level only** (the sole cross-persona shared node — see §3). Below the Outcome, **bias to coverage: never suppress a possibly-distinct flow**; below-outcome duplicates are cheap to merge later and a merge never loses data, whereas a false-positive dedup permanently drops a flow.

### 2.1 Outcome dedup — DETERMINISTIC list-all, NOT semantic search (mandatory)

Do NOT rely on a `Functional_Graph_Search` similarity threshold to dedup Outcomes — near-duplicates routinely score **0.45–0.55**, below any usable cutoff, and slip through as false "fresh" outcomes, fragmenting the graph. Instead, **enumerate the complete existing outcome set and match on the normalized name**:

1. `Get_all_personas(PROJECT_UUID)` → for each persona `Get_all_outcomes_for_a_persona_id` → collect **every** existing Outcome name across the whole graph (the set is small — tens of names — so a full list is cheap and *complete*).
2. Normalize each candidate + existing name to a `nameKey` (lowercase, trim, collapse whitespace) and compare.
3. **If the candidate is the SAME CAPABILITY as an existing Outcome → reuse that Outcome's exact name verbatim.** The Outcome is a cross-persona shared bucket; the upsert merges it.
4. Only mint a new Outcome when no existing name denotes the same capability.

### 2.2 Canonical outcome vocabulary (prefer before minting)

Before creating a new Outcome name, **prefer an existing/canonical name for the same capability** so parallel passes and different personas converge on one bucket. Reuse the name whenever the capability matches; vary the *description and scenarios* to carry persona/context specifics.

- **Capability-level floor (do NOT over-merge):** reuse only when it is genuinely the **same capability**. Never collapse *distinct* capabilities into one generic bucket to chase reuse (e.g. `Manage Code Ontologies` and `Manage Architecture Model` are distinct — keep them separate). Generic is good until it erases meaning.
- Quality bar: understandable by a non-technical stakeholder; stable across implementation changes; broad enough to absorb future Scenarios.
- Good: `Manage Fund Allocations`, `Monitor Compliance Status`, `Generate Reports`.
- Bad (anti-patterns): `Handle API Requests`, `Process Database Queries`, `Render Components`, one Outcome per endpoint, Outcome names matching a function/class/route/resolver, **duplicate Outcomes with slightly different wording** (the exact failure list-all prevents).

### 2.3 Below the Outcome — coverage-first (no inline suppression)

- **Scenario / Step / Action:** emit freely. Do NOT drop or skip a candidate because it *might* duplicate an existing node. Capturing the flow is the priority; a genuine duplicate is reconciled in the merge pass (§2.4). Naming stays descriptive — Good: `Filter Dashboard by Date Range`, `Submit Compliance Report`; Bad: `Use the System`, `Do Things with Data`.
- The only inline exception is a **within-your-own-payload** obvious duplicate (two identical scenarios you drafted this run) — collapse those before emitting.

### 2.4 Reconciliation is mandatory, not "later"

Because coverage-first (§2.3) and parallel passes will produce below-outcome duplicates, a **reconciliation/merge pass is a required finalization step, not optional cleanup.** The orchestrating skill MUST, after the fan-out completes, collapse below-outcome duplicates within each persona via `Merge_Functional_Nodes` (reuse within the same persona only; never merge across personas — Outcome is the sole shared node). A run that skips reconciliation is incomplete.

> `Functional_Graph_Search` is now an **optional discovery aid only** (find a similar flow when you don't know where to start) — it is **NOT** the dedup engine. Outcome dedup is the deterministic list-all above; below-outcome dedup is the merge pass. Never treat a `Functional_Graph_Search` score as a source of code knowledge.

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
| **aspx Case-A1** — façade/service called **in-process** (direct `new`, DI/Spring `GetObject`, or field on the same host) | `InProcess` | operation name | `<Class>.<Method>` (e.g. `AttendanceService.SaveManualAttendance`) |
| **aspx Case-A2** — service invoked **over a WCF/ASMX wire** (client proxy: `ClientBase<T>`/`ChannelFactory<T>`/generated `*Client`/service-reference, or a `<client><endpoint>` binding in `Web.config`) | `SOAP` | operation name | endpoint address + SOAPAction (from `.svc`/config, resolved to a literal) |
| **aspx Case-B** (side effect with no URL) | — | — | **no `apis[]`** — name the repository/table/SP in `description` instead (system-overlay rule-a fallback) |

> **In-process vs WCF-wire is classified PER SEAM from disk evidence, not per app, and NOT from `[ServiceContract]` attributes** (those only prove a service is WCF-*capable*, never that a *call* crosses a wire). A single page may do both — an in-process facade save AND a WCF autocomplete lookup — so decide each call independently by reading the source: **A2 (SOAP)** only when the call site resolves to a client proxy (`ClientBase`/`ChannelFactory`/generated `*Client`/`ServiceReference`/`System.ServiceModel`) **or** a `Web.config <client><endpoint>` names that contract; the `.svc` `<%@ ServiceHost Service="…" %>` directive names the concrete impl for the endpoint. Otherwise the call is **A1 (InProcess)** — join on `<Class>.<Method>`. When the deciding files are unreadable, default to **A1 `InProcess`** and record `audit.warnings[] {type:"seam_type_unverified"}` — never label a seam `SOAP` on a naming hunch. (`type` is free text server-side; `InProcess` is a recommended addition to the set alongside `SOAP`.)
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

- **The local source checkout is the SOURCE OF TRUTH for fields/markup/behaviour; the code graph is the discovery + contract-resolution layer.** `Read` + `Grep` on disk are the backbone. A run may use **zero** graph calls **only when the seed has no hazard family** (see §6.1) — a genuinely self-contained leaf surface fully traceable by reading it + its direct imports. When a hazard family IS present, the graph is **required** (§6.1 steps 1–2) to discover/inventory it, and `Read` is **still** required (§6.1 step 3) for the leaf detail. The graph (`Code_Graph_Search` / `Get_Code_Nodes_By_Label`) earns its keep by: (a) discovering reachable-but-not-imported members, (b) resolving the concrete **next-hop** of a cross-file call (interface / DI / overload) that `Grep` can't disambiguate, and (c) **repo-wide inventories** (all routes / DB calls). For a true leaf, `Grep`+`Read` alone is faster and always current.
- **⚠️ The code graph does NOT capture every statement — so it is NEVER the source of step/action detail.** It locates code; it does not define behaviour. **Every literal (route, URL, stored proc, table, field code, decorator, guard) and every Step/Action MUST be derived from `Read`ing the real file** — never from a graph summary. At **step/action granularity the local file is the ONLY source of truth.** A graph hit that lacks a statement you expect means "go Read the file," not "the statement doesn't exist."
- **⚠️ Graph-scoping gotchas** (each agent states the base rule "scope every query to `CODE_ONTOLOGY_ID`, fall back to `repository_name` + a `cgs_unscoped` warning"; these two easy-to-miss details live here as the shared reference): (a) on `Get_Code_Nodes_By_Label` the id goes **inside `filters`** (`filters={"codeOntologyId": <id>, …}`) — `repositoryName` is **rejected** as a filter (mutable display name); (b) a bad/missing `codeOntologyId` **fails loud** (`No repository with codeOntologyId … Available: …`), never a silent cross-repo or empty result.
- **Enumerate, do not sample.** Every declared field / widget / injected dependency / side effect that the adapter discovers must be accounted for — either as its own action or folded into a `Review …` description (human) / the operation's payload (system). The adapter records what it found in `audit.declaredFields[]`, `audit.filesRead[]`, and (where relevant) `audit.sideEffects[]`; the validators check the graph against that audit.
- **Drill-down rule:** every dependency the adapter flags as significant (an imported stateful component for UI; a constructor-injected service/repository/client for backend; a referenced `MFLT`/`CRUD`/`.java` handler for a metadata app) **must be `Read`** before scenarios are drafted, and **cited**. If skipped, justify it in the audit's `skipped*` list.

### 6.0 Functional distinctness — split by what the USER sees, never merge by shared code (HARD GATE)

The functional graph captures **what a user perceives and does when they open the application**, not how the code is structured. Therefore:

- **N user-visible choices = N scenarios.** When a surface presents the user a set of distinct options — tabs, categories, entity types, list/filter types, menu items, wizard branches, cards, sections — emit **one scenario per user-visible choice**, EVEN IF a single shared component / form / field-set / route renders all of them behind the scenes. The user sees 8 architecture-layer panels → that is **8 scenarios**, regardless of whether one dialog component with one field config backs all 8.
- **Implementation reuse is NEVER a reason to collapse a functional distinction.** "Same fields", "same component", "same endpoint", "same handler with a `type` param" are technical facts the user never sees — they do not reduce scenario count. Detect the set of choices from what the user would see (tab titles, category labels, option lists, menu entries), not from the backing component's field map.
- **Dedup (§2) still applies, but only to genuine duplicates of the SAME user action** — never to distinct things the user sees that happen to share code. Collapsing distinct user-visible choices is under-coverage, not dedup.
- The only time a multi-choice surface is ONE scenario is when the user genuinely perceives a single undifferentiated action (no visible branching, no choice presented).

This rule is stack-agnostic: it holds for SPA tabs/menus, Razor/aspx panels and grids, and metadata-driven screens alike.

### 6.1 Hazard-family traversal (HARD GATE — the seed's import tree is NOT enough)

> **Scope: code-sourced generation only.** This rule concerns import trees, `Code_Graph_Search`, and component/handler families — it applies to the code-based passes (SPA / backend / Razor / Web Forms / metadata). It is **N/A for design/visual sources** (`visual-to-text` and other non-code generators), which have no seed import tree — those passes derive scenarios from the design surface directly and rely on §6.0 (functional distinctness) instead.

A pure import-walk of the seed misses functionality that is **reachable but not directly imported by the seed** — the recurring coverage failure. When the seed reaches a **hazard family** (definition per stack below), the graph and `Read` play **complementary** roles and BOTH are required — this is a three-step hybrid, not "graph instead of read" nor "read instead of graph":

1. **Discover** the family with `Code_Graph_Search` (semantic — use when you don't know the exact member names, e.g. "the child views opened behind this tab/menu"). It ranks and surfaces members you didn't know to name.
2. **Inventory** it completely with `Get_Code_Nodes_By_Label` (deterministic — scope every query with `filters={"codeOntologyId": <id>, …}`; filter by a `path`/`name` `$contains` on the family's own naming pattern in THIS repo, or `label="Statement"` for routes/DB calls). This is the *complete* set (no ranking, no misses) plus each member's **resolved contract/next-hop** (mutation/handler → API, route, `db_method_call`) — which the graph gives you **for free and more reliably than reading**.
3. **`Read` each discovered member for the leaf detail the graph captures UNRELIABLY or not at all** — field labels/types/required flags, dynamically-built forms, and especially **markup templates** (`.aspx`/`.ascx`/`.cshtml`/`.html` and framework equivalents) which the parser **largely skips**. The graph tells you *which* files to read and hands you the contract; `Read` is the authoritative source for fields/markup. Never enumerate fields from a graph text-blob alone — it may be flattened or partial.

**Hazard-family signals (per stack) — presence of ANY makes step 1–3 mandatory:**
- **SPA (React/Vue/Angular/Next):** seed (or a file it reads) imports a family of `*-dialog` / `*-modal` / `*-drawer` / `*-sheet` components; tab containers (`Tabs`/`role="tab"`/`activeTab ===`); lazy-mounted children (`lazy(() => import())`, dynamic import, `Suspense` subtree); dispatcher components (branch on a `type`/`kind`/`mode`/`variant` prop into N field sets). → **Read for:** JSX field sets.
- **Backend (REST/GraphQL/queue, any language):** interface→implementation via DI, method overloads, decorator/annotation-driven routes, an injected client whose concrete type isn't in a read file. → **Read for:** DTO/enum field lists, validation rules, SQL column sets (graph flattens these).
- **ASP.NET Web Forms / monolith:** the in-process chain code-behind → façade → service → repository → SQL, runtime-mounted `.ascx` controls, and WCF/ASMX service-proxy hops. → **Read for:** `.aspx`/`.ascx` **markup** (fields, grids — parser skips markup) and stored-proc / SQL bodies.
- **ASP.NET MVC / Razor:** `@await Component.InvokeAsync(...)` view-components, partials, editor/display templates, `SelectList`/policy referenced but not located. → **Read for:** `.cshtml` **markup** fields (Razor templates skipped like aspx).
- **Metadata (MAPL/MSCR):** not applicable — fields are declared in MAPL and already enumerable; no hidden import tree.

**Phase-6 hard gate (mechanical, not judgment):** if any file you read imports/references a hazard-family member (dialog/modal/drawer, DI'd service/interface impl, runtime-mounted `.ascx`, view-component/partial, decorator route) that was **neither `Read` nor graph-resolved**, the run is **INVALID** — resolve it (steps 1–3) or record an explicit `audit.warnings[]` justification for why it is out of this EP's scope. "I read the seed and its direct imports" is NOT sufficient when a hazard family is present.

---

## 7. Citations (HARD GATE on prefix AND placement)

A citation is `{ "type": "code", "name": <label>, "reference": <path> }` where `reference` **must** match `^[A-Za-z0-9_.\-]+/` — i.e. start with `<repo-name>/`. The `citations` validator enforces the prefix.

### 7.1 Placement (C3) — citations live ONLY on scenario / step / action
This is a fixed contract, **not** a judgement call — decide once, at authoring time. There are exactly **three** node levels that may carry a `citations[]`, and **two** that must never carry one:

| Node | `citations[]`? |
|---|---|
| **Action** | ✅ **REQUIRED** (≥1) — the handler / field / widget the action came from (tightest, most useful link) |
| **Step** | ✅ **REQUIRED** (≥1) — the file(s) that define that stage |
| **Scenario** | ✅ **REQUIRED** (≥1) — a file that spans the whole flow (the route / page / `MAPL`), or the app-specific audit anchor |
| **Outcome** | ⛔ **forbidden — do NOT emit a `citations[]` key at all** |
| **Persona** | ⛔ **forbidden — do NOT emit a `citations[]` key at all** |

**Every scenario, step, AND action MUST carry at least one citation** — this is a HARD gate (`validate.py citations` exit 2 on any empty scenario/step/action `citations[]`). A missing citation is a defect, not an option: cite the source file the node was derived from. You may NOT satisfy a node's requirement by citing its parent — the citation goes on the node itself. (Outcome/Persona remain forbidden — never required, never allowed.)

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
