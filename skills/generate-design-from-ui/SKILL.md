---
name: generate-design-from-ui
description: >
  Generate design graph (UserJourney, Flow, Page, Component) from
  functional graph scenarios, enriched by reading the actual frontend UI
  codebase. Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "design from UI", "ui to design graph", "generate design
  from frontend", "map ui to user journeys".
argument-hint: "[repo-path]"
---

## What this skill does

Generates **design graph nodes** from functional graph scenarios,
using the **actual UI codebase** as the primary source for component
discovery, hierarchy, props, and states.

```
Design Ontology
├── User Journey  (1:1 with functional Scenario)
│   └── Flow      (a distinct path/way to complete the journey — detected from UI)
│       └── Page   (screens needed to complete the flow — one or many)
│           └── Component (UI elements: atoms, molecules, organisms, templates)
```

Unlike `generate-design` which infers components from action
descriptions, this skill **reads the actual UI code** to discover
real components, their nesting, props, states, and flow structure.

See [design-ontology.md](references/design-ontology.md) for hierarchy
rules, entity fields, and functional graph linkage.

## Resources

**⛔ MANDATORY REFERENCES — Read at the specified points below.**

These reference documents contain critical rules that MUST be followed. They are extracted from the main flow to reduce verbosity while maintaining completeness.

| Reference | What it covers | When to read |
|---|---|---|
| **[references/blocking-gates.md](references/blocking-gates.md)** | ⛔ All blocking gates, validation rules, per-scenario checklist, recovery procedures | **Before Step 2** (processing loop) — review all gates. Refer back inline at each gate. |
| **[references/flow-discovery-patterns.md](references/flow-discovery-patterns.md)** | Grep patterns, Type A/B classification, multi-page detection, evidence block format | **At Step 3** (flow discovery) — follow grep strategy exactly. |
| **[references/atomic-design-rules.md](references/atomic-design-rules.md)** | Component classification (ATOM/MOLECULE/ORGANISM/TEMPLATE), composition rules, naming, scope | **At Step 5** (component classification) — use decision tree and examples. |
| [../generate-design/references/guide.md](../generate-design/references/guide.md) | Shared design ontology guide, bulk upsert payload schema | For payload structure details |
| [../generate-design/references/atomic-design-theory.md](../generate-design/references/atomic-design-theory.md) | Atomic design theory background | For additional classification context |

## Inputs

- **UI repo path** — if provided as argument (`$ARGUMENTS`), use it
  directly; otherwise resolved in Phase -1
- **`.breeze.json`** — for `apiBase`, `projectUuid`
- **Functional graph** — scenarios, steps, actions (fetched
  incrementally per scenario)
- **Existing design graph** — queried for dedup, not assumed empty

## Outputs

- **Design graph** updated with UserJourney > Flow > Page > Component
  nodes via `Bulk_Update_Design_Nodes` MCP tool
- **`existingcomponents.json`** — component registry for dedup

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing or incomplete, tell the user to run `/breeze:setup-project`
3. Extract `projectUuid`

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). Pass `.breeze.json`'s `projectUuid` value as `uuid`.
>
> **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter
> MUST be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or
> `scenario_id`).
>
> **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
> the node label as **`label`** (e.g., `label: "Component"`), NOT as
> `parameters0_Value`.

---

## Phase -1 — Resolve the target UI repo

1. Check if user passed a path via `$ARGUMENTS` — validate it exists
   and looks like a frontend repo
2. Check `.breeze.json` field `targetRepos.frontend`
3. Check if cwd looks like a frontend repo
4. Ask the user — single prompt: "Which UI repo do you want me to
   read? Provide an absolute path."
5. Persist the chosen path to `.breeze.json`:
   ```json
   { "targetRepos": { "frontend": "/abs/path/to/ui-repo" } }
   ```
6. If path has no frontend router file, stop and inform user

> **Frontend repo detection:** A valid frontend repo has `package.json`
> AND at least one of: `src/router/`, `src/routes/`, `app/routes`,
> `pages/`, `src/pages/`, `app/`, or React/Vue/Angular Router imports.

---

## Phase 0 — Configuration

### 0a. Detect Framework

Look for framework signals in the UI repo:

- React Router: `<Route`, `createBrowserRouter`, `useRoutes`
- Vue 2/3: `src/router/index.{js,ts}`
- Next.js: `pages/` or `app/` directory
- Angular: `*-routing.module.ts` or `app.routes.ts`
- Nuxt: `pages/` with `.vue` files
- SvelteKit: `src/routes/`

Record the detected framework for use during component reading.

### 0b. Processing Mode

Ask user which processing mode to use:

| Mode      | Description                                                |
| --------- | ---------------------------------------------------------- |
| `confirm` | Show preview and ask for confirmation before each scenario |
| `auto`    | Skip per-scenario confirmation; process all automatically  |
| `outcome` | Process all scenarios within an outcome on auto, then pause and wait for user input before starting the next outcome |
| `dry-run` | Build all payloads but do NOT call any MCP mutation tools. Instead, append each call to `apicalls.json` for review or external execution |

Default: `confirm` if user doesn't specify.

In `dry-run` mode:

- Behaves like `auto` for scenario processing (no per-scenario
  confirmation, no pausing)
- **ALL MCP mutation calls are replaced with file writes** — see
  Step 6g-dry and 6i-dry below
- Read-only MCP calls (fetching scenarios, steps, actions) still
  execute normally — only mutations are deferred
- `existingcomponents.json` and flow/page registries are still
  updated on disk (these are local files, not API calls)
- Scenarios are NOT marked as processed (`isDesignGenerated` stays
  `false`) since the upsert hasn't actually happened
- At the end, show the total count of queued calls and the file path

In `auto` mode:

- Skip user confirmation in Step 6 entirely
- Log a one-line progress update per scenario
- On error: log the failure, skip the scenario, continue to the next
- **CRITICAL — DO NOT STOP OR PAUSE DURING AUTO MODE.** When `auto` mode is selected, you MUST process ALL scenarios from start to finish without stopping to ask "should I continue?", "shall I proceed?", or any continuation prompt. The user has given blanket consent by selecting `auto`. Process every scenario until the loop exits naturally. The ONLY acceptable reason to stop is an unrecoverable error that prevents ALL further processing.

In `outcome` mode:

- **Scenario selection is automatically Option 4 (Outcome-by-Outcome)**
  — skip the scenario selection question in Step 2a entirely
- Within each outcome: behaves like `auto` — no per-scenario
  confirmation, no pausing, process all scenarios sequentially
- **Between outcomes: STOP and show an outcome summary**, then wait
  for user input before proceeding to the next outcome
- This gives the user a natural checkpoint to review progress, fix
  issues, or stop without losing work
- On error within an outcome: log the failure, skip the scenario,
  continue to the next scenario in the SAME outcome (don't skip
  the whole outcome)

### 0c. Detect & Confirm Modalities

**Auto-detect the primary modality from the repo:**

| Repo Signal                                                        | Detected Modality         |
| ------------------------------------------------------------------ | ------------------------- |
| React Router, Next.js, Nuxt, Vue Router, Angular Router, SvelteKit | `WEB`                     |
| React Native, `react-native` in package.json, `expo`               | `MOBILE`                  |
| Electron, `electron` in package.json, Tauri                        | `DESKTOP`                 |
| Ionic, Capacitor                                                   | `MOBILE` + `WEB` (hybrid) |
| Flutter web, responsive meta tags + mobile breakpoints             | `WEB` + `MOBILE`          |

