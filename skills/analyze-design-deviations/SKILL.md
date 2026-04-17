---
name: analyze-design-deviations
description: >
  Compare Figma design system components against the Breeze design graph
  component registry. First builds existingcomponents.json by iteratively
  fetching all Component nodes from MCP, then reads a user-provided
  figmaComponents.json file and performs a multi-dimensional comparison:
  name matching (with semantic equivalence resolution), type
  (ATOM/MOLECULE/ORGANISM/TEMPLATE) alignment, and supportingComponents
  parity. Outputs a structured comparison report.
  Use when: "compare components", "figma vs design graph", "component
  drift analysis", "compare figma components", "component comparison",
  "design system audit".
argument-hint: "<figmaComponents.json path>"
---

## What this skill does

Compares two component registries — one from the **Breeze design graph**
(fetched live from MCP) and one from a **Figma design system export**
(user-provided JSON file) — to identify mismatches, gaps, and drift
across four dimensions:

1. **Name matching** — components present in one but missing in the other,
   with semantic equivalence resolution (e.g., `IconBCI` → `TNLMIcon`,
   `TypographyBody` → `Typography`)
2. **Type alignment** — same component classified under different atomic
   levels (e.g., ATOM in Figma but MOLECULE in design graph)
3. **Supporting components parity** — whether the child component
   compositions match between the two sources (after resolving
   semantic equivalents)

```
Comparison Dimensions
├── Name Match        (present in both / only Figma / only Design Graph)
│   └── Semantic equivalence resolution applied before matching
├── Type Alignment    (ATOM ↔ MOLECULE ↔ ORGANISM ↔ TEMPLATE)
└── Supporting Comps  (child component list diff, equivalents resolved)
```

## Inputs

- **`$ARGUMENTS`** — path to `figmaComponents.json` (required)
- **`.breeze.json`** — for `projectUuid` (to query MCP)

## Outputs

- **`existingcomponents.json`** — refreshed component registry from MCP
- **Comparison report** — printed to console as structured markdown

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the project root. If missing, tell user to
   run `/breeze:setup-project`.
2. Extract `projectUuid`.
3. Validate `$ARGUMENTS`:
   - If empty, ask user: "Please provide the path to your
     figmaComponents.json file."
   - If provided, verify the file exists and is valid JSON.
   - Read and parse the file. It must have top-level keys from the set:
     `ATOM`, `MOLECULE`, `ORGANISM`, `TEMPLATE`.

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). Pass `.breeze.json`'s `projectUuid` value as `uuid`.
>
> **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
> the node label as **`label`** (e.g., `label: "Component"`), NOT as
> `parameters0_Value`.

---

## Phase 1: Build existingcomponents.json from MCP

### 1-pre. Check for Existing Registry (Skip Gate)

Before fetching from MCP, check if `existingcomponents.json` already
exists in the plugin working directory.

**If the file exists and is non-empty:**

Ask the user:

```
Found existing existingcomponents.json with {N} components
({A} atoms, {M} molecules, {O} organisms, {T} templates).

1. **Use as-is** — skip MCP fetch, compare against this file directly
2. **Re-fetch** — pull fresh data from MCP and overwrite

Choose 1 or 2:
```

- If user chooses **1** → skip Steps 1a–1c entirely, load the file
  into memory, and proceed to Phase 2.
- If user chooses **2** → continue with Steps 1a–1c below.

**If the file does not exist or is empty** → continue with Steps
1a–1c below (no prompt needed).

### 1a. Fetch All Components (Paginated)

Fetch **all** components from the design graph by paginating through
`Get_all_Design_By_Label`:

```
allComponents = []
page = 1
limit = 50

LOOP:
  1. Call Get_all_Design_By_Label(
       uuid: <projectUuid>,
       label: "Component",
       page: "<page>",
       limit: "<limit>"
     )
  2. Append returned nodes to allComponents
  3. IF returned count < limit → EXIT (no more pages)
  4. page += 1
  5. REPEAT
END LOOP
```

### 1b. Structure into existingcomponents.json

Organize fetched components into the standard registry format, keyed by
component name under atomic type:

```json
{
  "ATOM": {
    "Button": {
      "designSystemRef": "mui-button",
      "scope": "GLOBAL",
      "id": "uuid-from-mcp",
      "supportingComponents": []
    }
  },
  "MOLECULE": { ... },
  "ORGANISM": { ... },
  "TEMPLATE": { ... }
}
```

**Classification rules:**
- Each component node from MCP has a `type` field with values like
  `ATOM`, `MOLECULE`, `ORGANISM`, or `TEMPLATE`
