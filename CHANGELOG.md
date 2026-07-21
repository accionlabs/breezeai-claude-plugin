# Changelog

All notable changes to the Breeze AI Claude plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Bump the version in **both** `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`, and add an entry here, in the same commit.

## [Unreleased]

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
