---
name: validate-design-graph
description: >
  Validate the design graph for structural integrity, ontology compliance,
  and functional graph linkage. Checks orphan nodes, empty hierarchy,
  duplicate names, missing scenarioIds, invalid enums (lowercase modality/
  pageType/type), template compliance, supportingComponents rules,
  actionIds on pages, and optional cross-validation against the functional
  graph. Use when: "validate design", "check design graph", "audit design
  graph", "design graph health check", "design quality".
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

---

## Step 1 — Collect Design Graph Data

Fetch all design nodes by label. For each label, paginate until all
nodes are collected:

```
FOR label IN ["UserJourney", "Flow", "Page", "Component"]:
  page = 1
  LOOP:
    result = Get_all_Design_By_Label(uuid: <projectUuid>, label: label, page: page, limit: 100)
    append items to collection
    IF collected >= total → EXIT
    page += 1
  END LOOP
```

Combine all nodes into a single JSON file and save to
`design-graph-export.json` in the project root.

---

## Step 2 — Collect Functional Graph (optional but recommended)

Ask the user:
> "Do you want to cross-validate against the functional graph? (y/n)"

**If yes:**
1. Call `Get_complete_functional_graph` with the project UUID
2. Note the saved file path — pass it to the validation script with `--functional`

**If no:**
- The script will still run all structural checks; it will skip
  functional linkage validation

---

## Step 3 — Run Validation Script

Run the validation script against the saved design graph file:

```bash
# Without functional cross-validation
python3 {SKILL_BASE_DIR}/scripts/validate-design.py design-graph-export.json design-validation-report.json

# With functional cross-validation
python3 {SKILL_BASE_DIR}/scripts/validate-design.py design-graph-export.json design-validation-report.json --functional <functional-graph-file>
```

The script performs these checks automatically:

| Check | Severity | What it catches |
|-------|----------|-----------------|
| **Structural — P0** | | |
| Empty hierarchy | P0 | UserJourneys with no Flows, Flows with no Pages, Pages with no Components |
| Missing scenarioId | P0 | UserJourneys without a linked functional Scenario |
| Invalid enums | P0 | Invalid `modality`, `pageType`, `type`, `layoutType` values |
| Template compliance | P0 | Pages missing a TEMPLATE component |
| Dangling parent refs | P0 | Flow's `userJourneyIds` references a UserJourney that doesn't exist, Page's `flowIds` references a missing Flow, Component's `pageIds` references a missing Page |
| Broken hierarchy chains | P0 | Full chain validation: Component → Page → Flow → UserJourney — any broken link means the node is unreachable |
| **Linkage — P1** | | |
| Orphan nodes | P1 | Flows/Pages/Components with empty parent ID arrays (no parent at all) |
| Duplicate linkage | P1 | Same parent ID appearing multiple times in a node's array (e.g., same flowId twice in a Page's `flowIds`, same pageId twice in a Component's `pageIds`, same stepId twice in a Flow's `stepIds`) |
| **Naming — P1** | | |
| Duplicate names | P1 | Exact same name within a node type (considering modality/pageType) |
| Near-duplicate names | P1 | Fuzzy name matches — e.g., "LoginForm" vs "SignInForm", "UserListPage" vs "User List Page" (token-set similarity with synonym expansion) |
| **Component rules — P1** | | |
| supportingComponents | P1 | Below minimum count, references to non-existent components, TEMPLATEs referencing non-ORGANISMs |
| actionIds on Pages | P1 | Pages with actionIds (actions should map to Components only) |
| Lowercase enums | P1 | Enum values that should be UPPERCASE |
| Description coverage | P1 | Nodes with missing, empty, or placeholder descriptions (rejects: null, empty, <5 chars, "N/A", "TBD", "TODO", "placeholder") — reported per node type with coverage percentage |
| **Functional ↔ Design cross-validation (with `--functional`)** | | |
| Scenario coverage | P1 | scenarioIds in design not found in functional graph, human scenarios with no matching UserJourney |
| Step coverage | P1 | stepIds in Flows/Pages not found in functional graph, functional steps not referenced by any Flow or Page |
| Action coverage | P1 | actionIds in Components not found in functional graph, functional actions (in covered scenarios) not mapped to any Component |
| Step-action consistency | P1 | Component maps to an actionId whose parent step is not in any Flow reachable from that Component's Page — cross-level mismatch |
| **Cosmetic / Info** | | |
| Template naming | P2 | Template name doesn't match expected for pageType |
| Modality coverage | INFO | Which modalities are used and their distribution |
| Component distribution | INFO | ATOM/MOLECULE/ORGANISM/TEMPLATE counts |

