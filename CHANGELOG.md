# Changelog

All notable changes to the Breeze AI Claude plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Bump the version in **both** `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`, and add an entry here, in the same commit.

## [Unreleased]

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
