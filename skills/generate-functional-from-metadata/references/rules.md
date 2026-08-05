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
| `MCAP(<screenId>)` | **Screen caption / label definitions** (`MCAPP01` = label text) | **field labels for custom-HTML screens that have NO `MFID`** — a second field source for the 100% gate |
| `PNTC(<appId_code>)` | Notification / mail templates (subject, body, `${ReplaceKey}` tokens) | System-half notification actions — what is sent, to whom, against what deadline |
| `WWZA` / `WWSC` / `WWSS` | Wizard definition / Wizard screen definition / Wizard sub-screen (questions + inputs) | Wizard-driven apps — the definition trio the Wizard runtime renders |
| `MAAP` / `MASC` | Batch app / schedule defs (`*-starter`, `pippen-*`) | System persona, scheduled trigger |
| `mod.json` | Vert.x module descriptor | module identity |

> **`MCAP` matters for the hard gate.** Some modules declare their fields ONLY in `MCAP` —
> custom-HTML screens with no `MFID` at all. If you enumerate from `MFID`/`MFLT`/`CRUD` alone,
> `audit.declaredFields[]` comes back EMPTY and `field-coverage` passes **vacuously at 0/0**: the
> financial-completeness guarantee silently does not hold. Whenever a screen resolves no `MFID`,
> look for `MCAP` before concluding the app declares no fields.

### MAPL internals

- `MAPLD01` = feature title, `MAPLD02` = description.
- `MAPLD03` = **entry/control handler name, NOT a role code.** Observed values are control
  identifiers (`StartControl`, `SS01`, `DF01`, `WD01`, `BackNavigate`, `WDRoleCheck`), and the SAME
  value appears under apps owned by different business roles. **Never treat it as a persona seed** —
  see "Persona rules" below for what to do instead.
- `MAPLQ.<date>.<NN>` = ordered steps. Each step:
  - `MAPLQ01` = step name
  - `MAPLQ02` = **verb** — `ShowScreen` | `DoFilter` | `WriteData` | `GoApplication` | `EndApplication` (+ `DetermineRoleByWebAppEngine` etc.)
  - `MAPLQ03` = target id (screen id / filter id / `$CustomFilterXXXX` / WriteData handler / target app id)
  - `MAPLQ04` = parameters
- `MAPLP.<date>.<NN>.MAPLP01` = **declared parameter names** (`endAppId`, `backPrm3…10`, …). These
  resolve the `@`-prefixed `GoApplication` targets — `@endAppId` is satisfied by the `endAppId`
  parameter declared here.
- `MAPLR.<date>.<NN>` = **button → routing table**: `MAPLR04` = button/handler name (`Back`, `End`,
  `WDKitAssersion`), `MAPLR06` = screen+button id (`S9UR02B01`), `MAPLR07` = route class
  (`Main` / `Err`). This is the branch structure — which button leads where, and which path is the
  error path.
- `MAPLS.<date>.<NN>` = **step transition chain**: `MAPLS01` = transition kind (`CNT` = continue),
  `MAPLS02` = from-step, `MAPLS03` = to-step. Together with `MAPLR` this is the app's state machine.

> **`MAPLR`/`MAPLS` are branch structure, and the graph has no lateral edges.** The upsert schema is
> a strict tree (`persona → outcome → scenario → step → action`) with no `next`/`link`/`transition`
> field. So express branching as **distinct Scenarios** (one per materially different path — e.g.
> the `Err` route vs the `Main` route) and as explicit step ordering, never as an invented edge.
> Do not silently flatten several routes into one linear scenario.

### MAPLQ verb → functional meaning

| `MAPLQ02` verb | Half | Functional action |
|---|---|---|
| `ShowScreen <S###>` | **Human** | a UI step — user provides/reviews the fields on that screen (`MSCR`+`MFID`) |
| `DoFilter <H###>` | **System** | a data-read — resolve `MFLT(<H###>)`; action describes the query, joins, conditions |
| `DoFilter $CustomFilterXXXX` | **System** | a custom read — read the Java handler `CustomFilterXXXX.java`; describe its logic |
| `WriteData <Handler>` | **System** | a write/side-effect — read `<Handler>.java`; describe the persisted/output data |
| `GoApplication <appId>` | **Human** | a **hand-off to another application** — the user completes here and continues in `<appId>`. Emit ONE terminal action naming the target *capability* (not the app id) |
| `GoApplication @<param>` | **Human** | same, target resolved at runtime — resolve `@<param>` against the `MAPLP` parameter names before giving up |
| `EndApplication` | — | terminal; not emitted as an action |

#### `GoApplication` — the cross-application hand-off (do NOT drop it)