- Use the component `name` as the key within each type bucket
- Preserve `designSystemRef`, `scope`, `id`, and `supportingComponents`
  from the MCP response

### 1c. Write to Disk

Write the structured registry to `existingcomponents.json` in the
plugin working directory (overwrite if exists).

Log: `"Fetched {N} components from design graph ({A} atoms, {M} molecules, {O} organisms, {T} templates)"`

---

## Phase 2: Load and Normalize Figma Components

### 2a. Read figmaComponents.json

Read the file from the path provided in `$ARGUMENTS`. Parse it as JSON.

### 2b. Normalize Structure

The figmaComponents.json follows this structure:

```json
{
  "ATOM": {
    "ComponentName": {
      "designSystemRef": "ref-string",
      "scope": "GLOBAL",
      "id": "",
      "supportingComponents": ["ChildA", "ChildB"]
    }
  },
  "MOLECULE": { ... },
  "ORGANISM": { ... },
  "TEMPLATE": { ... }
}
```

Build a flat lookup map for quick access:

```
figmaMap = {}
for each type in [ATOM, MOLECULE, ORGANISM, TEMPLATE]:
  for each (name, details) in figmaComponents[type]:
    figmaMap[name] = { type, ...details }
```

Build the same flat map for design graph components:

```
graphMap = {}
for each type in [ATOM, MOLECULE, ORGANISM, TEMPLATE]:
  for each (name, details) in existingcomponents[type]:
    graphMap[name] = { type, ...details }
```

Log: `"Figma: {N} components | Design Graph: {M} components"`

---

## Phase 3: Compare Components

Run all three comparison dimensions and collect findings.

> **IMPORTANT — Semantic Equivalents:**
> Figma uses granular component names while the design graph uses
> consolidated names. These are the **same components** under different
> naming conventions and must NOT be reported as mismatches.
>
> Known equivalence map (Figma → Design Graph):
>
> ```
> TypographyHeading  → Typography
> TypographyBody     → Typography
> TypographyCaption  → Typography
> IconBCI            → TNLMIcon
> IconMaterial       → TNLMIcon
> Checkbox           → TNLMCheckbox
> RadioButton        → Radio
> ToggleSwitch       → IOSSwitch
> Accordion          → TNLMAccordion
> Pagination         → TNLMPagination
> DatePicker         → TNLMDatepicker
> DropdownSelect     → TNLMSelect
> SearchBar          → SearchInput
> Badge              → (no equivalent — truly missing)
> ```
>
> Apply this map during **name matching** (Phase 3a) and
> **supporting components parity** (Phase 3c).

### 3a. Name Matching

Compare the two sets of component names, resolving semantic
equivalents first:

```
# Build a normalized name resolver
equivalenceMap = { ... }  // as defined above

resolvedFigmaMap = {}
for each (name, details) in figmaMap:
  resolvedName = equivalenceMap[name] OR name
  resolvedFigmaMap[resolvedName] = { originalName: name, ...details }

allNames = union(resolvedFigmaMap.keys, graphMap.keys)

For each name in allNames:
  - IN BOTH:     name exists in resolvedFigmaMap AND graphMap → "matched"
  - FIGMA ONLY:  name exists in resolvedFigmaMap but NOT graphMap → "figma_only"
  - GRAPH ONLY:  name exists in graphMap but NOT resolvedFigmaMap → "graph_only"
```

Collect into three lists: `matched`, `figmaOnly`, `graphOnly`.

When reporting matched components that were resolved via the
equivalence map, note the original Figma name alongside the
graph name (e.g., "IconBCI → TNLMIcon").

### 3b. Type Alignment (for matched components)

For each component in the `matched` list, compare atomic types:

```
For each name in matched:
  figmaType = resolvedFigmaMap[name].type     (e.g., "ATOM")
  graphType = graphMap[name].type             (e.g., "MOLECULE")

  IF figmaType != graphType:
    → Record type mismatch: { name, figmaType, graphType }
```

### 3c. Supporting Components Parity (for matched components)

For each component in the `matched` list, compare
`supportingComponents` arrays, resolving semantic equivalents
before diffing:

```
For each name in matched:
  figmaChildren = set(
    equivalenceMap[child] OR child
    for child in resolvedFigmaMap[name].supportingComponents
  )
  graphChildren = set(graphMap[name].supportingComponents)

  onlyInFigma  = figmaChildren - graphChildren
  onlyInGraph  = graphChildren - figmaChildren
  common       = figmaChildren & graphChildren

  IF onlyInFigma is not empty OR onlyInGraph is not empty:
    → Record supporting component mismatch:
      { name, onlyInFigma, onlyInGraph, common }
```

---

## Phase 4: Generate Report