Read the output `design-validation-report.json` — it's structured JSON.

---

## Step 4 — Present Results

Present the validation report in this format:

```
## Design Graph Validation Report

### Summary

| Metric | Value |
|---|---|
| UserJourneys | {N} |
| Flows | {N} |
| Pages | {N} |
| Components | {N} (ATOMs: {N}, MOLECULEs: {N}, ORGANISMs: {N}, TEMPLATEs: {N}) |
| Health | {HEALTHY / NEEDS_ATTENTION / CRITICAL} |

### P0 Issues (Must Fix)

{List each P0 issue with specific node names and IDs}

### P1 Issues (Should Fix)

{List each P1 issue with specific node names}

### P2 Issues (Consider)

{List each P2 issue}

### Detailed Results

#### Structural Integrity (P0)

**Empty Hierarchy**
{Table of UserJourneys/Flows/Pages with no children}

**Dangling Parent References**
{Table of nodes referencing non-existent parents}

| Node Type | Name | Field | Dangling ID |
|-----------|------|-------|-------------|
| Flow | Login Flow | userJourneyIds | abc-123 (UserJourney not found) |
| Page | Dashboard | flowIds | def-456 (Flow not found) |

**Broken Hierarchy Chains**
{Table of components whose full chain to UserJourney is broken}

#### Linkage Quality (P1)

**Orphan Nodes**
{Table of nodes with empty parent ID arrays}

**Duplicate Linkage**
{Table of nodes with repeated IDs in their parent/link arrays}

| Node Type | Name | Field | Duplicate ID | Count |
|-----------|------|-------|--------------|-------|
| Page | Settings | flowIds | flow-abc | 2x |
| Component | SaveButton | pageIds | page-xyz | 3x |

#### Naming (P1)

**Duplicate Names**
{Tables per node type}

**Near-Duplicate Names**
{Table per node type with similarity score}

| Type | Name A | Name B | Similarity | Action |
|------|--------|--------|------------|--------|
| Flow | Email Login | Email Sign In | 0.80 | Merge → "Email Login" |
| Page | UserListPage | User List | 0.75 | Merge → "UserListPage" |
| Component | SearchInput | SearchField | 0.67 | Merge → "SearchInput" |

#### Component Rules (P1)

**Template Compliance**
{Table of pages missing templates or with wrong template names}

**Description Coverage**

| Node Type | Total | Missing | Coverage |
|-----------|-------|---------|----------|
| UserJourney | {N} | {N} | {pct}% |
| Flow | {N} | {N} | {pct}% |
| Page | {N} | {N} | {pct}% |
| Component | {N} | {N} | {pct}% |
| **Total** | {N} | {N} | {pct}% |

{Table of nodes with missing/invalid descriptions, per type}

**supportingComponents Violations**
{Table of components below minimum or with invalid refs}

#### Functional ↔ Design Cross-Validation (if --functional provided)

**Scenario Coverage**

| Metric | Value |
|---|---|
| Human Scenarios (functional) | {N} |
| Covered by Design | {N}/{M} ({pct}%) |
| Uncovered Scenarios | {N} |
| Dangling scenarioId refs | {N} |

{Table of uncovered scenarios}

**Step Coverage**

| Metric | Value |
|---|---|
| Human Steps (functional) | {N} |
| Referenced by Flows/Pages | {N} |
| Dangling stepId refs | {N} |
| Unmapped Steps | {N} |

{Table of unmapped steps — functional steps not in any Flow/Page}

**Action Coverage**

| Metric | Value |
|---|---|
| Human Actions (functional) | {N} |
| Referenced by Components | {N} |
| Dangling actionId refs | {N} |
| Unmapped Actions | {N} |

{Table of unmapped actions — functional actions not on any Component}

**Step-Action Consistency**

{Table of cross-level mismatches: Component maps to an actionId
whose parent step is not in the Flow reachable from that Component's Page}

| Component | Action | Expected Step | Issue |
|-----------|--------|---------------|-------|
| LoginForm | Submit credentials | Navigate to login | Step not in any Flow containing this component's Page |
```

---

## Step 5 — Recommend Actions

Based on the findings, provide a prioritized action list:

1. **P0 fixes** — specific nodes to populate, link, or correct
2. **P1 fixes** — specific duplicates to merge, orphans to link,
   supportingComponents to fill, enums to uppercase