`GoApplication` is a high-frequency verb (it can outnumber `ShowScreen` in navigation-heavy trees).
Dropping it turns every application into an island and loses the multi-app journeys the business
actually runs — e.g. one real-world life event that chains several modules together.

1. **Emit an action.** A terminal human action on the last step: `Continue to <target capability>`.
   Name the capability, never the raw app id (`Continue to Family Registration`, not
   `Continue to CEPAY0564`). Put the app id in the description.
2. **Resolve the target.** A literal app id is used directly. An `@`-prefixed target is a runtime
   parameter — resolve it against `MAPLP` parameter names, and against the caller's `MAPLQ04` where
   the caller is known. If it still cannot be resolved, emit the action and record
   `resolved: false` — **never invent a target.**
3. **Record it for the journey map.** Append every hand-off to
   `audit.appTransitions[] = [{ fromAppId, toAppId, resolved, via }]`. The orchestrating skill
   aggregates these into a journey map artifact.
4. **Do NOT fabricate a graph edge.** The schema is a tree; there is no relation field. The
   hand-off lives as an action + description + the `audit` record — nothing else.

---

## ⛔ Entry points are METADATA **plus** CODE — MAPL alone is incomplete

The `MAPL` record declares the **screen flow**. It does NOT declare every endpoint the running app
exposes. Modules routinely register EventBus addresses that the browser calls directly and that no
`MAPLQ` step mentions — inline field validation being the most important, plus resource lookups and
shared formal-screen renderers.

Treating MAPL as the complete entry-point list therefore **silently drops real user-facing
behaviour**. In a financial app that is a correctness problem, not a cosmetic one: it is how a graph
ends up saying *"Enter the change date"* while omitting *"must be 8 digits and a valid calendar
date, else MSG70001"* — because the rule lives behind an endpoint MAPL never names.

**Always reconcile the two sources:**

1. **Declared** — every `MAPLQ03` target across the app's `MAPL` records.
2. **Exposed** — bus addresses / handler registrations in the repo's own `app/` package. A cheap
   grep for quoted `"<module>/<path>"` string constants and `registerHandler(...)` finds them.
3. **Called** — the URLs in `src/main/resources/**/*.js` (`url:` in `$.ajax`), which prove an
   address is reachable from the browser rather than dead.
4. **Diff.** Anything **exposed and/or called but not declared** is an additional entry point.
   Record it in `audit.undeclaredEntryPoints[]` and model its behaviour like any other — do not
   discard it because MAPL is silent.

Typical undeclared addresses (verified in real modules): `<module>/validation`,
`<module>/resources`, `pippen/approver/formal`, `pippen/kit/formal`.

## Reading depth — follow references, do not stop at the MAPL targets

Reading only the classes MAPL names captures the **spine** and misses the leaves: the handlers it
names delegate to validators, services, components and domain classes that hold the actual rules.
Measured on a real module, a MAPL-targets-only pass read **11 of 65** app-package classes (17%).

From each class you read, follow same-repo `import jp.co.payroll.p3.**.app.**` references to
**depth 2**, skipping framework imports (`org.vertx.*`, `java.*`, `org.apache.*`). This is
name-agnostic — it finds services and components, not just things called `*Validator`. Bound it to
classes reachable from fields already enumerated; do NOT read the whole package.

Capture what you find **on the field's own action**: `Enter <field>` should carry the concrete rule
(format, length, range, message code), not just the label.

## Screen templates — read the HTML

`src/main/resources/template/**/*.html` is the actual markup for a screen. `MSCR`/`MFID`/`MCAP`
give codes and labels; the template shows **which fields render, in what widget, and whether they
are editable**. A pass that never opens the templates is guessing at editability. Read the templates
for the screens in scope.

### Caption codes are scoped to a SCREEN (`MCAPAK4`), not to the application ⛔

`MCAP` records are keyed `MCAP(<appId>_<screenId>)`, and the codes inside restart per screen. **The
same `$CAP…$` code means different text on different screens of the same app.**

Worked example (`pippen-navigate`, CEPAY0557): `$CAP0000001$` is *"1. First items to enter"* on
screen `S8VY`, but *"The specified application has a separately saved application"* on screen
`S8VZ`. `holdingUser.html` uses `$CAP0000001$` and belongs to `S8VZ` — resolving it against the app's
main screen yields a confident, completely wrong label.

So: resolve every template's codes against **its own owning screen**. Establish the
template→screen mapping first (via the `ShowScreen` step that renders it), then look the codes up in
that screen's `MCAP`. Never build one flat app-wide code→text dictionary.

### Captions are also injected from Java — templates alone are not the full set

Some captions never appear in markup; the handler puts them into the template engine at runtime,
typically `ctx.getCaptions().get("CAP…")` / `hte.put(...)`. These render as real on-screen text and
must be captured.