Print a structured markdown report to the console AND save it to
`design-deviation-report.md` in the plugin working directory.

The report must be visually rich, scannable, and actionable. Use
status indicators, grouped sections, and per-component detail cards.

### Report Template

> **IMPORTANT:** Follow this template exactly. Replace all `<placeholder>`
> values with actual data. Omit any section that has zero items (e.g.,
> skip "Type Mismatches" entirely if there are none). Never show empty
> tables.
>
> For Section 1b (graph-only components), do NOT list all components
> individually if there are many (e.g., 100+). Instead, list ATOM-level
> graph-only components in a full table (these are usually few), and
> summarize MOLECULE/ORGANISM/TEMPLATE graph-only components as a
> count + notable examples paragraph per type.

````markdown
# Design Deviation Report

> **Figma Source:** `figmaComponents.json`
> **Design Graph:** `existingcomponents.json` — fetched live from MCP
> **Generated:** <YYYY-MM-DD>

---

## Executive Summary

<Write 2-3 sentences summarizing the overall health of the design
system alignment. Include: total unique component count, match count,
type drift count, composition drift count. Explain why the overlap
may be low (e.g., Figma defines an idealized design system while the
graph captures the full implementation reality with domain-specific
components).>

### Health Score

| Dimension                  | Aligned | Deviated | Coverage |
| -------------------------- | ------- | -------- | -------- |
| Name presence              | X / Y   | —        | X%       |
| Type classification        | X / Y   | Z        | X%       |
| Supporting components      | X / Y   | Z        | X%       |
| **Overall alignment**      |         |          | **X%**   |

> **Coverage formula:**
> - Name presence = matched / total unique names (after resolving semantic equivalents)
> - Type / Supporting = aligned / matched
> - Overall = average of the three percentages

### At-a-Glance Counts

```
Figma components ........... X
Design Graph components .... X
                              ───
Matched (in both) ......... X    <<<  these are compared below
  (of which via equivalence) X   <<<  matched by semantic equivalence map
Only in Figma ............. X    <<<  gap — not in design graph
Only in Design Graph ...... X    <<<  gap — not in Figma
                              ───
Type mismatches ........... X
Composition drifts ........ X
```

---

## 1. Coverage Gaps

_Components that exist in one source but not the other._

### 1a. Only in Figma — Missing from Design Graph

> These components are defined in the Figma design system but have no
> corresponding node in the Breeze design graph.

List every Figma-only component with a specific, actionable
recommendation:

| # | Component | Type | Recommendation |
|---|-----------|------|----------------|
| 1 | <name>    | ATOM | Add to design graph — <brief reason> |
| 2 | ...       | ...  | ... |

### 1b. Only in Design Graph — Missing from Figma

> These components exist in the design graph but have no Figma
> counterpart. State the total count prominently.

**ATOM** (<N> graph-only):

List all graph-only ATOMs in a table with Scope and Recommendation:

| # | Component | Scope | Recommendation |
|---|-----------|-------|----------------|
| 1 | <name>    | GLOBAL | Add to Figma — <reason> |
| 2 | <name>    | DOMAIN | Review: domain-specific, may be code-only |
| 3 | <name>    | PAGE   | Mark as code-only (<region>-specific) |

**MOLECULE** (<N> graph-only): <Summarize as a paragraph listing
notable examples like `FolderCard`, `NotificationCard`, `DateFilter`,
etc. — state that most are PAGE or DOMAIN scoped.>

**ORGANISM** (<N> graph-only): <Summarize as a paragraph listing
notable examples like `DashboardHeader`, `SearchFilters`,
`PipelineTable`, etc. — state that these are predominantly PAGE
scoped implementations.>

**TEMPLATE** (<N> graph-only): <List all template names inline since
there are usually few, e.g., `ModalLayout`, `SplitPaneLayout`,
`DetailPageLayout`, ...>

---

## 2. Type Classification Mismatches

_Components present in both sources but classified at different
atomic design levels. This causes hierarchy and composition confusion._

For each mismatch, output a detail card:

---

#### `<GraphComponentName>`

| Property       | Figma             | Design Graph      |
| -------------- | ----------------- | ----------------- |
| **Type**       | `<ATOM>`          | `<MOLECULE>`      |
| Children count | <N>               | <M>               |
| Figma name     | `<original name>` | —                 |

> Include the "Figma name" row only if the component was matched
> via the semantic equivalence map (i.e., original Figma name differs
> from graph name).

**Diagnosis:** <Explain why the types differ based on children count
and atomic design principles. A component with zero children is an
atom; one that wraps multiple primitives is a molecule.>

