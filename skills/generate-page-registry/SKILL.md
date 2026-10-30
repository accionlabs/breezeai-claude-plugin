---
name: generate-page-registry
description: >
  Scan a frontend UI codebase's router to discover pages, classify each
  by page type (LIST, DETAIL, FORM, DASHBOARD) and build the
  `existingpages.json` registry that `generate-design-from-ui` reads.
  Scans every route, or only the screens of chosen outcomes / scenarios.
  Use when: "build page registry", "scan pages", "create page inventory",
  "populate existingpages.json", "page discovery from UI",
  "pages for these scenarios".
argument-hint: "[repo-path] [--outcome <name>] [--scenarios <id,id>] [--app <name>]"
---

## What this skill does

Parses the router of a frontend repo, resolves each route to the file that
renders it, gives each screen a page name and a page type, and writes the
`existingpages.json` registry. It is the page counterpart of
`/breeze:generate-component-registry`.

```
Input:  UI codebase (router file + page files)
        optional: functional graph, to scope to some outcomes / scenarios

Output: existingpages.json
        {
          "Search Result|LIST|WEB": { "name": "Search Result", "pageType": "LIST", ... },
          "Project Detail|DETAIL|WEB": { ... },
          ...
        }
```

`generate-design-from-ui` uses this registry to **link before create**: a
page already in the registry is reused by name (the backend adds the new
parent edge) instead of being created again, and its `citations` are used
as-is.

**Key difference from `generate-design-from-ui`:** this skill creates no
design nodes (no UserJourneys, Flows, Pages or Components in Breeze). It
only writes the local registry file.

## Resources

| Reference | What it covers | When to read |
|---|---|---|
| [../generate-component-registry/SKILL.md](../generate-component-registry/SKILL.md) § Step 1a | Router parsing per framework (React Router, Next.js, Vue, Nuxt, Angular, SvelteKit), lazy routes, Angular `loadChildren` | Step 1 |
| [../generate-design-from-ui/references/design-ontology.md](../generate-design-from-ui/references/design-ontology.md) | Page entity fields, page types | Step 2 |
| [../generate-design-from-ui/references/reusability.md](../generate-design-from-ui/references/reusability.md) | How the page registry is used for reuse | Before Step 3 |
| [../generate-design-from-ui/references/mcp-tools.md](../generate-design-from-ui/references/mcp-tools.md) | MCP parameter naming, pagination | Only in scoped mode or Step 4 |

## Inputs

- **UI repo path**: from `$ARGUMENTS`, else resolved in Phase 0.
- **Scope (optional):**
  - `--outcome <name>`: only screens used by that outcome's scenarios.
  - `--scenarios <id,id,…>`: only screens used by those scenarios.
  - Neither: every route in the app.
- **`--app <name>`**: which app or route set, when the repo has several.

## Outputs

- **`existingpages.json`** (or `existingpages.{PLATFORM_ID}.json`) in
  `OUTPUT_BASE`, the folder `generate-design-from-ui` uses:
  `{uiRepo}/design_output` (or `{uiRepo}/design_output/{PLATFORM_ID}`).

## Project

Project-bound per the plugin's `CLAUDE.md`, but only the scoped mode
(reads the functional graph) and Step 4 (citations) make MCP calls. A
full-app scan with no linked project runs without one, and leaves
`citations` empty.

---

# PHASES

---

## Phase 0 — Resolve UI Repo & Configure

### 0a. Resolve the target UI repo

1. Path from `$ARGUMENTS`, else `.breeze.json` `targetRepos.frontend`,
   else the cwd if it is a frontend repo, else ask for an absolute path.
2. **Frontend repo detection:** `package.json` and at least one of
   `src/router/`, `src/routes/`, `app/routes`, `pages/`, `src/pages/`,
   `app/`, or framework router imports.

### 0b. Platform and output folder

Read `designGraph.platform` from `.breeze.json` as
`generate-design-from-ui` does: `PLATFORM_ID = designGraph.platform.id`,
else `""`. Set `OUTPUT_BASE` to `{uiRepo}/design_output/{PLATFORM_ID}` when
set, else `{uiRepo}/design_output`. The file is `existingpages.json`, or
`existingpages.{PLATFORM_ID}.json` when `PLATFORM_ID` is set. Remind the
user to keep `design_output/` in the UI repo's `.gitignore`.

### 0c. App and framework

1. Detect the framework (see the component registry's Step 0b table).
2. **Several apps or route sets?** A monorepo, or one repo with more than
   one router (for example `src/app/app.tsx` + `src/routes/routes.apac.tsx`
   and `src/app/app-us.tsx` + `src/routes/routes.us.tsx`). Use `--app`;
   otherwise list them and ask which one, or "all" (each entry is then
   tagged with its `app`).
3. Detect the modality: web routers → `WEB`; `react-native` / `expo` →
   `MOBILE`; `electron` / Tauri → `DESKTOP`; Ionic / Capacitor → `WEB` and
   `MOBILE` (one entry per modality).

### 0d. Re-run behavior (if the registry exists)

```
Existing page registry found ({N} pages).

1. **Merge**: keep existing entries (and their IDs), add new pages
2. **Overwrite**: rebuild from scratch (loses IDs written by
   generate-design-from-ui after upserts)

Choose 1 or 2:
```

Default: 1 (merge). Never drop an entry whose `id` is a real node ID
without asking.

---

## Step 1: Discover routes

Parse the router as in the component registry's **Step 1a** (all
frameworks, lazy routes, Angular `loadChildren` / `loadComponent`). Also
handle:

