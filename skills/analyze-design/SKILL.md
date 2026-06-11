---
name: analyze-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from any
  input: Jira ticket, plain-text description, scenario references, or Figma
  wireframes. Builds requirement context, resolves matching functional graph
  scenarios/steps/actions, generates design nodes with component reuse, and
  optionally syncs results back to Jira. When a frontend UI repo is
  available, reads it to discover routes and navigation and split a scenario
  into multiple flows/pages. Use when: "analyze this design", "create design
  from this ticket", "generate design for these scenarios", user shares a
  Figma URL or Jira link, "design graph from requirement".
argument-hint: "[ui-repo-path]"
---

## Resources

- For functional graph node definitions (Outcome, Scenario, Step, Action), persona rules, action naming rules, and dedup decision matrix, read [references/functional-graph-rules.md](references/functional-graph-rules.md)
- For API tools, mapping rules, payload structures, bulk upsert format, component types, supportingComponents array, reusability patterns, and designSystemRef lookup tables, read [references/guide.md](../generate-design/references/guide.md)
- For atomic design theory, component type decision rules, hierarchy examples, full page breakdowns, and common mistakes, read [references/atomic-design-theory.md](../generate-design/references/atomic-design-theory.md)

---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

### Resolve UI repo (optional but strongly preferred)

When a frontend repo is available, this skill reads the codebase to discover
routes, deep links, and navigation so one scenario can be split into
**multiple flows and pages** (not just one-flow-one-page). If no repo can be
resolved, the skill proceeds without UI discovery.

Resolution order:

1. **`$ARGUMENTS`** — if the user passed a path, validate it exists
2. **`.breeze.json` → `targetRepos.frontend`** — use if set
3. **Current working directory** — autodetect if it looks like a frontend repo
4. **Ask the user once** — "Do you have a frontend UI repo I can read to
   enrich the design graph? Provide an absolute path, or say 'skip'."

A directory qualifies as a frontend repo when it has a `package.json` AND
at least one of: `src/router/`, `src/routes/`, `app/routes`, `pages/`,
`src/pages/`, `app/`, or a React/Vue/Angular/Svelte router import.

If resolved, persist to `.breeze.json`:

```json
{ "targetRepos": { "frontend": "/abs/path/to/ui-repo" } }
```

Record a boolean `uiRepoAvailable` used by Step 1.5 and Step 3b. If the user
says "skip" or no repo is found, set `uiRepoAvailable = false` and continue.

> **Parameter naming hint:** All Breeze MCP tools require the project ID
> parameter to be named **`uuid`** (NOT `projectId`, `projectid`, or
> `projectUuid`). When calling any Breeze MCP tool, pass the value from
> `.breeze.json`'s `projectUuid` field as the `uuid` argument. Using any other
> name will fail with `Required → at uuid`.
>
> **Scenario ID hint:** When calling
> `Get_all_steps_actions_for_a_scenario_id`, the scenario ID parameter MUST
> be named **`parameters0_Value`** (NOT `scenarioId`, `id`, or `scenario_id`).
> It maps to `filters[id][$eq]` on the backend. Using any other name fails
> with `Required → at parameters0_Value`.
>
> **Design-by-label hint:** When calling `Get_all_Design_By_Label`, pass
> the node label as **`label`** (e.g., `label: "Component"`), NOT as
> `parameters0_Value`. The `parameters0_Value` naming is specific to
> `Get_all_steps_actions_for_a_scenario_id` — do not generalize it. Using
> the wrong name fails with `Required → at label`.

---

## Step 0: Gather Input & Build Requirement Context

The user provides **any one (or more)** of the inputs below. A single input
is sufficient — do NOT ask for additional inputs if the user has already
provided one. Only ask if nothing was provided at all.

### 0a. Accepted Inputs

| Input                           | Example                                       | How to Fetch                                                                                                  |
| ------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| **A. Jira ticket** (link or ID) | `PROJ-123` or `https://…/browse/PROJ-123`     | `mcp__plugin_atlassian_atlassian__getJiraIssue` → extract summary, description, acceptance criteria, comments |
| **B. Plain-text description**   | User types the requirement directly           | Use as-is                                                                                                     |
| **C. Scenario reference**       | "create design for the login scenarios"       | Noted — resolved in Step 1                                                                                    |
| **D. Figma URL(s)**             | `figma.com/design/:fileKey/…?node-id=:nodeId` | Fetch via Figma MCP, then run `/breeze:visual-to-text` to extract functional description                      |

