---
name: update-design-from-diff
description: >
  Incrementally update the design ontology (UserJourney, Flow, Page,
  Component) from a git diff between two commit IDs. Scopes work to
  only the UI files that changed — no full regeneration. Use when:
  "update design from diff", "sync design graph with commits",
  "incremental design update", "design graph from commits",
  user provides two commit SHAs and wants design-only updates.
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

Takes two git commit IDs (previous and current), computes the diff,
identifies changed **frontend UI files**, and incrementally updates the
design graph:

```
UserJourney (1:1 with functional Scenario)
  └── Flow (distinct path per modality)
       └── Page (screens in the flow)
            └── Component (TEMPLATE / ORGANISM / MOLECULE / ATOM)
```

Only the design nodes affected by the diff are created, updated, or
flagged — no full codebase scan.

---

## Inputs

Two commit IDs are **required**. Extract from `$ARGUMENTS`:

```
/breeze:update-design-from-diff <prev-commit-id> <current-commit-id>
```

- `prev-commit-id` — the baseline commit (older)
- `current-commit-id` — the target commit (newer). Accepts `HEAD`.

If either is missing, ask the user. Validate both with
`git rev-parse --verify <id>`.

**Optional flags:**
- `--modality <WEB|MOBILE|DESKTOP>` — override detected modality
  (default: `WEB`)
- `--dry-run` — analyze and present plan but do not write to graph

---

## Execution Flow

### Phase 0 — Bootstrap

1. Resolve `projectUuid` per `CLAUDE.md`.
2. Call `Call_Get_Project_Details_` — cache project name; load
   `metadata.projectContext` into active context.
3. Parse `$ARGUMENTS` to extract the two commit IDs. Validate with
   `git rev-parse --verify`.
4. Resolve UI repo path from `$ARGUMENTS`, `.breeze.json` →
   `targetRepos.frontend`, or cwd.
5. Detect framework (React / Vue / Angular / Next / Svelte) from
   `package.json`, `angular.json`, or similar signals.

### Phase 1 — Compute Diff & Filter UI Files

1. Run `git diff --name-status <prev-commit-id> <current-commit-id>`
   to get changed files with status (A/M/D/R).

