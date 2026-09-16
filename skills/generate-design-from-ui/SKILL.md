---
name: generate-design-from-ui
description: >
  Generate design graph (UserJourney, Flow, Page, Component) from
  functional graph scenarios, enriched by reading the actual frontend UI
  codebase. Scenario->UserJourney, Step->Flow/Page, Action->Component.
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
+-- User Journey  (1:1 with functional Scenario)
|   +-- Flow      (a distinct path/way to complete the journey -- detected from UI)
|       +-- Page   (screens needed to complete the flow -- one or many)
|           +-- Component (UI elements: atoms, molecules, organisms, templates)
```

This skill uses a **sub-agent architecture** with **one agent per
outcome**. The parent orchestrates: project setup, outcome discovery,
checkpoint management, and reconciliation. Each sub-agent
(`breeze:design-from-ui-structuring-agent`) handles one outcome end-to-end:
grep discovery, UI code reading, component classification, payload building,
and MCP upserting for ALL scenarios in that outcome.

**Why outcome-per-agent?** Scenarios within an outcome almost always
share the same target pages. The agent reads page files once and
processes all scenarios against that shared context — far more efficient
than one-agent-per-scenario. Up to 5 outcomes run in parallel.

## How to Create the Design Ontology — Full Workflow

The design ontology (UserJourney → Flow → Page → Component) sits on top
of the functional graph. This skill requires a **frontend UI repo** — it
reads actual code for accurate component discovery.

| Step | Skill | What it does | Prerequisites |
|------|-------|-------------|---------------|
| 1 | `/breeze:setup-project` | Link Breeze project, create `.breeze.json` | None |
| 2 | `/breeze:generate-functional-from-ui` | Build functional graph (Persona → Outcome → Scenario → Step → Action) from the UI codebase | Step 1 |
| 3 | `/breeze:generate-component-registry` | Pre-scan UI repo, classify all components (ATOM/MOLECULE/ORGANISM/TEMPLATE), write `existingcomponents.json` | Step 1 + UI repo |
| 4 | **`/breeze:generate-design-from-ui`** ← this skill | Generate design graph from functional graph + UI code. Uses component registry cache from Step 3 for faster, consistent classification | Steps 2 + 3 |
| 5 | `/breeze:analyze-design-deviations` *(optional)* | Compare generated design graph components against Figma design system — find drift, missing components, type mismatches | Step 4 + Figma export |

> **Step 3 is optional but strongly recommended.** Without it, this skill
> classifies every component from scratch per outcome. With it,
> classifications are cached and consistent across parallel sub-agents.

## Resources

**Reference documents are read by the sub-agent, not the parent.**

| Reference | Used by | What it covers |
|---|---|---|
| **[references/flow-discovery-patterns.md](references/flow-discovery-patterns.md)** | Sub-agent | Grep patterns, Type A/B classification |
| **[references/atomic-design-rules.md](references/atomic-design-rules.md)** | Sub-agent | Component classification (incl. Angular) |
| **[references/component-rules.md](references/component-rules.md)** | Sub-agent | Naming, composition, reuse |
| **[references/design-ontology.md](references/design-ontology.md)** | Sub-agent | Entity fields, linkage |
| **[references/reusability.md](references/reusability.md)** | Sub-agent | Registry dedup, multi-parent linking |
| **[references/mcp-tools.md](references/mcp-tools.md)** | Sub-agent | MCP parameter naming |
| **[references/pitfalls.md](references/pitfalls.md)** | Sub-agent | Common mistakes checklist |
| **[references/blocking-gates.md](references/blocking-gates.md)** | Sub-agent | Validation gates |
| **[references/design-structuring-agent.prompt.md](references/design-structuring-agent.prompt.md)** | Parent | Per-call input template |

## Inputs

- **UI repo path** -- if provided as argument (`$ARGUMENTS`), use it
  directly; otherwise resolved in Phase -1
- **`.breeze.json`** -- for `apiBase`, `projectUuid`
- **Functional graph** -- scenarios, steps, actions (fetched per outcome)

## Outputs

- **Design graph** updated via `Bulk_Update_Design_Nodes` (called by sub-agents)
- **`design-progress.json`** -- checkpoint for multi-session resume
- **Per-outcome payload files** in `{uiRepo}/design_output/` for audit -- each
  file contains full functional linkage: `outcomeId`, `personaId`,
  `personaName` at top level; `scenarioId`, `outcomeId`, `personaId`,
  `personaName`, `outcomeName` on every UserJourney; `stepIds` on
  flows/pages; `actionIds` on components

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing or incomplete, tell the user to run `/breeze:setup-project`
3. Extract `projectUuid`
4. Read `designGraph.platform` from `.breeze.json`:

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

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes (multi-platform) | Unique slug for this platform. Used to scope registry files, output dirs, and checkpoint. |
| `suffix` | Yes (multi-platform) | Appended to every design node name before upserting. Supplementary visual indicator — the backend now deduplicates by `projectUuid + name + platform`, so the `platform` field is the primary isolation mechanism. |
| `personas` | Yes (multi-platform) | Persona names that belong to THIS platform. Only outcomes from these personas are processed. Outcomes from other personas are excluded — they belong to another platform's design graph. |

- If `designGraph.platform` exists → set `PLATFORM_ID`, `APP_SUFFIX`,
  and `PLATFORM_PERSONAS`.
- If absent → set `PLATFORM_ID = ""`, `APP_SUFFIX = ""`,
  `PLATFORM_PERSONAS = null` (no filtering — single-platform project).

> **Why platform isolation matters:** A single Breeze project may host
> design graphs for multiple applications (e.g., customer portal + admin
> dashboard, or web + mobile). Without isolation, context leaks between
> platforms through six vectors:
>
> | Leak vector | What goes wrong |
> |---|---|
> | **Backend name dedup** | Without `platform` field, "Login Page" from Web merges with "Login Page" from Mobile into one node |
> | **Shared registries** | Sub-agent reuses Platform A's component when building Platform B |
> | **Shared persona outcomes** | Sub-agent processes outcomes from both platforms in one run |
> | **MCP queries** | `Get_all_Design_By_Label` returns nodes from both platforms; sub-agent links to wrong one |
> | **Reconciliation** | Merges same-name nodes across platforms (destroys both) |
> | **Checkpoint** | Progress file mixes scenarios from both platforms |
>
> The `platform` config prevents ALL of these by:
> 1. **Name suffixing** — `APP_SUFFIX` makes names unique across platforms
> 2. **Persona scoping** — only outcomes from `PLATFORM_PERSONAS` are queued
> 3. **Registry scoping** — each platform gets its own registry files
> 4. **Output scoping** — each platform gets its own output dir and checkpoint
> 5. **MCP query filtering** — sub-agents filter results by suffix before reusing
> 6. **Reconciliation scoping** — only merges nodes with matching suffix

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). Pass `.breeze.json`'s `projectUuid` value as `uuid`.
>
> **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter
> MUST be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or
> `scenario_id`).

---

## Phase -1 -- Resolve the target UI repo

1. Check if user passed a path via `$ARGUMENTS` -- validate it exists
   and looks like a frontend repo
2. Check `.breeze.json` field `targetRepos.frontend`
3. Check if cwd looks like a frontend repo
4. Ask the user -- single prompt: "Which UI repo do you want me to
   read? Provide an absolute path."
5. Persist the chosen path to `.breeze.json`:
   ```json
   { "targetRepos": { "frontend": "/abs/path/to/ui-repo" } }
   ```
6. If path has no frontend router file, stop and inform user
7. Set `OUTPUT_BASE`:
   - If `PLATFORM_ID` is non-empty: `{uiRepo}/design_output/{PLATFORM_ID}`
   - Otherwise: `{uiRepo}/design_output`
8. Ensure `design_output/` is in the target repo's `.gitignore`

> **Frontend repo detection:** A valid frontend repo has `package.json`
> AND at least one of: `src/router/`, `src/routes/`, `app/routes`,
> `pages/`, `src/pages/`, `app/`, or React/Vue/Angular Router imports.

---

## Phase 0 -- Configuration

### 0a. Detect Framework

Look for framework signals in the UI repo:

- React Router: `<Route`, `createBrowserRouter`, `useRoutes`
- Vue 2/3: `src/router/index.{js,ts}`
- Next.js: `pages/` or `app/` directory
- Angular: `*-routing.module.ts` or `app.routes.ts`
- Nuxt: `pages/` with `.vue` files
- SvelteKit: `src/routes/`

Record the detected framework for sub-agent injection.

### 0b. Processing Mode

Ask user which processing mode to use:

| Mode      | Description                                                |
| --------- | ---------------------------------------------------------- |
| `auto`    | Sub-agents execute full pipeline; up to 5 outcomes in parallel |
| `outcome` | Auto within each outcome, pause between outcomes for review |
| `dry-run` | Sub-agents write payloads to disk only; no MCP mutations   |

Default: `auto` if user doesn't specify.

In `auto` mode:

- **CRITICAL -- DO NOT STOP OR PAUSE DURING AUTO MODE.** Process ALL
  outcomes without stopping to ask "should I continue?". The user has
  given blanket consent. The ONLY acceptable reason to stop is an
  unrecoverable error that prevents ALL further processing.

In `outcome` mode:

- Within each outcome: sub-agent runs all scenarios automatically
- Between outcomes: STOP and show outcome summary, wait for user input

### 0c. Detect & Confirm Modalities

**Auto-detect the primary modality from the repo:**

| Repo Signal                                                        | Detected Modality         |
| ------------------------------------------------------------------ | ------------------------- |
| React Router, Next.js, Nuxt, Vue Router, Angular Router, SvelteKit | `WEB`                     |
| React Native, `react-native` in package.json, `expo`               | `MOBILE`                  |
| Electron, `electron` in package.json, Tauri                        | `DESKTOP`                 |
| Ionic, Capacitor                                                   | `MOBILE` + `WEB` (hybrid) |

1. Detect the primary modality
2. Present and ask if user wants additional modalities
3. Store confirmed modalities list

---

## Step 1: Check for Existing Checkpoint (Resume Support)

Look for `{OUTPUT_BASE}/design-progress.json`.

- **If it exists and has remaining outcomes** -> show detailed status
  and offer to resume:

  ```
  Found existing checkpoint:

  Outcomes:
    Completed: {N} outcomes
    Remaining: {N} outcomes
    Failed:    {N} outcomes

  Scenarios:
    Completed: {N}/{total} scenarios
    Failed:    {N} scenarios
    Pending:   {N} scenarios

  Last completed: [{persona}] {outcomeName}
  Next pending:   [{persona}] {outcomeName} ({N} scenarios)

  Resume from where you left off? (y/n)
  ```

  Yes -> For remaining outcomes, re-fetch steps/actions for their
  scenarios (they may have changed since last session), then skip
  to Step 3. For failed outcomes, ask: "Retry failed outcomes too? (y/n)"

  No -> proceed fresh (rebuild checkpoint).

- **Doesn't exist** -> proceed to Step 2.

> **Partial outcome resume:** If an outcome was `PARTIAL` (some scenarios
> succeeded, some failed), the checkpoint has per-scenario status. On
> resume, only re-process the failed scenarios within that outcome —
> pass only the failed scenarios in `SCENARIOS` to the sub-agent.

---

## Step 2: Persona Discovery & Blocklist

### 2a. Fetch persona list and build blocklist

> **HARD STOP: Build this BEFORE any processing.**
>
> Only fetch the **persona list** here — NOT all outcomes for all
> personas. Outcomes are fetched one persona at a time in Step 3.

1. Call `Get_all_personas(uuid: "<projectUuid>")`
2. Classify each persona into one of three buckets:
   - **Blocked (non-human):** `System`, `External System` (always blocked)
   - **Blocked (cross-platform):** If `PLATFORM_PERSONAS` is set, block
     every human persona whose name is NOT in `PLATFORM_PERSONAS`
   - **Allowed:** human personas that pass both filters
3. Build `allowedPersonas` list (ordered) and `blockedPersonaIds` set
4. If zero **allowed** personas → STOP, tell user to check
   `designGraph.platform.personas` in `.breeze.json` or run
   `/breeze:generate-functional-from-ui` first
5. Log:
   ```
   Persona discovery:
     Total: {N} personas
     Allowed: {names} ({N})
     Blocked (non-human): {names} ({N})
     Blocked (cross-platform): {names} ({N})
   ```

### 2b. Show processing plan to user

```
Processing Plan:
Platform: {PLATFORM_ID or "single-platform (no isolation)"}
Mode: {mode}

