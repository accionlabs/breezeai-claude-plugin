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
- `--scope <app-path>` — limit processing to a specific frontend app
  within a monorepo (e.g., `--scope apps/source/web`). Multiple
  `--scope` flags are allowed.

---

## Execution Flow

### Phase 0 — Bootstrap

1. Resolve `projectUuid` per `CLAUDE.md`.
2. Call `Call_Get_Project_Details_` — cache project name; load
   `metadata.projectContext` into active context.
3. Parse `$ARGUMENTS` to extract the two commit IDs. Validate with
   `git rev-parse --verify`.
4. **Read platform config** from `.breeze.json`:

   ```json
   {
     "designGraph": {
       "platform": {
         "id": "source-web",
         "suffix": " [Source Web]",
         "personas": ["End User", "Admin"]
       }
     }
   }
   ```

   | Field | If present | If absent |
   |-------|-----------|-----------|
   | `id` | Set `PLATFORM_ID = "source-web"` | `PLATFORM_ID = ""` |
   | `suffix` | Set `APP_SUFFIX = " [Source Web]"` | `APP_SUFFIX = ""` |
   | `personas` | Set `PLATFORM_PERSONAS = [...]` | `PLATFORM_PERSONAS = null` |

   Announce on first line:
   ```
   Project: <name> (<uuid>)
   Platform: <PLATFORM_ID or "single-platform">
   Suffix:   <APP_SUFFIX or "none">
   Personas: <PLATFORM_PERSONAS or "all human personas">
   ```

   > **Why this matters:** When two platforms share a Breeze project
   > (e.g., source-web and source-mobile), the backend deduplicates
   > design nodes by `projectUuid + name + platform`. Without `APP_SUFFIX`,
   > `"Login Page"` from both platforms merge into one node —
   > corrupting both design graphs. Every node name created or
   > searched in this skill must be suffix-aware.

5. **Detect monorepo** — run the monorepo detection algorithm
   (see **Monorepo Detection & Classification** section below).
   Cache the workspace map for use in Phase 1.
6. Resolve UI app paths:
   - **Monorepo mode**: use workspace map to identify all frontend
     workspaces. If `--scope` provided, filter to those paths only.
   - **Single-repo mode**: resolve from `$ARGUMENTS`,
     `.breeze.json` → `targetRepos.frontend`, or cwd.
7. Detect framework **per frontend workspace** (not just at root):
   - Check each app's `package.json`, `project.json`, `angular.json`
   - Angular signals: `@angular/core` dep, `.component.ts` files,
     `src/app/` structure
   - React signals: `react` dep, `.tsx`/`.jsx` files, `src/pages/`
   - Next signals: `next` dep, `pages/` or `app/` at project root
   - Svelte/Vue: framework-specific deps and extensions

### Phase 1 — Compute Diff & Filter UI Files

1. Run `git diff --name-status <prev-commit-id> <current-commit-id>`
   to get changed files with status (A/M/D/R).

2. **Filter to frontend UI files only** using monorepo-aware rules:

   **If monorepo detected:**

   For each changed file, find its owning workspace by longest
   path-prefix match against the workspace map. Keep the file only if
   the workspace type is `frontend` or `shared-frontend`. Also keep
   `shared-both` files if they contain UI-relevant code (components,
   models used in templates).

   Discard files in `backend`, `shared-backend`, and `lambda`
   workspaces entirely.

   **If single-repo:**

   Keep files matching:
   - Path contains `src/pages/`, `src/views/`, `src/components/`,
     `src/app/`, `pages/`, `views/`, `components/`, `src/features/`
   - Extensions: `.tsx`, `.jsx`, `.vue`, `.svelte`, `.component.ts`,
     `.component.html`, `.cshtml`

   **Always exclude (both modes):**
   - `*.test.*`, `*.spec.*`, `*.stories.*`, `*.mock.*`
   - `*.css`, `*.scss`, `*.less`, `*.module.css` (pure style)
   - `*.d.ts`, `*.types.ts` (pure type defs)
   - `node_modules/`, `dist/`, `build/`, `.storybook/`
   - `azure-pipelines/`, `scripts/`, `tools/`, `docs/`, `e2e/`

