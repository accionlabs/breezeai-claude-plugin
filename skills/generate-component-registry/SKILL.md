---
name: generate-component-registry
description: >
  Scan a frontend UI codebase to discover all components, classify them
  by atomic design level (ATOM, MOLECULE, ORGANISM, TEMPLATE), and build
  the `existingcomponents.json` registry. Optionally upserts Component
  nodes to the Breeze design graph.
  Use when: "build component registry", "scan components", "create
  component inventory", "populate existingcomponents.json",
  "component discovery from UI".
argument-hint: "[repo-path]"
---

## What this skill does

Scans **all pages** in a frontend UI repo by parsing the router,
discovers every component, classifies them by atomic design level,
and builds a complete `existingcomponents.json` registry.

No functional graph required — pages are discovered directly from
the router file, not from personas or scenarios.

```
Input:  UI codebase (router file + page directories)

Output: existingcomponents.json
        {
          "ATOM":     { "Button": {...}, "Label": {...}, ... },
          "MOLECULE": { "SearchBar": {...}, ... },
          "ORGANISM": { "DataTable": {...}, ... },
          "TEMPLATE": { "FormPageLayout": {...}, ... }
        }

Optionally: Component nodes upserted to the Breeze design graph
```

**Key difference from `generate-design-from-ui`:** This skill does NOT
create UserJourneys, Flows, or Pages. It only discovers and registers
components. It processes by **unique page** (not per scenario), so
every page is scanned exactly once.

## Resources

| Reference | What it covers | When to read |
|---|---|---|
| [../generate-design-from-ui/references/component-rules.md](../generate-design-from-ui/references/component-rules.md) | Atomic levels, classification, naming, supportingComponents (min 2 for non-ATOMs), reuse | During component classification |
| [../generate-design-from-ui/references/design-ontology.md](../generate-design-from-ui/references/design-ontology.md) | Component entity fields, template rules | When building component payloads |
| [../generate-design-from-ui/references/mcp-tools.md](../generate-design-from-ui/references/mcp-tools.md) | MCP tool reference, parameter naming, pagination rule | When calling any MCP tool |
| [../generate-design-from-ui/references/pitfalls.md](../generate-design-from-ui/references/pitfalls.md) | Common mistakes | Quick check |

## Inputs

- **UI repo path** — if provided as argument (`$ARGUMENTS`), use it
  directly; otherwise resolved in Phase 0
- **`.breeze.json`** — for `projectUuid` (only needed if upserting
  to graph)

## Outputs

- **`existingcomponents.json`** — complete component registry
- **(Optional)** Component nodes in the Breeze design graph via
  `Bulk_Update_Design_Nodes`

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing and user wants graph upsert → tell user to run
   `/breeze:setup-project`
3. If missing and user wants registry-only → proceed without it
4. Extract `projectUuid` if available

> **Parameter naming:** All Breeze MCP tools require the project ID
> as **`uuid`** (NOT `projectId` or `projectUuid`). See
> [mcp-tools.md § Parameter Naming](../generate-design-from-ui/references/mcp-tools.md).

---

## Phase 0 — Resolve UI Repo & Configure

### 0a. Resolve the target UI repo

1. Check if user passed a path via `$ARGUMENTS`
2. Check `.breeze.json` field `targetRepos.frontend`
3. Check if cwd looks like a frontend repo
4. Ask the user: "Which UI repo? Provide an absolute path."
5. Persist to `.breeze.json` if available:
   `{ "targetRepos": { "frontend": "..." } }`

> **Frontend repo detection:** `package.json` AND at least one of:
> `src/router/`, `src/routes/`, `app/routes`, `pages/`, `src/pages/`,
> `app/`, or framework router imports.

### 0b. Detect Framework

Identify the framework from router files and `package.json`:

| Signal | Framework |
|---|---|
| `<Route`, `createBrowserRouter`, `useRoutes` | React Router |
| `pages/` or `app/` directory with Next config | Next.js |
| `src/router/index.{js,ts}` | Vue 2/3 |
| `pages/` with `.vue` files | Nuxt |
| `*-routing.module.ts` or `app.routes.ts` | Angular |
| `src/routes/` with `+page.svelte` | SvelteKit |

Record the detected framework for use during page discovery and
component reading.

### 0c. Ask user: mode

```
Component Registry Options:

1. **Registry only** — build existingcomponents.json (no MCP writes)
2. **Registry + Graph** — build registry AND upsert Component nodes
   to the Breeze design graph

Choose 1 or 2:
```

Default: 1 (registry only). Option 2 requires `.breeze.json` with
a valid `projectUuid`.

### 0d. Ask user: re-run behavior (if registry exists)

If `existingcomponents.json` already exists and is non-empty:

```
Existing registry found ({N} components).

1. **Merge** — keep existing entries, add newly discovered ones
   (additive — safe, preserves manual edits)
2. **Overwrite** — delete and rebuild from scratch
   (fresh scan — loses manual edits)

Choose 1 or 2:
```

Default: 1 (merge).

---

## Step 1: Discover All Pages from Router

> **Goal:** Parse the router to build a deduplicated list of every
> page in the app, including layout routes. No functional graph needed.

### 1a. Locate and parse the router

| Framework | Router location | What to extract |
|---|---|---|
| **React Router** | `src/router/index.tsx`, `src/App.tsx`, or file with `createBrowserRouter`/`<Route>` | `path` → `element`/`component` mappings, **including parent `<Route>` with `<Outlet/>`** |
| **Next.js** | `pages/**/*.tsx` or `app/**/page.tsx` | File path = route. **Also include `layout.tsx`/`_app.tsx` files** |
| **Vue 2/3** | `src/router/index.{js,ts}` | `path` → `component`, **including `children: [...]` nested routes** |
| **Nuxt** | `pages/**/*.vue` | File path = route. **Also include `layouts/*.vue`** |
| **Angular** | `*-routing.module.ts` or `app.routes.ts` | `path` → `component`/`loadComponent`, **including parent routes with `children`** |
| **SvelteKit** | `src/routes/**/+page.svelte` | File path = route. **Also include `+layout.svelte`** |

**Steps:**

1. Find the router file(s) using the detected framework
2. Read the router file(s)
3. Extract all route → component mappings, including:
   - **Leaf routes** — pages the user navigates to
   - **Layout routes** — parent routes with `<Outlet/>`, `layout.tsx`,
     `+layout.svelte`, etc. These contain navbars, sidebars, and
     shared chrome components that must be in the registry
4. For lazy-loaded routes (`() => import(...)`, `loadComponent`,
   `defineAsyncComponent`), resolve the import path to the actual file
5. Build `uniquePages` list:
   ```
   uniquePages = [
     { route: "(layout)", file: "src/layouts/MainLayout.tsx", type: "layout" },
     { route: "/dashboard", file: "src/pages/Dashboard/index.tsx", type: "page" },
     { route: "/search", file: "src/pages/Search/index.tsx", type: "page" },
     { route: "/settings", file: "src/pages/Settings/index.tsx", type: "page" },
     ...
   ]
   ```

### 1b. Discover shared component directories

Before page scanning, identify the repo's shared component directories:

```
Glob for common shared patterns:
  src/components/**/*.{tsx,jsx,vue,svelte,ts}
  src/ui/**/*.{tsx,jsx,vue,svelte,ts}
  src/lib/components/**/*.{tsx,jsx,vue,svelte,ts}
  src/shared/**/*.{tsx,jsx,vue,svelte,ts}
  components/**/*.{tsx,jsx,vue,svelte,ts}   (Nuxt/Next)
```

Record these paths — they'll be scanned in Step 2 as a dedicated
batch alongside pages.

### 1c. Expand page directories

For each page entry file, identify its directory and glob for
sibling files that are part of the same page:

```
src/pages/Dashboard/
  ├── index.tsx          ← page entry (already found)
  ├── widgets/           ← scan these
  ├── components/        ← scan these
  ├── sections/          ← scan these
  └── hooks/             ← note for state analysis
```

Add all discovered files to the page's scan list.

### 1d. Build agent batches

> **Don't launch one agent per page.** Small pages (1-3 files) are
> wasteful as individual agents. Group them.

| Page size | Batching |
|---|---|
| **Large page** (≥ 4 files in dir) | 1 agent per page |
| **Small pages** (< 4 files each) | Group 3-5 small pages into 1 agent |
| **Shared component dirs** | 1 dedicated agent for all shared dirs |
| **Layout routes** | Group with shared dirs agent (or own agent if large) |

> **⛔ Max 5 agents at a time.** Do NOT launch all agents at once.
> Process in waves of up to 5 parallel agents. When an agent in a
> wave completes, launch the next pending agent (keep 5 active).

Build the batch list:
```
agentBatches = [
  { id: 1, type: "shared", files: ["src/components/...", "src/ui/..."] },
  { id: 2, type: "layout", files: ["src/layouts/MainLayout.tsx"] },
  { id: 3, type: "page", name: "Dashboard", files: ["src/pages/Dashboard/..."] },
  { id: 4, type: "multi-page", pages: ["Login", "Register", "ForgotPassword"], files: [...] },
  ...
]
```

### 1e. Show discovery summary

