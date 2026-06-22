# Functional Ontology — Single Source of Truth

This directory is the **one** rulebook for the functional graph
(`Persona → Outcome → Scenario → Step → Action → apis[]`) across every Breeze skill
and sub-agent that generates, validates, or consumes it. It implements **ADR 0001**
(`docs/adr/0001-consolidate-functional-ontology-rules.md`).

Before this existed, the rules were triplicated and drifting across three generator
`rules.md`, three `upsert.schema.json`, three `validate.py`, a separate Python graph
validator, and several lossy forks — with at least one outright semantic conflict
(`visual-to-text` redefining *Step*). This folder collapses all of that into a layered
core + two overlays + one schema + one validator + one word-list file.

## Files

| File | Role | Audience |
|---|---|---|
| `core.md` | Universal rules true for **every** persona and source: node model, reuse/dedup, the dual human↔system subtree link, `apis[]` join models, `rule-a`, enumeration discipline, citations (regex + placement), write protocol, validation locus. | every functional skill |
| `human-overlay.md` | Rules that apply **only** to human personas: persona derivation, platform-agnostic action language + forbidden UI words, per-field atomicity, UI coverage. | ui pass, p3 human half, visual-to-text, analyze/update |
| `system-overlay.md` | Rules that apply **only** to `System` / `External System`: mechanical EP→persona map, required descriptions, one-operation-one-action (atomicity exempt), apis-OR-identifier `rule-a`. | backend pass, p3 system half |
| `verbs.json` | The single source for **every** word list (forbidden UI words, network/side-effect/input verbs, system/forbidden persona names, identifier & widget patterns, api types, overlap keywords). | `validate.py` + every other validator |
| `upsert.schema.json` | The ONE upsert schema. Persona = free string; `apis[].type` = free string (matches the server contract). | every generator |
| `validate.py` | The ONE validator engine. `validate.py <check> [--kind human\|system]`, reads `{payload, audit}` from STDIN, returns `{ok, errors, warnings}`. | every flow sub-agent's self-validate phase |

## How a generator skill uses this

1. Its `references/rules.md` shrinks to the **source-extraction adapter only** — which files / record types / decorators to read, and how to map them into the normalized
   `audit.declaredFields[]` / `audit.filesRead[]` (+ the two halves). It then **defers** to `core.md` + the relevant overlay rather than re-stating rules.
2. Its `schemas/` and `validators/` become the shared ones here (import / symlink / build-time copy — see *Build-time assembly*).
3. The flow sub-agent's self-validate phase runs `validate.py` for each hard gate and POSTs only when they pass. **Parent skills run no validators** — they orchestrate.

## Hard gates vs advisory (preserve through any change)

- **Hard (block the upsert):** `schema`, `rule-a` (`--kind`), `forbidden` (human half), `persona` (`--kind`), `citations --repo-name`, `field-coverage == 1.0`, `citation-completeness`.
- **Advisory (warn only):** `atomicity` (human half; skips System), `coverage` (`--kind`), `api-urls`.

## Conflict resolutions baked in (ADR 0001 §3)

| # | Conflict | Resolution adopted here |
|---|---|---|
| **C1** | Persona enum (backend hard-enum vs UI free string; server enforces none) | **No enum in the schema.** Persona-kind is gated by `validate.py persona --kind`. Matches the server's `@IsString` contract. |
| **C2** | Action `description` default is opposite for human vs system | **Persona-conditional, kept in the two overlays.** `core.md` says nothing about a description default. Human → `null` by default; System → required. |
| **C3** | Citation level | **Cite LOW** — citations live on **action / step / scenario** (prefer the action; the backend's nested upsert DTOs accept citations at all 5 levels). **Never on outcome/persona** — shared/merged nodes, citing them pollutes; `validate.py citations` warns on it. `citation-completeness` is a union across all levels, so a low citation satisfies it. (Updated 2026-06-22: broadened from scenario-only down to step+action.) |
| **C4** | `visual-to-text` redefines *Step* as a configuration variation | **Canonical sequential-Step wins** (`core.md §1`). `visual-to-text` must be refactored to it; variation → sibling Scenarios. |
| **C5** | `apis[].type` free text vs enum; aspx Case-B has no URL | **`type` is free text** with a recommended set; `core.md §4` documents the per-stack join models, including aspx Case-B (no `apis[]`; name the store in the description via the system `rule-a` identifier fallback). |

## Build-time assembly (the mechanism that makes the SSOT hold)

Pointing a skill at shared rules in prose does **not** stop drift — skills already did that and re-inlined anyway. The SSOT only holds if `core + overlay` are **mechanically inlined into each skill's references at package/build time**, and if every validator (including
`skills/validate-functional-graph/scripts/validate-graph.py`) **imports `verbs.json`** instead of re-listing words. Wiring those two mechanisms is the remaining Phase-2/Phase-3 work in ADR 0001; this folder is their single upstream source.

## Migration status

**Wired and in use (production):**
- Layered core + overlays + unified `verbs.json` / `upsert.schema.json` / `validate.py` authored here and tested.
- The three generator `validators/validate.py` are now **thin shims** that delegate to this `validate.py` (backend injects `--kind system`, ui injects `--kind human`, p3 auto-detects per half). All existing agent Phase-6 invocations work unchanged; `--kind` is optional (auto-detected from the single persona) and the engine exits 3 (degrade) when `jsonschema` is absent.
- The three per-skill `schemas/upsert.schema.json` are **deleted** — the shimmed validator loads the one schema here; SKILL docs repointed.
- `skills/validate-functional-graph/scripts/validate-graph.py` now **imports `verbs.json`** (forbidden UI words, forbidden persona names, system personas, overlap keywords) with an inline fallback — the Python word-list fork is closed.
- The three generator `references/rules.md` are **shrunk to adapters** with a "read the SSOT first" banner; the duplicated node-model/action blocks are removed.
- **`visual-to-text/references/guide.md` refactored to canonical sequential-Step (C4)** — the variation-Step model and the `Action TRIGGERED_BY Component` edge are gone.
- The legacy `skills/shared/functional-graph-rules.md` and the `analyze-design` functional fork carry **redirect banners** ("`functional/` wins") and retain only their non-duplicated material (MCP per-node write data-model / design-graph mapping).

- **Subagent prompts now point here too.** The six `agents/*.md` no longer inline the node model / forbidden words / action rules — they carry a "**Read `SHARED_FUNCTIONAL_PATH/core.md` + the relevant overlay FIRST**" instruction plus only their adapter-specific examples. The path arrives as an input: `VALIDATORS_PATH/../../shared/functional` for backend/p3, and a new `{{shared_functional_path}}` placeholder injected by the UI prompt renderer for spa/aspx. The discovery agents' EP→persona table is annotated as mirroring `system-overlay.md §1` (kept inline because discovery routes EPs before any payload/validator exists). The forbidden-word list now lives in exactly one place — `verbs.json` (+ a documented inline fallback in `validate-graph.py`).

**Remaining (hardening, not blocking):**
- **Build-time assembly** — the pointer approach relies on the agent actually `Read`ing the shared files at runtime. The shared **validator** is the enforcement backstop (hard gates fire regardless of which prose the agent loaded), but inlining `core + overlay` into each prompt at package time would remove the runtime-read dependency entirely. Optional future hardening.
- Reconcile the `Get_all_steps_actions_for_a_scenario_id` parameter-name discrepancy (`parameters0_Value` in `analyze-design` vs `scenarioId` elsewhere).
- `rules/*.mdc` are **Cursor-only** and out of the Claude path — not a consumer of this SSOT.