Personas to process (in order):
  1. End User
  2. Admin
  3. Customer Support
  ...

Each persona's outcomes will be fetched and processed in batches
of up to 5 parallel sub-agents before moving to the next persona.
```

### 2c. Write Checkpoint

Write `{OUTPUT_BASE}/design-progress.json`:

```json
{
  "project": "<repo name>",
  "projectUuid": "<uuid>",
  "platformId": "<platform slug or empty>",
  "appSuffix": "<suffix or empty>",
  "platformPersonas": ["End User", "Admin"],
  "framework": "<framework>",
  "uiRepo": "<path>",
  "modalities": ["WEB"],
  "processingMode": "<auto|outcome|dry-run>",
  "allowedPersonas": [
    { "id": "persona-uuid-1", "name": "End User", "status": "pending" },
    { "id": "persona-uuid-2", "name": "Admin", "status": "pending" }
  ],
  "currentPersonaIndex": 0,
  "personas": {}
}
```

> The `personas` object is populated progressively — one persona at a
> time in Step 3. This avoids fetching 3,000+ scenarios upfront.

---

## Step 3: Per-Persona Processing Loop

> **This is the main loop.** Process one persona at a time. For each
> persona: fetch outcomes → batch into groups of up to 5 → spawn
> parallel sub-agents → wait → update checkpoint → next batch →
> when all outcomes done → next persona.

### 3a. Fetch outcome list for current persona

> **Only fetch the outcome list here — NOT scenarios or steps/actions.**
> Sub-agents fetch their own scenarios and steps/actions to save parent
> context. The parent only needs outcome IDs and names for dispatching.

For the current persona in `allowedPersonas`:

1. Call `Get_all_outcomes_for_a_persona_id(uuid, personaId)`
2. For each outcome, call `Get_all_scenarios_for_a_outcome_id` but
   **only to get scenario count and filter `isDesignGenerated`** —
   do NOT fetch steps/actions (sub-agent does that)
3. Skip outcomes with zero unprocessed scenarios
4. Build the persona's outcome list:

```json
{
  "personaId": "...",
  "personaName": "End User",
  "outcomes": [
    {
      "outcomeId": "...",
      "outcomeName": "Authentication",
      "scenarioCount": 5,
      "scenarioIds": ["uuid-1", "uuid-2", "uuid-3", "uuid-4", "uuid-5"]
    }
  ]
}
```

5. Update checkpoint — add this persona's outcomes:

```json
{
  "personas": {
    "End User": {
      "personaId": "persona-uuid-1",
      "status": "in_progress",
      "totalOutcomes": 12,
      "outcomes": [
        {
          "outcomeId": "...",
          "outcomeName": "Authentication",
          "status": "pending",
          "scenarioCount": 5
        }
      ],
      "completed": [],
      "remaining": ["outcome-uuid-1", "outcome-uuid-2"],
      "failed": []
    }
  }
}
```

6. Log:
   ```
   Persona: End User
     Outcomes: {N}
     Processing in batches of 5...
   ```

### 3b. Batch and spawn sub-agents

Take up to 5 outcomes from the persona's `remaining` list and spawn
sub-agents in parallel:

```
Batch 1/4: [Authentication (5 scenarios), Search (8 scenarios), Cart (3 scenarios)]
  Spawning 3 sub-agents...