2. **Keep only frontend UI files** — files matching:
   - Path contains `src/pages/`, `src/views/`, `src/components/`,
     `src/app/`, `pages/`, `views/`, `components/`, `src/features/`
   - Extensions: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.component.ts`,
     `.component.html`, `.cshtml`
   - Exclude: `*.test.*`, `*.spec.*`, `*.stories.*`, `*.mock.*`
   - Exclude: `*.css`, `*.scss`, `*.less`, `*.module.css` (pure style)
   - Exclude: `*.d.ts`, `*.types.ts` (pure type defs)
   - Exclude: `node_modules/`, `dist/`, `build/`, `.storybook/`

3. **Classify each file by change type:**

   | Status | Meaning | Design Impact |
   |--------|---------|---------------|
   | `A` | Added | New pages/components → new design nodes |
   | `M` | Modified | Changed UI structure → update existing nodes |
   | `D` | Deleted | Removed pages/components → flag for review |
   | `R` | Renamed | Node name update → flag for review |

4. **Group files by page/feature directory** — files in the same
   page directory are processed together (e.g., all files under
   `src/pages/Dashboard/` form one unit).

5. Present the filtered file list to the user:

   ```
   Diff: <prev>..<current>
   Framework: React (detected)
   Modality: WEB

   UI files changed (N):
     A  src/pages/NewFeature/index.tsx
     A  src/pages/NewFeature/components/Widget.tsx
     M  src/pages/Dashboard/index.tsx
     M  src/components/shared/DataTable.tsx
     D  src/pages/OldPage/index.tsx

   Grouped by page/feature:
     1. NewFeature (2 files — new page)
     2. Dashboard (1 file — modified)
     3. shared/DataTable (1 file — shared component modified)
     4. OldPage (1 file — deleted)

   Skipped (N): [tests, styles, types...]
   ```

   **Wait for user confirmation before proceeding.**

### Phase 2 — Load Existing Graph Context

#### 2a. Load Functional Graph (read-only — for linkage)

The design graph links to the functional graph. Load the relevant
functional context:

1. Call `Get_all_personas` — cache all personas.
2. For each **human persona** (skip System / External System), call
   `Get_all_outcomes_for_a_persona_id` — cache outcomes.
3. For outcomes related to changed files (match by name/route), call
   `Get_all_scenarios_for_a_outcome_id` — cache scenarios.
4. For each relevant scenario, call
   `Get_all_steps_actions_for_a_scenario_id` — cache steps and
   actions with their UUIDs for `stepIds[]` / `actionIds[]` wiring.

> **HARD GATE:** If no human personas exist, STOP and tell the user
> to run `/breeze:generate-functional-from-ui` first. Design graph
> requires functional graph as a prerequisite.

#### 2b. Load Existing Design Graph

1. Call `Design_Graph_Search` with key terms from changed file names
   and routes — find existing UserJourneys, Flows, Pages, Components.
2. Load existing registries if present:
   - `existingcomponents.json` — component registry
   - `existingflows.json` — flow registry
   - `existingpages.json` — page registry

### Phase 3 — Analyze Changes Per File Group

For each page/feature group from Phase 1:

#### 3a. Read Current File Content

For each file in the group:
- If status `A` or `M`: read via `git show <current-commit-id>:<file>`
- If status `D`: note as deleted (do not read)
- If status `R`: read the new path

#### 3b. Read Diff Hunks

Run `git diff <prev-commit-id> <current-commit-id> -- <file>` to
understand what specifically changed.

#### 3c. Classify Functional Impact

| Change | Classification | Design Action |
|--------|---------------|---------------|
| New page component added | New page | Create UserJourney + Flow + Page + Components |
| New component added to existing page | New component | Add Component to existing Page |
| Component JSX structure changed | Modified component | Update Component hierarchy |
| Component removed from page | Removed component | Flag for review |
| Page deleted | Removed page | Flag for review |
| Refactor / rename without behavior change | No impact | Skip (NO-OP) |
| Style-only changes | No impact | Skip (NO-OP) |
| Props/types changed without UI structure change | No impact | Skip (NO-OP) |

#### 3d. Flow Discovery (for new/modified pages)

For pages that are new or have significant structural changes, run
flow discovery greps per `../generate-design-from-ui/references/flow-discovery-patterns.md`:

**Type A — Entry-point flows (who navigates TO this page?):**

```bash
# React
grep -rn "navigate\(.*<route>\|push\(.*<route>" --include="*.tsx" --include="*.jsx"
grep -rn "<Link.*to=.*<route>" --include="*.tsx" --include="*.jsx"

# Angular
grep -rn "routerLink=.*<route>\|\[routerLink\].*<route>" --include="*.html" --include="*.ts"
grep -rn "router\.navigate\(.*<route>" --include="*.ts"

# Vue
grep -rn "router\.push\(.*<route>\|<router-link.*to=.*<route>" --include="*.vue" --include="*.ts"
```

**Type B — On-page branching (conditional rendering):**

```bash
# Ternaries / conditionals
grep -rn "?\s*<\|:\s*<" src/pages/<PageDir>/ --include="*.tsx"

# Tabs / steppers
grep -rn "<Tab\|<Tabs\|<Stepper\|activeStep\|activeTab" src/pages/<PageDir>/

# Auth switches, feature flags, mode toggles
grep -rn "authMethod\|viewMode\|editMode\|isAdvanced\|featureFlag" src/pages/<PageDir>/
```

**Type B — Angular-specific:**

```bash
# Structural directives
grep -rn "\*ngIf=\|@if\s*(\|@switch\s*(" --include="*.html" --include="*.ts"