3. **Apply `--scope` filter** — if `--scope` was provided, discard
   files that don't fall under any of the specified scope paths.

4. **Classify each file by change type:**

   | Status | Meaning | Design Impact |
   |--------|---------|---------------|
   | `A` | Added | New pages/components → new design nodes |
   | `M` | Modified | Changed UI structure → update existing nodes |
   | `D` | Deleted | Removed pages/components → flag for review |
   | `R` | Renamed | Node name update → flag for review |

5. **Group files by workspace, then by page/feature directory.**

   In monorepo mode, files from different apps are NEVER mixed in
   the same group. Each app is processed independently:

   ```
   apps/source/web/src/app/products/  → one group
   apps/cpd/web/src/app/dashboard/    → separate group
   libs/ngx-source-components/src/... → shared component group
   ```

6. Present the filtered file list to the user. **In monorepo mode,
   group by workspace:**

   ```
   Diff: <prev>..<current>
   Repo type: Monorepo (Nx)
   Modality: WEB

   apps/source/web [Angular] (N files):
     A  apps/source/web/src/app/products/product-detail.component.ts
     A  apps/source/web/src/app/products/product-detail.component.html
     M  apps/source/web/src/app/products/product-list.component.ts
     ...

   apps/cpd/web [Angular] (N files):
     M  apps/cpd/web/src/app/dashboard/dashboard.component.ts
     ...

   libs/ngx-source-components [Shared Frontend — Angular] (N files):
     M  libs/ngx-source-components/src/lib/data-table/data-table.component.ts
     ...

   Grouped by page/feature:
     apps/source/web:
       1. products (3 files — new + modified)
     apps/cpd/web:
       1. dashboard (1 file — modified)
     libs/ngx-source-components:
       1. data-table (1 file — shared component modified)

   Skipped (N): [tests, styles, types, backend files...]
   ```

   **Wait for user confirmation before proceeding.**

### Phase 2 — Load Existing Graph Context

#### 2a. Load Functional Graph (read-only — for linkage)

The design graph links to the functional graph. Load the relevant
functional context:

1. Call `Get_all_personas` — cache all personas.
2. **Filter personas for this platform:**
   - Always skip non-human personas: `System`, `External System`
   - If `PLATFORM_PERSONAS` is set, also skip human personas whose
     name is NOT in `PLATFORM_PERSONAS` — they belong to another
     platform's design graph and their scenarios should not be linked
     to this platform's nodes
3. For each **allowed persona**, call
   `Get_all_outcomes_for_a_persona_id` — cache outcomes.
4. For outcomes related to changed files (match by name/route), call
   `Get_all_scenarios_for_a_outcome_id` — cache scenarios.
5. For each relevant scenario, call
   `Get_all_steps_actions_for_a_scenario_id` — cache steps and
   actions with their UUIDs for `stepIds[]` / `actionIds[]` wiring.

> **HARD GATE:** If no allowed personas remain after filtering, STOP.
> Either no functional graph exists (run `/breeze:generate-functional-from-ui`)
> or `designGraph.platform.personas` in `.breeze.json` is misconfigured.

#### 2b. Load Existing Design Graph

1. Call `Design_Graph_Search` with key terms from changed file names
   and routes — find existing UserJourneys, Flows, Pages, Components.

   **⛔ Platform filter — apply before reusing any result:**
   - If `APP_SUFFIX` is non-empty, only use nodes whose name ends
     with `APP_SUFFIX`. Discard all others — they belong to another
     platform and must NOT be linked to this platform's new nodes.

   ```
   Example — APP_SUFFIX = " [Source Web]":
     "Login Page [Source Web]"    → ✅ reuse
     "Login Page [Admin Portal]"  → ❌ skip — other platform
     "Login Page"                 → ❌ skip — no suffix, other platform
   ```

