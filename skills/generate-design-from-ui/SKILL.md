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
than one-agent-per-scenario. Up to 3 outcomes run in parallel.

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
- **Per-scenario payload files** in `{uiRepo}/.breeze-output/` for audit

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
7. Set `OUTPUT_BASE = {uiRepo}/.breeze-output`
8. Ensure `.breeze-output/` is in the target repo's `.gitignore`

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
| `auto`    | Sub-agents execute full pipeline; up to 3 outcomes in parallel |
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

## Step 2: Build Outcome Queue

### 2a. Build non-human outcome blocklist

> **HARD STOP: Build this BEFORE any processing.**

1. Call `Get_all_personas(uuid: "<projectUuid>")`
2. Identify non-human personas: `System`, `External System`
3. For each non-human persona, call
   `Get_all_outcomes_for_a_persona_id(uuid, personaId: "<id>")`
4. Collect all outcome IDs into `blockedOutcomeIds`
5. If zero personas → STOP, tell user to run
   `/breeze:generate-functional-from-ui` first
6. Log: `"Blocklist built: {N} non-human outcome(s) excluded"`

### 2b. Build the outcome queue

1. For each **human persona**, call
   `Get_all_outcomes_for_a_persona_id(uuid, personaId)`
2. For each outcome, fetch its scenarios:
   `Get_all_scenarios_for_a_outcome_id(uuid, outcome_id, page, limit)`
   Paginate until all fetched. Filter out `isDesignGenerated == true`.
3. For each scenario, fetch steps/actions:
   `Get_all_steps_actions_for_a_scenario_id(uuid, parameters0_Value: scenarioId)`
4. Skip outcomes with zero unprocessed scenarios
5. Build the queue:

```json
[
  {
    "outcomeId": "...",
    "outcomeName": "Authentication",
    "personaName": "End User",
    "scenarios": [
      {
        "id": "scenario-uuid",
        "name": "Login with Email",
        "stepsActions": [{ "stepId": "...", "stepName": "...", "actions": [...] }]
      }
    ]
  }
]
```

### 2c. Show the queue to user

```
Outcome Queue ({N} outcomes, {M} total scenarios):

  1. [End User] Authentication — 5 scenarios
  2. [End User] Search — 8 scenarios
  3. [Admin] User Management — 4 scenarios

Processing mode: {mode}
```

### 2d. Write Checkpoint

Write `{OUTPUT_BASE}/design-progress.json` with **scenario-level
tracking** (like `entrypoints.json` in the functional skill):

```json
{
  "project": "<repo name>",
  "projectUuid": "<uuid>",
  "framework": "<framework>",
  "uiRepo": "<path>",
  "modalities": ["WEB"],
  "processingMode": "<auto|outcome|dry-run>",
  "blockedOutcomeIds": ["..."],
  "totalOutcomes": 5,
  "totalScenarios": 28,
  "outcomes": [
    {
      "outcomeId": "...",
      "outcomeName": "Authentication",
      "personaName": "End User",
      "status": "pending",
      "scenarios": [
        {
          "id": "scenario-uuid-1",
          "name": "Login with Email",
          "status": "pending",
          "payloadPath": null,
          "flowsCreated": 0,
          "pagesCreated": 0,
          "componentsCreated": 0,
          "error": null,
          "completedAt": null
        },
        {
          "id": "scenario-uuid-2",
          "name": "Register New Account",
          "status": "pending",
          "payloadPath": null,
          "flowsCreated": 0,
          "pagesCreated": 0,
          "componentsCreated": 0,
          "error": null,
          "completedAt": null
        }
      ]
    }
  ],
  "completed": [],
  "remaining": ["outcome-uuid-1", "outcome-uuid-2"],
  "failed": [],
  "reconciliationDone": false
}
```

> **Scenario status values:** `pending` → `completed` | `failed`
>
> The sub-agent writes a `results_{outcomeName_slug}.json` manifest
> after processing, which the parent reads to update scenario-level
> status in the checkpoint.

---

## Step 3: Per-Outcome Sub-Agent Loop

### 3-pre. Resolve Component Registry Path

Check if `existingcomponents.json` exists in the plugin working
directory (may have been created by `/breeze:generate-component-registry`
or prior design runs).

- **Exists and non-empty** → set `componentRegistryPath` to its
  absolute path. Sub-agents will use it as a classification cache
  (skip re-classifying known components).
- **Missing or empty** → set `componentRegistryPath` to `"none"`.
  Sub-agents classify everything from scratch.

> **Recommended workflow:** Run `/breeze:generate-component-registry`
> first to pre-populate the registry. This makes design generation
> faster (cached classifications) and more consistent (same naming
> across outcomes processed in parallel).

### 3a. Spawn Sub-Agents (up to 3 in parallel)

For each outcome in the queue (or batch of up to 3 in `auto`/`dry-run` mode):

**Pre-flight:**
1. Skip if outcome already in `completed`
2. Skip if `outcomeId` in `blockedOutcomeIds`

**Render sub-agent prompt:**

Read the template at `references/design-structuring-agent.prompt.md`
and substitute:

