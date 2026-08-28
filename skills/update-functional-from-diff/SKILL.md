---
name: update-functional-from-diff
description: >
  Incrementally update functional ontology (UI + backend) and design
  ontology (UI) from a git diff between two commit IDs. Use when:
  "update functional from diff", "sync graph with commits",
  "update functional from commits", "incremental functional update",
  "diff-based graph update", user provides two commit SHAs.
argument-hint: "<prev-commit-id> <current-commit-id>"
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per
`CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID,
or a natural-language project hint in the prompt → otherwise the `projectUuid`
in `.breeze.json`. A per-invocation override applies to that invocation only
and must NOT mutate `.breeze.json`. If no project resolves, list accessible
projects via `Call_List_Project_` and ask the user to pick (or run
`/breeze:project setup`). Announce the active project on the first response
line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also
covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

---

## Purpose

Takes two git commit IDs (previous and current), computes the diff, classifies
changed files as **frontend UI**, **backend**, or **irrelevant**, and
incrementally updates:

1. **Functional ontology from UI changes** — human-persona scenarios
   (Persona > Outcome > Scenario > Step > Action)
2. **Functional ontology from backend changes** — System / External System
   persona scenarios
3. **Design ontology from UI changes** — UserJourney > Flow > Page > Component

This avoids a full regeneration pass — only the parts of the graph affected
by the diff are created or updated.

---

## Inputs

Two commit IDs are **required**. Extract from `$ARGUMENTS`:

```
/breeze:update-ontology-from-diff <prev-commit-id> <current-commit-id>
```

- `prev-commit-id` — the baseline commit (older)
- `current-commit-id` — the target commit (newer). Accepts `HEAD` as alias.

If either is missing, ask the user. Validate both are valid commit SHAs by
running `git rev-parse --verify <id>` for each.

**Optional flags:**
- `--functional-only` — skip design ontology update
- `--design-only` — skip functional ontology update
- `--ui-only` — process only frontend changes
- `--backend-only` — process only backend changes

---

## Execution Flow

### Phase 0 — Bootstrap

1. Resolve `projectUuid` per `CLAUDE.md`.
2. Call `Call_Get_Project_Details_` — cache project name; load
   `metadata.projectContext` into active context.
3. Resolve `apiBase` and `uiBaseUrl` from `breeze.config.json`
   (with `.breeze.json` overrides).
4. Parse `$ARGUMENTS` to extract `<prev-commit-id>` and
   `<current-commit-id>`. Validate both with `git rev-parse --verify`.

### Phase 1 — Compute Diff & Classify Files

1. Run `git diff --name-status <prev-commit-id> <current-commit-id>` to get
   the list of changed files with their status (Added/Modified/Deleted/Renamed).

2. **Exclude irrelevant files** — skip files matching these patterns:
   - `*.md`, `*.txt`, `*.json` (config), `*.yml`, `*.yaml` (CI/CD),
     `*.lock`, `*.log`
   - `node_modules/`, `dist/`, `build/`, `.git/`, `.vscode/`,
     `.idea/`, `__pycache__/`
   - `*.test.*`, `*.spec.*`, `*_test.*`, `*_spec.*` (test files)
   - `*.css`, `*.scss`, `*.less`, `*.svg`, `*.png`, `*.jpg`
     (pure style/assets — unless component co-located)
   - `.env*`, `Dockerfile`, `docker-compose*`, `Makefile`

3. **Classify remaining files** into categories:

   | Signal | Classification |
   |---|---|
   | Path contains `src/pages/`, `src/views/`, `src/components/`, `src/app/`, `pages/`, `views/`, `components/`, or framework view extensions (`.tsx`, `.jsx`, `.vue`, `.svelte`, `.cshtml`, `.aspx`, `.html` with component logic) | **Frontend UI** |
   | Path contains `controllers/`, `resolvers/`, `services/`, `routes/`, `handlers/`, `consumers/`, `processors/`, `jobs/`, `middleware/`, or backend extensions (`.controller.ts`, `.service.ts`, `.resolver.ts`, `Controller.cs`, `Controller.java`, `views.py`, `routes.py`) | **Backend** |
   | Files that could be both (e.g., shared types, utils) | Classify by **directory context** — if under a frontend project root, treat as UI; if under a backend project root, treat as Backend |
   | Pure config, CI, docs, assets | **Irrelevant** — skip |

4. **Detect repo type** — if `.breeze.json` has `targetRepos.frontend` and/or
   `targetRepos.backend`, use those paths to anchor classification. If only
   one repo type is present, classify all source files accordingly.

5. Present the classification to the user:

   ```
   Diff: <prev-commit-id>..<current-commit-id>
   Total files changed: N
   
   Frontend UI files (N):
     M  src/pages/Dashboard/index.tsx
     A  src/components/NewWidget.tsx
     ...
   
   Backend files (N):
     M  src/controllers/OrderController.ts
     D  src/services/LegacyService.ts
     ...
   
   Skipped (N): [config, tests, assets...]
   
   Planned updates:
     - Functional graph (UI): Yes/No
     - Functional graph (Backend): Yes/No
     - Design graph (UI): Yes/No
   ```

   **Wait for user confirmation before proceeding.**

### Phase 2 — Load Existing Graph Context

For each classification that has files:

1. Call `Get_all_personas` — cache all existing personas.
2. For each persona, call `Get_all_outcomes_for_a_persona_id` — cache
   the outcome inventory.
3. Call `Functional_Graph_Search` with key terms derived from changed
   file names and paths — find nearest existing scenarios.

For design graph updates, additionally:
4. Call `Design_Graph_Search` with key terms from changed UI files —
   find existing UserJourneys, Flows, Pages, Components.

### Phase 3 — Analyze Changes (per file)

For each changed file (grouped by classification):

1. **Read the current file content** (`git show <current-commit-id>:<file>`
   for the new version).
2. **Read the diff hunks** (`git diff <prev-commit-id> <current-commit-id>
   -- <file>`) to understand what specifically changed.
3. **Determine the functional impact** — classify each change as:
   - **New functionality** — new routes, new components, new handlers,
     new user flows → requires new graph nodes
   - **Modified functionality** — changed business logic, updated
     validation, altered user flow → requires updating existing nodes
   - **Removed functionality** — deleted routes, removed components,
     removed handlers → flag for user review (do NOT auto-delete
     graph nodes)
   - **No functional impact** — refactoring, renaming without behavior
     change, code formatting → skip (report as NO-OP)

### Phase 4 — Update Functional Graph (UI)

*Skip if `--backend-only` or no frontend files changed.*

Process frontend UI files following `update-functional-graph` rules and
`../shared/functional/core.md` + `../shared/functional/human-overlay.md`:

#### 4a. Resolve Personas (REUSE FIRST)

- Match to existing human personas from Phase 2 cache.
- Apply persona resolution rules from `update-functional-graph/SKILL.md`:
  named human role > generic human role. Never create System personas
  from UI code.
- Forbidden persona names: Developer, Engineer, API, Service, etc.

#### 4b. Map Changes to Outcomes & Scenarios

For each changed UI file:

- **New component/page** → Check if it belongs under an existing Outcome.
  If yes, create a new Scenario under it. If no existing Outcome fits,
  create a new Outcome.
- **Modified component/page** → Find the existing Scenario(s) that
  cover this component via `Functional_Graph_Search`. Update Steps
  and Actions to reflect the diff.
- **Deleted component/page** → Report to user; do NOT delete graph
  nodes automatically. Suggest manual cleanup if confirmed.

#### 4c. Build Node Hierarchy

For new or modified functionality, build:

```
Persona (REUSE existing)
  └── Outcome (REUSE if possible, CREATE if genuinely new capability)
       └── Scenario (REUSE if same flow, CREATE if new flow)
            └── Step (sequential stages)
                 └── Action (platform-agnostic intent verbs)
