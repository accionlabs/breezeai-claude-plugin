# ADR 0001 — Consolidate the Functional-Ontology Rules into a Single Layered Source of Truth

- **Status:** Accepted — implemented (Phase 1–2 + most of Phase 3 wired 2026-06-22; build-time assembly is the remaining hardening). See `skills/shared/functional/README.md` § Migration status.
- **Date:** 2026-06-22
- **Owner:** Anirudha
- **Scope:** `breezeai-claude-plugin` — the functional-graph generation/validation/consumption skills
- **Decision driver:** functional-ontology rules are duplicated and drifting across `rules/*.mdc`, `skills/shared/`, per-skill `references/rules.md`, three `schemas/upsert.schema.json`, three `validators/validate.py`, and a Python validator — with at least one outright semantic conflict.

---

## 1. Context

The functional graph (`Persona → Outcome → Scenario → Step → Action → apis[]`) is authored by three generator skills, validated by one, and consumed by ~eight more. Each carries its own statement of "the rules." There is **no enforced single source of truth**: `skills/shared/functional-graph-rules.md` is pointed at in prose by a few skills but **never `Read` at runtime**, and is frequently re-inlined or forked.

This ADR records a full audit of where functional-ontology rules live, what diverges, and a proposed layered consolidation.

### 1.1 Audit — where rules live today

| Tier | File(s) | Role | Problem |
|---|---|---|---|
| Cursor rules | `rules/breeze-functional-graph-rules.mdc` (+ `breeze-guard.mdc`, `breeze-skill-routing.mdc`) | Cursor-only steering | **Not wired into Claude.** Zero `skills/` references; `.claude-plugin/plugin.json` has no `rules` key (only `.cursor-plugin/plugin.json` does). 55-line summary already drifted from `shared/` (diff: 0 common lines). |
| De-facto canonical | `skills/shared/functional-graph-rules.md` (230 lines) | Node model, persona priority, forbidden persona names, persona-aware action rules, MCP tool map | Pointed at by `analyze-functional`, `update-functional-graph`, `validate-functional-graph` **in prose only** — never `Read`; often re-inlined. Does **not** contain the rich rules (apis/citations/rule-a/coverage/atomicity). |
| Generator rich rules | `skills/generate-functional-from-{ui,backend,metadata}/references/rules.md` + `schemas/upsert.schema.json` + `validators/validate.py` | apis[].type, citation regex, rule-a, field-coverage, atomicity, forbidden words | The **real** rulebook lives here, triplicated, and diverges between ui/backend/metadata. |
| Forks & copies | see §1.2 | — | Silent drift. |

### 1.2 Confirmed divergences (evidence)

1. **Three independent copies of the forbidden persona-name / UI-word lists:**
   - `skills/update-functional-graph/SKILL.md` (markdown, full inline)
   - `skills/analyze-design/references/functional-graph-rules.md` (markdown, **lossy fork** — missing the full forbidden-persona list and the System/External action rules)
   - `skills/validate-functional-graph/scripts/validate-graph.py` (**Python** — a markdown SSOT will never reach this)
2. **`skills/analyze-functional/references/guide.md`** ≈ near-copy of `shared/functional-graph-rules.md`.
3. **`skills/analyze-design/references/functional-graph-rules.md`** shares only a filename with `shared/…` — `diff` = fully divergent (13,984 B vs 8,166 B). It is a partial functional fork bolted onto design-graph rules.
4. **`skills/visual-to-text/references/guide.md` is a SEMANTIC CONFLICT:** it redefines **Step** as a *configuration variation* ("with coupon / without coupon") and adds `Action TRIGGERED_BY Component` — contradicting the canonical *sequential-stage* definition of Step.
5. **Three schemas, three validators** (`ui`/`backend`/`metadata`) that are ~90% identical. The validators are **source-agnostic** (no MAPL/JSX strings; they read only `payload` + `audit`), so triplication is pure duplication.
6. **Verb-set inconsistency even within one skill:** backend `rule-a` uses a 26-verb `SIDE_EFFECT_VERBS` set, but the backend `rules.md` coverage note lists only 11.

### 1.3 The rules cleave cleanly into layers

The audit shows the rules are **not** an entangled mess — they separate into a universal core, two persona overlays, and per-skill adapters:

- **Universal core** — node model; schema shape; citations (regex `^[A-Za-z0-9_.\-]+/`, placement at persona/outcome/scenario only); `rule-a` (side-effect-verb action ⇒ non-empty `apis[]`); enumeration rule; dedup matrix; Code_Graph_Search hygiene; write protocol (`/functional-graph/v2/upsert`, wrapper body `{payload, project, skipStepAndAction}`, `api-key:` header); the **dual human↔system subtree linked by a shared Outcome name**.
- **Human (non-system) overlay** — atomic action per **editable** field (filled / filtered / selected); view-only fields fold into a `Review …` description; platform-agnostic intent verbs; **forbidden UI words**; `description = null` default; persona derivation; persona-visibility / RBAC audit; the `Validate/Submit/Persist` action owns the `apis[]` / Event / socket-push link.
- **System overlay** — entrypoints = routes / queue consumers / event handlers / cron / webhooks; persona ∈ `{System, External System}` (mechanical EP→persona map); **one operation = one action** (field list IS the request payload ⇒ per-field atomicity is **exempt**); action `description` **REQUIRED**.
- **Per-skill adapter** — source extraction only: Vert.x-metadata (`MAPL/MSCR/MFID`, widget codes `E/L/H/R/I/P/B`), UI (JSX/DOM/React-Query hooks), backend (routes/DTO/queues), aspx (SOAP/SQL). Each emits a **normalized `audit.declaredFields[]` + the two halves**, then runs the *same* validators.

**`generate-functional-from-metadata` is the reference implementation** — the only skill that already builds *both* halves and links them by shared Outcome. UI builds human-only; backend builds system-only.

---

## 2. Decision

Adopt a **single, layered source of truth** for the functional ontology:

```
skills/shared/functional/
  core.md            # universal core (absorb apis/citations/rule-a/dedup/enumeration/write-protocol)
  human-overlay.md   # non-system persona rules (atomicity, forbidden words, visibility, persona derivation)
  system-overlay.md  # System/External persona rules (EP→persona, description-required, atomicity-exempt)
  upsert.schema.json # ONE schema, persona-kind aware
  validate.py        # ONE validator engine: validate.py <check> --kind human|system
  verbs.json         # single source for SIDE_EFFECT_VERBS / INPUT_VERBS / FORBIDDEN_UI_WORDS

skills/generate-functional-from-{ui,backend,metadata}/
  references/rules.md  # SHRINKS to this source's adapter only (extraction → audit + two halves)
  # schema + validator become imports/symlinks of the shared ones
```

**Reject** a single flat file (some rules are persona-conditional opposites — see §3). **Reject** status-quo (drift is already live).

Two mechanisms are mandatory for the SSOT to actually hold:

- **Assemble at package/build time — do not rely on runtime `Read`.** Skills point at shared rules today but never load them, which is *why* drift persists. A small build step inlines `core + overlay` into each skill's references at package time: one source, mechanically fanned out, no dependence on the model choosing to read.
- **De-duplicate the Python validator.** `validate-graph.py` must import `verbs.json` rather than re-listing the words, or it will keep drifting independently of any markdown SSOT.

---

## 3. Conflicts that MUST be resolved before merging (the real cost)

These are the reasons a naïve merge fails; each needs an explicit decision.

| # | Conflict | Options | Recommendation |
|---|---|---|---|
| C1 | **Persona enum.** Backend schema hard-enums `{System, External System}`; UI persona = any string. Server enforces **no** enum (`@IsString()`), so the enum is a client-side guard only. | (a) no enum in shared schema, enforce persona-kind in the overlay validator; (b) `--kind`-switched schema. | **(a)** — matches the server contract; overlay validator gates human-vs-system names. |
| C2 | **Action `description` default is opposite.** Human = null + UI words forbidden; System = required. | Keep persona-conditional in the two overlays; core stays silent on description default. | Persona-conditional. Never a single "actions need/▱don't-need descriptions" rule. |
| C3 | **Citation level.** | **RESOLVED 2026-06-22 — cite LOW.** Citations live on **action/step/scenario** (prefer action; backend DTOs accept all 5 levels), **never outcome/persona** (shared → pollution; validator warns). Schema extended to step+action; completeness is a union across levels. Supersedes the earlier scenario-only stance. |
| C4 | **`visual-to-text` Step semantics** (variation vs sequential stage). | (a) adopt canonical sequential-Step, refactor visual-to-text; (b) carve a documented exception. | **(a)** unless variation-Step is intentional; this is a correctness issue, not just drift. |
| C5 | **`apis[].type`** is free text server-side but prose tables read like an enum; backend extends with `SQL`/`Event`/etc.; aspx Case-B carries the side effect in `description` with **no** URL. | Core states: free text, open recommended set, per-stack join-model addendum (SPA fetch-literal / aspx SOAP-or-SQL / backend route / Vert.x Event). | Document the join models explicitly; the "Validate/Submit action owns apis[]" thesis is correct for SPA but **incomplete** for aspx Case-B. |