# Material dialogs / bottom sheets
grep -rn "MatDialog\|this\.dialog\.open\|MatBottomSheet" --include="*.ts"

# Tab groups
grep -rn "<mat-tab-group\|<mat-tab\b\|<mat-stepper" --include="*.html"
```

**Page-nav greps (multi-page detection):**

```bash
grep -rn "navigate\|<Link\|router\.push\|routerLink" src/pages/<PageDir>/ --include="*.tsx" --include="*.ts" --include="*.html"
```

**Flow classification rules:**

| Pattern | Separate Flow? |
|---------|---------------|
| Different source pages with different preceding steps | YES |
| Same source, different trigger (button vs link) | NO |
| Ternary with different component trees | YES |
| Tab group with distinct workflows | YES |
| Show/hide optional fields | NO |
| Loading/error states | NO |
| Permission gates | NO |
| Responsive layout switches | NO — handled by modality |
| Auth method switch (email vs social) | YES |
| Feature flag / A-B test | YES |

Produce a **Flow Discovery Evidence Block** for each new/significantly-modified page:

```
┌─── FLOW DISCOVERY EVIDENCE: "<page>" ───┐
│ TARGET ROUTE: /path                      │
│ TARGET FILES: src/pages/Page/            │
│                                          │
│ TYPE A GREPS: <N> entry points found     │
│ TYPE B GREPS: <N> branching patterns     │
│ PAGE NAV: <N> outbound links             │
│                                          │
│ FINAL: <N> flows, <N> pages              │
└──────────────────────────────────────────┘
```

### Phase 4 — Map Changes to Design Nodes

For each page/feature group, determine the design graph operations:

#### 4a. New Page (status `A`)

1. **Find the functional Scenario** this page belongs to — match by
   route, component name, or semantic search via
   `Functional_Graph_Search`.
2. If no matching Scenario exists, STOP for this page and tell the
   user: *"No functional Scenario found for <page>. Run
   `/breeze:update-ontology-from-diff` or
   `/breeze:update-functional-graph` first."*
3. Build the design hierarchy:

   ```
   [CREATE] UserJourney: <scenario name>
     scenarioId: <scenario UUID>
     [CREATE] Flow: <flow name>
       modality: WEB
       userJourneyIds: [<UJ id>]
       stepIds: [<from functional graph>]
       [CREATE] Page: <page name>
         pageType: <LIST|DETAIL|FORM|DASHBOARD>
         flowIds: [<flow id>]
         stepIds: [<from functional graph>]
         [CREATE] Component: <PageLayout> (TEMPLATE)
           pageIds: [<page id>]
         [CREATE] Component: <ComponentName> (ORGANISM|MOLECULE|ATOM)
           pageIds: [<page id>]
           actionIds: [<from functional graph>]
   ```

4. Classify each component using atomic design rules:

   | Type | Signal |
   |------|--------|
   | **TEMPLATE** | One per page. Named by layout pattern (`FormPageLayout`, `ListPageLayout`, `DetailPageLayout`, `DashboardLayout`). Contains only ORGANISMs. Scope: `GLOBAL`. |
   | **ORGANISM** | Self-contained sections: forms, tables, data grids, charts, card groups, navigation bars, sidebars. Has own state or data fetching. |
   | **MOLECULE** | Small component groups: search bar with button, card with image + text, list item with icon + label, form field with label + input + error. |
   | **ATOM** | Indivisible elements: button, input, label, icon, badge, avatar, spinner, divider. |

   **Template rules:**

   | `pageType` | TEMPLATE Name | `layoutType` |
   |------------|--------------|-------------|
   | `FORM` | `FormPageLayout` | `FLEX` |
   | `LIST` | `ListPageLayout` | `FLEX` |
   | `DETAIL` | `DetailPageLayout` | `FLEX` |
   | `DASHBOARD` | `DashboardLayout` | `GRID` |

5. **Use actual component names from the code** — never invent
   generic names. If the code exports `<UserProfileCard>`, the
   component name is `UserProfileCard`.

#### 4b. Modified Page (status `M`)

1. **Find existing design nodes** for this page via
   `Design_Graph_Search` with the page/component name.
2. **Compare the diff** to identify:
   - New components added to the JSX tree → create new Component nodes
   - Components removed from the JSX tree → flag for user review
   - Component hierarchy changes (e.g., component moved from one
     section to another) → update `pageIds[]` / `supportingComponents`
   - New conditional rendering branches → may require new Flows
3. For new components, classify using atomic design rules (4a.4).
4. For modified component structure, update `supportingComponents[]`
   on parent components.

#### 4c. Deleted Page (status `D`)

1. **Find existing design nodes** via `Design_Graph_Search`.
2. **Do NOT auto-delete.** Present findings:
   ```
   ⚠️ Deleted: src/pages/OldPage/index.tsx
   Mapped to design nodes:
     - UserJourney: "View Old Page" (ID: <id>)
     - Flow: "View Old Page" (ID: <id>)
     - Page: "OldPage" (ID: <id>)
     - Components: OldPageLayout, OldWidget, ... (N components)
   
   Action needed: Confirm deletion of these design nodes,
   or skip if the page was moved/renamed.
   ```
3. If user confirms deletion, use `Delete_Design_Node` for each node
   (bottom-up: Components → Pages → Flows → UserJourneys). The
   backend handles orphan cleanup for shared children.

#### 4d. Shared Component Modified (not page-scoped)

For components in shared directories (`src/components/shared/`,
`src/ui/`, `libs/shared/`):

1. Find all Pages that use this component via `Design_Graph_Search`
   or `existingcomponents.json`.
2. If the component's **type** changed (e.g., simple atom became a
   molecule with sub-components), update its `type` and
   `supportingComponents[]`.
3. If the component was **split** into multiple components, create
   new Component nodes and link to the same Pages.
4. Report which Pages are affected.

### Phase 5 — Present Plan & Upsert

#### 5a. Present the Full Plan

```
## Design Graph Update Plan