```

**Action rules (human persona):**
- Use intent verbs: Provide, Choose, Confirm, Review, Dismiss, Open,
  Close, Submit, Cancel, Specify, Indicate, Acknowledge, Request
- FORBIDDEN: click, tap, button, dropdown, modal, dialog, checkbox,
  radio, slider, tooltip, menu, sidebar, navbar, tab, icon
- `description` = null unless a constraint exists

#### 4d. Present Plan & Create Nodes

Present the proposed changes in this format:

```
[REUSE] Persona: <name> (ID: <id>)
  [REUSE] Outcome: <name> (ID: <id>)
    [CREATE] Scenario: <name>
      [CREATE] Step 1: <name>
        [CREATE] Action: <specific interaction>
  [UPDATE] Outcome: <name> (ID: <id>)
    [UPDATE] Scenario: <name> (ID: <id>)
      [CREATE] Step 3: <new step from diff>
        [CREATE] Action: <new interaction>
```

**Wait for user approval**, then create/update nodes using
`Call_Create_Functional_Node_` (top-down: Persona → Outcome → Scenario →
Step → Action) and `Call_Update_Functional_Node_` for existing nodes.

**Citations:** Use `citationIds: [0]` and
`citations: [{ type: "document", name: "skip", inputText: "skip" }]`
on every create/update call.

### Phase 5 — Update Functional Graph (Backend)

*Skip if `--ui-only` or no backend files changed.*

Process backend files following `update-functional-graph` rules and
`../shared/functional/core.md` + `../shared/functional/system-overlay.md`:

#### 5a. Resolve Personas (mechanical mapping)

| Change type | Persona |
|---|---|
| REST controller / GraphQL resolver / internal route | `System` |
| Webhook receiver / partner callback / 3rd-party queue | `External System` |
| Queue consumer / cron / scheduled job | `System` |

Never create human personas from backend code.

#### 5b. Map Changes to Outcomes & Scenarios

For each changed backend file:

- **New controller/handler** → Create new Outcome (if no existing
  Outcome covers the capability) and Scenario.
- **Modified controller/handler** → Find existing Scenario via
  `Functional_Graph_Search`. Update Steps and Actions to reflect
  changed business logic.
- **Deleted controller/handler** → Report to user; do NOT auto-delete.

#### 5c. Build Node Hierarchy

```
Persona (System or External System — REUSE existing)
  └── Outcome (business capability — REUSE if possible)
       └── Scenario (specific processing flow)
            └── Step (processing phases)
                 └── Action (atomic operations)
                      └── apis[] (if applicable)