1. Detect the primary modality from the framework identified in 0a
   and `package.json` dependencies
2. Present the detected modality to the user:

   ```
   Detected modality: **web** (React Router SPA)

   Do you also want to generate design nodes for other modalities?
   This creates separate Flows per modality under each UserJourney.

   Available: mobile, desktop

   Enter additional modalities (comma-separated), or press Enter to
   continue with web only:
   ```

3. If user adds modalities → each scenario gets duplicate Flows per
   modality (e.g. "Login" for web + "Login" for mobile) with the
   same pages but separate `modality` field values
4. Store confirmed modalities list for the per-scenario loop

---

## Step 1: Load or Create Registries (No Upfront MCP Fetch)

> **No MCP queries at startup.** The backend deduplicates by
> `projectUuid + name` (case-insensitive), so even if the local
> registries are empty, including a node by name in the bulk payload
> will link to an existing node — never creating a duplicate.
>
> Registries are populated incrementally via post-upsert sync
> (Step 6h) as scenarios are processed. Disk files provide
> cross-session persistence.

### 1a. Load or create `existingcomponents.json`

Look for `existingcomponents.json` in the plugin working directory.

- **If it exists and is non-empty** → load it as-is (data from prior
  sessions)
- **If it does NOT exist or is empty** → create with empty structure:

```json
{
  "ATOM": {},
  "MOLECULE": {},
  "ORGANISM": {},
  "TEMPLATE": {}
}
```

**Component Registry structure** — component name as key for fast
lookup:

```json
{
  "ATOM": {
    "Label": {
      "designSystemRef": "ds-label",
      "scope": "GLOBAL",
      "supportingComponents": []
    }
  },
  "MOLECULE": {},
  "ORGANISM": {},
  "TEMPLATE": {}
}
```

### 1b. Load or create `existingflows.json`

> **Flows and Pages are reusable across scenarios.** A "Login" flow
> created for Scenario A can be reused when Scenario B also passes
> through login. Same for pages. These registries enable
> LINK-before-CREATE at every level.
>
> **⛔ These registries are persisted to disk** so they survive across
> batched runs and separate Claude Code sessions.

Look for `existingflows.json` in the plugin working directory.

- **If it exists and is non-empty** → load it as the Flow Registry
- **If it does NOT exist or is empty** → create with empty structure:
  `{}`

**Flow Registry structure** — index by `(name, modality)`:

```json
{
  "Login|WEB": {
    "id": "flow-uuid-1",
    "stepIds": ["step-1"],
    "modality": "WEB"
  },
  "Registration|WEB": {
    "id": "flow-uuid-2",
    "stepIds": ["step-2"],
    "modality": "WEB"
  }
}
```

### 1c. Load or create `existingpages.json`

Same pattern as flows. Look for `existingpages.json` in the plugin
working directory.

- **If it exists and is non-empty** → load it as the Page Registry
- **If it does NOT exist or is empty** → create with empty structure:
  `{}`

> **Pages have NO modality field.** Modality lives on the Flow only.
> The same page can be shared across web and mobile flows. The Page
> Registry is keyed by `(name, pageType)` — NOT `(name, pageType, modality)`.

**Page Registry structure** — index by `(name, pageType)`:

```json
{
  "Dashboard|DASHBOARD": {
    "id": "page-uuid-1",
    "stepIds": ["step-3"],
    "pageType": "DASHBOARD"
  },
  "Login|FORM": {
    "id": "page-uuid-2",
    "stepIds": ["step-1"],
    "pageType": "FORM"
  }
}
```

**After each scenario's upsert**, add newly created Flows and Pages
to these disk-persisted registries so subsequent scenarios (including
across batched sessions) can reuse them — same pattern as
`existingcomponents.json` for Components.

---

## Step 2: Select Scenarios & Process

> **⛔ Three non-negotiable constraints:**
> 1. **No bulk graph fetch** — always fetch incrementally per scenario
> 2. **Sequential scenario processing** — one at a time, each must
>    fully complete before next begins. (UI file reads within a
>    scenario CAN be parallelized — reading is safe)
> 3. **Skip System/External System personas** — no UI to design
>    (see blocklist in Step 2a-pre)

> **⛔ MANDATORY READ: [references/blocking-gates.md](references/blocking-gates.md)**
>
> Before proceeding, read the blocking gates reference document. It contains:
> - All 7 blocking gates with detailed steps
> - Per-scenario checklist
> - What happens when you skip a gate
> - Recovery procedures
> - Auto mode clarification
>
> You will encounter gates at Steps 2a-pre, 3e, 6d, 6f, 6h, 6h-post, and 6i.
> Refer back to the document at each gate to verify you're following the
> correct procedure.

### 2a-pre. Build non-human outcome blocklist ⛔ BLOCKING GATE

> **⛔ HARD STOP: You MUST NOT proceed to scenario selection or
> processing until the blocklist is fully built. This gate ensures no
> System/External System scenario is ever processed. There is NO valid
> reason to skip this step — even in `auto` mode, even to "save time".**

The functional graph hierarchy is **Persona → Outcome → Scenario**.
`Get_scenarios_by_uuid` does not have a persona filter, so we build
a blocklist of outcome IDs belonging to non-human personas and check
each scenario against it.

**Steps:**

1. Call `Get_all_personas(uuid: "<projectUuid>")`
2. From the response, identify non-human personas:
   - `System` → non-human
   - `External System` → non-human
   - Everything else (User, Admin, named roles) → human
3. For each **non-human persona**, call
   `Get_all_outcomes_for_a_persona_id(uuid, personaId: "<id>")`
4. Collect all outcome IDs from these calls into a
   `blockedOutcomeIds` set
5. **Verify** the set was built — if `Get_all_personas` returned
   zero personas, STOP and tell user to run
   `/breeze:generate-functional-from-ui` first
6. Log: `"Blocklist built: {N} non-human outcome(s) from {M} non-human persona(s) will be excluded"`

**⛔ Gate check:** `blockedOutcomeIds` must exist before ANY scenario
is fetched, displayed, or processed. If this step fails, do not
continue.

**Usage during scenario processing:**

When fetching scenarios (Browse & Pick, Search, or Process All),
each scenario has an `outcomeId`. Check it against `blockedOutcomeIds`:

- `outcomeId` **in** `blockedOutcomeIds` → **skip** — show user:
  `"Skipping '{scenarioName}' — belongs to non-human persona (no UI)"`
- `outcomeId` **not in** `blockedOutcomeIds` → **proceed** normally

### 2a. Scenario Selection Mode

> **Skip this question in `outcome` mode.** When processing mode is
> `outcome`, automatically use **Option 4 (Outcome-by-Outcome)** below.
> Do not ask the user to choose a scenario selection mode.

Ask the user how they want to select scenarios for design generation:

**Question:** "How would you like to select scenarios?\n\n1. **Browse & Pick** — I'll show you 10 scenarios at a time, you pick which ones to process\n2. **Search & Generate** — Search for a scenario by name, then generate design for it\n3. **Process All** — Process all unprocessed scenarios one by one (batch mode)\n4. **Outcome-by-Outcome** — Process all scenarios grouped by outcome, pause between outcomes\n\nChoose 1, 2, 3, or 4:"

---

#### Option 1: Browse & Pick

1. Fetch a page of scenarios:
   `Get_scenarios_by_uuid(uuid: "<projectUuid>", page: "<currentPage>", limit: "10", isDesignGenerated: "false")`
2. For each scenario, check `outcomeId` against `blockedOutcomeIds`
   (from Step 2a-pre) — exclude matches from the display list