If **none** of the above are provided, ask the user for at least one.
If the user provides just one input, proceed with that — do not prompt for others.

### 0b. Fetch Raw Content

For each input provided:

1. **Jira ticket →** call `getJiraIssue` and capture:
   - Summary & description
   - Acceptance criteria / definition of done
   - Comments (latest 10)
   - Linked issues (may reveal related scenarios)

2. **Figma URL(s) →** process wireframes to extract functional descriptions:
   1. Extract fileKey and nodeId from each URL (convert `-` to `:` in nodeId)
   2. Call `get_design_context` (Figma MCP) to fetch the screenshot and design data
   3. Run the **`/breeze:visual-to-text`** skill on the fetched frames — this
      produces structured user stories (personas, outcomes, scenarios, steps,
      actions) describing the functional intent behind the visual design
   4. Capture the visual-to-text output as part of the requirement context —
      this gives you both the UI elements identified AND the functional intent
      they represent

3. **Plain-text description →** use verbatim

4. **Scenario reference →** hold for Step 1

### 0c. Build Requirement Context

Synthesize all fetched content into a single **Requirement Context** document.
This is the lens through which you will search the functional graph and
generate design nodes.

```
REQUIREMENT CONTEXT
───────────────────
Source:        [Jira PROJ-123 | User description | Figma frame "Login" | …]

Summary:       <1-2 sentence description of what the user needs>

Key Capabilities:
  - <capability 1> (e.g., "User can log in with email and password")
  - <capability 2> (e.g., "User can reset password via email link")
  - …

From Figma / visual-to-text (if available):
  Personas identified:
    - <persona>: <description>
  Scenarios identified:
    - <scenario name>: <brief description>
  UI Elements:
    - <element>: <purpose> (e.g., "Email input: captures user email")
  Functional Intent:
    - <step → action mapping from visual-to-text output>

Acceptance Criteria (from Jira, if available):
  - <criterion 1>
  - …

Key Terms for Search:
  - <term 1>, <term 2>, <term 3>, …
```

Present this context to the user for confirmation:
**"Here's my understanding of the requirement. Does this look correct, or would you like to adjust anything?"**

---

## Step 1: Resolve Scenarios, Steps & Actions

Use the Requirement Context from Step 0 to find the functional graph nodes
that fulfil this requirement.

> **MANDATORY — DO NOT BULK FETCH THE FUNCTIONAL GRAPH.**
> NEVER call `Get_complete_functional_graph` or any tool that returns the entire
> functional graph in one shot. Always fetch incrementally per scenario.

> **SKIP SYSTEM PERSONA SCENARIOS.**
> This skill generates design nodes for UI — System and External System
> persona scenarios have no user interface and MUST be excluded.
> See Step 1a-pre below for how to build the blocklist.

### 1a-pre. Build non-human outcome blocklist ⛔ BLOCKING GATE

> **⛔ HARD STOP: You MUST NOT proceed to scenario selection or
> processing until the blocklist is fully built. This gate ensures no
> System/External System scenario is ever processed. There is NO valid
> reason to skip this step.**

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
   zero personas, STOP and tell user to populate the functional graph first
6. Log: `"Blocklist built: {N} non-human outcome(s) from {M} non-human persona(s) will be excluded"`

**⛔ Gate check:** `blockedOutcomeIds` must exist before ANY scenario
is fetched, displayed, or processed. If this step fails, do not
continue.

**Usage during scenario processing:**

When resolving or processing scenarios, each scenario has an `outcomeId`.
Check it against `blockedOutcomeIds`:

- `outcomeId` **in** `blockedOutcomeIds` → **skip** — show user:
  `"Skipping '{scenarioName}' — belongs to non-human persona (no UI)"`
- `outcomeId` **not in** `blockedOutcomeIds` → **proceed** normally

### 1a. Resolve Scenarios

Scenarios can come from **three sources** — check each that applies and
merge into a single candidate list (deduplicate by scenario ID):

#### Source 1: Direct scenario reference (input C)