```

**Action rules (System persona):**
- `description` REQUIRED on every action — formula, threshold,
  field names, condition, error message, data format, or I/O contract.
- Side-effect actions must include `apis[]` or data-store identifier.

#### 5d. Present Plan & Create Nodes

Same approval flow as Phase 4d. Present proposed changes, wait for
user approval, then create/update via `Call_Create_Functional_Node_`
and `Call_Update_Functional_Node_`.

**Citations:** Use `citationIds: [0]` and
`citations: [{ type: "document", name: "skip", inputText: "skip" }]`.

### Phase 6 — Update Design Graph (UI)

*Skip if `--functional-only`, `--backend-only`, or no frontend files changed.*

Process frontend UI changes to update the design ontology, following
the design graph hierarchy:

```
UserJourney (1:1 with functional Scenario, linked via scenarioId)
  └── Flow (per modality, linked via userJourneyIds[], stepIds[])
       └── Page (linked via flowIds[], stepIds[])
            └── Component (TEMPLATE/ORGANISM/MOLECULE/ATOM,
                          linked via pageIds[], actionIds[])
```

#### 6a. Map Changes to Design Nodes

For each changed UI file:

- **New page/component** → Identify which functional Scenario it
  belongs to (from Phase 4 results or existing graph). Create
  corresponding UserJourney (if new scenario), Flow, Page, and
  Component nodes.
- **Modified page/component** → Find existing design nodes via
  `Design_Graph_Search`. Update component hierarchy if the diff
  introduces new sub-components, removes old ones, or changes
  the page structure.
- **Deleted page/component** → Report to user; do NOT auto-delete.

#### 6b. Classify Components (Atomic Design)

| Type | Description |
|---|---|
| TEMPLATE | One per page — the page-level layout shell |
| ORGANISM | Complex, self-contained UI sections (forms, tables, charts) |
| MOLECULE | Small groups of elements (search bar, card, list item) |
| ATOM | Indivisible elements (button, input, icon, label) |

#### 6c. Build Design Payload & Upsert

For each affected scenario, build the design payload and call
`Bulk_Update_Design_Nodes` — **one call per scenario**.

The payload follows the nested structure:
```json
{
  "projectUuid": "<uuid>",
  "data": {
    "userJourneys": [{
      "name": "...", "scenarioId": "...",
      "flows": [{
        "name": "...", "modality": "WEB",
        "userJourneyIds": [], "stepIds": [],
        "pages": [{
          "name": "...", "pageType": "LIST|DETAIL|FORM|DASHBOARD",
          "flowIds": [], "stepIds": [],
          "components": [{
            "name": "...", "type": "TEMPLATE|ORGANISM|MOLECULE|ATOM",
            "pageIds": [], "actionIds": []
          }]
        }]
      }]
    }]
  }
}
```

Backend deduplicates by `projectUuid + name` (case-insensitive).
Including a node by name reuses it and appends parent edges.

#### 6d. Mark Scenarios as Design-Generated

After successful upsert, call `Update_Functional_Node` on each
processed scenario with `isDesignGenerated: true`, using:
- `citationId: [0]`
- `citations: [{ type: "document", name: "skip", inputText: "skip" }]`

### Phase 7 — Summary

Present a final summary:

```
## Ontology Update Summary