Diff: <prev>..<current>
Project: <name> (<uuid>)
Modality: WEB

### New Design Nodes
[CREATE] UserJourney: "New Feature Flow"
  scenarioId: <uuid>
  [CREATE] Flow: "New Feature Flow" (WEB)
    [CREATE] Page: "NewFeaturePage" (FORM)
      [CREATE] Component: FormPageLayout (TEMPLATE)
      [CREATE] Component: NewFeatureForm (ORGANISM)
      [CREATE] Component: SubmitButton (ATOM) — reuse existing

### Updated Design Nodes
[UPDATE] Page: "Dashboard"
  [CREATE] Component: NewWidget (MOLECULE) — added in diff
  [UPDATE] Component: DashboardLayout (TEMPLATE)
    supportingComponents: [..., "NewWidget"]

### Flagged for Review
[DELETE?] Page: "OldPage" — file deleted in diff
  Associated: 1 UserJourney, 1 Flow, 3 Components
```

**Wait for user approval before proceeding.**

If `--dry-run`, stop here.

#### 5b. Update Component Registry (BLOCKING GATE)

Before any `Bulk_Update_Design_Nodes` call:

1. Read `existingcomponents.json`.
2. For each NEW component in the plan, add an entry:
   ```json
   "ComponentName": {
     "designSystemRef": "<ds-ref>",
     "scope": "<PAGE|DOMAIN|GLOBAL>",
     "id": "<generated-id>",
     "supportingComponents": ["ChildA", "ChildB"]
   }
   ```
3. Add under the correct type key: `ATOM`, `MOLECULE`, `ORGANISM`,
   `TEMPLATE`.
4. Write file back. Verify write succeeded.

> **This is the most commonly forgotten step.** Skipping it causes
> duplicate components across scenarios.

#### 5c. Build Payload & Call Bulk_Update_Design_Nodes

Build the nested payload per scenario and call
`Bulk_Update_Design_Nodes` — **one call per scenario**:

```json
{
  "projectUuid": "<uuid>",
  "data": {
    "userJourneys": [{
      "name": "<scenario name>",
      "scenarioId": "<scenario UUID>",
      "flows": [{
        "name": "<flow name>",
        "modality": "WEB",
        "userJourneyIds": [],
        "stepIds": ["<step-uuid-1>", "<step-uuid-2>"],
        "pages": [{
          "name": "<page name>",
          "pageType": "FORM",
          "flowIds": [],
          "stepIds": ["<step-uuid-1>"],
          "components": [
            {
              "name": "FormPageLayout",
              "type": "TEMPLATE",
              "layoutType": "FLEX",
              "pageIds": [],
              "supportingComponents": ["NewFeatureForm"]
            },
            {
              "name": "NewFeatureForm",
              "type": "ORGANISM",
              "pageIds": [],
              "actionIds": ["<action-uuid-1>", "<action-uuid-2>"]
            }
          ]
        }]
      }]
    }]
  }
}
```

**Backend dedup:** Nodes are matched by `projectUuid + name`
(case-insensitive). Including a node by name that already exists
appends parent edges — no duplicate is created.

**Reused nodes:** Include reused Flows with `pages: []` and reused
Pages with `components: []` so the backend adds `INCLUDES_FLOW` /
`CONTAINS_PAGE` edges.

#### 5d. Update Flow & Page Registries (BLOCKING GATE)

After successful upsert:

1. Read `existingflows.json`. For each new Flow, add:
   ```json
   "FlowName|WEB": {
     "id": "<real-uuid-from-response>",
     "stepIds": ["step-1", "step-2"],
     "modality": "WEB"
   }
   ```
   Write back to disk.

2. Read `existingpages.json`. For each new Page, add:
   ```json
   "PageName|FORM|WEB": {
     "id": "<real-uuid-from-response>",
     "stepIds": ["step-1"],
     "pageType": "FORM"
   }
   ```
   Write back to disk.

#### 5e. Mark Scenarios as Design-Generated (BLOCKING GATE)

After all registries are updated, call `Update_Functional_Node` on
each processed scenario:

```
Update_Functional_Node(
  uuid: <projectUuid>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true },
  citationId: [0],
  citations: [{ "type": "document", "name": "skip", "inputText": "skip" }]
)
```

> **This must be last** — only mark complete after all registries are
> persisted. Premature marking hides incomplete data.

#### 5f. Handle Deletions (if user confirmed)

For each confirmed deletion, call `Delete_Design_Node` bottom-up:
1. Delete Components (ATOMs first, then MOLECULEs, ORGANISMs, TEMPLATEs)
2. Delete Pages
3. Delete Flows
4. Delete UserJourneys

The backend handles orphan cleanup for shared children that lose
their last parent.

### Phase 6 — Summary

```
## Design Graph Update Summary