3. Display only human-persona scenarios:

   ```
   Unprocessed Scenarios (Page 1 of N — showing 10 of <total>):

   1. Login with Email — Persona: End User
   2. Register New Account — Persona: End User
   3. Reset Password — Persona: End User
   ...
   10. View Dashboard — Persona: Admin

   (N system persona scenarios excluded)

   Actions: Enter number(s) to select (e.g. "1,3,5"), "next" for next page, "all" to select all on this page
   ```

4. User selects scenarios by number (comma-separated), or:
   - `next` / `prev` — paginate through scenarios
   - `all` — select all scenarios on the current page
5. Collect selected scenarios into a `selectedScenarios` list
6. Ask: **"You selected {count} scenario(s). Proceed?"**
7. Process only the selected scenarios using the Processing Loop below

#### Option 2: Search & Generate

1. Ask: **"Enter scenario name (or keyword) to search:"**
2. Call `Functional_Graph_Search(query: "<userInput>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")` to find matching scenarios
3. Filter results: exclude any scenario whose `outcomeId` is in
   `blockedOutcomeIds`
4. If multiple matches found, display numbered list and let user pick
   one or more (same format as Option 1)
5. If exactly one match, confirm: **"Found: '{scenarioName}'. Generate design for this scenario?"**
6. If no matches, inform user and ask to try again or switch to another
   selection mode
7. Process selected scenario(s) using the Processing Loop below

#### Option 3: Process All (Default for `auto` mode)

Batch mode. All unprocessed scenarios (`isDesignGenerated=false`) are
processed one by one, **skipping any whose `outcomeId` is in
`blockedOutcomeIds`**. This is the default if the user doesn't specify.

---

#### Option 4: Outcome-by-Outcome (Default for `outcome` mode)

> **This option is automatically selected when processing mode is
> `outcome`.** It can also be chosen manually from the selection menu.

Process all unprocessed scenarios grouped by their parent outcome.
After all scenarios in one outcome complete, pause and wait for user
input before starting the next.

**Step 4a. Build the outcome queue:**

1. Call `Get_all_personas(uuid: "<projectUuid>")` — reuse the data
   from Step 2a-pre (already fetched for the blocklist)
2. For each **human persona**, call
   `Get_all_outcomes_for_a_persona_id(uuid, personaId: "<id>")`
3. For each outcome, fetch its scenarios **directly by outcome ID**:
   ```
   Get_all_scenarios_for_a_outcome_id(
     uuid: "<projectUuid>",
     outcome_id: "<outcomeId>",
     page: 1,
     limit: 10
   )
   ```
   Paginate using the `total`-based rule (see
   [mcp-tools.md § Pagination Rule](references/mcp-tools.md)).
   Filter out already-processed scenarios client-side
   (`isDesignGenerated == true` → skip).
   > **Why per-outcome fetch?** `Get_all_scenarios_for_a_outcome_id`
   > returns only scenarios belonging to one outcome — much smaller
   > payload than fetching ALL unprocessed scenarios project-wide and
   > filtering by `outcomeId` client-side. The only client-side filter
   > needed is `isDesignGenerated` (not supported by this tool).
4. Build the outcome queue — only include outcomes with ≥ 1
   unprocessed scenario:

```
outcomeQueue = [
  {
    outcomeId, outcomeName, personaName,
    scenarios: [{ id, name, outcomeId }, ...]
  },
  ...
]
```

**Step 4b. Show the outcome queue to the user:**

```
Outcome Queue ({N} outcomes, {M} total scenarios):

  1. [End User] Registration — 5 scenarios
  2. [End User] Login — 3 scenarios
  3. [Admin] User Management — 8 scenarios
  ...

Processing mode: outcome (auto within each outcome, pause between outcomes)
```

**Step 4c. Process outcomes one at a time:**

```
FOR each outcome in outcomeQueue:
  1. Show outcome header:
     "━━━ OUTCOME {i}/{total}: [{personaName}] {outcomeName} ({N} scenarios) ━━━"
  2. ⛔ RUN UPFRONT GREP DISCOVERY for this outcome (Step 3-upfront below)
     — Grep ALL target routes, pages, branching patterns for ALL
       scenarios in this outcome BEFORE processing any of them
     — Compile the Grep Evidence Cache
  3. Process all scenarios in this outcome using the Processing Loop
     (Step 2b) with auto-mode behavior (no per-scenario confirmation)
     — set selectedScenarios = outcome.scenarios for the loop
     — each scenario uses the Grep Evidence Cache from step 2 instead
       of running its own greps
  4. After ALL scenarios in this outcome are processed (or failed),
     show the Outcome Summary:

     ┌─── OUTCOME COMPLETE: "{outcomeName}" ───┐
     │ Processed: {N} scenarios                 │
     │ Succeeded: {N}                           │
     │ Failed: {N}                              │
     │ Skipped (system): {N}                    │
     │                                          │
     │ Registry counts:                         │
     │   Components: {N}                        │
     │   Flows: {N}                             │
     │   Pages: {N}                             │
     │                                          │
     │ Next outcome: [{persona}] {name} ({N})   │
     └──────────────────────────────────────────┘

  4. ⛔ PAUSE AND WAIT FOR USER INPUT.
     Ask: "Outcome complete. Continue to next outcome, or stop?"

     | Response       | Action                                   |
     | -------------- | ---------------------------------------- |
     | **continue/y** | Proceed to the next outcome              |
     | **stop/n**     | Exit the loop, show final summary        |
     | **skip**       | Skip the next outcome, show the one after|

  5. REPEAT for next outcome
END FOR
```

> **Why pause between outcomes?** This mode is designed for interactive
> sessions where context window management matters. Each outcome is a
> natural boundary — scenarios within an outcome tend to share pages
> and components, so they benefit from shared context. Between outcomes,
> the user can review results, and if the context window is getting
> large, they can stop and start a fresh session knowing the registries
> on disk will preserve all progress.

---

### 2b. Processing Loop

> **⛔ NO CONTINUATION PROMPTS in `auto` or `outcome` mode.** Process
> all scenarios without pausing. In `outcome` mode, pauses happen in
> Option 4's outer loop between outcomes — not here.

```
⛔ STRICTLY SEQUENTIAL — one scenario at a time, no parallel processing.

counter = 0, skippedSystem = 0
LOOP:
  1. Get next scenario (Option 3: fetch one where isDesignGenerated=false;
     Option 1/2: take next from selectedScenarios)
  2. IF none remaining → EXIT
  3. IF outcomeId IN blockedOutcomeIds → skip, skippedSystem++, REPEAT
  4. counter += 1
  5. Fetch steps/actions: Get_all_steps_actions_for_a_scenario_id(
       uuid, parameters0_Value: <scenarioId>)
     → Extract scenarioId, stepIds, actionIds
  6. Show: "[counter/total] Scenario: <name>"
  7. Execute Steps 3→4→5→6 for this scenario

  ⛔ PER-SCENARIO GATE (verify ALL before next scenario):
    □ Flow discovery evidence produced (Step 3e)
    □ UI files read, components classified (Steps 4-5)
    □ existingcomponents.json updated (Step 6d) — BEFORE bulk upsert
    □ Bulk_Update_Design_Nodes called (Step 6g) — or appended to
      apicalls.json in dry-run mode (Step 6g-dry)
    □ Flow/Page registries written to disk (Step 6h)
    □ Scenario marked processed (Step 6i) — SKIPPED in dry-run mode
    If ANY unchecked → DO NOT proceed.

  8. REPEAT
END LOOP
```
> Do not reorder, batch, or skip these steps.