```

For each outcome in the batch, render the sub-agent prompt and spawn
(same as before — see sub-agent template placeholders).

### 3c. Collect results and update checkpoint

After all agents in the batch complete:

1. Read each agent's results manifest
2. Update per-scenario status in the checkpoint
3. Move completed outcomes from `remaining` to `completed`
4. Move failed outcomes to `failed`
5. Write checkpoint to disk
6. Log batch summary:
   ```
   Batch 1/4 complete:
     ✅ Authentication — 5/5 scenarios
     ✅ Search — 7/8 scenarios (1 failed)
     ✅ Cart — 3/3 scenarios
   ```

### 3d. Next batch or next persona

- **More outcomes remaining for this persona?** → go to 3b (next batch)
- **All outcomes done for this persona?** → mark persona as `completed`
  in checkpoint, log summary, advance `currentPersonaIndex`
- **More personas remaining?** → go to 3a (fetch next persona's outcomes)
- **All personas done?** → proceed to Step 4 (reconciliation)

```
Persona complete: End User
  Outcomes: 12/12 completed
  Scenarios: 44/45 succeeded, 1 failed
  
Next persona: Admin (2/5)
  Fetching outcomes...
```

### 3e. Resume from checkpoint

If `design-progress.json` exists with in-progress data:

1. Find `currentPersonaIndex` — resume from that persona
2. For the current persona, check `remaining` outcomes
3. For partially processed outcomes (status = `PARTIAL`), re-send
   ALL scenario metadata but mark which ones need re-processing
4. Skip fully completed personas
5. Log:
   ```
   Resuming from checkpoint:
     Personas completed: {N}/{total}
     Current persona: {name}
     Remaining outcomes: {N}
   ```

> **Scenario status values:** `pending` → `completed` | `failed`
>
> The sub-agent writes all scenario data into the outcome file
> (`design_{outcome_slug}.json`). Each scenario entry has a `status`
> field. The parent reads this file to update scenario-level status
> in the checkpoint.

---

## Step 3 Reference: Registry Paths, Sub-Agent Template, Response Handling

### Registry Paths (resolve once at start)

All registries are **platform-scoped** when `PLATFORM_ID` is set:

| Registry | Single-platform path | Multi-platform path |
|---|---|---|
| Components | `existingcomponents.json` | `existingcomponents.{PLATFORM_ID}.json` |
| Flows | `existingflows.json` | `existingflows.{PLATFORM_ID}.json` |
| Pages | `existingpages.json` | `existingpages.{PLATFORM_ID}.json` |

> **UJ duplicate detection:** No separate registry file. Sub-agents
> scan `OUTPUT_DIR/design_*.json` payload files for `ujName` values.

**Component registry** (pre-populated by `/breeze:generate-component-registry`):
- **Exists and non-empty** → set `componentRegistryPath` to absolute path.
- **Missing or empty** → STOP. Run `/breeze:generate-component-registry`
  first. Components must come from the registry (Critical Rule 16).

**Page registry** (`existingpages.json` / scoped variant):
- **Exists and non-empty** → set `pageRegistryPath` to absolute path.
- **Missing or empty** → set `pageRegistryPath` to `"none"`.

> **⛔ Component registry is REQUIRED.** The sub-agent selects
> components from the registry — it does not classify from scratch.
> Without a pre-populated registry, the sub-agent has nothing to
> select from. Run `/breeze:generate-component-registry` first.

### Sub-Agent Prompt Template

Read `references/design-structuring-agent.prompt.md` and substitute:

| Placeholder | Value |
|---|---|
| `{{outcome_id}}` | outcome UUID |
| `{{outcome_name}}` | outcome name |
| `{{persona_name}}` | persona name |
| `{{persona_id}}` | persona UUID |
| `{{modalities}}` | comma-separated: `"WEB"` or `"WEB", "MOBILE"` |
| `{{framework}}` | detected framework from Phase 0a |
| `{{repo_root_absolute_path}}` | absolute UI repo path |
| `{{project_uuid}}` | from `.breeze.json` |
| `{{output_dir}}` | `{OUTPUT_BASE}/` |
| `{{skill_references_path}}` | absolute path to references directory |
| `{{component_registry_path}}` | absolute path to `existingcomponents.json`, or `"none"` |
| `{{page_registry_path}}` | absolute path to `existingpages.json`, or `"none"` |
| `{{mode}}` | `live` or `dry-run` |
| `{{app_suffix}}` | `APP_SUFFIX` (e.g., `" [Source Web]"` or `""`) |
| `{{platform_id}}` | `PLATFORM_ID` (e.g., `"source-web"` or `""`) |

### Sub-Agent Response Handling

**Parse summary line:**

| Prefix | Action |
|---|---|
| `OK` | All scenarios succeeded |
| `PARTIAL` | Some scenarios failed — check outcome file |
| `BUDGET` | Hit context budget — pending scenarios need re-processing |
| `FAIL` | Outcome-level failure |

**Read outcome file** (`{OUTPUT_DIR}/design_{outcome_slug}.json`):

The outcome file contains all scenario data keyed by scenario ID.
Each entry has `status`, `stats`, `payload`, and `validation` fields.

```
FOR each scenarioId, entry in file.scenarios:
  IF entry.status == "completed":
    → update checkpoint with entry.stats
  IF entry.status == "failed":
    → log entry.error
  IF entry.status == "pending":
    → keep in remaining for re-processing
