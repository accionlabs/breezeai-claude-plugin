# <APP_NAME> — Module Builder Guide

Render this into `<APP_DIR>/AGENT_GUIDE.md` during Phase 3, filling every `<...>` and the lists below
with the REAL scaffold you built. Each module-builder agent reads this first. Keep it concrete — agents
rely on the exact export names here.

## What you are building
One feature module of <APP_NAME> — <one-line app description> — recreated from the Breeze functional
graph for persona **<PERSONA_NAME> (<PERSONA_CODE>)**.

## Source of truth: the Breeze functional graph
- Project UUID: `<PROJECT_UUID>`
- Persona ID: `<PERSONA_ID>`

Read the real graph for EVERY assigned outcome, then build to cover every Scenario → Step → Action.
Load the MCP tools (ToolSearch `select:mcp__plugin_breeze_breeze-mcp__Get_all_scenarios_for_a_outcome_id,mcp__plugin_breeze_breeze-mcp__Get_all_steps_actions_for_a_scenario_id`),
then per outcome: `Get_all_scenarios_for_a_outcome_id(uuid, outcome_id, limit=50)` → per scenario
`Get_all_steps_actions_for_a_scenario_id(uuid, scenario_id)`. **Every Action is a behaviour you must
build — a missed action is a missing flow.** Field/filter/column/validation detail lives in action
descriptions and sibling `Validate <field>` actions; entry-point actions carry `HAS_API` contracts.
If a result exceeds the token limit it is saved to a file path — read that file.

## Persona gating
`import { <persona export> } from '<persona module>'` — <PERSONA_CODE> is: <region/role/tier> with
flags <list the userData flags + what each gates>. Apply the same gating the graph describes (show/hide
fields, surfaces, and admin-only actions accordingly).

## Tech & conventions (FOLLOW EXACTLY)
- Stack: <stack>. Import alias `<@>` → `<src>`. Styling: <styling>. Do NOT add npm dependencies.
- **Design system / shared libs** — import from `<ui barrel path>` and icons from `<icons path>`:
  `<list the real exported component names>`. (Open `<ui file>` to see the full set + signatures.)
- **Data layer** — import from `<data layer path>`: `<list entities + helpers>`. Types in `<types path>`.
  Formatters: `<list>`. Use this shared data; add extra local rows in your own folder only if needed.
- All flows interactive via local state: buttons open a modal/drawer, filter/sort a list, toggle, navigate,
  or fire a toast. No dead ends, no static mockups. Cover empty states, pagination, validation, gating.

## Your output
- Put ALL files under `<MODULE_FOLDER>`. Split into a few well-named files.
- Export `routes` from `<MODULE_FOLDER>/routes.tsx`:
  ```tsx
  import type { AppRoute } from '<routes type path>'
  export const routes: AppRoute[] = [
    { path: '<owned-path>', element: <Page/>, nav: { section: '<section>', label: '<Label>', icon: '<Icon>', order: <n> } },
    { path: '<owned-path>/:id', element: <Detail/> }, // no nav → not in sidebar
  ]
  ```
  `path` is relative to `<route base>`. Add `nav` ONLY to the routes your assignment designates.
- Use `<navigate/link api>` for cross-links and `<params api>` for ids.
- Do NOT edit shared files (`<shared dirs>`) or the route registry — only your folder. The parent
  concatenates module route arrays and runs the full build.

## Route / endpoint ownership map (so agents don't collide)
<table: domain → folder → owned routes/prefixes → nav routes>

## Quality bar
Production-grade B2B SaaS: clean tables, side-panel/toolbar filters, drawers for detail, modals for
create/edit/confirm, breadcrumbs, badges, empty states, pagination, toasts. Cover EVERY assigned
outcome and its actions. Return a short manifest of routes/endpoints created and outcomes covered.