Diff: <prev>..<current>
Project: <name> (<uuid>)
Modality: WEB

### Files Processed
| Status | Count | Design Impact |
|--------|-------|---------------|
| Added | N | N new pages/components |
| Modified | N | N updated nodes |
| Deleted | N | N flagged for review |
| No Impact | N | skipped |

### Design Nodes
| Node Type | Created | Updated | Deleted | Reused |
|-----------|---------|---------|---------|--------|
| UserJourney | N | N | N | N |
| Flow | N | N | N | N |
| Page | N | N | N | N |
| Component | N | N | N | N |

### Component Breakdown
| Type | Created | Reused |
|------|---------|--------|
| TEMPLATE | N | N |
| ORGANISM | N | N |
| MOLECULE | N | N |
| ATOM | N | N |

### Registries Updated
- existingcomponents.json: +N entries
- existingflows.json: +N entries
- existingpages.json: +N entries

### Scenarios Marked Complete
- <scenario name> (ID: <id>) ✓

### Items Needing Manual Review
- <deleted file> → <design node name> (ID: <id>)
```

---

## Design Graph Principles

Refer to `../generate-design-from-ui/references/design-ontology.md`
for the complete entity model:

- UserJourney ↔ Scenario (1:1 link via `scenarioId`)
- Flow multiplied per modality
- Page types: `LIST`, `DETAIL`, `FORM`, `DASHBOARD` (uppercase only)
- Multi-parent support via `*Ids[]` arrays
- Backend dedup by `projectUuid + name` (case-insensitive)

Refer to `../generate-design-from-ui/references/atomic-design-rules.md`
for component classification:

- TEMPLATE: layout shell, one per page, contains only ORGANISMs
- ORGANISM: self-contained UI sections
- MOLECULE: small component groups
- ATOM: indivisible elements

Refer to `../generate-design-from-ui/references/component-rules.md`
for naming and composition rules.

Refer to `../generate-design-from-ui/references/flow-discovery-patterns.md`
for Type A / Type B / multi-page grep patterns.

---

## Blocking Gates Checklist

Before moving to the next page group, verify ALL gates passed:

```
⛔ PER-SCENARIO CHECKLIST:
  □ Flow discovery greps executed (Type A + Type B + page nav)
  □ existingcomponents.json updated with new components
  □ Bulk_Update_Design_Nodes called (one per scenario)
  □ existingflows.json updated with real IDs
  □ existingpages.json updated with real IDs
  □ Scenario marked isDesignGenerated=true