---

## 4. Phased migration plan

**Phase 1 — kill drift, no behavior change (high value, low risk):**
- Delete or clearly mark `rules/*.mdc` as Cursor-only (out of the Claude path).
- Create `verbs.json`; point `validate-graph.py` and the generator validators at it; remove the inline word lists.
- Replace `update-functional-graph`'s inline rule block and delete `analyze-functional/references/guide.md` in favor of the shared core pointer.

**Phase 2 — extract the layered core (the heart):**
- Lift `core.md` + `human-overlay.md` + `system-overlay.md` from the metadata ruleset (most evolved).
- Shrink ui/backend/metadata `references/rules.md` to adapter tables only.
- Unify to one `upsert.schema.json` + one `validate.py` (`--kind human|system`); skills import them.
- Add the package-time assembly step.

**Phase 3 — rewire consumers (decisions first):**
- Resolve C1–C5.
- Refactor `analyze-design`'s functional fork into a pointer + design-only local rules.
- Reconcile `visual-to-text` Step semantics.
- Point `detect-personas`, `search`, `generate-spec` prose at the shared core.

---

## 5. Consequences

**Positive:** one place to change a rule; no Python/markdown divergence; the human/system split is explicit and matches reality; per-skill adapters stay small and source-focused; new source types (e.g. aspx, metadata) plug in by writing an adapter + reusing the shared core/validator.

**Negative / risks:** package-time assembly adds a build step; C1–C5 require judgement calls; the Python validator import path must be kept working; a botched extraction could regress the metadata generation (mitigate: the metadata ruleset is the model and is regression-checked against the live metadata-app project graph).

**Explicitly out of scope (stays per-skill, by design):** the source-extraction adapters (MAPL/JSX/route/SOAP). Unifying those would be the *nuisance* with no upside.

---

## 6. Alternatives considered

- **Big-bang single flat rulebook.** Rejected — C1/C2 are persona-conditional opposites; one flat file would over- or under-constrain a persona half.
- **Keep separate (status quo).** Rejected — drift is already live (three forbidden-word copies, a semantic Step conflict, a lossy design fork).
- **Runtime `Read` of a shared file.** Rejected as the *sole* mechanism — skills already "reference" shared rules and still drift because nothing forces the load. Package-time assembly is the enforcement.

---

## Appendix A — Canonical file map (authoritative repo)

- Canonical (today): `skills/shared/functional-graph-rules.md`
- Generator rich rules: `skills/generate-functional-from-{ui,backend,metadata}/{references/rules.md, schemas/upsert.schema.json, validators/validate.py}`
- Flow agents: `agents/{spa,aspnet-webforms,backend,metadata}-flow-structuring-agent.md`, `agents/{backend-entrypoint,metadata-application}-discovery-agent.md`
- Drift surfaces: `skills/update-functional-graph/SKILL.md`, `skills/analyze-design/references/functional-graph-rules.md`, `skills/analyze-functional/references/guide.md`, `skills/visual-to-text/references/guide.md`, `skills/validate-functional-graph/scripts/validate-graph.py`
- Cursor-only (not in Claude path): `rules/*.mdc`

## Appendix B — Hard gates vs advisory (to preserve through consolidation)

- **Hard (block upsert):** schema; `rule-a` (side-effect verb ⇒ apis[]); `persona` (kind/count); `citations` (`<repo>/` prefix); `field-coverage == 1.0`; `citation-completeness`.
- **Advisory (warn only):** `atomicity` (human half only; skipped for System); `coverage`/`api-urls` (where present).
- **Enforcement locus:** the **sub-agent's Phase 6 self-validate** is the real gate; the parent skills run no validators. The consolidated docs must not present `validate.py` as the orchestrator gate.
