# Changelog

All notable changes to the Breeze AI Claude plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Bump the version in **both** `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`, and add an entry here, in the same commit.

## [Unreleased]

## [3.9.0] — 2026-07-29

Metadata pass: three silent-failure modes found while regenerating a ~100-repo Vert.x/MAPL tree.
Each produced a *clean-looking* run that had quietly skipped real content. All changes are confined
to `generate-functional-from-metadata` and its two agents; `skills/shared/functional/` is untouched.

### Fixed
- **`MAPLD03` is not a role code.** `references/rules.md` documented it as the persona seed. It
  actually holds the entry/control handler name (`StartControl`, `SS01`, `DF01`, `WD01`), and the
  same value recurs across apps owned by different business roles. The discovery agent could not map
  it, fell back to inferring the persona from repo name and title — reasonable — but stamped the
  result `confidence: "mapped"`. Because the confirmation gate keys off non-`mapped`, `humanRawRole`
  came back **0** and **every persona shipped unreviewed** on a 326-app run. `"mapped"` now means
  *"read from an authoritative role source"* only; inference is `"inferred"` and carries its
  evidence, so the gate actually fires.
- **`field-coverage` could pass vacuously at 0/0.** Enumeration read `MFID`/`MFLT`/`CRUD` only, so
  modules declaring labels solely in **`MCAP`** (custom-HTML screens with no `MFID`) produced an
  empty `declaredFields[]` and the 100%-capture "hard gate" succeeded having checked nothing.
  `MCAP` is now a field source, and an app with screens but zero declared fields must be reported
  rather than accepted. *(The soft-pass in shared `validate.py` is correct generically and was
  deliberately left alone — the fix is to populate its input.)*
- **`GoApplication` was unmapped and silently dropped.** A high-frequency verb — in the reference
  tree it outnumbered `ShowScreen` — with no row in the verb table, so every cross-application
  hand-off was lost and each application became an island.

