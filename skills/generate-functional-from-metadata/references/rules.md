# Vert.x metadata-driven → Functional Graph mapping rules — adapter

> **Read the single source of truth FIRST** (ADR 0001): `../../shared/functional/core.md`
> + `human-overlay.md` (human half) + `system-overlay.md` (System/External half). This
> file is the **metadata source-extraction adapter** — record types, MAPLQ verb mapping, metadata
> persona resolutions, apis[] typing, the field-capture gate. It refines, never overrides,
> the shared rules; hard gates are enforced by the shared `validate.py` (shimmed in this
> skill's `validators/`).

This targets a Vert.x metadata-driven platform: ~hundreds of Vert.x/Java
Gradle modules sharing a `webapp-engine`. Behaviour is **declared in JSON metadata**,
not imperative code. The functional flow for every feature is already written down in
a `MAPL` record. This file is the canonical mapping; it is embedded in both metadata agents'
system prompts.

---

## The record types you will read

| Record (filename `TYPE(KEY).json`) | Meaning | Used for |
|---|---|---|
| `MAPL(<appId>)` | **Application recipe** — the ordered step flow | Scenario skeleton + steps + action verbs |
| `MSCR(<screenId>)` | Screen layout (grid of field codes) | which fields a screen shows |
| `MFID(<fieldGroup>)` | **Field definitions** — code + label per field | 100% field enumeration |
| `MFLT(<filterId>)` | Declarative DB query (conditions, joins, output columns, sort) | System data-read actions + field detail |
| `CRUD(<module_table>)` | Per-table CRUD access (custom-HTML modules) | System data actions + columns |
| `MMSG(<appId_code>)` | User/validation messages | action descriptions / error branches |
| `MAAP` / `MASC` | Batch app / schedule defs (`*-starter`, `pippen-*`) | System persona, scheduled trigger |
| `mod.json` | Vert.x module descriptor | module identity |

### MAPL internals

- `MAPLD01` = feature title, `MAPLD02` = description, `MAPLD03` = role code (persona seed).
- `MAPLQ.<date>.<NN>` = ordered steps. Each step:
  - `MAPLQ01` = step name
  - `MAPLQ02` = **verb** — `ShowScreen` | `DoFilter` | `WriteData` | `EndApplication` (+ `DetermineRoleByWebAppEngine` etc.)
  - `MAPLQ03` = target id (screen id / filter id / `$CustomFilterXXXX` / WriteData handler)
  - `MAPLQ04` = parameters

### MAPLQ verb → functional meaning

| `MAPLQ02` verb | Half | Functional action |
|---|---|---|
| `ShowScreen <S###>` | **Human** | a UI step — user provides/reviews the fields on that screen (`MSCR`+`MFID`) |
| `DoFilter <H###>` | **System** | a data-read — resolve `MFLT(<H###>)`; action describes the query, joins, conditions |
| `DoFilter $CustomFilterXXXX` | **System** | a custom read — read the Java handler `CustomFilterXXXX.java`; describe its logic |
| `WriteData <Handler>` | **System** | a write/side-effect — read `<Handler>.java`; describe the persisted/output data |
| `EndApplication` | — | terminal; not emitted as an action |

---

## The two linked subtrees (the metadata-app advantage)

A single `MAPL` yields BOTH halves of the functional graph, joined by the **app id**:

- **Human subtree** — persona = resolved human role (see Persona rules). Built from the
  `ShowScreen` steps. Actions = what the user provides/reviews/confirms (platform-agnostic).
- **System subtree** — persona = `System` (or `External System` for inbound integrations /
  SOAP-Axis / partner callbacks). Built from the `DoFilter`/`WriteData` steps. Actions = internal
  processing, each with a required description + `apis[]`.

**Link rule:** both subtrees use the **same Outcome name** (derived from `MAPLD01` /
business capability). The upsert merges by name, so the human "what" and the System
"how" attach to one Outcome. Use the agent's own persona-scoped dedup read-back (live graph) to reuse existing
Outcomes/Scenarios — never create a second Outcome that means the same thing.

---

## apis[] typing (metadata)

`apis[].type ∈ {REST, GraphQL, gRPC, WebSocket, Event}`. For this metadata model:

- **`Event`** — internal Vert.x EventBus calls, `DoFilter` (Data-API filter), custom-filter
  EventBus addresses, `WriteData` handlers. `method` = verb (`DoFilter`/`WriteData`/address),
  `url` = filter id / handler name, `request`/`response` = field shapes.
- **`REST`** — only the explicit browser `$.ajax` calls in custom-HTML modules
  (`src/main/resources/web/*.js`), e.g. `POST /apy-common-screen/Script`. `method` = HTTP verb,
  `url` = the endpoint path.

Engine-rendered (Flavor A) screens make NO REST call from the page — leave human-side
`apis[]` empty; the call surfaces on the System side as `Event`.

---

## Field capture + action atomicity (financial-app hard requirement)

Every field is declared, so capture is provable (`field-coverage` == 1.0 is the hard gate).
Coverage alone, though, can be satisfied by clubbing every field into one description — which
defeats granularity. So **prefer atomic actions: one user-editable field = one action.**

**Atomicity is a PREFERENCE, not a universal hard rule:**
- It does **NOT** apply to **System / External System** personas — a `DoFilter`/`WriteData`
  processing action is one atomic operation, and its field list is the request payload of that
  single call. Leave System actions as one-per-filter/write.
- For **human** personas it is the default/expected shape, but **not mandatory in every case**
  — some screens are naturally one action (a single field, or a tightly-coupled set). Use
  judgement; the `atomicity` check is advisory (warnings), not a blocking gate.

Classify every declared field by its screen widget (from the `MSCR` layout + `MFID` type):

- **Editable** — text entry, numeric, date, dropdown / pulldown, radio, checkbox, file upload
  (the input + selection widgets; in these metadata widget codes these are the `E`-type and picker widgets).
  These are the fields a user actually fills or chooses.
- **Read-only** — headers (`H`), labels (`L`), formatted / result holders (`R`), grid / list
  display columns (`I` / `P`), and navigation buttons (`B`).

Rules:

1. **Enumerate** all field codes+labels from every `MFID` referenced by the app's screens,
   every `MFLT` output-column map (`MFLTP04`), and every `CRUD` column list. Record them in
   `audit.declaredFields[]` as `{source, code, label, editable:<true|false>, widget:"<E|L|H|R|I|P|B|…>"}`.
2. **One atomic action per editable field.** Each editable input / selection field becomes its
   OWN action — `Enter <field>` for text/number/date, `Select <field>` for dropdown / radio /
   checkbox. The action references exactly that one field. Do NOT list multiple editable fields
   in one action's description.
3. **Read-only fields do NOT each need an action.** List display / grid columns, labels and
   headers inside the relevant `Review …` action's description so they are covered. Navigation
   buttons are not actions — except a mutually-exclusive pair (back/continue, submit/cancel),
   which is ONE branch decision: a single `Indicate whether to …` action. Never split a button
   pair into two actions.
4. **The backend call is its own action.** A field-entry action makes NO API call — typing a
   field hits no endpoint. The validate / submit / persist call (`DoFilter` / `WriteData` /
   `$.ajax`) belongs on a dedicated `Validate …` / `Submit …` / `Persist …` action that OWNS
   the `apis[]`, ordered AFTER the entry actions. Input / selection actions therefore have
   empty `apis[]`. (System-half `DoFilter`/`WriteData` processing actions are already atomic —
   one filter/write = one action; their field list is the request payload of that one call.)
5. **Assert** in Phase 6: `field-coverage` == 1.0 — this is the HARD gate (financial
   completeness). `atomicity` is an ADVISORY check (human half only; skipped for System) that
   surfaces clubbed input actions, input actions carrying `apis[]`, and editable fields with no
   dedicated action — review its warnings and split where it makes sense, but it does NOT block
   the run.

Also capture, where present in `MFLT`: filter conditions (`==`, `~`, `>=`), status codes
(e.g. `C05=101`), date windows (`C06 >= $hireDate`), join tables, and sort order — these go in
the System action description (thresholds/field names are required there).

---

## Persona rules (metadata-app-specific)

Follow the single source of truth — `../../shared/functional/core.md` plus
`../../shared/functional/human-overlay.md` (human half) and
`../../shared/functional/system-overlay.md` (System / External half) — with these metadata resolutions:

- **Human persona** — from `MAPLD03` role code. Map known role codes to business-domain names
  (e.g. an HR/payroll back-office approver → "Payroll Administrator"). If the role library /
  mapping is unknown, surface the raw code to the parent's confirmation gate; never invent.
- **System persona** — `DoFilter`/`WriteData`-only apps, `*-starter` async modules, `pippen-*`
  batch (`MAAP`/`MASC`), internal EventBus handlers.
- **External System persona** — inbound integrations: SOAP/Axis (`lib/axis.jar`), partner
  callbacks, file-ingest (`fileg-*`).
- Forbidden persona names (engine/tech): never `Engine`, `Verticle`, `Filter`, `Handler`,
  `Module`, `API`, `WebAppEngine`, etc.

---

## Module classification (for discovery)

| Signal | Class | Default persona side |
|---|---|---|
| has `MAPL` + `ShowScreen` steps + `MSCR`/`MFID` | web app (Flavor A) | Human + System |
| has `MAPL` + `src/main/resources/web/*.html` + `*.js` `$.ajax` | web app (Flavor B) | Human + System (REST apis) |
| name `*-starter`, has `batch_config.json` / `MAAP` / `MASC` | async/batch trigger | System |
| `pippen-*` | batch worker | System |
| only `.git` + empty `README.md` | EMPTY placeholder (`epy-*`) | SKIP |
| `lib/axis.jar`, SOAP client | integration | External System |