```

**⛔ Hierarchy completeness check (parent-side guard):**

```
FOR each scenarioId, entry in file.scenarios WHERE entry.status == "completed":
  FOR each userJourney in entry.payload.userJourneys:
    IF userJourney.flows is empty → FAIL this scenario
    FOR each flow in userJourney.flows:
      IF flow.pages is empty → FAIL this scenario
      FOR each page in flow.pages:
        IF page.components is empty → FAIL this scenario
```

If any fails → mark as `failed` with `HIERARCHY_INCOMPLETE` error,
downgrade outcome to `PARTIAL`.

**Update checkpoint:**
- `OK` → mark persona's outcome as `completed`
- `PARTIAL` → mark `completed` (failed scenarios stay `failed`)
- `BUDGET` → keep outcome in `remaining` (pending scenarios stay `pending`)
- `FAIL` → mark as `failed`

### Outcome Mode: Pause Between Outcomes

In `outcome` mode only — after each outcome:

```
--- OUTCOME COMPLETE: "{outcomeName}" ---
  Scenarios: {succeeded}/{total}
  Next: [{persona}] {name} ({N} scenarios)
Continue? (continue/stop/skip)
```

### Budget Management

When parent context reaches ~75%, flush checkpoint and stop:
```
Context budget reaching limit. Progress saved.
  Personas completed: {N}/{total}
  Current persona: {name} — {N}/{M} outcomes done