### 2c. Extracted Data

From `Get_all_steps_actions_for_a_scenario_id`, extract and hold in
memory: `scenarioId`, and for each step: `stepId`, `stepName`, `order`,
and each action's `actionId`, `actionName`. These IDs wire into the
design payload (see
[design-ontology.md § Linkage](references/design-ontology.md)).

---

## Step 3: Locate UI Code & Discover Flows for This Scenario

> **⛔ MANDATORY READ: [references/flow-discovery-patterns.md](references/flow-discovery-patterns.md)**
>
> Before starting flow discovery, read the flow discovery patterns document. It contains:
> - Complete grep patterns for all major frameworks
> - Type A (entry-point) and Type B (on-page) classification rules
> - Multi-page detection strategy
> - Evidence block format requirements
> - Common edge cases and misclassifications
>
> **Follow the grep strategy exactly.** Do not skip, infer, or abbreviate.

> **⛔ GREP-FIRST RULE:** Run all grep discovery **UPFRONT** for the
> batch/outcome (Step 3-upfront) before processing individual
> scenarios. Every scenario MUST have grep evidence — never default to
> "1 flow, 1 page" without it.

### 3-upfront. Batch Grep Discovery (⛔ RUN BEFORE ANY SCENARIO)

> **⛔ BLOCKING GATE — You MUST complete this step before processing
> the FIRST scenario in the batch/outcome.** This is the single most
> important quality gate in the entire skill. Skipping it causes
> shallow, inaccurate design graphs for all subsequent scenarios.

Run all grep-based discovery for ALL scenarios in the current batch
upfront, compile results into a **Grep Evidence Cache**, then use
that cache during per-scenario processing.