2. Load existing **platform-scoped** registries:

   | Registry | Single-platform | Multi-platform (`PLATFORM_ID` set) |
   |---|---|---|
   | Components | `existingcomponents.json` | `existingcomponents.{PLATFORM_ID}.json` |
   | Flows | `existingflows.json` | `existingflows.{PLATFORM_ID}.json` |
   | Pages | `existingpages.json` | `existingpages.{PLATFORM_ID}.json` |

   > These files contain only this platform's nodes. Never read or
   > write to the other platform's registry files.

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
3. Build the design hierarchy, applying `APP_SUFFIX` to every name
   before writing:

   ```
   [CREATE] UserJourney: <scenario name> for <persona name>{APP_SUFFIX}
     scenarioId: <scenario UUID>
     [CREATE] Flow: <flow name>{APP_SUFFIX}
       modality: WEB
       userJourneyIds: [<UJ id>]
       stepIds: [<from functional graph>]
       [CREATE] Page: <page name>{APP_SUFFIX}
         pageType: <LIST|DETAIL|FORM|DASHBOARD>
         flowIds: [<flow id>]
         stepIds: [<from functional graph>]
         [CREATE] Component: <PageLayout>{APP_SUFFIX} (TEMPLATE)
           pageIds: [<page id>]
         [CREATE] Component: <ComponentName>{APP_SUFFIX} (ORGANISM|MOLECULE|ATOM)
           pageIds: [<page id>]
           actionIds: [<from functional graph>]
   ```

   > **Suffix rules:**
   > - Append `APP_SUFFIX` BEFORE building the payload or querying
   >   the registry
   > - Do NOT double-suffix — if a name already ends with `APP_SUFFIX`,
   >   skip
   > - If `APP_SUFFIX` is empty (single-platform), names are unchanged

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
   `Design_Graph_Search` with the page/component name
   (include `APP_SUFFIX` in the search term when set, e.g.,
   search for `"Login Page [Source Web]"` not `"Login Page"`).
   **Discard any result that doesn't end with `APP_SUFFIX`.**
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

1. Read the **platform-scoped** component registry:
   - `PLATFORM_ID` set → `existingcomponents.{PLATFORM_ID}.json`
   - `PLATFORM_ID` empty → `existingcomponents.json`
2. For each NEW component in the plan, add an entry keyed by the
   **suffixed name** (e.g., `"LoginForm [Source Web]"`):
   ```json
   "LoginForm [Source Web]": {
     "designSystemRef": "<ds-ref>",
     "scope": "<PAGE|DOMAIN|GLOBAL>",
     "id": "<generated-id>",
     "supportingComponents": ["EmailInput [Source Web]", "SubmitButton [Source Web]"]
   }
   ```
3. Add under the correct type key: `ATOM`, `MOLECULE`, `ORGANISM`,
   `TEMPLATE`.
4. Write file back. Verify write succeeded.

> **This is the most commonly forgotten step.** Skipping it causes
> duplicate components across scenarios and across platforms.

#### 5c. Collect Citations via Code Graph

Before building the payload, look up source files from the diff to get
code ontology node IDs for per-node citations.

For each **new or modified** Page and Component (ORGANISM/MOLECULE):

1. Take the source file path from the diff
2. Call `Code_Graph_Search(uuid: <projectUuid>, query: "<relative-file-path>")`
3. If a matching code node is found, attach as citation:
   `{"type": "code", "reference": "<code-node-id>"}`
4. If no match, skip — do NOT block the upsert on citation failures

Batch unique file paths to minimise MCP calls.

#### 5d. Build Payload & Call Bulk_Update_Design_Nodes

Build the nested payload per scenario and call
`Bulk_Update_Design_Nodes` — **one call per scenario**:

```json
{
  "projectUuid": "<uuid>",
  "data": {
    "userJourneys": [{
      "name": "<scenario name>",
      "scenarioId": "<scenario UUID>",
      "citations": [{"type": "figma", "reference": "https://..."}],
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
          "citations": [{"type": "code", "reference": "<code-node-id>"}],
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
              "actionIds": ["<action-uuid-1>", "<action-uuid-2>"],
              "citations": [{"type": "code", "reference": "<code-node-id>"}]
            }
          ]
        }]
      }]
    }]
  }
}
```