3. **P2 improvements** — template naming corrections

---

## Step 6 — Optionally Fix Issues

Ask the user:
> "Would you like me to fix any of these issues?"

If yes, for each fix type:

**Structural (P0):**
- **Empty hierarchy:** Ask whether to populate children or remove the
  empty node via `Delete_Design_Node`
- **Missing scenarioId:** Search functional graph for matching scenario
  by name, then `Update_Design_Node` to set the link
- **Invalid/lowercase enums:** Fix via `Update_Design_Node` with correct
  uppercase value
- **Missing templates:** Generate appropriate TEMPLATE component and
  upsert via `Bulk_Update_Design_Nodes`
- **Dangling parent refs:** Remove the dangling ID from the array via
  `Update_Design_Node`, or ask if the referenced parent should be created
- **Broken chains:** Trace the break point, fix the missing link via
  `Update_Design_Node` to add the parent ID

**Linkage (P1):**
- **Orphan nodes:** Ask whether to link to an existing parent or remove
- **Duplicate linkage:** Deduplicate the parent ID array via
  `Update_Design_Node` (remove repeated entries)

**Naming (P1):**
- **Duplicates:** Ask whether to merge (keep one, reassign edges) or
  differentiate names
- **Near-duplicates:** Present each pair with similarity score. For each,
  ask: merge to canonical name (keep one, delete other, reassign edges),
  or mark as intentionally distinct. For merges, use `Update_Design_Node`
  to reassign child edges to the surviving node, then `Delete_Design_Node`
  on the duplicate

**Component rules (P1):**
- **Missing descriptions:** Generate meaningful descriptions based on
  node name, type, parent context, and linked functional nodes. For
  Components, derive from the action name and component type. For Pages,
  derive from child components and pageType. For Flows, derive from
  the page sequence and modality. For UserJourneys, derive from the
  linked scenario. Batch update via `Update_Design_Node`
- **supportingComponents violations:** Read component source to fill
  missing references, then `Update_Design_Node`
- **actionIds on Pages:** Move actionIds to the correct Component nodes,
  clear from Page via `Update_Design_Node`

**Functional linkage (P1, with --functional):**
- **Dangling stepIds/actionIds:** Remove invalid IDs from the array or
  search functional graph for the correct ID
- **Unmapped steps:** Add the stepId to the appropriate Flow/Page via
  `Update_Design_Node`
- **Unmapped actions:** Add the actionId to the appropriate Component
  via `Update_Design_Node`
- **Step-action consistency:** Move the Component to the correct Page,
  or fix the Flow's stepIds to include the missing step

Always confirm each batch of changes with the user before executing.

---

## Design Ontology Rules Reference

The design graph follows this hierarchy:

```
UserJourney (1:1 with functional Scenario, scenarioId required)
  └── Flow (modality required, stepIds[] link to functional Steps)
      └── Page (pageType UPPERCASE, stepIds[] link to functional Steps)
          └── Component (type UPPERCASE, actionIds[] link to functional Actions)
```

**Key rules enforced by this validation:**

**Structural integrity:**
- Every UserJourney must have a `scenarioId`
- Every node must have valid parent references (no dangling IDs)
- Full chain UserJourney → Flow → Page → Component must be unbroken
- No duplicate IDs in parent/link arrays

**Hierarchy:**
- Every UserJourney must have at least one Flow
- Every Flow must have at least one Page
- Every Page must have at least one Component
- Every Page must have exactly one TEMPLATE component

**Component rules:**
- TEMPLATEs can only reference ORGANISMs in `supportingComponents`
- `supportingComponents` minimum: TEMPLATE >= 2, ORGANISM >= 2, MOLECULE >= 2, ATOM = 0
- Pages must NOT have `actionIds` — actions map to Components only

**Enum values (UPPERCASE only):**
- `modality`: WEB, MOBILE, TABLET, DESKTOP, VOICE, API, KIOSK, WATCH, TV
- `pageType`: LIST, DETAIL, FORM, DASHBOARD
- `type`: ATOM, MOLECULE, ORGANISM, TEMPLATE
- `layoutType`: GRID, FLEX, SIDEBAR, FULL

**Functional ↔ Design linkage:**
- Every `scenarioId` on a UserJourney must exist in the functional graph
- Every `stepId` on a Flow/Page must exist in the functional graph
- Every `actionId` on a Component must exist in the functional graph
- An action's parent step should be in a Flow reachable from the Component's Page