```
Page Discovery Summary:
  Framework: {name}
  Router file: {path}
  Pages found: {N} (+ {M} layout routes)
  Shared dirs: {paths}
  Agent batches: {N} ({M} page agents, {K} shared/layout agents)
  Max parallel: 5

  Batches:
    1. [shared]  src/components/ + src/ui/        (42 files)
    2. [layout]  MainLayout                        (3 files)
    3. [page]    Dashboard                         (12 files)
    4. [page]    Search                            (8 files)
    5. [multi]   Login + Register + ForgotPassword (5 files)
    ...

Proceed with component scan?
```

---

## Step 2: Scan & Build Registry (Write-on-Completion)

> **⛔ WRITE-ON-COMPLETION — NOT BATCH-AT-END.**
> Each agent returns results to the main agent, which writes to
> `existingcomponents.json` immediately. Do NOT wait for all agents
> to complete before writing.

### 2a. Initialize `existingcomponents.json`

- **Overwrite mode:** Create with empty structure:
  ```json
  { "ATOM": {}, "MOLECULE": {}, "ORGANISM": {}, "TEMPLATE": {} }
  ```
- **Merge mode:** Load existing file as-is. New components will be
  added alongside existing entries.

### 2b. Launch agents in waves (max 5 parallel)

Each agent receives a prompt containing:

```
You are scanning UI files for component discovery.

Framework: {name}
Batch type: {shared|layout|page|multi-page}
Page(s): {name(s)}
Files to read: {list of file paths}

For each component you find, return a JSON array:

[
  {
    "name": "ExactComponentName",
    "type": "ATOM|MOLECULE|ORGANISM|TEMPLATE",
    "description": "Brief purpose",
    "designSystemRef": "library-component-name or null",
    "supportingComponents": ["ChildA", "ChildB"],
    "scope": "GLOBAL|DOMAIN|PAGE",
    "sourceFile": "src/path/to/file.tsx"
  }
]

Classification rules:
- ATOM: Single UI element, no internal state, no children.
  supportingComponents = []
- MOLECULE: 2-4 atoms composed together, minimal state.
  supportingComponents must have ≥ 2 ATOMs.
- ORGANISM: Self-contained section with own hooks/state.
  supportingComponents must have ≥ 2 MOLECULEs and/or ATOMs.
- TEMPLATE: Layout-only, no business logic, just slots.
  supportingComponents must have ≥ 2 ORGANISMs.

⛔ If a non-ATOM has fewer than 2 supportingComponents, it is
likely misclassified. Re-check:
  - 1 child MOLECULE → probably an ATOM
  - 1 child ORGANISM → probably a MOLECULE
  - 1 child TEMPLATE → probably an ORGANISM

Naming: Use exact exported name or PascalCase file name.
Skip: Skeleton, LoadSkeleton, NoData, Empty, Spinner, LoadingOverlay.

Read each file, extract components, classify, and return the JSON.
```

> **⛔ Shared dirs agent runs FIRST.** Launch the shared component
> directories agent in wave 1 alongside the first page agents. Shared
> components (ATOMs, MOLECULEs) are the most reused — having them in
> the registry early means page agents' results can deduplicate against
> them immediately.

### 2c. Write-on-completion (⛔ SEQUENTIAL FILE WRITES)

> **⛔ Agents run in parallel. File writes are sequential.**
> When an agent completes, the MAIN agent (not the subagent)
> handles the registry write. This prevents concurrent file
> corruption.

As each agent returns its component list:

```
ON agent completion for batch "{batchName}":
  1. READ existingcomponents.json from disk
  2. For each component in the agent's result:
     a. Check if name already exists under its type key
     b. IF exists:
        - Widen scope if now seen on 2+ pages
          (PAGE → DOMAIN → GLOBAL)
        - Merge supportingComponents (union of both lists)
        - Skip otherwise (don't overwrite)
     c. IF new:
        - VALIDATE: non-ATOM must have ≥ 2 supportingComponents.
          If < 2, log warning: "⚠ {name} ({type}) has {N}
          supportingComponents — likely misclassified"
        - Add under the appropriate type key
  3. WRITE existingcomponents.json to disk
  4. Log: "[{completed}/{total}] {batchName} — {N} new, {M} skipped, {K} warnings"
  5. Launch next pending agent if wave has a free slot
```

**Scope widening rules:**

| Currently | Seen again in | New scope |
|---|---|---|
| `PAGE` | Same feature dir | `PAGE` (no change) |
| `PAGE` | Different feature dir | `DOMAIN` |
| `PAGE` | 3rd distinct feature | `GLOBAL` |
| `DOMAIN` | Any new feature | `GLOBAL` |
| `GLOBAL` | Anywhere | `GLOBAL` (no change) |
| From `src/components/` or `src/ui/` | — | Always `GLOBAL` |

### 2d. Handle agent failures

If an agent fails or times out:

1. Log: `"[FAILED] {batchName} — {error}. Skipping."`
2. Continue processing other agent completions — DO NOT abort
3. Add to `failedBatches` list for the summary
4. Launch next pending agent in the wave slot
5. The registry still has all components from successful agents

---

## Step 3: Verify Registry

> **No separate "build" step needed.** The registry was built
> incrementally in Step 2c. This step validates.

### 3a. Read and validate

1. Read `existingcomponents.json` from disk
2. Count components per type
3. **Validate supportingComponents minimum:**
   - For each MOLECULE: must have ≥ 2 entries (all ATOMs)
   - For each ORGANISM: must have ≥ 2 entries (MOLECULEs and/or ATOMs)
   - For each TEMPLATE: must have ≥ 2 entries (all ORGANISMs)
   - Log violations as warnings
4. **Check dangling references:** verify each name in
   `supportingComponents` exists somewhere in the registry.
   Warn on missing (likely from a failed agent's page)
5. **Check ATOMs have empty supportingComponents:** if an ATOM has
   children, it should be reclassified as MOLECULE

### 3b. Show registry state

```
Registry built incrementally ({N} batches completed, {M} failed):

  ATOM:     {N} components
  MOLECULE: {N} components
  ORGANISM: {N} components
  TEMPLATE: {N} components
  Total:    {N} components

  Scope distribution:
    GLOBAL: {N}  |  DOMAIN: {N}  |  PAGE: {N}

  Validation:
    ⚠ {N} components with < 2 supportingComponents (see warnings above)
    ⚠ {N} dangling supportingComponent references
```

---

## Step 4: (Optional) Upsert to Design Graph

> **Only if user chose Option 2 in Phase 0c.**

### 4a. Build component payloads

Group components into batches by page. For each page, build a minimal
payload with a placeholder Page wrapper:

```json
{
  "userJourneys": [
    {
      "name": "Component Registry: {PageName}",
      "description": "Auto-generated component inventory for {PageName}",
      "scenarioId": "",
      "flows": [
        {
          "name": "Component Scan: {PageName}",
          "modality": "WEB",
          "stepIds": [],
          "pages": [
            {
              "name": "{PageName}",
              "pageType": "DETAIL",
              "stepIds": [],
              "components": [
                {
                  "name": "ComponentName",
                  "type": "ORGANISM",
                  "description": "...",
                  "designSystemRef": "...",
                  "supportingComponents": ["ChildA", "ChildB"],
                  "actionIds": []
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

> **Note:** These are placeholder containers to get components into
> the graph. When `/breeze:generate-design-from-ui` runs later, the
> backend dedup by name will find these existing components and link
> them to real UserJourneys/Flows/Pages automatically.

### 4b. Upsert in batches

```
FOR each page batch:
  Call Bulk_Update_Design_Nodes(uuid, data: <payload>)
END FOR
```

> **No MCP sync needed.** Backend dedup is by name, not UUID.
> `existingcomponents.json` is already accurate from the incremental
> writes in Step 2c.

---

## Step 5: Output Summary

```
Component Registry Complete

  Framework:        {name}
  Batches:          {N} completed, {M} failed
  Pages scanned:    {N} (+ {M} layout routes, {K} shared dirs)
  Total components: {N}

  By type:
    ATOM:     {N}
    MOLECULE: {N}
    ORGANISM: {N}
    TEMPLATE: {N}

  By scope:
    GLOBAL: {N}
    DOMAIN: {N}
    PAGE:   {N}

  Validation warnings: {N}
  Upserted to graph: {yes/no}

  Registry: existingcomponents.json ({N} entries)
```

**Failed batches** (if any):

| Batch | Pages | Error |
|---|---|---|
| {id} | {names} | {reason} |

> Failed batches can be retried by running the skill again in
> **merge mode** — the registry on disk already has all components
> from successful batches.

**Next steps:**

- Review validation warnings and fix misclassifications if needed
- Run `/breeze:generate-design-from-ui` — the registry is pre-populated,
  so component reuse will be accurate from the first scenario

---

# REFERENCE

## When to use this skill

| Situation | Use this skill? |
|---|---|
| Before first run of `generate-design-from-ui` | **Yes** — pre-populates registry |
| Component registry is empty or stale | **Yes** — rebuilds from source |
| Want to audit component inventory | **Yes** — registry-only mode |
| Need full design graph (UJ/Flow/Page/Component) | **No** — use `generate-design-from-ui` |
| No functional graph exists yet | **Yes** — works from router alone |
| No `.breeze.json` configured | **Yes** — registry-only mode needs no MCP |

## Cost

~**2-4 tool calls per unique page** (read page + read widgets +
follow imports). For 30 pages grouped into ~10 agent batches:
~40-80 calls. Much cheaper than full design generation.