**Recommendation:** <Which source to fix and how, with specific
children to add if promoting.>

**Severity:** `HIGH` | `MEDIUM` | `LOW`

> Severity rules:
> - HIGH: ATOM <-> ORGANISM or ATOM <-> TEMPLATE (2+ level gap)
> - MEDIUM: ATOM <-> MOLECULE or MOLECULE <-> ORGANISM (1 level gap)
> - LOW: ORGANISM <-> TEMPLATE

---

_(Repeat the card for each type mismatch)_

---

## 3. Supporting Components Drift

_Components whose child composition differs between Figma and the
design graph. Mismatched children lead to inconsistent rendering and
broken component contracts._

> **NOTE:** Child names shown here are already resolved via the
> semantic equivalence map. For example, if Figma lists `IconBCI`
> and the graph lists `TNLMIcon`, they are treated as the same child
> and appear in the "In both" row.

For each drift, output a detail card:

---

#### `<ComponentName>` (`<TYPE>`)

| Child Status       | Components                              |
| ------------------ | --------------------------------------- |
| In both            | `<ChildA>`, `<ChildB>`, ...             |
| Only in Figma      | `<ChildX>`, `<ChildY>`                  |
| Only in Graph      | `<ChildZ>`                              |

**Visual diff:**

```
Figma:         [ChildA] [ChildB] [ChildX] [ChildY]
Design Graph:  [ChildA] [ChildB] [ChildZ]
                                  ^^^^^^^^  ^^^^^^^^
                                  missing   extra
```

**Impact:** <Explain what the mismatch means functionally. Be specific
about what UI features are missing or extra.>

**Recommendation:** <Specific action: which children to add/remove
from which source.>

---

_(Repeat for each drift)_

---

## 4. Fully Aligned Components

_Components that match perfectly across all three dimensions
(name, type, and supporting components)._

List all fully aligned component names grouped by type. For components
matched via equivalence map, show the mapping:

**ATOM** (`<N>` aligned): `Button`, `TNLMCheckbox` (Checkbox),
`IOSSwitch` (ToggleSwitch), `TextField`, `Typography`
(TypographyHeading/Body/Caption), ...

> Parenthetical shows the original Figma name when it differs.

---

## 5. Actionable Recommendations

_Prioritized list of actions to bring both systems into alignment._

### Priority 1 — Critical (type mismatches + composition drift combined)

> Components that need both type reclassification AND children added.

| # | Action | Component | Details |
|---|--------|-----------|---------|
| 1 | Promote to MOLECULE + add children | `<name>` | ATOM->MOLECULE, add <children list> |

### Priority 2 — Important (composition drifts for correctly-typed components)

> Components with correct type but missing children.

| # | Action | Component | Details |
|---|--------|-----------|---------|
| 1 | Add children to graph | `<name>` | Add <children list> |

### Priority 3 — Important (Figma-only coverage gaps — GLOBAL components)

> Figma components that should exist in the design graph.

| # | Action | Component | Details |
|---|--------|-----------|---------|
| 1 | Add to design graph | `<name>` | <TYPE> — <brief description> |

### Priority 4 — Housekeeping (Figma-only organisms and templates)

> Higher-level Figma components to add to graph.

| # | Action | Component | Details |
|---|--------|-----------|---------|
| 1 | Add to design graph | `<name>` | <TYPE> — <brief description> |

### Priority 5 — Review (graph-only GLOBAL atoms to consider adding to Figma)

> Graph components that may be worth adding to the Figma design system.

| # | Action | Component | Details |
|---|--------|-----------|---------|
| 1 | Add to Figma | `<name>` | GLOBAL atom — <description> |
| 2 | Review overlap | `<A>` vs `<B>` | May be redundant — consolidate |

---

_Report generated by `/breeze:analyze-design-deviations`_
````

---

## Phase 5: Save Report

After printing the report to the console, **always** save it to
`design-deviation-report.md` in the plugin working directory.

Log: `"Report saved to design-deviation-report.md"`

Then ask: "Would you like me to act on any of the recommendations?
For example, I can update design graph nodes or list specific
components to fix."

---

## Error Handling

- **MCP fetch fails:** Log the error, report how many components were
  successfully fetched, and proceed with partial data. Add a warning
  banner at the top of the report:
  ```
  > **Warning:** MCP fetch incomplete — only {N} of expected components
  > were retrieved. Results may be partial.
  ```
- **figmaComponents.json invalid:** Stop and tell the user the expected
  format with an example
- **No matched components:** Still generate the full report showing
  coverage gaps. The Health Score table will show 0% for type/
  supporting dimensions. Add a note: "No overlapping components found —
  the two systems appear to define entirely different component sets."