If ANY box unchecked → DO NOT proceed to next scenario.
```

---

## NO-OP Rule

If the diff contains only:
- Style-only changes (CSS/SCSS without component structure changes)
- Props/type changes without UI structure impact
- Refactoring (renames, extractions, formatting) with no new/removed
  components
- Test / story / mock file changes
- Documentation changes

Report: **"No design impact detected in this diff. No design graph
updates needed."**

List the files examined and why each was classified as no-impact.

---

## Safety Rules

1. **Never auto-delete design nodes** — always flag for user review
   and require explicit confirmation before calling `Delete_Design_Node`.
2. **Always present the plan** before any `Bulk_Update_Design_Nodes` call.
3. **Reuse existing nodes first** — the backend deduplicates by name,
   so include reused nodes by name in the payload.
4. **Functional graph is a prerequisite** — design nodes must link to
   functional Scenarios, Steps, and Actions. If no functional graph
   exists, redirect to `/breeze:generate-functional-from-ui`.
5. **One bulk call per scenario** — never batch multiple scenarios.
6. **Component registry update before upsert** — this is the most
   commonly skipped step and causes duplicate components.
7. **Registry persistence after upsert** — Flow and Page registries
   must be written to disk after every successful upsert.
8. **Mark scenario last** — `isDesignGenerated=true` only after all
   registries are confirmed persisted.
9. **Never print API keys or AWS credentials.**

---

## Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| Reading only `index.tsx` | < 3 components per page | Glob the page dir, read 4-10 files |
| Inventing generic names | Design graph doesn't match code | Use actual exported component names |
| Missing TEMPLATE | Page has no layout structure | Mandatory for every Page |
| Skipping `existingcomponents.json` update | Duplicate components | BLOCKING GATE — never skip |
| Classifying all as ORGANISM | Flat hierarchy | Use all atomic design levels |
| Guessing components from action names | Misses real UI | Read actual JSX/template code |
| Not fetching steps/actions | Missing `stepIds`/`actionIds` | Always call `Get_all_steps_actions_for_a_scenario_id` |
| Using `designSystemRef` as dedup key | Duplicates created | Backend deduplicates by `projectUuid + name` |
| Lowercase `pageType`/`modality` | Backend rejects | Always uppercase: `FORM`, `LIST`, `WEB`, etc. |
| Adding `actionIds` to Page | Field doesn't exist on Page | Actions map to Components only |
| Omitting reused flows from payload | Orphaned UserJourneys | Include with `pages: []` |
| Omitting reused pages from payload | Orphaned Flows | Include with `components: []` |