Resume: /breeze:generate-design-from-ui continue from {uiRepo}
```

---

## Step 4: Reconciliation Pass

> **Run AFTER all outcomes complete (or on resume when remaining = 0).**

Since sub-agents run in parallel and independently create design nodes,
check for edge-case duplicates. The backend deduplicates by
`projectUuid + name + platform` (case-insensitive), so most cases are handled.
This catches near-name mismatches across parallel agents.

> **⛔ Platform scoping (critical):** When `APP_SUFFIX` is non-empty,
> reconciliation MUST only operate on nodes belonging to this platform.
> After fetching all nodes via `Get_all_Design_By_Label`, **filter to
> keep only nodes whose name ends with `APP_SUFFIX`** before grouping
> and merging. Never merge a node from this platform with a node from
> another platform — that destroys both graphs.

### 4a. Flow Reconciliation

1. `Get_all_Design_By_Label(uuid, label: "Flow")` (paginate)
2. **Filter:** keep only nodes matching this platform (name ends with
   `APP_SUFFIX`, or all nodes if `APP_SUFFIX` is empty)
3. Group by `(name, modality)` — find groups with >1 entry
4. True duplicates → merge (keep one, reassign edges, delete other)
5. Near-duplicates → log for user review

### 4b. Page Reconciliation

Filter to platform, then group by `(name, pageType)`, merge true
duplicates.

### 4c. Component Reconciliation

Filter to platform, then group by `name`, merge true duplicates.

### 4d. Record Results

Update checkpoint:
```json
{
  "reconciliationDone": true,
  "reconciliation": {
    "flowsMerged": 0,
    "pagesMerged": 0,
    "componentsMerged": 0,
    "nearDuplicatesFlagged": 2
  }
}
```

---

## Step 5: Output Summary

**Processing Summary**

| Metric              | Count |
| ------------------- | ----- |
| Total outcomes      | N     |
| Outcomes completed  | N     |
| Outcomes failed     | N     |
| Total scenarios     | N     |
| Scenarios completed | N     |
| Scenarios failed    | N     |

**Per-Outcome Breakdown**

```
  1. [End User] Authentication     5/5 scenarios  OK
  2. [End User] Search             7/8 scenarios  PARTIAL (1 failed)
  3. [Admin] User Management       4/4 scenarios  OK
  ...
