# Functional Ontology — Human (non-System) Overlay

> Applies when the persona is a **named human role** or a generic human (`User`, `Customer`, `Visitor`). Read **after** `core.md`. Everything here is in addition to the core. For `System` / `External System` personas use `system-overlay.md` instead.

---

## 1. Persona derivation (human)

Resolve the persona in **strict priority order** (REUSE existing personas first):

1. **Named human role** implied by the business domain — e.g. `Admin`, `Fund Manager`, `Compliance Officer`, `HR Administrator`, `Payroll Administrator`, `Store Manager`, `Approver`.
2. **Generic human role** when no domain role can be determined → `User`, `Customer`, `Visitor`.

Decision aids:
- If the actor is ambiguous between User and System, ask **"Does a human make a real-time decision that causes this to run?"** → YES → human persona. (If still truly ambiguous, default to **`User`**, never `System`.)
- Merge similar roles (`Admin User` ≡ `Administrator` → one).

### Extraction discipline
- **Extract literal role names from the source only — never invent.** For UI: prefer `/breeze:detect-personas` output (it does per-variable usage counting and drops dead-code roles) over manual grep. For P3: map `MAPLD03` role codes to business-domain names; if the mapping is unknown, **surface the raw code to the confirmation gate** — do not guess.
- **Verify actual usage:** a role constant defined but with **0 usages** outside its definition/import lines is dead code and MUST NOT become a persona. Grep each role variable **individually** (never combined with `|`).
- **Subscription tiers / feature flags are NOT personas** — list them separately under "feature flags — not personas".
- The confirmed persona set is a **closed set**: if the per-EP loop needs a persona not in the set, **STOP and ask the user**.

### Forbidden persona names — NEVER use
Any of `verbs.json → forbidden_persona_names` (Developer, Engineer, Programmer, Architect, DevOps, API, Service, Component, Module, Worker, Backend, Frontend, Database, Controller, Handler, Repository, plus P3 engine names Verticle/Filter/WebAppEngine/Engine). If you catch yourself writing one, STOP and re-resolve by the priority order. The `persona --kind human` gate fails these.

> **Boundary:** the human/UI pass writes **only** human personas — never `System`. It never reads backend repos, never cites backend paths, never claims anything about controllers/routes/handlers.

---

## 2. Action language — platform-agnostic intent (HARD GATE: `forbidden`)

Human actions describe what the user **PROVIDES, DECIDES, or OBSERVES** — they must read identically for web, mobile, CLI, or voice.

- **FORBIDDEN words** (`verbs.json → forbidden_ui_words`): click, tap, swipe, hover, scroll, drag, drop, toggle, button, dropdown, modal, dialog, popup, panel, checkbox, radio, slider, tooltip, menu, sidebar, navbar, tab, icon. The `forbidden` check (word-boundary match) fails on any of these in a human action name.
- **USE instead** — intent verbs (`verbs.json → human_intent_verbs`): Provide, Choose, Confirm, Review, Dismiss, Open, Close, Submit, Cancel, Specify, Indicate, Acknowledge, Request, Enter, Select, Filter.
- **`description` is REQUIRED on every action (HARD GATE — `validate.py descriptions`).** State what the action accomplishes in user terms: for a field action, the field metadata (`label: …; type: …; required: …`, per Pattern A §3); for a constraint, the rule (`Minimum 20 characters`, `Blocked until all files uploaded`); for a branch, the choice. **Never** put code-level prose in a human action description (no `onStageClick`, no component names, no table/SP/SQL — that's the system half). Scenarios are likewise required to carry a non-empty description.

---

## 3. Action atomicity — one editable field, one action (ADVISORY: `atomicity`)

Field coverage alone can be gamed by clubbing every field into one description, which destroys granularity. So the **preferred shape is atomic**:

1. **Classify every declared field** by its input widget and record it in `audit.declaredFields[]` as `{ source, code, label, editable: <bool>, widget }`:
   - **Editable** — text/numeric/date entry, dropdown/pulldown, radio, checkbox, file upload (the fields a user fills or chooses). For P3: the `E`-type and picker widgets.
   - **Read-only** — headers, labels, formatted/result holders, grid/list display columns, navigation buttons. For P3: `H` / `L` / `R` / `I` / `P` / `B`.
2. **One atomic action per editable field** — `Enter <field>` for text/number/date, `Select <field>` for dropdown/radio/checkbox, `Filter by <field>` for search criteria. The action references exactly that one field; do not list multiple editable fields in one action.
3. **Read-only fields do NOT each need an action** — fold their labels/columns into the relevant `Review …` action's description so they are still covered.
4. **A mutually-exclusive button pair** (back/continue, submit/cancel) is **ONE** branch decision → a single `Indicate whether to …` action. **Never** split a button pair into two actions.
5. **The backend call is its own action.** Typing a field hits no endpoint, so field-entry/selection actions have **empty `apis[]`**. The validate/submit/persist call gets its **own** `Validate …` / `Submit …` / `Persist …` action, ordered **after** the entry actions, and that action **owns the `apis[]`** (or the Event / socket-push link).

**Atomicity is a PREFERENCE, not a hard gate.** Some screens are naturally one action (a single field, or a tightly-coupled set) — use judgement. The `atomicity` check is **advisory** (warnings only): it surfaces clubbed input actions, input actions that wrongly carry `apis[]`, and editable fields with no dedicated action. Review the warnings and split where it makes sense; it never blocks the run. (If `declaredFields[]` is untagged with `editable`, the check no-ops with a warning.)

> The only HARD coverage gate is **`field-coverage == 1.0`** (see core §9): every declared field must appear in some action name or description.

---

## 4. Coverage (advisory, UI-specific)

Where the adapter supplies a JSX widget inventory (`coverage --seed-file`), ≥90% of widgets should map to an action. Common chrome (close affordances, breadcrumbs) may be listed in `viewOnlyChrome[]` with a one-line justification, **but widgets carrying action verbs (Save, Submit, Generate, Delete, Upload, Download, Send, Confirm, Apply, Run, Create, Update) can never be excluded** — an unmatched one fails the audit. `api-urls` (advisory) warns if an `apis[].url` literal is not found in the source tree.

---

## 5. Human `rule-a`

First word of a human action in `verbs.json → network_verbs` ⇒ **non-empty `apis[]` required** (no description fallback — that fallback is system-only). Fix by adding the `apis[]` from the service/query file, or rename to drop the verb if local-only (and say why, e.g. "persists to localStorage").