Worked example (CEPAY0557): `CAP0000034` *"Enter information regarding family members"* — a visible
guide-card title — is injected at `NavigaterCustomFormalForm:707`, and `CAP0000048` is injected as an
error string. Neither appears in any `.html`. On that screen a template-only sweep resolves 45 of 54
declared codes and silently drops both.

So: after sweeping `$CAP…$` in templates, **grep the app's Java for `CAP\d{7}`** and fold in what you
find. A code declared in `MCAP` but absent from both is a candidate dead caption — say so, do not
invent a purpose for it.

### UI assembled from a remote call is a BOUNDARY — declare it, do not claim it

A template placeholder may be filled with markup fetched over the EventBus rather than rendered
locally. The fields inside that markup are **not reachable** from this repo, and field coverage must
not be presented as covering them.

Worked example: `navigater/main.html` ends with `$$kitHtml$$` and `$$approvalHtml$$`;
`NavigaterCustomFormalForm` fills them from `pippen/kit/formal` and `pippen/approver/formal`
(`body.getString("data")`), gated on `LNAVP16` / `LNAVP08`. The same two calls are made by
`CustomFormal_FormBase`, so **every** Pippen form embeds them. Neither service is implemented in the
repo set.

So: record the call in `apis[]` on the action that triggers it (this part already works), and state
in the action description that the region's fields are supplied by that service and are outside this
repo. Do **not** enumerate or estimate them.

## Shared `submodules/` — analyse ONCE, never per app

`src/main/java/**/submodules/**` is shared platform code **physically copied into every repo**
(same file, identical bytes, in 60+ repos). Re-reading it per application is pure waste.

But it is not empty of behaviour — e.g. `CustomFormal_BTN_Verify_base` hides the approve/reject
button pair when the session role is `040` (Overall HR) or `060` (Payer HR), which is real
persona-conditional UI behaviour and the ONLY role branch in the whole application layer.

So: the orchestrating skill analyses the shared framework **once** and passes the findings to every
per-app agent as context. The per-app agent does NOT re-read `submodules/`; it applies the brief it
is given.

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
   every `MFLT` output-column map (`MFLTP04`), every `CRUD` column list, **and every `MCAP`
   caption record (`MCAPP01`) for screens that resolve no `MFID`**. Record them in
   `audit.declaredFields[]` as `{source, code, label, editable:<true|false>, widget:"<E|L|H|R|I|P|B|…>"}`.
   `MCAP` entries carry a label but no widget code — infer `editable` from the surrounding HTML
   input element and set `widget:"MCAP"`.

   **If the app has screens but you end up with ZERO declared fields, that is a finding, not a
   pass.** Say so explicitly in `audit.warnings[]` — `field-coverage` will report 0/0 and succeed
   soft, which looks identical to real coverage. Check for `MCAP` and for custom HTML before
   accepting an empty enumeration.

   **Cite the caption code in the action description.** When an action covers a field or control
   whose label came from `MCAP`/`MFID`, name the code — `(caption CAP0000025)`, `(field: lastName;
   captions CAP0000018, CAP0000031)`. An action that describes a field only in translated English is
   *functionally* correct but not traceable: an auditor re-deriving the declared set from source
   cannot match it, and the field looks uncovered. Measured on a real app, this alone was the
   difference between an apparent 46% and an actual ~94% coverage — the content was there, the
   references were not.
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

- **Human persona — `MAPLD03` is NOT a reliable role source.** It holds the entry/control handler
  name (`StartControl`, `SS01`, `DF01`, `WD01`), and the same value legitimately appears under apps
  owned by different business roles. A code→name lookup on it is therefore not possible in the
  general case, and pretending otherwise is what produced silently-unverified personas.

  Resolve in this order, and **record which source you used**:
  1. A genuine role field, if the tree has one (a role master / `LNAV`-style mapping / an explicit
     role code that is *not* `MAPLD03`) → `confidence: "mapped"`.
  2. Otherwise **infer** from repo name, `MAPLD01` title and screen content (e.g. a `store-*` module
     → "Store Manager"). This is a reasonable heuristic and you SHOULD do it — but it is a guess:
     set **`confidence: "inferred"`**, and record the evidence in `personaHumanEvidence`.
  3. Nothing usable at all → emit the raw value with `confidence: "raw"`.

  **`mapped` means "read from an authoritative role source" — nothing else.** Do NOT stamp an
  inference as `mapped`. The parent's confirmation gate keys off anything that is not `mapped`; if
  inferences are mislabelled the gate has nothing to show and 100% of personas ship unreviewed.
  Never invent a role that no evidence supports.
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