- **Config-array routes:** arrays of objects with `path`, `component` or
  `element`, `name`, `children` (e.g. `RouteTypes[]`), not only JSX.
- **Path aliases:** resolve `@app/...`-style imports via `tsconfig`
  `paths` / bundler `resolve.alias` to the real file.

For every route, record: `path`, the page file, the guard (protected or
public, roles), and the parent layout. **Skip** redirects, wildcard / 404
routes and layout-only routes (they render only an outlet).

### Scoped mode (`--outcome` / `--scenarios`)

1. Resolve the project (CLAUDE.md). Read the scenarios: for `--outcome`,
   `Get_all_personas` → `Get_all_outcomes_for_a_persona_id` → match by name
   → its scenarios; for `--scenarios`, those IDs. Read their steps and
   actions with
   `../generate-design-from-ui/scripts/fetch_steps_actions.py`.
2. Map each scenario's steps to the routes where they happen, opening only
   the candidate page files to confirm the actions exist there.
3. Keep only those routes. Record the scenario IDs per page in
   `usedByScenarios`.

## Step 2: Name and classify each page

- **`name`:** the screen's name made readable, **without a "Page"
  suffix**: `SearchResultPage` / `pages/SearchResult` → "Search Result";
  `ProjectDetailComponent` → "Project Detail". A dynamic route
  (`/project/:id`) is its own page. Use the route's display `name` /
  `title` when the router has one and it is clearer.
- **`pageType`** (UPPERCASE), from the page file when the name doesn't
  make it obvious:

  | Page mainly… | `pageType` |
  |---|---|
  | submits input (create / edit / settings forms, wizards) | `FORM` |
  | shows a collection (tables, search results, grids) | `LIST` |
  | shows one record | `DETAIL` |
  | shows widgets, charts or summary cards | `DASHBOARD` |

- **Same screen on several routes** (e.g. `/project/new` and
  `/project/:id/edit` rendering one form): one entry, with all paths in
  `routes`.
- **Name collisions** across apps (when scanning "all"): append the app's
  `APP_SUFFIX` from `.breeze.json` if set, else the app name.

## Step 3: Write `existingpages.json`

Keyed `"{name}|{pageType}|{modality}"`, the key
`generate-design-from-ui` looks pages up by:

```json
{
  "Search Result|LIST|WEB": {
    "id": null,
    "name": "Search Result",
    "pageType": "LIST",
    "modality": "WEB",
    "routes": ["/search-result"],
    "app": "apac",
    "requiresAuth": true,
    "roles": [],
    "stepIds": [],
    "usedByScenarios": [],
    "sourceFile": "src/pages/SearchResult/index.tsx",
    "citations": []
  }
}
```

- **`id: null`** means the page is not in the design graph yet.
  `generate-design-from-ui` creates it by name in the bulk upsert, then
  writes the real node ID here (blocking gate 5). Merge mode keeps
  existing IDs.
- `stepIds` starts empty; `generate-design-from-ui` appends to it.
- `usedByScenarios` is filled in scoped mode only.

Write the file once, after all pages are classified.

## Step 4: Populate citations

> Requires a linked project with a code graph. Without `projectUuid`,
> skip this step; `citations` stay `[]`.

1. Collect the unique `sourceFile` paths.
2. One `Code_Graph_Search(uuid: PROJECT_UUID, query: "<relative-file-path>")`
   per path; cache `sourceFile → code-node-id`.
3. Set `"citations": [{"type": "code", "reference": "<code-node-id>"}]`, or
   `[]` when no node is found, and write the file back.

The design sub-agent uses these citations directly, so it does not query
the code graph again for pages.

## Step 5: Output summary

```
Page Registry Complete

  App(s):       {app} ({framework}, {modality})
  Mode:         {all routes | outcome "<name>" | scenarios <ids>}
  Routes read:  {N}   Skipped: {redirects, 404, layouts}
  Pages:        {N}   (merged: {M} kept, {K} new)

  By type:   LIST {N} · DETAIL {N} · FORM {N} · DASHBOARD {N}
  Protected: {N}
  Citations: {N}/{total}

  Registry: {OUTPUT_BASE}/existingpages.json
```

Then a table of every page: name, type, route(s), file.

**Next steps:**

- Run `/breeze:generate-component-registry` if `existingcomponents.json`
  is missing.
- Run `/breeze:generate-design-from-ui`. Pages in the registry are reused
  by name from the first scenario.

---

# REFERENCE

## When to use this skill

| Situation | Use this skill? |
|---|---|
| Before the first run of `generate-design-from-ui` | **Yes**: page names and types are fixed up front, so parallel sub-agents name the same screen the same way |
| Designing only some outcomes or scenarios | **Yes**: scoped mode registers just their screens |
| Page registry is missing or stale | **Yes**: merge mode keeps existing IDs |
| Need Page nodes in the Breeze graph | **No**: `generate-design-from-ui` creates them |
| No functional graph yet | **Yes**: full-app mode works from the router alone |

## Cost

Full app: ~1 call per router file plus ~1 per page whose type is not
obvious from its name; for 40 routes, ~15–40 calls. Scoped mode: the
functional-graph reads plus ~1 call per candidate page. Step 4 adds one
`Code_Graph_Search` per page.