Diff: <prev-commit-id>..<current-commit-id>
Project: <name> (<uuid>)

### Files Processed
| Category | Changed | Processed | Skipped (no impact) |
|----------|---------|-----------|---------------------|
| Frontend UI | N | N | N |
| Backend | N | N | N |

### Functional Graph Updates
| Level | Created | Updated | Flagged for Removal |
|-------|---------|---------|---------------------|
| Persona | N | N | N |
| Outcome | N | N | N |
| Scenario | N | N | N |
| Step | N | N | N |
| Action | N | N | N |

### Design Graph Updates
| Node Type | Created | Updated |
|-----------|---------|---------|
| UserJourney | N | N |
| Flow | N | N |
| Page | N | N |
| Component | N | N |

### Deleted Files (manual review needed)
- <file> — previously mapped to Scenario: <name> (ID: <id>)
```

---

## Functional Graph Principles

Refer to `../shared/functional-graph-rules.md` and
`../shared/functional/core.md` for the complete shared specification:

- Persona resolution rules (priority order, forbidden names)
- Outcome rules (reuse-first, business language)
- Scenario rules (testable, clear start/end)
- Step rules (sequential, no description needed)
- **Action rules (PERSONA-AWARE):**
  - Human personas: platform-agnostic, intent verbs only
  - System persona: description REQUIRED with business logic
  - External System: API/integration operations
- Context type handling (documents, code, Figma)
- Data model and MCP tools

---

## Design Graph Principles

Refer to `../generate-design-from-ui/references/design-ontology.md` for
the complete design graph entity model:

- UserJourney ↔ Scenario (1:1 link via scenarioId)
- Flow multiplied per modality
- Page types (LIST, DETAIL, FORM, DASHBOARD)
- Atomic design classification (TEMPLATE, ORGANISM, MOLECULE, ATOM)
- Multi-parent support via `*Ids[]` arrays

---

## NO-OP Rule

If the diff contains only:
- Refactoring with no behavior change (renames, extractions, formatting)
- Test file changes only
- Config/CI changes only
- Style-only changes (CSS/SCSS without component logic changes)
- Documentation changes

Report: **"No functional or design impact detected in this diff.
No graph updates needed."**

List the files examined and why each was classified as no-impact.

---

## Safety Rules

1. **Never auto-delete graph nodes** — even if a file is deleted in
   the diff, only flag for user review.
2. **Always present the plan** before creating/updating any nodes.
3. **Reuse existing nodes first** — create new nodes only when no
   existing node can logically contain the new functionality.
4. **One phase at a time** — complete functional UI updates before
   starting functional backend updates, then design updates.
5. **Deleted files** — always cross-reference against the graph to
   identify which scenarios/components may be orphaned. Present
   findings to the user.
6. **Never print API keys or AWS credentials.**