**Why upfront?**
- Prevents grep-skipping drift (the #1 quality problem)
- More efficient — one grep pass covers all scenarios sharing a page
- Actions on the same page (modals, drawers, conditional UI) are
  only visible when you grep the FULL page against ALL scenario actions

**Step 3-upfront procedure:**

1. **Identify all target routes/pages** for the batch's scenarios:
   - Use citations on the parent Outcome (preferred) or grep for
     route matches from scenario/step/action names
   - Group scenarios by target page — many scenarios in an outcome
     will share a page (e.g., 8 search scenarios → `/main/search`)

2. **For each unique target page, run ALL greps ONCE:**

   a. **Type A greps** — entry-point flows (navigate/Link to target):
      ```
      Grep entire repo for navigate()/Link/to= pointing to <route>
      ```
   b. **Type B greps** — on-page branching:
      ```
      Grep target page directory for:
        - Conditional rendering (ternary JSX)
        - Tabs/steppers
        - Modal/drawer/dialog triggers
        - Feature flags / mode toggles
        - Auth method switches
      ```
   c. **Page nav greps** — outbound navigation:
      ```
      Grep target page files for navigate()/Link calls to OTHER routes
      ```
   d. **Read the page files** — understand the full component tree,
      all conditional sections, all modals/drawers/panels

3. **For each scenario in the batch, analyze its actions against
   the grep results:**

   For every action in the scenario, ask:
   - Does this action trigger a **modal/dialog**? (grep hit for
     `showModal`, `openDialog`, `<Modal>`, `<Dialog>` etc.)
   - Does this action open a **drawer/panel**? (grep hit for
     `openDrawer`, `<Drawer>`, `<Sheet>` etc.)
   - Does this action use a **different entry point**? (Type A hit
     from a different source page)
   - Does this action depend on **specific state**? (Type B hit for
     conditional rendering based on data state)

4. **Compile the Grep Evidence Cache:**

   ```json
   {
     "targetPages": {
       "/main/search": {
         "files": ["src/pages/Search/index.tsx", ...],
         "typeA": {
           "grepCommand": "...",
           "hits": 3,
           "entryPoints": [
             { "source": "Sidebar", "via": "Link" },
             { "source": "Dashboard", "via": "navigate" }
           ]
         },
         "typeB": {
           "grepCommand": "...",
           "hits": 5,
           "branchingPatterns": [
             { "pattern": "showSaveModal && <SaveSearchModal>", "line": 42 },
             { "pattern": "showDeleteConfirm && <ConfirmDialog>", "line": 78 },
             { "pattern": "isFilterDrawerOpen && <FilterDrawer>", "line": 55 }
           ]
         },
         "pageNav": {
           "grepCommand": "...",
           "outboundLinks": []
         }
       }
     },
     "scenarioAnalysis": {
       "Search for projects": {
         "targetPage": "/main/search",
         "actionFlows": "main page only — no modals/drawers triggered",
         "flows": 1, "pages": 1
       },
       "Save current search": {
         "targetPage": "/main/search",
         "actionFlows": "triggers SaveSearchModal (line 42)",
         "flows": 1, "pages": 2
       },
       "Delete saved search": {
         "targetPage": "/main/search",
         "actionFlows": "triggers ConfirmDialog (line 78)",
         "flows": 1, "pages": 2
       }
     }
   }
   ```

   This cache is held in memory (not written to disk) and used by
   Step 3e to produce per-scenario evidence blocks without re-running
   greps.

5. **Show the compiled summary to the user** (before processing):

   ```
   ┌─── GREP EVIDENCE CACHE: Outcome "{outcomeName}" ───┐
   │                                                      │
   │ Target pages: 1 (/main/search)                       │
   │ Entry points: 2 (Sidebar, Dashboard)                 │
   │ Branching patterns: 3 (modal, dialog, drawer)        │
   │                                                      │
   │ Per-scenario flow/page breakdown:                    │
   │   1. Search for projects     → 1 flow, 1 page       │
   │   2. Save current search     → 1 flow, 2 pages (+modal) │
   │   3. Delete saved search     → 1 flow, 2 pages (+dialog) │
   │   4. Apply saved search      → 1 flow, 1 page       │
   │   5. Sort search results     → 1 flow, 1 page       │
   │   6. Filter search results   → 1 flow, 2 pages (+drawer) │
   │   7. Paginate results        → 1 flow, 1 page       │
   │   8. Export search results   → 1 flow, 2 pages (+modal) │
   │                                                      │
   │ Total unique flows: 1                                │
   │ Total unique pages: 5 (main + 3 modals + 1 drawer)  │
   └──────────────────────────────────────────────────────┘
   ```

> **After this step, the per-scenario Step 3 can reference the cache
> instead of running fresh greps.** Step 3e evidence blocks still
> required for every scenario, but they pull from the cache — no
> new grep calls needed.

---

### 3a. Map scenario to UI entry points

**Option 1: Use citations (preferred — faster and more accurate)**

Scenarios created by `/breeze:generate-functional-from-ui` have citations
on their parent **Outcome** node pointing to the exact UI source files.
Check citations first before falling back to grep:

1. The scenario has an `outcomeId` — use
   `Get_all_outcomes_for_a_persona_id` (already fetched during blocklist
   build) or `Functional_Graph_Search` to get the outcome node
2. Read the outcome's `citations[]` array — each citation has:
   - `type`: `"code"`
   - `name`: file name (e.g. `"ProjectDetail.tsx"`)
   - `reference`: file path (e.g. `"src/pages/ProjectDetail.tsx"`)
3. `Read` each cited file to understand the page structure, components,
   routes, and conditional rendering
4. These files are the **primary source of truth** for this scenario's
   UI — they tell you exactly which components exist, what props they
   take, what state they manage, and how they're composed

> **Why citations first?** The functional graph was generated from these
> exact files. Using them directly avoids grep guesswork and gives you
> the actual component tree, imports, and rendering logic. This produces
> more accurate Flow/Page/Component identification.

**Option 2: Grep fallback (when citations are missing)**

If the outcome has no citations (e.g. scenario was created manually or
via `/breeze:analyze-functional`), fall back to grep:

1. Use the scenario name and step names to grep the UI repo for
   matching routes, page titles, or component names
2. Use `Code_Graph_Search` as an accelerator, then confirm with `Read`
3. Identify the primary page directory for this scenario

### 3b. Discover flows (distinct paths) from UI code

Two types: **Type A** (entry-point — different navigation paths TO
the page) and **Type B** (on-page — conditional rendering creating
different component trees). Both grep passes are mandatory.

---

#### Type A: Discover entry-point flows (different ways to reach the page)

**1. Identify the target route/page for this scenario** from Step 3a
(e.g. `/ticket/:id`, `/settings/profile`).

**2. Grep the ENTIRE UI repo for all navigation calls to that route.**

Use the framework detected in Phase 0a to select the correct grep
patterns. Replace `<route>` with the target route segment (e.g.
`ticket`, `settings/profile`).

| Framework | File globs | Navigation patterns to grep |
|---|---|---|
| **React Router** | `*.tsx`, `*.jsx` | `navigate(.*<route>`, `<Link.*<route>`, `to=.*<route>`, `push(.*<route>` |
| **Next.js** | `*.tsx`, `*.jsx` | `router.push(.*<route>`, `router.replace(.*<route>`, `<Link.*href=.*<route>`, `useRouter` |
| **Vue 2/3** | `*.vue`, `*.ts`, `*.js` | `router.push(.*<route>`, `$router.push(.*<route>`, `<router-link.*<route>`, `<NuxtLink.*<route>` |
| **Nuxt** | `*.vue`, `*.ts` | `navigateTo(.*<route>`, `<NuxtLink.*<route>`, `useRouter` |
| **Angular** | `*.ts`, `*.html` | `routerLink=.*<route>`, `router.navigate(.*<route>`, `router.navigateByUrl(.*<route>` |
| **SvelteKit** | `*.svelte`, `*.ts` | `goto(.*<route>`, `<a.*href=.*<route>`, `pushState` |
| **Always include** | (same as framework) | `href=.*<route>`, `window.location.*<route>`, `target="_blank"` |

Run **both** the framework-specific patterns AND the generic
patterns — some codebases mix approaches (e.g. `<a href>` alongside
`<Link>`).

**3. For each hit, identify the source page/component:**

- Which page/route does this `navigate()` or `<Link>` live in?
- Record: `{ sourcePage, sourceComponent, targetRoute }`

**4. Classify each entry point as a distinct flow or not:**

| Pattern                                                                    | Separate Flow?                                                  | Why                                                 |
| -------------------------------------------------------------------------- | --------------------------------------------------------------- | --------------------------------------------------- |
| Different source pages with different preceding steps                      | **Yes**                                                         | User navigates through different pages to get there |
| Same source page, different trigger components (sidebar vs card vs button) | **No** — same flow, different UI trigger                        | All start from the same page                        |
| Dashboard shortcut that skips listing page                                 | **Yes**                                                         | Different page sequence (1 page vs 2 pages)         |
| Breadcrumb/back navigation                                                 | **No**                                                          | Return path, not a forward flow                     |
| Deep link / direct URL                                                     | **Yes** — if the page behaves differently with no prior context | Different entry context                             |

**5. Check if target page behaves differently per entry point:**

- Grep the target page for `from`, `source`, `returnUrl`,
  `searchParams`, `location.state` — does it read where the user
  came from?
- If YES and renders differently → confirms separate flows
- If NO and renders identically → entry points share the same
  flow (different entry points don't create different page sequences)

---

#### Type B: Discover on-page flows (conditional paths on the target page)

**1. Grep the target page directory for branching patterns.**

Use the file globs from the framework table above (e.g. `*.vue` for
Vue, `*.svelte` for SvelteKit, `*.tsx`/`*.jsx` for React/Next).

| Category | Patterns to grep |
|---|---|
| **Conditional rendering** | `? <`, `: <`, `&& <` (JSX/TSX), `v-if`, `v-else` (Vue), `*ngIf`, `@if` (Angular), `{#if`, `{:else}` (Svelte) |
| **Tab/stepper variants** | `<Tab`, `<Tabs`, `<Stepper`, `<Step`, `activeStep`, `activeTab`, `TabPanel`, `mat-tab` (Angular), `v-tabs` (Vuetify) |
| **Auth method switches** | `authMethod`, `loginType`, `signInWith`, `provider`, `OAuth`, `SSO`, `socialLogin` |
| **Feature flags / modes** | `isAdvanced`, `viewMode`, `editMode`, `quickMode`, `expressMode`, `isBulk` |
| **Modal vs page** | `openModal`, `showDrawer`, `useDisclosure`, `isInline`, `isFullPage`, `MatDialog` (Angular), `v-dialog` (Vue) |

> **Conditional rendering syntax varies by framework.** JSX uses
> ternary (`? <X/> : <Y/>`) and logical AND (`&& <X/>`). Vue uses
> `v-if`/`v-else`/`v-show`. Angular uses `*ngIf`/`@if`/`@else`.
> Svelte uses `{#if}`/`{:else}`. Always grep for the syntax matching
> the detected framework.

**2. Read each hit and classify:**

| Pattern Found                               | Separate Flow? | Example                                             |
| ------------------------------------------- | -------------- | --------------------------------------------------- |
| Ternary rendering different component trees | **Yes**        | `isOAuth ? <SocialAuth/> : <EmailForm/>`            |
| Tab group with self-contained workflows     | **Yes**        | `<Tab label="Import CSV">` / `<Tab label="Manual">` |
| Wizard with express/skip mode               | **Yes**        | `quickMode ? skipToStep3() : showAll()`             |
| Modal vs full-page for same operation       | **Yes**        | `isInline ? <InlineEditor/> : navigate("/edit")`    |
| Bulk vs single operation                    | **Yes**        | `isBulk ? <BulkForm/> : <SingleConfirm/>`           |
| Show/hide optional fields                   | **No**         | `showAdvanced && <AdvancedOptions/>`                |
| Loading/error states                        | **No**         | `isLoading ? <Spinner/> : <Content/>`               |
| Permission-gated sections                   | **No**         | `canEdit && <EditButton/>`                          |
| Responsive layout switches                  | **No**         | `isMobile ? <MobileLayout/> : <DesktopLayout/>`     |

---

#### Combine Type A + Type B results

**Build the flow list:**

1. Start with discovered entry-point flows (Type A) — each distinct
   navigation path with different page sequences becomes a flow
2. Within each entry-point flow, check for on-page branching (Type B)
   — if found, split further
3. If no Type A or Type B signals → one default flow
4. Name each flow descriptively:
   - Type A: `"Generate User Stories from Dashboard"`,
     `"Generate User Stories from Projects List"`
   - Type B: `"Email Registration"`,
     `"Social Login"`
   - Combined: `"CSV Import via Settings"`
5. Multiply all flows by each selected modality

**Record for each flow:**

- Flow name and description
- Entry point (which page the user starts from)
- Exit point (where the user ends up after completing the flow)
- Page sequence (which pages the user navigates through)
- Which UI components belong to this path
- Which steps/actions from the functional data map to this flow

### 3b-post. Page Discovery Strategy

> **⛔ CRITICAL — MULTI-PAGE DETECTION IS MANDATORY.**
> You MUST grep each page file for outbound navigation calls using the
> framework-specific patterns from the Type A table above. A flow with
> only 1 page is valid — but only AFTER you have grepped and confirmed
> there are no outbound navigation links that lead to a next step in
> the flow. Do NOT assume single-page flows without evidence.

Multi-page flows are identified by following navigation links in code:

| Scenario Type                                          | Pages in Flow                                                          |
| ------------------------------------------------------ | ---------------------------------------------------------------------- |
| Notification → Project link (`target="_blank"`)        | 2 pages: Notifications Page → Project Detail Page                      |
| Settings → Sub-page navigation (`Link to="/main/..."`) | 2 pages: Settings Page → Destination Page (Preferences/Email/Password) |
| Single-page interactions (filter, select, scroll)      | 1 page: Same page, different components activated                      |
| Error states (API returns 404/401)                     | 1 page: Replaced page (NotFound or OutsideSubscription)                |

### 3c. Map steps/actions to UI files per flow

For each discovered flow:

1. Identify which **steps** belong to this flow path
   - Record mapping: `stepId → page directory path`
   - Shared steps (e.g. "View confirmation page") can appear in
     multiple flows' `stepIds[]`
2. Identify which **actions** correspond to which UI components
   in this flow's component tree
   - Record mapping: `actionId → component file path`

### 3d. Build the file reading list

Collect all files that need to be read for this scenario (across
all discovered flows):

- Page entry components (`index.tsx`, `page.tsx`)
- Widget/component directories (`widgets/*`, `components/*`)
- Form components, modals, dialogs
- Shared components imported by the page
- Source pages for entry-point flows (the pages users navigate FROM)
- Flow-specific components (e.g. `SocialAuthPanel`, `EmailForm`,
  `BulkDeleteForm`, `WizardStepper`)

### 3e. Flow Discovery Evidence Gate (⛔ BLOCKING GATE)

> **⛔ GATE 2 — See [references/blocking-gates.md](references/blocking-gates.md#gate-2-flow-discovery-evidence-block)**
>
> **HARD STOP: You MUST NOT proceed to Step 4 until you have
> produced a Flow Discovery Evidence Block for this scenario.**
> This gate exists because AI agents consistently skip grep-based flow
> discovery after ~10 scenarios, defaulting to "1 flow, 1 page" without
> evidence. The evidence block makes skipping observable.

**If Step 3-upfront was run** (outcome mode, or batch pre-processing),
pull this scenario's data from the **Grep Evidence Cache**. No new
grep calls needed — the cache has all Type A/B/page-nav results.

**If Step 3-upfront was NOT run** (single scenario, search mode),
you must run the greps now per Step 3b.

**Before proceeding, write the following evidence block** (in your
response, not to a file):

```
┌─── FLOW DISCOVERY EVIDENCE: "{scenarioName}" ───┐
│                                                   │
│ TARGET ROUTE: /path/to/page                       │
│ TARGET FILES: src/pages/PageName/index.tsx         │
│ SOURCE: Grep Evidence Cache / fresh greps         │
│                                                   │
│ TYPE A (entry-point flows):                       │
│   hits: <N> results                               │
│   entry points found:                             │
│     1. <sourcePage> → <targetRoute> (via <Link>)  │
│     2. <sourcePage> → <targetRoute> (via navigate) │
│   classification: <N> distinct flows              │
│                                                   │
│ TYPE B (on-page branching):                       │
│   hits: <N> results                               │
│   branching patterns found:                       │
│     1. <pattern> → <separate flow? yes/no + why>  │
│   classification: <N> additional flows            │
│                                                   │
│ THIS SCENARIO'S ACTION ANALYSIS:                  │
│   Action: "<actionName>"                          │
│   → Triggers: <component> (found at line <N>)     │
│   → RESULT: <modal page / drawer / same page>     │
│                                                   │
│ PAGE NAV (multi-page detection):                  │
│   outbound links: <N>                             │
│   classification: <N> pages per flow              │
│                                                   │
│ FINAL: <N> flows, <N> pages                       │
│ EVIDENCE: cache-confirmed / grep-confirmed        │
└───────────────────────────────────────────────────┘
```

**Rules for this gate:**

1. **Every field must be filled** — no placeholders, no "N/A",
   no "skipped". If a grep returns 0 hits, write `hits: 0 results`
   and explain why
2. **The "THIS SCENARIO'S ACTION ANALYSIS" section is MANDATORY** —
   this is the part that differs per scenario even when sharing a page.
   You must map each action to the specific UI element it triggers
   (modal, drawer, conditional section, or main page interaction)
3. **If flow count = 1 AND page count = 1**, the evidence block MUST
   include an explicit line:
   `SINGLE-FLOW JUSTIFICATION: <why this action doesn't trigger
   any modal/drawer/conditional UI>`
4. **If using the Grep Evidence Cache**, write `SOURCE: Grep Evidence
   Cache (from Step 3-upfront)` — this is valid and expected

**⛔ Gate check:** If this evidence block is not present in your
response for the current scenario, you have skipped flow discovery.
STOP and go back to Step 3b (or Step 3-upfront if it wasn't run).

---

## Step 4: Deep-Read UI Code (Component Discovery Strategy)

Read actual JSX/TSX files via background agents to extract real
component hierarchy:

| Step                 | What to do                                                                        |
| -------------------- | --------------------------------------------------------------------------------- |
| Page-level read      | Read all page `index.tsx` files identified in Step 3                              |
| Widget drill-down    | Read all `widgets/*` files (top-details, tab-details, sidebar-contacts, etc.)     |
| Component drill-down | Read all `components/*` files (side-card, filter-keyword, tab-contact-card, etc.) |
| Template discovery   | Read template registry + all template variants                                    |
| Import tracking      | Follow imports to discover shared library atoms (icons, selects, tabs, etc.)      |

### 4a. Read page files

For each file identified in Step 3b, `Read` the file and extract:

- Component hierarchy (JSX nesting)
- Props interface/type definitions
- State management (`useState`, `useReducer`, hooks)
- Interactive elements (forms, buttons, selects, tables)
- Layout structure (grid, flex, sidebar, header)

### 4b. Component-import drill-down

For every imported component matching
`/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/` AND
that has its own `useState`/`useReducer`/`useStore` hook, you MUST
read the file before drafting design nodes.

### 4c. Follow-the-trigger

For modals, drawers, panels triggered from this page:

- Viewer (read-only) → capture as components under this page
- Feature-rich (own forms/CRUD) → note for separate scenario processing

### 4d. Skip leaf primitives

Do NOT read: `Skeleton`, `LoadSkeleton`, `NoData`, `Empty`,
`Spinner`, `LoadingOverlay`. These are chrome, not functional
components.

---

## Step 5: Build Component Hierarchy from UI Code

> **⛔ MANDATORY READ: [references/atomic-design-rules.md](references/atomic-design-rules.md)**
>
> Before classifying any component, read the atomic design rules document. It contains:
> - Complete classification rules for ATOM/MOLECULE/ORGANISM/TEMPLATE
> - Code pattern recognition (state hooks, composition depth, etc.)
> - Decision tree for edge cases
> - Real-world examples from codebases
> - Common misclassifications and fixes
> - Component naming conventions (use exact repo names)
> - `supportingComponents` composition rules
> - Scope assignment logic
>
> **Use the decision tree and examples** — do not rely on intuition or component name alone.

For each component found in Step 4:

1. **Classify** by atomic level using code patterns from atomic-design-rules.md
   (hooks → ORGANISM, composed atoms → MOLECULE, single element → ATOM, layout-only → TEMPLATE)
2. **Name** using the exact exported/file name from the repo (PascalCase)
3. **Build `supportingComponents`** from JSX nesting per composition rules
4. **Check reuse** against `existingcomponents.json` — read it before
   creating any component. Backend dedup by name handles linking

---

## Step 6: Build and Upsert Design Payload

### 6a. Assemble the design hierarchy (REUSE FIRST at every level)

> **Read [reusability.md](references/reusability.md) for backend dedup
> mechanism and reuse rules per level.** Key principle: include nodes
> by name in the payload — the backend deduplicates by
> `projectUuid + name` and handles all linking automatically.
>
> **Read [design-ontology.md](references/design-ontology.md) for
> entity fields and functional graph linkage.**

Build the tree using flows from Step 3b and IDs from Step 2c:

**1. Scenario → UserJourney** — 1:1, always new. `scenarioId` required.

**2. Flows** — check Flow Registry by `(name, modality)`.
Match → include by name with `pages: []`. No match → create with
full pages. After upsert, add to registry.

> **⛔ ALWAYS include reused flows in the payload.** A UserJourney
> with `flows: []` is orphaned — the backend only creates edges from
> the nested payload.

**3. Pages** — check Page Registry by `(name, pageType)`.
Match → include by name with `components: []`. No match → create.

**4. Components** — check `existingcomponents.json` using
[reuse resolution rules](references/component-rules.md). Include
by name — backend dedup handles linking.

**Linking completeness:** Every stepId and actionId from the fetched
functional data MUST appear in at least one design node.

### 6b. Determine page types and assign TEMPLATEs

Derive `pageType` from UI code (`FORM`, `LIST`, `DETAIL`, `DASHBOARD`).
Every Page MUST have a TEMPLATE — see
[design-ontology.md § Template Rules](references/design-ontology.md)
for the pageType→TEMPLATE mapping. Check `existingcomponents.json`
TEMPLATE section for reuse before creating.

### 6d. Update `existingcomponents.json` (⛔ BLOCKING — before bulk upsert)

> **⛔ GATE 3 — See [references/blocking-gates.md](references/blocking-gates.md#gate-3-component-registry-pre-upsert-update)**
>
> **MUST complete before `Bulk_Update_Design_Nodes`.** Skipping
> causes duplicate components — the #1 drift bug after ~5 scenarios.

1. Read `existingcomponents.json`
2. Add each new component under its type key (`ATOM`/`MOLECULE`/`ORGANISM`/`TEMPLATE`)
3. Write the file back and verify success

### 6e. Build the bulk payload

Assemble the nested tree: UserJourney → Flows → Pages → Components
(with `supportingComponents`) + TEMPLATEs.

**Payload structure (example with multiple flows):**

```json
{
  "userJourneys": [
    {
      "name": "User Registration",
      "description": "End-to-end account registration",
      "scenarioId": "scenario-uuid",
      "flows": [
        {
          "name": "Email Registration",
          "description": "Register with email and password form",
          "modality": "WEB",
          "entryPoint": "Registration page",
          "exitPoint": "Dashboard redirect",
          "stepIds": ["step-uuid-1", "step-uuid-2"],
          "pages": [
            {
              "name": "Registration Form",
              "description": "User fills in registration details",
              "pageType": "form",
              "requiresAuth": false,
              "allowedRoles": [],
              "stepIds": ["step-uuid-1"],
              "components": [
                {
                  "name": "FormPageLayout",
                  "type": "TEMPLATE",
                  "designSystemRef": "ds-form-page-layout",
                  "supportingComponents": ["RegistrationForm"]
                },
                {
                  "name": "RegistrationForm",
                  "type": "ORGANISM",
                  "description": "Email registration form with validation",
                  "designSystemRef": "ds-registration-form",
                  "props": "{\"onSubmit\": \"function\"}",
                  "states": ["idle", "loading", "error", "success"],
                  "actionIds": ["action-uuid-1"],
                  "supportingComponents": [
                    "TextInputField",
                    "PasswordInputField",
                    "SubmitButton"
                  ]
                },
                {
                  "name": "TextInputField",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-text-input-field",
                  "actionIds": ["action-uuid-2"],
                  "supportingComponents": ["Label", "TextInput", "ErrorMessage"]
                },
                {
                  "name": "SubmitButton",
                  "type": "ATOM",
                  "designSystemRef": "ds-submit-button",
                  "supportingComponents": []
                }
              ]
            },
            {
              "name": "Email Verification",
              "description": "Confirm email address",
              "pageType": "detail",
              "stepIds": ["step-uuid-2"],
              "components": [
                {
                  "name": "ConfirmationMessage",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-confirmation-msg",
                  "actionIds": ["action-uuid-3"],
                  "supportingComponents": ["Icon", "Heading", "Label"]
                }
              ]
            }
          ]
        },
        {
          "name": "Social Login",
          "description": "Register via Google/GitHub OAuth",
          "modality": "WEB",
          "entryPoint": "Registration page",
          "exitPoint": "Dashboard redirect",
          "stepIds": ["step-uuid-1", "step-uuid-3"],
          "pages": [
            {
              "name": "Social Auth",
              "description": "Choose OAuth provider and authorize",
              "pageType": "form",
              "requiresAuth": false,
              "stepIds": ["step-uuid-1", "step-uuid-3"],
              "components": [
                {
                  "name": "SocialAuthPanel",
                  "type": "ORGANISM",
                  "description": "OAuth provider selection buttons",
                  "designSystemRef": "ds-social-auth-panel",
                  "actionIds": ["action-uuid-4"],
                  "supportingComponents": [
                    "SocialLoginButton",
                    "Divider",
                    "Label"
                  ]
                },
                {
                  "name": "SocialLoginButton",
                  "type": "MOLECULE",
                  "designSystemRef": "ds-social-login-btn",
                  "actionIds": ["action-uuid-5"],
                  "supportingComponents": ["Icon", "Label"]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Payload rules:**

- **One UserJourney per call** — one scenario per call
- **Nesting = hierarchy** — backend wires parent-child relationships
- **`scenarioId`** links UserJourney to functional scenario
- **`stepIds`** links Flows/Pages to functional steps
- **`actionIds`** links Components to functional actions
- **Multi-modality** — separate Flow entries per modality under same
  UserJourney
- **NO `children` field** — composition via `supportingComponents` only

### 6f. Flow Count Validation Gate (⛔ BLOCKING)

> **⛔ GATE 4 — See [references/blocking-gates.md](references/blocking-gates.md#gate-4-flow-count-validation)**

Validate before preview/progress log (all modes):

- **1 flow, 1 page** → requires `SINGLE-FLOW JUSTIFICATION` in
  Step 3e evidence. Missing → re-run greps
- **1 flow, >1 pages** → OK
- **>1 flows** → OK
- **0 flows** → ERROR — every scenario needs ≥ 1 flow

### 6f-post. User confirmation (confirm mode only)

> **Skip in `auto` and `outcome` mode.** Print a progress line instead:
> `"[{current}/{total}] Processing: {scenarioName} → {flowCount} Flows, {pageCount} Pages, {componentCount} Components"`

Show preview covering: UserJourney, Flows, Pages, Components
(new + reused), Templates. Ask: **"Proceed with creating these
design nodes?"**

| Option     | Action                                   |
| ---------- | ---------------------------------------- |
| **Yes**    | Create all nodes as shown                |
| **No**     | Skip this scenario, move to next         |
| **Modify** | Let user specify changes before creating |

### 6g. Make the bulk upsert call (live modes)

> **Skip this step in `dry-run` mode** — use Step 6g-dry instead.

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  data: <nested payload from 6e>
)
```

**One call per scenario.** Never batch multiple scenarios.

### 6g-dry. Append to `apicalls.json` (dry-run mode only)

> **Replaces 6g, 6i in `dry-run` mode.** No MCP mutations are made.

Instead of calling MCP, append the call to `apicalls.json` in the
plugin working directory. Each entry is one API call that would have
been made:

**File structure — JSON array, one entry per call, in execution order:**

```json
[
  {
    "order": 1,
    "scenarioName": "Register New Account",
    "scenarioId": "scenario-uuid",
    "tool": "Bulk_Update_Design_Nodes",
    "params": {
      "uuid": "<projectUuid>",
      "data": { "userJourneys": [{ ... full payload from 6e ... }] }
    }
  },
  {
    "order": 2,
    "scenarioName": "Register New Account",
    "scenarioId": "scenario-uuid",
    "tool": "Update_Functional_Node",
    "params": {
      "uuid": "<projectUuid>",
      "label": "Scenario",
      "id": "<scenario-uuid>",
      "data": { "isDesignGenerated": true },
      "citationId": [0],
      "citations": [{ "type": "document", "name": "skip", "inputText": "skip" }]
    }
  }
]
```

**Write protocol:**

1. Read `apicalls.json` from disk (or create `[]` if first scenario)
2. Append the `Bulk_Update_Design_Nodes` entry
3. Append the `Update_Functional_Node` entry
4. Write `apicalls.json` to disk
5. Log: `"[dry-run] Queued 2 calls for '{scenarioName}' (total: {N} calls in apicalls.json)"`

> **⛔ Read-append-write, not overwrite.** Like `existingcomponents.json`,
> each scenario appends to the existing array. Never overwrite the file.

**What dry-run mode does NOT do:**
- Does NOT call `Bulk_Update_Design_Nodes`
- Does NOT call `Update_Functional_Node`
- Does NOT mark scenarios as processed (`isDesignGenerated` stays `false`)
- Does NOT update flow/page registries with real IDs (no upsert response
  to read from) — registries are updated with **names only** (no `id`
  field), which is sufficient for local dedup

### 6h. Post-upsert: update Flow & Page registries (⛔ PERSIST TO DISK)

> **⛔ GATE 5 — See [references/blocking-gates.md](references/blocking-gates.md#gate-5-registry-disk-persistence-post-upsert)**
>
> **Write registries to disk after EVERY scenario.** These are the
> cross-session persistence mechanism.
>
> **In dry-run mode:** still update registries, but with names only
> (no `id` field since there's no upsert response). This enables
> flow/page dedup for subsequent scenarios in the same run.

For each new flow/page in the payload:
1. **Live modes:** Fetch real ID from bulk upsert response (or
   `Design_Graph_Search`)
2. **Dry-run mode:** Use name only, set `id: "pending"`
3. Add to registry: Flow → `existingflows.json` keyed by
   `"{name}|{modality}"`, Page → `existingpages.json` keyed by
   `"{name}|{pageType}"`
4. Write to disk and verify

See [reusability.md § Registry Update Timing](references/reusability.md)
for the full protocol.

### 6i. Mark scenario as processed (live modes only)

> **⛔ GATE 7 — See [references/blocking-gates.md](references/blocking-gates.md#gate-7-scenario-processed-marker)**
>
> **Skip in `dry-run` mode** — the call is already queued in
> `apicalls.json` (Step 6g-dry).

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

### 6j. Error handling

| Failure Point          | `confirm` mode                             | `auto` / `outcome` mode                        | `dry-run` mode                      |
| ---------------------- | ------------------------------------------ | ----------------------------------------------- | ----------------------------------- |
| Entire bulk call fails | Retry once; if still fails, report to user | Retry once; log error, skip scenario, continue  | N/A — no API calls made             |
| Partial failure        | Log failed nodes, report to user           | Log failed nodes, continue                      | N/A                                 |
| File write fails       | Report to user                             | Log error, skip scenario, continue              | Report to user — payload data lost  |

In `auto` and `outcome` mode, collect errors in `failedScenarios`
list for the final summary (or per-outcome summary in `outcome` mode).

---

## Step 7: Output Summary

**Processing Summary**

| Metric           | Count |
| ---------------- | ----- |
| Total scenarios  | N     |
| Processed        | N     |
| Skipped (errors) | N     |

**Dry-run Summary** (`dry-run` mode only)

```
Dry-run complete — no API calls were made.

  Scenarios processed: {N}
  API calls queued:    {N} (in apicalls.json)
    Bulk_Update_Design_Nodes: {N}
    Update_Functional_Node:   {N}

  File: apicalls.json ({size})

  To execute: review apicalls.json, then re-run in `auto` mode
  to make the actual API calls. Or use an external script to
  replay the queued calls from the file.
```

> **In dry-run mode:** scenarios are NOT marked as processed. Re-running
> in `auto` mode will process the same scenarios and make real API calls.
> The `apicalls.json` file is preserved for reference/audit.

**Failed Scenarios** (all modes, only if errors)

| Scenario | Error |
| -------- | ----- |
| Name     | ...   |

> Failed scenarios remain `isDesignGenerated=false` and will be picked
> up on the next run.

---

**Design Graph Generated (by Modality)**

| Modality  | UserJourneys | Flows | Pages | Templates (New/Reused) | Components (New) |
| --------- | ------------ | ----- | ----- | ---------------------- | ---------------- |
| web       | N            | N     | N     | N / N                  | N                |
| **Total** | N            | N     | N     | N / N                  | N                |

**Component Reuse Statistics**

| Metric                        | Count |
| ----------------------------- | ----- |
| New GLOBAL components created | N     |
| New DOMAIN components created | N     |
| New PAGE components created   | N     |
| Existing components reused    | N     |

**Reuse Efficiency:** `(Reused / Total Components) x 100`%

**Next Steps**

- Refine design nodes with additional properties
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design

---

# REFERENCE

## What makes this skill different from `generate-design`

| Aspect              | `generate-design`                 | `generate-design-from-ui`            |
| ------------------- | --------------------------------- | ------------------------------------ |
| Component source    | Inferred from action descriptions | Read from actual JSX/TSX code        |
| Component hierarchy | Guessed from action grouping      | Derived from real import tree        |
| Props & states      | Inferred                          | Extracted from TypeScript interfaces |
| Realism             | Approximate                       | Matches actual UI implementation     |

Both skills share: scenario selection, component registry,
`Bulk_Update_Design_Nodes`, `existingcomponents.json` workflow.

## Cost per scenario

~**8-12 tool calls per scenario** (including UI code reading).
For 50 scenarios: 400-600 calls. Plan for multiple sessions.

## When NOT to use

- **No functional graph yet** — run `/breeze:generate-functional-from-ui`
  first to create scenarios
- **No UI repo available** — use `/breeze:generate-design` which works
  from functional graph alone
- **Backend-only repos** — this skill reads frontend UI code only
- **Figma-first workflow** — use `/breeze:analyze-design`

## See also

- `/breeze:generate-design` — design graph from functional graph (no UI code)
- `/breeze:generate-functional-from-ui` — functional graph from UI code
- `/breeze:create-page` — generate UI code from design nodes
- `/breeze:analyze-design` — analyze Figma designs