- **Entry points were derived from `MAPL` alone, which is incomplete.** Modules register EventBus
  addresses the browser calls directly that no `MAPLQ` step declares — `<module>/validation`,
  `<module>/resources`, `pippen/*/formal`. Verified end-to-end in a real module: `main.js` calls
  `/services/validate/<module>/validation`, which runs `D1Validator` ("numeric, exactly 8 digits,
  valid calendar date, else MSG70001"), and **none of it reached the graph**. Discovery now
  reconciles declared (MAPL) against exposed (code) and called (JS), and records the difference in
  `undeclaredEntryPoints[]` for the per-app agent to model. For a financial app this was a
  correctness defect, not a depth preference.
- **Reading stopped at the MAPL targets.** Those handlers are the spine; the rules live one
  reference hop further. Measured on a real module: **11 of 65 app-package classes read (17%)**,
  with every validator, service and component class missed — even though `Validation.java`, which
  *was* read, imports them by name. Phase 1 now follows same-repo `app/**` imports to depth 2.
- **Screen templates were never read** — 38 HTML templates per repo, 0 opened. `MSCR`/`MFID`/`MCAP`
  give codes and labels; only the template shows which fields render, in what widget, and whether
  they are editable.
- **Shared `submodules/` was neither read nor excluded.** It is copied verbatim into 60+ repos
  (identical bytes), so per-app reading is 60× waste — but it is not behaviour-free:
  `CustomFormal_BTN_Verify_base` hides the approve/reject pair for roles `040`/`060`, the only role
  branch in the entire application layer, and every per-app run missed it. Now analysed **once** by
  the parent into `shared-framework-brief.md` and injected into every agent.

### Added
- `GoApplication` verb mapping: a terminal `Continue to <capability>` action, `@param` targets
  resolved via the newly documented `MAPLP`, unresolved targets marked rather than invented, and
  every hand-off recorded in `audit.appTransitions[]`.
- **Journey map** artifact (`.breeze-metadata-output/journey-map.md`) aggregating those transitions.
  The upsert schema is a strict tree with no lateral-edge field, so multi-application journeys
  cannot be graph edges — this is where they become visible.
- New record types in `references/rules.md`: **`MCAP`** (screen captions / labels), **`PNTC`**
  (notification & mail templates), **`WWZA`/`WWSC`/`WWSS`** (the Wizard definition trio).
- New MAPL internals documented: **`MAPLP`** (declared parameter names — resolves `@endAppId` /
  `@backAppId`), **`MAPLR`** (button→route table), **`MAPLS`** (step-transition chain). These are the
  app's branch structure; branches are to be emitted as distinct Scenarios, never flattened.
- Discovery now records `declaredParams[]`, `hasRouting`, `appTransitions[]`, `goApplicationCount`,
  `undeclaredEntryPoints[]` and a tree-level `sharedFramework` note, and reports
  `personaMapped` / `personaInferred` / `personaRaw` / `transitions` / `undeclaredEPs` in its summary.
- **Phase 0b shared-framework pass** in the skill — one analysis of `submodules/` for the whole tree,
  written to `shared-framework-brief.md` and injected into every per-app prompt.
- Per-app agent gains `UNDECLARED_ENTRY_POINTS` and `SHARED_FRAMEWORK_BRIEF` inputs, an
  `audit.validatorsRead[]` record, and a self-check that warns when an app has editable fields but
  captured **zero** validation rules (no hard gate can catch that — the existing
  `citation-completeness` check only verifies *read ⇒ cited*, never *read enough*).
- Field enumeration now attaches the **rule** to each editable field, not just the label —
  `Enter the change date — 8 digits, must be a valid calendar date (MSG70001)`.
- Both agents list their Breeze MCP tools under **both** the `mcp__plugin_breeze_breeze-mcp__` and
  `mcp__breeze-mcp-pat__` prefixes. Interim compatibility measure: where the configured server name
  differs from the plugin's expectation the tools silently resolve to nothing, and the agents then
  run blind — no live-graph read-back, so Outcome dedup degrades to naming by convention and the
  Human↔System join (which is *by Outcome name*) drifts. Prefer aligning the MCP server name and
  dropping the duplicate list.

### Added — from a 40-app production run
- **Browser-call reconciliation self-check** (Phase 6). Diff every `url:` in the repo's JS against
  every `apis[].url` in the payloads; an unexplained difference is a defect. Caught a real miss: an
  app called `/services/custom/searchAddress` twice from `js/main.js` — the postal-code lookup that
  autofills the address — and the graph had no action and no api for it, while a sibling app
  captured the same endpoint correctly. Mechanically checkable, so it should never be eyeballed.
- **Temp-file hygiene rule** (Phase 7). Under parallel batches agents share one scratchpad; a
  generic `build_payload.py` was silently overwritten mid-run by a sibling. Every helper script and
  temp file must be suffixed with `APP_ID`.
- **Caption-code citation rule** (`rules.md` Phase 2). Actions must name the `MCAP`/`MFID` code they
  cover, not only the translated English label. Without it the content is correct but untraceable —
  on one measured app this was the difference between an apparent 46% and an actual ~94% field
  coverage when an auditor re-derived the declared set from source.

Second batch, found by auditing generated output against **screenshots of the running application**
rather than against the metadata alone:

- **Persona was inferred per repository, not per application.** A repo is not a persona boundary. In
  the reference tree `pippen-navigate` holds ten apps: eight are HR target-pickers, but `CEPAY0556`
  / `CEPAY0557` are the *employee's* own self-service screens — confirmed by screenshots of an
  employee session. All ten were stamped `HR Administrator`, which would have filed every employee
  journey's entry point under the wrong actor and broken the Human↔System Outcome join for those
  apps. Discovery now weights `MAPLD01` above the repo name, and emits `mixedPersonaRepos[]` for the
  parent to surface at the gate. An empty list on a tree of multi-app repos is now itself a warning.
- **Caption codes are scoped per screen (`MCAPAK4`), not per application.** Codes restart at
  `0000001` on every screen, so one app-wide code→text dictionary yields confident, wrong labels:
  `$CAP0000001$` is *"1. First items to enter"* on screen `S8VY` but *"The specified application has
  a separately saved application"* on `S8VZ`, and `holdingUser.html` uses the code from the latter.
  Templates must now be resolved against their own owning screen.
- **Captions injected from Java were invisible to a template-only sweep.** Handlers put captions
  into the template engine at runtime (`ctx.getCaptions().get("CAP…")`). On CEPAY0557 a template
  sweep resolves 45 of 54 declared codes and drops `CAP0000034` — a *visible* guide-card title —
  along with an error string. The Java sweep for `CAP\d{7}` is now required alongside the template
  sweep.
- **UI assembled from a remote call was not declared as a boundary.** `$$kitHtml$$` /
  `$$approvalHtml$$` are filled from `pippen/kit/formal` and `pippen/approver/formal`, whose services
  exist in no repo of the set; the same two calls are made by `CustomFormal_FormBase`, so every form
  embeds them. The calls were already captured in `apis[]`, but nothing said the region's *fields*
  are unreachable — so reported field coverage read as if it included the approver block.

### Changed
- Persona confirmation gate presents the **full** persona list with app counts and confidence, not
  only `raw` entries, and hard-stops when a tree with no role master reports zero inferred/raw
  personas — that combination means the confidences are wrong, not that the run is clean.
- **Atomicity warnings are now must-fix at the agent**, though the validator stays advisory (the
  shared engine is untouched). The previous "use judgement… not mandatory" wording let two apps in
  one run model the same three-input name row differently — `CEPAY0625` split last/first/middle,
  `CEPAY0607` bundled them into one action. N separate editable inputs now means N actions; the only
  exemptions are read-only content folded into a `Review …` description, and System personas.
- **Tenant-configured field slots are named as such, not as "optional".** Screens render blocks whose
  labels exist nowhere in the repo (customer configuration — often untranslated, sometimes naming a
  specific company) and which are frequently `Required`. Calling them *optional* misrepresents them;
  they are now `tenant-configured` typed slots whose description states the labels come from customer
  configuration.

**Not changed, deliberately:** the `field-coverage` gate. An independent caption-based audit put two
apps at 46–47%, but checking against the rendered screens showed every visible field was captured —
the caption denominator (which mixes unrendered tenant slots and error strings) was the flawed
measure, not the gate.
- The Outcome-only reconciliation rule now states explicitly that it **narrows** shared `core.md`
  §2.4 for metadata trees, and why (one app per sub-agent ⇒ near-duplicate scenarios are usually
  genuine distinct coverage from different applications).

## [3.8.0] — 2026-07-21

### Added
- `generate-architecture`: **DataLake schema ingestion** — the skill now populates the schema layer beneath a DataLake (`DDLTable → DDLColumn`, `DDLConstraint`, `DDLIndex`, `DDLView`, `DDLProcedure`, `DDLSequence`, and `ESIndex → ESField` / `ESAlias`). Previously it stopped at `DataLake` as a leaf and had no DDL/ES path at all. New reference `references/db-schema-ingestion.md` documents the write-path decision, preprocessing, batching, and verification.
- `generate-architecture`: **multi-source input** — auto-detects and composes code, Terraform/IaC, `.sql` / ES mappings, spec docs, diagrams, and Confluence URLs. A repo containing `terraform/` and `db/*.sql` now runs all three passes with no flags. Previously the skill required a spec document and told users with only a codebase to go elsewhere. New reference `references/source-discovery.md` covers per-source extraction, the precedence table, and **per-layer probes** so a layer is never silently reported empty.
- `generate-architecture`: new flags `--sql <path>` (force a schema pass) and `--no-schema` (topology only).
- `references/architecture-ontology.md`: attribute-level definitions for all DDL/ES node types, the containment model with edge names, and the attribute traps (`dataType` decomposition, `parameters` array-in/JSON-string-out, `indexType` losing clustered/nonclustered).

### Fixed
- `generate-architecture` Bootstrap: previously asserted **"No API key is needed"**. That is false for schema ingest, which is REST (`/db-ontology/stream-ingest`) and requires `apiKey`. The key is now resolved **lazily** — prompted only when a schema pass will actually run, so topology-only runs still need no credential.

### Changed
- `generate-architecture`: added an **accuracy rules** section covering the failure modes that produce wrong graphs — verify before asserting, *empty must be proven* (with evidence shown in the gate), never silently overwrite across sources, a `202` parse receipt is not an ingest, and partial ingests leave derived fields (`columnCount`, `hasPrimaryKey`) permanently wrong until a full re-run.
- `generate-architecture` confirmation gate now also renders the schema summary, layers proven empty with their evidence, and cross-source divergences for arbitration.
- `db-schema-ingestion.md` §3 is written **dialect-neutrally** (test one file first; guard idioms tabulated for T-SQL / PostgreSQL / Oracle / MySQL) rather than as a T-SQL-only recipe, with an explicit requirement that the transforms be byte-identical no-ops on already-clean DDL.

### Notes for implementers
Two hazards are documented in `db-schema-ingestion.md` because both are silent and costly:
- **Never loop `Create_DB_Schema_Column`.** Each per-object column write triggers a server-side `refreshTable` that re-embeds the table *and every column already attached* — O(n²). Measured: 3,029 columns ⇒ ~32,563 embedding operations (10.8×), which stalls the ingest.
- **Foreign-key `REFERENCES` edges can only be created by the bulk path.** The per-object constraint endpoint accepts no target-table input, so an MCP-built schema yields tables with zero relationships.

## [3.7.3] — 2026-07-18

### Fixed
- `generate-functional-from-aspnet-webforms` §0.5: the review gate was being **skipped in practice** — the model collapsed the 0.4 scope gate and 0.5 EP-list gate into a single bare confirmation question and entered Phase 1 without ever rendering the (EP × persona) table. Hardened the gate with an explicit non-collapsible ordering (render the full table + "won't get a run" breakdown in-message *first*, then ask), a rule that naming a count inside a confirmation prompt does not satisfy the gate, an explicit "0.4 and 0.5 are distinct — never merge" instruction, and a `reviewGate.planRendered` guard the loop checks before spawning the first Phase-1 agent.

## [3.7.2] — 2026-07-18

### Added
- `generate-functional-from-aspnet-webforms`: **§0.5 UI entry-point review & exclusion gate** — a mandatory hard gate between the scope gate (0.4) and the per-EP loop that renders the concrete (EP × persona) work plan for approval, summarizes the buckets that will *not* get their own run (folded controls, orphans, Phase-2 non-UI EPs), and lets the user exclude rows/EPs/categories before generation. Brings the Web Forms pass to parity with `-from-ui` (§0.9) and `-from-backend` (§0.4), which already presented an entry-point list for approval. Previously the Web Forms skill fell straight from the persona gate into generation with no summary of what would be walked.

## [3.7.1]

### Changed
- `project` skill: reduced default project-list size to the latest 10 (`Call_List_Project_(page=1, limit=10)`), with `list all` / `list <N>` / `list page <N>` opt-ins — an unbounded list was noise in workspaces holding thousands of per-ticket scratch projects.
- Functional-generation skills: all generated artifacts (`entrypoints.json`, per-EP payloads) now live under a single `<repo>/.breeze-output/` folder instead of polluting the target repo root; `.breeze-output/` is auto-added to the target repo's `.gitignore`.

## [3.7.0] — feat(skill): improved functional extraction

### Changed
- Per-call seam classification (A1 in-process vs A2 SOAP/WCF wire) decided per call from disk, never from `[ServiceContract]` attributes; added `InProcess` apis[] type to the upsert schema.
- Agent-side persona-scoped dedup (removed parent-side `EXISTING_NEIGHBORHOOD` pre-query); mandatory Outcome-level reconciliation pass after fan-out.

## [3.6.1] — improved functional extraction skills

## [3.6.0] — asp.net webform/razor support

### Added
- `generate-functional-from-aspnet-webforms` skill (unified UI + in-process backend pass for Web Forms monoliths) and the `aspnet-webforms-flow-structuring-agent`.
- `aspnet-razor-flow-structuring-agent` for MVC / Razor Pages (human half), joined to the backend pass by action-route URL.
- Documentation for the new code-ontology (cog) parser.

## [3.5.1] — feat(impact-analysis): statement-level analysis

## [3.5.0] — feat(functional): improved rules parity

## [3.4.0] — feat(improvements): consolidated rules

## [3.3.0] — .NET support for functional extraction

## [3.2.1] — feat(v2): upsert v2

### Changed
- Functional-graph writes moved to the `/functional-graph/v2/upsert` REST endpoint (direct POST with api-key header, avoids MCP argument-size clipping).

## [3.2.0] — feat(enhancements): enhanced skill flows

## [3.1.1] — feat(impact-analysis-v2)

## [3.1.0] — feat(api-key): local api-key effect

_Earlier 3.0.x releases predate this changelog; see `git log -- .claude-plugin/plugin.json` for the full version history._