| Placeholder | Value |
|---|---|
| `{{outcome_id}}` | outcome UUID |
| `{{outcome_name}}` | outcome name |
| `{{persona_name}}` | persona name |
| `{{scenarios_json}}` | JSON array of scenarios with stepsActions |
| `{{modalities}}` | comma-separated: `"WEB"` or `"WEB", "MOBILE"` |
| `{{framework}}` | detected framework from Phase 0a |
| `{{repo_root_absolute_path}}` | absolute UI repo path |
| `{{project_uuid}}` | from `.breeze.json` |
| `{{output_dir}}` | `{OUTPUT_BASE}/` |
| `{{skill_references_path}}` | absolute path to references directory |
| `{{component_registry_path}}` | absolute path to `existingcomponents.json`, or `"none"` |
| `{{mode}}` | `live` or `dry-run` |

**Spawn:**

```
Agent(
  subagent_type: "breeze:design-from-ui-structuring-agent",
  description: "Design outcome: {outcomeName} ({N} scenarios)",
  prompt: <rendered template>
)
```

For `auto`/`dry-run` mode, spawn up to 3 agents in a single message.

### 3b. Handle Sub-Agent Response

Parse the summary line, then read the results manifest for details.

**Step 1: Parse summary line:**

| Prefix | Action |
|---|---|
| `OK` | All scenarios succeeded |
| `PARTIAL` | Some scenarios failed — check manifest |
| `BUDGET` | Sub-agent hit ~75% context budget — some scenarios still `pending`. Treat outcome as `PARTIAL` for checkpoint; pending scenarios need re-processing on resume |
| `FAIL` | Outcome-level failure (e.g., could not read target page) |

**Step 2: Read results manifest:**

The sub-agent writes `{OUTPUT_DIR}/results_{outcome_slug}.json`:
```json
{
  "outcomeId": "...",
  "outcomeName": "Authentication",
  "scenarios": [
    {
      "id": "scenario-uuid-1",
      "name": "Login with Email",
      "status": "completed",
      "payloadPath": ".breeze-output/design_login-with-email.json",
      "flowsCreated": 2,
      "pagesCreated": 3,
      "componentsCreated": 12,
      "completedAt": "2026-08-10T..."
    },
    {
      "id": "scenario-uuid-2",
      "name": "Social Login",
      "status": "failed",
      "error": "FAIL_UPSERT · http: 422",
      "payloadPath": ".breeze-output/design_social-login.json"
    }
  ],
  "totals": {
    "scenarios": 5,
    "succeeded": 4,
    "failed": 1,
    "flows": 8,
    "pages": 10,
    "components": 34
  }
}
```

**Step 3: Merge into checkpoint:**

For each scenario in the manifest, update the matching entry in
`design-progress.json` with status, stats, payloadPath, error.

### 3c. Update Checkpoint

After each outcome (or batch):
- `OK` → move outcome from `remaining[]` to `completed[]`
- `PARTIAL` → move to `completed[]` (failed scenarios stay `failed` in checkpoint)
- `BUDGET` → keep outcome in `remaining[]` with per-scenario status updated (completed scenarios marked done, pending scenarios stay `pending` for re-processing on resume)
- `FAIL` → move to `failed[]`
- Update every scenario's status/stats from the results manifest
- Write checkpoint to disk
- Log progress: `"[{completed}/{total}] Outcome: {name} — {succeeded}/{scenarioCount} scenarios"`

### 3d. Outcome Mode: Pause Between Outcomes

After each outcome completes (only in `outcome` mode):

```
--- OUTCOME COMPLETE: "{outcomeName}" ---
  Scenarios: {succeeded}/{total} succeeded
  Failed: {N}
  Flows: {N}, Pages: {N}, Components: {N}

  Next outcome: [{persona}] {name} ({N} scenarios)

Continue to next outcome? (continue/stop/skip)
```

| Response | Action |
|---|---|
| continue/y | Proceed |
| stop/n | Exit, go to reconciliation |
| skip | Skip next, show the one after |

### 3e. Budget Management

Tune the batch size down to 1 if you are near your context budget or
hitting rate limits.

When context reaches ~75%, flush checkpoint and stop:
```
Context budget reaching limit. Progress saved.

  Completed: {N} outcomes ({M} scenarios)
  Remaining: {N} outcomes ({M} scenarios)

Resume: /breeze:generate-design-from-ui continue from {uiRepo}
```

---

## Step 4: Reconciliation Pass

> **Run AFTER all outcomes complete (or on resume when remaining = 0).**

Since sub-agents run in parallel and independently create design nodes,
check for edge-case duplicates. The backend deduplicates by
`projectUuid + name` (case-insensitive), so most cases are handled.
This catches near-name mismatches across parallel agents.

### 4a. Flow Reconciliation

1. `Get_all_Design_By_Label(uuid, label: "Flow")` (paginate)
2. Group by `(name, modality)` — find groups with >1 entry
3. True duplicates → merge (keep one, reassign edges, delete other)
4. Near-duplicates → log for user review

### 4b. Page Reconciliation

Group by `(name, pageType)`, merge true duplicates.

### 4c. Component Reconciliation

Group by `name`, merge true duplicates.

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
Payloads:  {OUTPUT_BASE}/design_*.json
Manifests: {OUTPUT_BASE}/results_*.json

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