**Backend dedup:** Nodes are matched by `projectUuid + name + platform`
(case-insensitive). Including a node by name that already exists
appends parent edges — no duplicate is created.

**Per-node citations:** UserJourney, Page, and Component accept a
`citations` array (merged with top-level). Flow does NOT support
per-node citations. Cite the source artifact each node was derived from.
Format: `{"type": "code", "reference": "<code-node-id>"}`.

**Reused nodes:** Include reused Flows with `pages: []` and reused
Pages with `components: []` so the backend adds `INCLUDES_FLOW` /
`CONTAINS_PAGE` edges.

#### 5e. Update Flow & Page Registries (BLOCKING GATE)

After successful upsert:

1. Read the **platform-scoped** flow registry:
   - `PLATFORM_ID` set → `existingflows.{PLATFORM_ID}.json`
   - `PLATFORM_ID` empty → `existingflows.json`

   For each new Flow, add (key includes the suffixed name):
   ```json
   "Standard Login [Source Web]|WEB": {
     "id": "<real-uuid-from-response>",
     "stepIds": ["step-1", "step-2"],
     "modality": "WEB"
   }
   ```
   Write back to disk.

2. Read the **platform-scoped** page registry:
   - `PLATFORM_ID` set → `existingpages.{PLATFORM_ID}.json`
   - `PLATFORM_ID` empty → `existingpages.json`

   For each new Page, add:
   ```json
   "Login Page [Source Web]|FORM|WEB": {
     "id": "<real-uuid-from-response>",
     "stepIds": ["step-1"],
     "pageType": "FORM"
   }
   ```
   Write back to disk.

#### 5f. Mark Scenarios as Design-Generated (BLOCKING GATE)

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
> confirmed persisted. Premature marking hides incomplete data.

#### 5g. Handle Deletions (if user confirmed)

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
Platform: <PLATFORM_ID or "single-platform">
Suffix: <APP_SUFFIX or "none">
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
- existingcomponents.{PLATFORM_ID}.json (or existingcomponents.json): +N entries
- existingflows.{PLATFORM_ID}.json (or existingflows.json): +N entries
- existingpages.{PLATFORM_ID}.json (or existingpages.json): +N entries

### Scenarios Marked Complete
- <scenario name> (ID: <id>) ✓

### Items Needing Manual Review
- <deleted file> → <design node name> (ID: <id>)