```

**Design Graph Generated**

| Modality  | UserJourneys | Flows | Pages | Components |
| --------- | ------------ | ----- | ----- | ---------- |
| WEB       | N            | N     | N     | N          |
| **Total** | N            | N     | N     | N          |

**Reconciliation**

| Metric | Count |
|---|---|
| Flows merged | N |
| Pages merged | N |
| Components merged | N |

**Failed Scenarios** (only if errors)

| Outcome | Scenario | Error |
| ------- | -------- | ----- |
| Search  | Bulk Export | FAIL_UPSERT · http: 422 |

> Failed scenarios remain `isDesignGenerated=false` and will be
> retried on the next run.

**Dry-run Summary** (`dry-run` mode only)

```
Dry-run complete -- no MCP mutations were made.
Payload files in: {OUTPUT_BASE}/
Re-run in auto mode to execute.
```

**Checkpoint**

```
Progress:  {OUTPUT_BASE}/design-progress.json
Payloads:  {OUTPUT_BASE}/design_*.json (one per outcome, scenarios keyed by ID)

Resume: /breeze:generate-design-from-ui continue from {uiRepo}
```

**Next Steps**

- `/breeze:create-page` -- generate UI code from design nodes
- Export to Figma for visual design

---

# REFERENCE

## Architecture: Parent + Sub-Agent (Outcome-per-Agent)

```
Parent (this skill)              Sub-Agent (per outcome)
+---------------------------+    +-----------------------------+
| Guard, repo resolution    |    | Phase 1: Grep discovery     |
| Framework detection       |    |   (all scenarios at once)   |
| Outcome queue building    |    | Phase 2: Read UI code       |
| Checkpoint management     |--->|   (shared pages, read once) |
| Spawn sub-agents (1-3)    |    | Phase 3: Per-scenario loop  |
| Parse summary lines       |<---|   classify → build → upsert |
| Reconciliation            |    | Phase 4: Return summary     |
| Final summary             |    +-----------------------------+
+---------------------------+
```

**Why outcome-per-agent?**
- Scenarios in an outcome share pages — read once, process many
- Agent runs its own greps — no cache serialization overhead
- Far fewer agent spawns (5 outcomes vs 40 scenarios)
- Cross-scenario reuse is natural within the outcome
- Fresh context per outcome — no drift across outcomes

## What makes this different from `generate-design`

| Aspect | `generate-design` | `generate-design-from-ui` |
|---|---|---|
| Component source | Inferred from action descriptions | Read from actual code |
| Component hierarchy | Guessed from action grouping | Derived from real imports |
| Props & states | Inferred | Extracted from TypeScript |
| Architecture | Single agent | Outcome-per-agent + parallel |

## When NOT to use

- **No functional graph yet** -- run `/breeze:generate-functional-from-ui` first
- **No UI repo** -- use `/breeze:generate-design`
- **Backend-only repos** -- this skill reads frontend UI code only
- **Figma-first** -- use `/breeze:analyze-design`

## See also

- `/breeze:generate-design` -- design from functional graph (no UI code)
- `/breeze:generate-functional-from-ui` -- functional graph from UI code
- `/breeze:create-page` -- generate UI code from design nodes
- `/breeze:analyze-design` -- analyze Figma designs