If the user explicitly named scenarios (e.g., "create design for the login
scenarios"), fetch them directly:

- Call `Functional_Graph_Search(query: "<scenario name>", project_uuid: "<projectUuid>", includeLabels: "[\"Scenario\"]")`
- Or call `Get_scenarios_by_uuid` and match by name
- Add matched scenarios to the candidate list

#### Source 2: Jira ticket linked scenarios

If a Jira ticket was provided, check whether it already has scenario
references — look for Breeze scenario names, scenario IDs, or functional
graph references in the ticket description, comments, or custom fields.

If found:

- Fetch each referenced scenario via `Functional_Graph_Search` or
  `Get_scenarios_by_uuid` to validate it exists in the graph
- Add validated scenarios to the candidate list

#### Source 3: Search by requirement context

Using the **Key Terms** from the Requirement Context, search for additional
matching scenarios:

```
Functional_Graph_Search(
  query: "<key terms>",
  project_uuid: "<projectUuid>",
  includeLabels: "[\"Scenario\"]"
)
```

Run multiple searches if the requirement spans different domains (e.g., one
search for "login authentication", another for "password reset").

Add results to the candidate list (skip duplicates already found via
Source 1 or 2).

> **Priority:** If Source 1 or Source 2 already yielded scenarios, those are
> the primary candidates. Source 3 results are supplementary — present them
> separately so the user can decide whether to include them.

### 1b. Handle No Scenarios Found — HARD STOP

If no matching scenarios are found:

> _"No functional graph scenarios found matching your requirement. The
> functional graph must exist before design generation can proceed. Please use
> `/breeze:update-functional-graph` to create the functional graph first, then
> re-run `/breeze:analyze-design`."_

**Stop here.**

### 1c. Fetch Steps & Actions for Each Matched Scenario

For each scenario found, call
`Get_all_steps_actions_for_a_scenario_id(uuid, parameters0_Value: <scenarioId>)`
and extract:

- `scenarioId` (UUID), scenario name
- For each step: `stepId`, step name, step order
- For each action under each step: `actionId`, action name, action description

### 1d. Map Requirement Context → Scenarios → Steps → Actions

Cross-reference the Requirement Context against the fetched functional data.
For each **Key Capability** and **UI Element** from the context, identify which
scenario → step → action covers it.

Present a coverage summary to the user, grouped by source:

```
Requirement Coverage:

  From direct reference / Jira ticket:
    1. ✓ Login with Email — Persona: End User [design: not generated]
       ├── Step 1: Enter Credentials
       │   ├── Action: Display email input field
       │   ├── Action: Display password input field
       │   └── Action: Display login button
       └── Step 2: Validate & Redirect
           ├── Action: Show validation errors
           └── Action: Redirect to dashboard

  From functional graph search:
    2. Reset Password — Persona: End User [design: not generated]
       ├── Step 1: Request Reset
       │   └── Action: Display reset form
       └── Step 2: Confirm Reset
           └── Action: Display confirmation message

  Gaps (not covered by any scenario):
  - <UI element or capability with no matching action>

  Unmatched Actions (in graph but not in requirement):
  - <action that exists but isn't relevant to this requirement>

Scenarios to process: 2 | Steps: 4 | Actions: 7
```

### 1e. User Confirms Scope

Ask: **"These are the scenarios, steps, and actions I'll use to generate the
design graph. Proceed with all, or would you like to adjust the selection?"**

- User can exclude scenarios, add more via search, or accept all
- If user says "none", stop

### 1f. Handle Already-Generated Scenarios

If any selected scenarios have `isDesignGenerated: true`, ask:

> \_"The following scenario(s) already have design nodes:
>
> - Login with SSO
>
> 1. **Skip** — exclude these
> 2. **Regenerate** — delete existing and regenerate
> 3. **Continue anyway** — may create duplicates"\_

### 1g. Select Target Modalities

Ask which modalities to generate design nodes for:

| Modality        | Description                        |
| --------------- | ---------------------------------- |
| `web`           | Browser-based interface            |
| `mobile/tablet` | Native mobile & tablet application |
| `desktop`       | Desktop application                |

Default: `web` if user doesn't specify.

### 1h. Processing Mode

Ask user which processing mode to use:

| Mode      | Description                                                                     |
| --------- | ------------------------------------------------------------------------------- |
| `confirm` | Show preview and ask for confirmation before each scenario (default)            |
| `auto`    | Skip per-scenario confirmation; process all unprocessed scenarios automatically |

**Question:** "Do you want to confirm each scenario before creating design nodes, or process all automatically? (`confirm` / `auto`)"

- Default: `confirm` if user doesn't specify
- In `auto` mode:
  - Skip Step 4 (User Confirmation) entirely
  - Log a one-line progress update per scenario instead (e.g., `"[3/15] Processing: Login Scenario → 2 Flows, 3 Pages, 8 Components"`)
  - On error: log the failure, skip the scenario, and continue to the next one
  - Show a final summary at the end (Step 7)
  - **CRITICAL — DO NOT STOP OR PAUSE DURING AUTO MODE.** When `auto` mode is selected, you MUST process ALL scenarios from start to finish without stopping to ask "should I continue?", "shall I proceed?", or any continuation prompt. The user has given blanket consent by selecting `auto`. Process every scenario until the loop exits naturally. The ONLY acceptable reason to stop is an unrecoverable error that prevents ALL further processing.

---

## Step 1.5: UI Repo Discovery (runs once if `uiRepoAvailable`)

> **Skip this entire step if no UI repo was resolved in Guard.** The
> skill then falls back to inferring flows/pages from scenario steps
> alone, as before.

The functional graph tells you **what** the user does. The UI code reveals
**how many distinct ways** they can do it and **how many screens** each way
takes. Use the repo to split each scenario into multiple flows and pages
instead of collapsing it to one.

### 1.5a. Detect framework

Look for the primary router/frame signal:

| Signal in repo                                 | Framework      |
| ---------------------------------------------- | -------------- |
| `<Route`, `createBrowserRouter`, `useRoutes`   | React Router   |
| `src/router/index.{js,ts}` with `createRouter` | Vue Router     |
| `pages/` or `app/` with route conventions      | Next.js / Nuxt |
| `*-routing.module.ts`, `app.routes.ts`         | Angular        |
| `src/routes/` with `+page.svelte`              | SvelteKit      |
| `react-native`, `expo` in `package.json`       | React Native   |

Record the framework. Use it to decide what files and patterns to search.

### 1.5b. Build a repo route map (once, cached in memory)

Using Glob + Read + Grep on the resolved repo, produce a **route map**:

```
route path        →  component file(s)     →  outgoing links / nav targets
/login            →  src/pages/Login.tsx   →  /forgot-password, /signup
/signup           →  src/pages/SignUp.tsx  →  /verify-email
/verify-email     →  src/pages/Verify.tsx  →  /dashboard
```

Extract:

- **Route paths** — from router config or file-based routing conventions
- **Component file for each route** — the top-level component rendered
- **Deep links / modals / tabs** — panels, tabs, or drawers rendered
  conditionally on the same route (discover via `useSearchParams`,
  `isOpen` modal patterns, tab state, nested `<Outlet/>`)
- **Outgoing navigation** — `<Link to>`, `navigate()`, `router.push()`,
  `<a href>` calls inside each route's component subtree
- **Entry points / guards** — redirects, auth guards, role gates that
  sit in front of the route

Do NOT walk the full repo indiscriminately — scope searches by scenario
keywords and progressively widen only if nothing is found.

### 1.5c. Per-scenario discovery → UI Discovery Map

For each selected scenario, use the scenario name + step names + action
descriptions as search terms. Find:

1. **Candidate entry route(s)** — the route(s) where this scenario
   starts. A scenario can have more than one entry (e.g., "Login" may
   start from `/login` and also from a "Sign in" modal on `/`).
2. **Navigation graph from each entry** — follow outgoing links
   relevant to the scenario (stop at unrelated routes or when the
   scenario goal is reached) to form one or more **flow paths**.
3. **Pages along each path** — each distinct route reached on the way
   to completing the scenario is a page candidate.
4. **Step → page mapping** — map each functional step to the page(s)
   on which it is implemented (a step can span multiple pages; a page
   can host multiple steps).

Emit a **UI Discovery Map** per scenario:

```
Scenario: Login with Email
  entries:
    - /login                        (primary)
    - /  (sign-in modal via ?auth=1)
  flow candidates:
    Flow "Password login"
      pages: /login → /dashboard
      steps: Enter Credentials → Validate & Redirect
    Flow "Magic link login"
      pages: /login → /check-email → /verify → /dashboard
      steps: Enter Credentials → (Email sent) → Validate & Redirect
  unmapped steps: <any functional step with no page match>
```

If a step has **no matching route/component**, mark it `unmapped` —
do not silently drop it. Surface unmapped steps in Step 4's preview
and in the final summary.

### 1.5d. Reuse check — match map against existing design graph

Before presenting the map, cross-reference each discovered Flow and
Page against the **existing design graph** so repeated structures
LINK instead of duplicating.

Build the reuse registries once for this run (not per-scenario):

- **Flow registry** — `Get_all_Design_By_Label(label: "Flow")`,
  indexed by `(name, modality, routeSignature)` where
  `routeSignature` is the ordered list of route paths in the flow
- **Page registry** — `Get_all_Design_By_Label(label: "Page")`,
  indexed by `(name, pageType, modality, routePath,
designSystemRef)`

These are the same registries Step 2b needs. Build them here, cache
them, and let Step 2b reuse the cached result instead of re-querying.

**For each Flow in the UI Discovery Map**, walk this priority order
and stop at the first match:

1. **Route signature match** — existing flow has the same ordered set
   of route paths (regardless of name) → REUSE
2. **Exact `(name, modality)` match** — same name (case-insensitive,
   stem-normalized) and same modality → REUSE
3. **Semantic + overlap match** — ≥70% of the discovered pages exist
   in an existing flow with a semantically similar name (e.g.
   "Password Login" ↔ "Login with Password") → REUSE after user
   confirmation in Step 4
4. **No match** → CREATE NEW

**For each Page in the UI Discovery Map**, priority order:

1. **Route path match** — existing page already has this
   `routePath` + `modality` → REUSE
2. **Exact `(name, pageType, modality)` match** → REUSE
3. **Same `designSystemRef` and route component file** → REUSE
4. **Semantic name match in same `pageType` + `modality`** (e.g.
   "Dashboard" ↔ "Home Dashboard") → REUSE after confirmation
5. **No match** → CREATE NEW

**Annotate the UI Discovery Map with REUSE/NEW** on each node:

```
Scenario: Login with Email
  flow candidates:
    Flow "Password login"                                   [REUSE existing: "Login with Password" — route-signature match]
      pages:
        /login       → Page "Sign In"                       [REUSE by routePath]
        /dashboard   → Page "Dashboard"                     [REUSE by (name, pageType)]
      steps: Enter Credentials → Validate & Redirect
    Flow "Magic link login"                                 [NEW]
      pages:
        /login        → Page "Sign In"                      [REUSE — already above]
        /check-email  → Page "Check Email"                  [NEW]
        /verify       → Page "Verify Email"                 [REUSE by routePath]
        /dashboard    → Page "Dashboard"                    [REUSE — already above]
      steps: Enter Credentials → (Email sent) → Validate & Redirect
```

Reuse semantics (consistent with Step 3b LINK-before-CREATE):

- **REUSE Flow** — do NOT emit the Flow or its child Pages in the
  bulk payload; instead issue `Update_Design_Node` to append this
  scenario's `stepIds[]` to the existing Flow
- **REUSE Page** — do NOT emit the Page or its components; issue
  `Update_Design_Node` to append the current step's UUID to the
  existing page's `stepIds[]`
- **Ties on priority** — prefer the higher-scope or
  more-referenced existing node (highest `stepIds[]` count)
- **Never downgrade scope on reuse** — a PAGE-scoped existing
  page is not upgraded to a GLOBAL flow, etc.

### 1.5e. Present and confirm

Show the UI Discovery Map to the user alongside the coverage summary
from Step 1d. Ask:

> _"I found {N} flow(s) across {M} page(s) in the repo for this
> requirement. {R} of these already exist in the design graph and will
> be REUSED (linked), {C} are NEW. Proceed with this structure, or would
> you like to adjust (merge/split flows, rename pages, override a REUSE
> decision, mark unmapped steps)?"_

In `auto` mode, skip the prompt and proceed with the map as generated
(including REUSE decisions); log any unmapped steps and any
semantic-match reuses requiring confirmation in the final summary
instead of pausing.

Process selected scenarios one at a time.

> **⛔ AUTO MODE — NO CONTINUATION PROMPTS.**
> When processing mode is `auto`: you MUST NOT pause, stop, or ask the user
> whether to continue at any point during this loop. Process ALL scenarios
> sequentially without interruption. Do not ask "should I continue?", "shall
> I proceed?", "do you want me to keep going?", or any variation. The loop
> runs to completion.

```
counter = 0
LOOP:
  1. Take next scenario from selected list
  2. IF no scenario remaining → EXIT
  3. counter += 1
  4. Show progress: "[counter/totalScenarios] Scenario: <name>"
  5. Execute Steps 2-3 for this scenario (check coverage, generate nodes)
  6. Step 4: User confirmation (skip in `auto` mode)
  7. Step 5: Bulk upsert
  8. Step 5e: Mark scenario as processed
  9. REPEAT from step 1
END LOOP
```

---

## Step 2: Check Existing Design Coverage

### 2a. Check Direct Mappings

Query existing design nodes to find what's already mapped:

| Functional Node | Design Node | Check Field   |
| --------------- | ----------- | ------------- |
| Scenario        | UserJourney | `scenarioId`  |
| Step            | Flow/Page   | `stepIds[]`   |
| Action          | Component   | `actionIds[]` |

### 2b. Build Reusable Registries

> **If Step 1.5d already built the Flow and Page registries, reuse
> those cached indexes instead of re-querying.** Only the Component
> registry below is new work per run.

**Flow Registry:**

If not already cached from Step 1.5d, query `Get_all_Design_By_Label`
(label=`Flow`). Index by `(name, modality)` AND `routeSignature`. Used
in Step 3b to avoid duplicating flows across scenarios.

**Page Registry:**

If not already cached from Step 1.5d, query `Get_all_Design_By_Label`
(label=`Page`). Index by `(name, pageType, modality)` AND
`(routePath, modality)`. Used in Step 3b to avoid duplicating pages
across scenarios.

**Component Registry:**

Query `Get_all_Design_By_Label` (label=`Component`). Search by name,
`designSystemRef`, or `componentType` to find existing components for reuse.
Used in Step 3c for component reuse decisions — reuse if found, create new
if not.

| Level    | Scope              |
| -------- | ------------------ |
| `GLOBAL` | Entire application |
| `DOMAIN` | Business domain    |
| `PAGE`   | Single page        |

### 2c. For Existing Mappings, Ask User

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

---

## Step 3: Generate Design Graph Nodes

### 3a. Scenario → UserJourney

One UserJourney per Scenario with `scenarioId` link.
Use the scenario name directly as the UserJourney name. Do NOT add "Journey" suffix.

A UserJourney can host **one or many Flows**. When a UI Discovery Map
exists for this scenario (Step 1.5), use the `flow candidates` from the
map — one Flow per candidate — instead of collapsing the whole journey
into a single flow.

### 3b. Step → Flow OR Page (Exclusive)

A Step maps to Flow OR Page, never both.

**When the UI Discovery Map is available (preferred):**

- Use the map's `flow candidates` as the authoritative list of Flows
  for this scenario. Flow names come from the map (e.g. "Password
  login"), not from a single step name.
- Each page in a flow's `pages:` list becomes a **Page** node, named
  after the route's component or a human-readable label derived from
  the route (e.g. `/check-email` → "Check Email"). Do NOT use the raw
  URL as the page name.
- Distribute steps across pages using the map's `steps:` per-flow
  mapping. A step that spans multiple pages is linked to each page's
  `stepIds[]`.
- Include any `unmapped` steps as Pages or Flows only after asking the
  user in Step 4 — never silently invent a page for them.

**When no UI repo is available — fallback heuristic:**

| Choose Flow When                  | Choose Page When                 |
| --------------------------------- | -------------------------------- |
| Multi-page navigation sequence    | Single screen interaction        |
| Reusable sub-journey pattern      | Data entry/display on one screen |
| Process spanning multiple screens | Form, list, detail, or dashboard |

Create separate Flow/Page for EACH selected modality.
**Name format:** Use the step name (fallback) or the flow/page name
from the UI Discovery Map directly (e.g., "Sign Up", "Registration").
Do NOT add "Flow"/"Page" suffix or modality — the node label and
`modality` field already convey these.

**Flow Deduplication (LINK before CREATE):**

Before creating a Flow, check the flow registry from Step 2b for an existing
flow with the same `(name, modality)`. If a match is found:

- Do NOT create a new Flow or its child Pages
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing flow's `stepIds[]`
- In the bulk payload, omit this flow entirely (it and its pages/components
  already exist)
- In the preview (Step 4), show the flow under "REUSE EXISTING" rather than
  "NEW"

A flow contains multiple pages that together complete the flow. Reusing a
flow automatically reuses all its pages and their components.

**Page Deduplication (LINK before CREATE):**

Before creating a Page, check the page registry from Step 2b for an existing
page with the same `(name, pageType, modality)`. If a match is found:

- Do NOT create a new Page
- LINK: issue an `Update_Design_Node` call to append the current step's UUID
  to the existing page's `stepIds[]`
- In the bulk payload, omit this page (and its components — they already
  exist on the page)
- In the preview (Step 4), show the page under "REUSE EXISTING" rather than
  "NEW"

This prevents the same page (e.g., "Patient Dashboard") from being duplicated
when multiple scenarios reference it.

### 3c. Component Reuse Resolution (REUSE FIRST)

> **Always search existing components via `Get_all_Design_By_Label(label: "Component")`
> or `Design_Graph_Search` before creating any component.**

Walk this priority order, stop at the first match:

1. **Exact `designSystemRef` match** in existing design graph → REUSE (append `actionId`)
2. **Semantic + type match in same domain** → REUSE
3. **Global atom/molecule match** → REUSE
4. **Template/layout match** → REUSE
5. **Create new** → narrowest correct scope (`GLOBAL` > `DOMAIN` > `PAGE`)

**Hard rules:**

- Always search the design graph BEFORE creating
- ORGANISM containers are page-specific — always CREATE NEW; supportingComponents follow rules 1–3
- Merge near-duplicates with same `designSystemRef`
- Never downgrade scope on reuse
- Ties: prefer higher scope and more `actionIds[]` linked

### 3d. Template Generation (Mandatory)

Every Page MUST be assigned a TEMPLATE. After generating all Pages in the
current scenario, apply this for each Page:

1. **Determine the layout pattern** from the Page's `pageType`:

   | `pageType`                      | Standard TEMPLATE  |
   | ------------------------------- | ------------------ |
   | form / create / edit / register | `FormPageLayout`   |
   | list / table / search           | `ListPageLayout`   |
   | detail / view / profile         | `DetailPageLayout` |
   | dashboard / overview            | `DashboardLayout`  |
   | wizard / multi-step             | `WizardLayout`     |
   | master-detail / split           | `SplitPaneLayout`  |
   | login / signup / reset          | `AuthPageLayout`   |

   If the page does not match any standard pattern, derive a generic layout
   name from its structure (e.g., `SettingsPageLayout`). Never name a template
   after a specific page — use the layout pattern name.

2. **Search existing TEMPLATEs** via `Get_all_Design_By_Label(label: "Component")`
   or `Design_Graph_Search` for a TEMPLATE with the matching `designSystemRef`.
   If found → REUSE it (do not create a duplicate). Add the Page's ORGANISMs
   to its `supportingComponents` if not already present.

3. **If no matching TEMPLATE exists → CREATE one** with:
   - `scope`: `GLOBAL` (templates are always reusable)
   - `designSystemRef`: the layout pattern name from the table above
   - `supportingComponents`: the ORGANISMs that slot into this layout

**Hard rules:**

- TEMPLATEs can ONLY contain ORGANISMs — never MOLECULEs or ATOMs directly
- TEMPLATEs define WHERE things go, not WHAT they are
- Name generically (`FormPageLayout`), never specifically (`PatientRegistrationTemplate`)
- One TEMPLATE per layout pattern, reused across all pages sharing that pattern

### 3e. Order Preservation

Preserve `order` field from functional graph in design nodes.

---

## Step 4: User Confirmation (Per Scenario)

> **Skip this step entirely when processing mode is `auto`.** In `auto` mode,
> proceed directly to Step 5 after generating the design nodes. Print a single
> progress line instead:
>
> `"[{current}/{total}] Processing: {scenarioName} → {flowCount} Flows, {pageCount} Pages, {componentCount} Components, {templateCount} Templates"`

Before creating nodes, show a preview for the current scenario covering:
UserJourneys, Flows, Pages, Components, Templates (new + reused). Include a
summary with total nodes to create and actions to link.

If a **UI Discovery Map** was built in Step 1.5 for this scenario, show it in
the preview alongside the design nodes — which route each page came from,
and call out any `unmapped` steps so the user can decide how to handle them
(skip, merge into an existing page, or create a new page).

Ask: **"Proceed with creating these design nodes for this scenario?"**

| Option     | Action                                   |
| ---------- | ---------------------------------------- |
| **Yes**    | Create all nodes as shown                |
| **No**     | Skip this scenario, move to next         |
| **Modify** | Let user specify changes before creating |

If "Modify": allow removing nodes, changing names, reusability levels,
modality assignments. Show updated preview and re-confirm.

---

## Step 5: Create Design Nodes (Bulk Upsert)

Use `Bulk_Update_Design_Nodes` to create the entire UserJourney tree for the
current scenario in **one call**. See [references/guide.md](../generate-design/references/guide.md)
for the full payload structure, supportingComponents array rules, and examples.

### 5a. Build the Bulk Payload

Assemble the nested tree from the confirmed preview: UserJourney → Flows →
Pages → Components (with `supportingComponents`) + TEMPLATEs. One UserJourney per call (one scenario).

Include any new TEMPLATE nodes generated in Step 3d in the payload. TEMPLATEs
sit at the Page level with their ORGANISM `supportingComponents`. If the
TEMPLATE already exists (reused), omit it from the payload.

### 5b. Payload Rules

- **Nesting = hierarchy** — backend wires parent-child relationships
- **Component supportingComponents** — ORGANISM → MOLECULE/ATOM, MOLECULE → ATOM, ATOM → `[]`
- **Reused components** — include with `designSystemRef`; backend deduplicates via upsert
- **Multi-modality** — separate Flow entries per modality under the same UserJourney

### 5c. Make the Call

```
Bulk_Update_Design_Nodes(
  uuid: <projectUuid>,
  data: <nested payload>
)
```

### 5d. Error Handling

| Failure Point              | `confirm` mode                              | `auto` mode                                                             |
| -------------------------- | ------------------------------------------- | ----------------------------------------------------------------------- |
| Entire bulk call fails     | Retry once; if still fails, report to user  | Retry once; if still fails, log error and skip scenario (continue loop) |
| Partial failure (returned) | Log failed nodes, report to user for review | Log failed nodes, continue to next scenario                             |

In `auto` mode, collect all errors in a `failedScenarios` list
and report them at the end in Step 7.

### 5e. Mark Scenario as Processed

```
Update_Functional_Node(
  uuid: <projectUuid>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true }
)
```

---

## Step 6: Sync to Jira (Conditional)

This step runs **only** if the original input included a Jira ticket link or
key. If no Jira ticket was provided, skip to Step 7.

> **Rules:** see [references/jira-sync-rules.md](references/jira-sync-rules.md)
> for confirmation gate, write protocol, description format preservation,
> analysis block template, and post-write confirmation.

### 6a. Ask for Confirmation

> _"Would you like me to append this design analysis to the description of
> Jira ticket `<TICKET-KEY>`? The existing description will be preserved and
> this analysis will be appended at the end."_

If the user declines → skip to Step 7. Never write to Jira without explicit
confirmation.

### 6b. Build & Append Analysis Block

1. Fetch the current ticket via `mcp__plugin_atlassian_atlassian__getJiraIssue`
   and capture the existing `description` verbatim
2. Build the analysis block using the template in
   [jira-sync-rules.md](references/jira-sync-rules.md) — fill from Steps 0–5
   (requirement context, coverage mapping, design graph created, gaps)
3. **Append** the analysis block to the existing description (never overwrite)
4. Call `mcp__plugin_atlassian_atlassian__editJiraIssue` with the combined
   description — only modify the `description` field, nothing else

### 6c. Confirm to User

Reply with the Jira ticket URL so the user can verify the appended analysis.
If the edit failed, surface the error and ask the user how to proceed.

---

## Step 7: Output Summary

**Design Graph Generated (by Modality)**

| Modality  | UserJourneys | Flows | Pages | Templates (New/Reused) | Components (New) |
| --------- | ------------ | ----- | ----- | ---------------------- | ---------------- |
| web       | N            | N     | N     | N / N                  | N                |
| mobile    | N            | N     | N     | N / N                  | N                |
| **Total** | N            | N     | N     | N / N                  | N                |

**Component Reuse Statistics**

| Metric                        | Count |
| ----------------------------- | ----- |
| New GLOBAL components created | N     |
| New DOMAIN components created | N     |
| New PAGE components created   | N     |
| Existing components reused    | N     |

**Reuse Efficiency:** `(Reused / Total Actions) × 100`%

**Processing Summary** (`auto` mode only)

| Metric           | Count |
| ---------------- | ----- |
| Total scenarios  | N     |
| Processed        | N     |
| Skipped (errors) | N     |

**Failed Scenarios** (`auto` mode, only if errors occurred)

| Scenario | Error |
| -------- | ----- |
| Name     | ...   |

> Failed scenarios remain `isDesignGenerated=false` and will be picked
> up on the next run.

**Next Steps**

- Refine design nodes with additional properties
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design