### Workspace Breakdown (monorepo only)
| Workspace | Framework | Files Changed | Processed | No Impact |
|-----------|-----------|---------------|-----------|-----------|
| apps/source/web | Angular | N | N | N |
| apps/cpd/web | Angular | N | N | N |
| libs/ngx-source-components | Angular | N | N | N |
```

---

## Monorepo Detection & Classification

### Detection Algorithm (Phase 0, Step 4)

Run these checks in order. Stop at the first match:

1. **Nx workspace** — check for `nx.json` at repo root.
   - If found, run `cat nx.json` and scan for `targetDefaults` or
     `$schema` containing `nx`.
   - List projects: `ls apps/` and `ls libs/` (Nx convention).
   - Set `repoType = "monorepo"`, `buildSystem = "nx"`.

2. **Lerna / Yarn / pnpm workspaces** — check for `lerna.json`,
   or `"workspaces"` key in root `package.json`, or
   `pnpm-workspace.yaml`.
   - If found, read the workspaces globs to discover packages.
   - Set `repoType = "monorepo"`, `buildSystem = "lerna|yarn|pnpm"`.

3. **Angular workspace** — check for `angular.json` at repo root
   with multiple `"projects"` entries.
   - Set `repoType = "monorepo"`, `buildSystem = "angular-cli"`.

4. **Fallback** — if none of the above, treat as single-project repo.

### Workspace Map Construction

Build a lookup table of every app and library with its classification:

```
WorkspaceMap = {
  "<relative-path>": {
    "name": "<project-name>",
    "type": "frontend" | "backend" | "shared-frontend" | "shared-backend" | "shared-both",
    "framework": "angular" | "nestjs" | "react" | "next" | "express" | "lambda" | "other",
    "scope": "app" | "lib"
  }
}
```

**Classification rules (applied per workspace):**

| Signal | Type | Framework |
|---|---|---|
| Path under `apps/*/web/` or `apps/*/syndication/` | `frontend` | Detect from deps / file patterns |
| Path under `apps/*/api/` | `backend` | Detect from deps |
| Path under `apps/lambda/` or `apps/*/sitemap-lambda/` | `backend` | `lambda` |
| Path under `apps/opensearch-ops/web/` | `frontend` | Detect |
| Path under `apps/opensearch-ops/api/` | `backend` | Detect |
| `libs/ngx-*` (Angular library prefix) | `shared-frontend` | `angular` |
| `libs/nest-*` (NestJS library prefix) | `shared-backend` | `nestjs` |
| `libs/express-*` or `libs/utils-node` | `shared-backend` | `express` / `node` |
| `libs/source-common`, `libs/utils-ts`, `libs/*-common` | `shared-both` | — |
| `libs/opensearch-ops-common` | `shared-backend` | — |
| `libs/*-index-structure` | `shared-backend` | — |

**Auto-detection fallback for unknown workspaces:**

If a workspace doesn't match the table above, inspect its contents:
- Has `src/app/`, `.component.ts`, `.component.html` → `frontend`, `angular`
- Has `.controller.ts`, `.service.ts` with NestJS imports → `backend`, `nestjs`
- Has `handler.ts`, `bootstrap.ts` with AWS/Lambda imports → `backend`, `lambda`
- Otherwise → `shared-both`

### Design Skill: Frontend-Only Filtering

Since the design skill only processes frontend UI files, use the
workspace map to **immediately discard** all files in `backend`,
`shared-backend`, and `lambda` workspaces. This is more reliable
than pattern-matching on file extensions alone, because in a monorepo
a `.service.ts` under `libs/ngx-source-core/` is frontend code, while
`.service.ts` under `libs/nest-source-catalogue/` is backend code.

### Shared Frontend Library Handling

When a shared frontend library (`libs/ngx-*`) file changes:

1. **Identify consuming apps** — grep for the library's import path
   (e.g., `@libs/ngx-source-components` or `@source/ngx-source-components`)
   across all frontend app workspaces.
2. **Report cross-app impact:**
   ```
   libs/ngx-source-components changed:
     M  libs/ngx-source-components/src/lib/data-table/data-table.component.ts

   Used by frontend apps:
     - apps/source/web (imports DataTableComponent in 3 pages)
     - apps/cpd/web (imports DataTableComponent in 1 page)

   Design graph updates will apply to components in BOTH apps.
   ```
3. **During design graph update**, handle shared components based on
   platform config:

   **Single-platform (`APP_SUFFIX` empty):** The shared component
   maps to a single Component node linked to Pages in multiple apps
   via `pageIds[]`. Do NOT create separate Component nodes per app.

   **Multi-platform (`APP_SUFFIX` non-empty):** Each platform gets
   its OWN suffixed Component node even if the underlying shared
   library component is the same source file. This is intentional —
   `DataTableComponent [Source Web]` and
   `DataTableComponent [Admin Portal]` are independent design nodes
   that can evolve separately.

   ```
   WRONG (multi-platform):
     "DataTableComponent" → pageIds: [source-web-page-id, admin-page-id]

   RIGHT (multi-platform):
     "DataTableComponent [Source Web]" → pageIds: [source-web-page-id]
     "DataTableComponent [Admin Portal]" → pageIds: [admin-page-id]
   ```

4. When this skill runs with `APP_SUFFIX = " [Source Web]"`, only
   update `DataTableComponent [Source Web]`. Never touch
   `DataTableComponent [Admin Portal]` — that belongs to a different
   platform run.

### Monorepo-Aware Flow Discovery

When running flow discovery greps (Phase 3d), scope the greps to
the correct workspace:

```bash
# WRONG — searches entire repo, gets false positives from other apps
grep -rn "routerLink=.*products" --include="*.html"

# RIGHT — scoped to the app being analyzed
grep -rn "routerLink=.*products" apps/source/web/ --include="*.html"
grep -rn "routerLink=.*products" libs/ngx-source-components/ --include="*.html"
```

For Angular monorepos, also check for:
- Lazy-loaded routes in `app.routes.ts` or `*-routing.module.ts`
  within the specific app
- `loadChildren` / `loadComponent` patterns

---

## Design Graph Principles

Refer to `../generate-design-from-ui/references/design-ontology.md`
for the complete entity model:

- UserJourney ↔ Scenario (1:1 link via `scenarioId`)
- UJ naming: `"{ScenarioName} for {PersonaName}{APP_SUFFIX}"` — persona
  qualifier prevents backend dedup from merging UJs across personas
- Flow multiplied per modality
- Page types: `LIST`, `DETAIL`, `FORM`, `DASHBOARD` (uppercase only)
- Multi-parent support via `*Ids[]` arrays
- Backend dedup by `projectUuid + name + platform` (case-insensitive)

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
  □ Platform config read: PLATFORM_ID, APP_SUFFIX, PLATFORM_PERSONAS
  □ Persona filter applied: only PLATFORM_PERSONAS processed
  □ Flow discovery greps executed (Type A + Type B + page nav)
  □ All new node names have APP_SUFFIX appended (before payload build)
  □ Design_Graph_Search results filtered: only suffix-matching nodes reused
  □ existingcomponents.{PLATFORM_ID}.json updated with new (suffixed) components
  □ Bulk_Update_Design_Nodes called (one per scenario)
  □ existingflows.{PLATFORM_ID}.json updated with real IDs
  □ existingpages.{PLATFORM_ID}.json updated with real IDs
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
10. **Platform isolation** — when `APP_SUFFIX` is set:
    - Append suffix to EVERY node name (UJ, Flow, Page, Component)
      before upserting
    - Filter ALL `Design_Graph_Search` / `Get_all_Design_By_Label`
      results by suffix before reusing any node
    - Read/write ONLY the platform-scoped registry files
    - Never touch design nodes whose name ends with a different suffix

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
| Using `designSystemRef` as dedup key | Duplicates created | Backend deduplicates by `projectUuid + name + platform` |
| Lowercase `pageType`/`modality` | Backend rejects | Always uppercase: `FORM`, `LIST`, `WEB`, etc. |
| Adding `actionIds` to Page | Field doesn't exist on Page | Actions map to Components only |
| Omitting reused flows from payload | Orphaned UserJourneys | Include with `pages: []` |
| Omitting reused pages from payload | Orphaned Flows | Include with `components: []` |
| Mixing files from different apps | Wrong scenario attribution | Group by workspace first, process each app independently |
| Unscoped flow discovery greps in monorepo | False positives from other apps | Always scope greps to the specific app directory |
| Treating `libs/ngx-*.service.ts` as backend | Frontend code skipped | Use workspace map, not file extension, to classify |
| Creating duplicate Component per consuming app (single-platform) | Redundant nodes | Shared components map to one Component node with multiple `pageIds[]` |
| Missing `APP_SUFFIX` on new node names | Nodes merge with other platform | Append suffix to EVERY name before upserting |
| Reusing `Design_Graph_Search` result without suffix check | Cross-platform edge created | Filter results: only use nodes ending with `APP_SUFFIX` |
| Reading shared `existingcomponents.json` in multi-platform project | Registry sees other platform's components | Use platform-scoped file: `existingcomponents.{PLATFORM_ID}.json` |
| Processing outcomes from non-platform personas | Links to wrong platform's functional graph | Filter by `PLATFORM_PERSONAS` in Phase 2a |
| Shared lib component maps to single node (multi-platform) | Both platforms edit same node | Multi-platform: each platform gets its own suffixed Component node |
