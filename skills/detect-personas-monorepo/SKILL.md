---
name: detect-personas-monorepo
description: >
  Detect user personas from all frontend apps inside a monorepo in parallel.
  Analyses routes, layouts, subscription tiers, roles, feature flags, and access
  control patterns. Handles Nx, pnpm, Lerna, Turbo, and npm/yarn workspace
  monorepos — auto-discovers frontend apps, launches one agent per app in
  parallel, then collates results into a unified cross-app persona matrix.
  Use when: "detect personas monorepo", "identify personas monorepo",
  "find user types in monorepo", "persona detector monorepo",
  "detect personas --app <name>".
---

## Project

This skill is project-bound — it needs a `projectUuid`. Resolve it per `CLAUDE.md` at the plugin root: a `--project <name|uuid>` flag, a bare UUID, or a natural-language project hint in the prompt → otherwise the `projectUuid` in `.breeze.json`. A per-invocation override applies to that invocation only and must NOT mutate `.breeze.json`. If no project resolves, list accessible projects via `Call_List_Project_` and ask the user to pick (or run `/breeze:project setup`). Announce the active project on the first response line: `Project: <name> (<uuid>)`. Auth handling on Breeze MCP 401s is also covered in `CLAUDE.md` (point the user at `/breeze:project auth`).

## Guard — Monorepo & Frontend App Resolution

### Step 0.1: Detect monorepo

Check for a monorepo config at the **repo root** and **one level down** (some
repos nest the workspace — e.g., `<root>/nx/`):

| Config file | Monorepo type |
|---|---|
| `nx.json` | Nx |
| `pnpm-workspace.yaml` | pnpm workspaces |
| `lerna.json` | Lerna |
| `turbo.json` | Turborepo |
| `package.json` → `workspaces` field | npm / yarn workspaces |

Set `$MONO_ROOT` to the directory containing the config file.

If **no monorepo config** is found, **stop** and tell the user:
_"This doesn't appear to be a monorepo. Use `/breeze:detect-personas` (the
single-repo variant) instead."_

### Step 0.2: Enumerate frontend apps

Starting from `$MONO_ROOT`, discover all workspace packages. The method depends
on the monorepo type:

| Monorepo type | How to enumerate |
|---|---|
| **Nx** | Read `apps/` and `packages/` directories; check each `project.json` for tags containing `runtime:browser` or `framework:angular\|react\|vue\|svelte`. Also check each app's `package.json` for frontend framework deps. |
| **pnpm / npm / yarn** | Read the `workspaces` globs from `package.json` or `pnpm-workspace.yaml`, resolve them, then check each workspace's `package.json` for frontend framework deps (`react`, `vue`, `angular`, `svelte`, `next`, `nuxt`, `gatsby`, `remix`, `solid`, `lit`, `ember`). |
| **Lerna** | Read `lerna.json` → `packages` globs, resolve, filter as above. |
| **Turbo** | Same as pnpm/npm/yarn (Turbo uses the same `workspaces` field). |

A package is a **frontend app** if ANY of:
- Its `package.json` lists a frontend framework as a dependency or devDependency
- Its `project.json` tags include `runtime:browser`
- It contains directories like `src/app/`, `src/pages/`, `src/views/`,
  `src/screens/`, `src/routes/`, `pages/`, `app/`
- It contains route definition files (`routes.ts`, `router.ts`,
  `app-routing.module.ts`, etc.)

Exclude packages that are clearly **libraries** (e.g., Nx libs under `libs/`)
from the app list — these will be included as associated libs in Step 0.3.

### Step 0.3: Select or parallelise frontend apps

- **If the user passed `--app <name>`** → match against discovered frontend
  app names (case-insensitive substring). Exactly one match → analyse that app
  only. Multiple → list and ask. Zero → error.
- **If zero frontend apps found** → **stop** and tell the user:
  _"No frontend apps found in this monorepo. The persona detector needs a
  frontend codebase (React, Vue, Angular, etc.)."_
- **If one or more frontend apps exist and no `--app` filter** → analyse
  **all of them in parallel** (see Step 0.5).

### Step 0.4: Resolve associated libraries (per app)

For each frontend app, identify its **associated libraries** — monorepo libs
that the app depends on:

- **Nx**: read `project.json` tags on libs. Include libs whose
  `application:<app>` tag matches the app, plus libs tagged
  `application:any`. Also scan the app's import paths (`tsconfig.paths` or
  `tsconfig.base.json` path aliases) to find referenced libs.
- **pnpm / npm / yarn / Lerna / Turbo**: read the app's `package.json`
  dependencies that reference workspace packages (e.g., `"@scope/ui": "workspace:*"`).

For each app, record:
- `$APP_ROOT` — the app's directory
- `$LIB_ROOTS` — list of associated library directories

### Step 0.5: Parallel agent dispatch

Launch one **Agent** per frontend app, all in a **single message** so they run
concurrently. Each agent receives a self-contained prompt containing:

1. The app name, `$APP_ROOT`, and `$LIB_ROOTS` paths.
2. The full analysis instructions (Steps 1–4 from this skill).
3. The required output format: the per-app persona table (Step 5.4 columns)
   plus the per-app dimension summaries (Steps 5.1–5.3).

Agent prompt template (fill in per app):

```
You are analysing the frontend app "<app_name>" inside a monorepo for user
personas. Your analysis scope:

  App root : <$APP_ROOT>
  Libs     : <$LIB_ROOTS (comma-separated paths)>

ALL Glob and Grep calls MUST be scoped to these directories only.

<paste Steps 1–4 verbatim from this skill>

When done, output your findings in this exact structure:

## App: <app_name>

### Framework & Detection Summary
<Step 5.1 content>

### Dimensions Discovered
<Step 5.2 content>

### Interaction Analysis
<Step 5.3 content>

### Persona Table
| # | Persona | Surface | Gate | Feature scope | Why it is distinct |
|---|---|---|---|---|---|
<rows>

Do NOT compare with the Breeze graph — the orchestrator will do that.
```

Use `subagent_type: "general-purpose"` for each agent.

If only one frontend app exists, still use a single agent so the orchestrator
flow remains consistent.

Announce to the user before dispatching:

    Monorepo: <type> at <$MONO_ROOT>
    Frontend apps detected: <count>
    <numbered list of app names + paths>
    Launching <count> parallel agent(s) to analyse each app…

---

## Overview

This skill detects user personas by analyzing **5 dimensions** of a frontend codebase:

| Dimension | What it reveals | Typical code patterns |
|-----------|----------------|----------------------|
| **1. Routes / Layouts** | Product variants, regional splits | Multiple route files, layout dirs, route groups |
| **2. Subscription Tiers** | Feature access levels | Tier constants, plan names, pricing references |
| **3. Roles & Permissions** | Who can act within features | Role enums, permission checks, guards, `isAdmin` |
| **4. Feature Flags / Modules** | Toggleable capabilities | Feature flag configs, `mod*` flags, `canAccess` patterns |
| **5. Special User Flags** | Edge-case user types | Employee flags, demo accounts, free tiers, internal users |

The output is a **persona matrix** showing which combinations are meaningfully distinct (different feature sets, not just labels).

---

## Step 1: Detect framework and locate key files

Read the `package.json` at `$APP_ROOT` to identify the frontend framework and
key dependencies.

Then use `Glob` and `Grep` **scoped to `$APP_ROOT` + `$LIB_ROOTS`** to locate:

| What to find | Search patterns |
|---|---|
| **Route definitions** | `Glob("**/routes.{ts,tsx,js,jsx}")`, `Glob("**/router.{ts,tsx,js,jsx}")`, `Glob("**/app-routing*.ts")`, `Glob("**/routing/**")` |
| **Layout / shell components** | `Glob("**/layout*/**")`, `Glob("**/shell*/**")`, `Glob("**/app.{tsx,jsx,vue}")` |
| **Auth types / interfaces** | `Grep("interface.*User\|type.*User\|UserData\|UserSession\|AuthContext", type: "ts")` |
| **Constants / enums** | `Grep("role\|tier\|permission\|subscription\|ROLE\|TIER\|PERMISSION", glob: "**/constants.*")` |
| **Guards / HOCs** | `Grep("Guard\|PrivateRoute\|ProtectedRoute\|withAuth\|useAuth\|canAccess\|hasPermission")` |
| **Feature flags** | `Grep("featureFlag\|feature_flag\|isEnabled\|showIf\|mod[A-Z]")` |

Read each discovered file. Build a mental map of the access control architecture before proceeding.

---

## Step 2: Analyze each dimension

### 2.1 Routes & Layouts (Product Variants)

Read all route definition files. For each route file or route group, extract:

- **Route file name / group name** (e.g., `routes.apac.tsx`, `routes.us.tsx`)
- **How many routes** it defines
- **How the app chooses** which route file to load (env var? user data? URL?)
- **Named route groups / tiers within the file** (e.g., `coreRoutes`, `liteRoutes`)

Determine if there are **product variants** — distinct sets of features served by the same codebase to different user populations (by region, plan, tenant, etc.).

Record each variant as a potential persona dimension.

### 2.2 Subscription Tiers

Search for tier/plan constants:
- `Grep("TIER\|PLAN\|SUBSCRIPTION\|subscriptionTier\|pricing\|LM_STANDARD\|LM_LITE\|FREE\|PREMIUM\|PRO\|ENTERPRISE\|BASIC")`
- Check `vite-env.d.ts`, `.env`, `constants.ts`, `config.ts` for tier definitions
- Check route filtering logic — how does the tier determine which routes load?

For each tier found, determine:
- **Tier name / constant value**
- **Which routes / features it enables**
- **How it's set** (from user session? env var? API response?)

### 2.3 Roles & Permissions

Search for role definitions and checks:
- `Grep("roleGroup\|userRole\|isAdmin\|isMaster\|isManager\|isMember\|isEditor\|isViewer\|role.*===\|hasRole\|checkRole")`
- `Grep("Admin\|Manager\|Member\|Editor\|Viewer\|Owner\|Operator", glob: "**/constants.*")`

For each role found:
- **Role name**
- **How it's defined** (enum, constant, string literal)
- **Where it's ACTUALLY CHECKED in the codebase** (not just defined) — count real usages
- **What it gates** (which features, form fields, UI elements)

**Mandatory verification — grep EACH role variable individually:**

For each role check variable found (e.g., `isMaster`, `isManager`, `isMember`):
1. Grep for that SINGLE variable name alone (NOT combined with others via `|`)
2. Exclude the definition file (e.g., `constants.ts`) and import lines
3. Record the count of ACTUAL usage sites per variable
4. If a role variable has 0 usages outside its definition + imports → mark as "defined but unused" and EXCLUDE it from persona generation

NEVER grep multiple role variables in a single pattern (e.g., `isMaster|isManager|isMember`) to count usages — this masks dead-code roles behind active ones. Each must be counted separately.

### 2.4 Feature Flags & Module Toggles

Search for toggleable features:
- `Grep("featureFlag\|feature_flag\|mod[A-Z]\|canAccess\|hasFeature\|isEnabled\|showOptions")`
- Check the user data type/interface for boolean or numeric toggle fields

For each flag found:
- **Flag name**
- **What it enables/disables**
- **Is it tier-dependent or independently toggled?**

### 2.5 Special User Flags

Search for edge-case user types:
- `Grep("isEmployee\|isDemoLite\|isFree\|isInternal\|isTrial\|isGuest\|isAnonymous\|emp_\|FREE_SUBSCRIBER")`
- Check for username-pattern checks (e.g., `username.indexOf("emp_")`)
- Check for special `flag` fields on user data

---

## Step 3: Build the interaction matrix

Now determine how the dimensions **interact**. The key question is: **are they orthogonal (independent) or coupled (one depends on another)?**

Check for places where **two or more dimensions are checked together**:
- `Grep` for conditions that combine role + tier (e.g., `isMaster && isStandard`)
- `Grep` for conditions that combine role + feature flag (e.g., `isMaster && modCustomField`)
- Read the route filtering function — does it consider role, or only tier?

Classify the relationship:

| Relationship | Meaning | Persona impact |
|---|---|---|
| **Orthogonal** | Role works the same regardless of tier | Role is a modifier, not a separate persona |
| **Coupled** | Certain role powers only exist in certain tiers | Role×Tier combos may need separate personas |
| **Redundant** | Role is defined but never checked | Ignore the role for persona modeling |

---

## Step 4: Determine distinct personas

A persona is **distinct** if it has a **meaningfully different feature set** — not just a different label.

**Pre-check before recommending role-based personas:**
Only create a separate persona for a role if that role's check variable has ≥3 usage sites outside its definition and imports. If a role enum/constant exists but its check is never evaluated in component/page code, it is dead code and MUST NOT produce a persona.

Apply these rules:

1. **If tiers define different route sets** → each tier is a candidate persona
2. **If roles gate different features AND are actually checked (≥3 usages)** → role is a persona modifier
3. **If roles are defined but never checked (0 usages outside definition/imports)** → collapse roles (they're identical in practice). Do NOT create separate personas for unused roles
4. **If a role only matters in one tier** (e.g., Admin powers only relevant in Core) → create a separate persona only for that tier×role combo
5. **If feature flags are tier-dependent** → they're part of the tier, not separate personas
6. **If feature flags are independently toggled** → note them as persona modifiers, not separate personas
7. **If special flags create a meaningfully different experience** (e.g., free users, demo accounts) → candidate persona

---

## Step 5: Collate & present findings

Once all parallel agents complete, the **orchestrator** (you) collates their
outputs into a single unified report.

### 5.1 Monorepo Summary

| Field | Value |
|---|---|
| Monorepo type | Nx / pnpm / Lerna / Turbo / npm-yarn |
| Mono root | `$MONO_ROOT` |
| Frontend apps analysed | `<count>` |
| Apps | `<app1> (<framework>), <app2> (<framework>), …` |

### 5.2 Per-app results

For **each app**, include the agent's output verbatim under a heading:

#### App: `<app_name>` (`<$APP_ROOT>`)

- Framework & Detection Summary (from agent)
- Dimensions Discovered (from agent)
- Interaction Analysis (from agent)
- Per-app Persona Table (from agent)

### 5.3 Cross-app analysis

After presenting per-app results, analyse **across apps**:

1. **Shared personas** — do any personas appear in multiple apps with the same
   gate / role / tier? (e.g., "Admin" exists in both `web` and `syndication`
   with the same role enum). Note them as shared.
2. **App-exclusive personas** — personas that only exist in one app (e.g.,
   "Syndication Publisher" only in the syndication app).
3. **Shared auth / constants** — if multiple apps import the same auth types or
   role constants from a shared lib, note that the persona definitions are
   structurally linked.

### 5.4 Unified Persona Matrix

Merge all per-app persona tables into a **single table**. The `Surface` column
distinguishes which app each persona belongs to. If a persona spans multiple
apps, list all surfaces.

| # | Persona | Surface | Gate | Feature scope | Why it is distinct |
|---|---|---|---|---|---|

Column definitions:

- **Persona** — a human-readable name for the user type (e.g., "Standard Admin", "Lite Member", "Free Subscriber").
- **Surface** — the UI surface / app this persona accesses (e.g., "web", "syndication", "web + syndication"). Use the monorepo app name.
- **Gate** — what mechanism determines this persona's access: subscription tier, role check, feature flag, special user flag, or a combination (e.g., "Tier: LM_STANDARD + Role: isMaster", "Flag: isEmployee"). Use the actual constant/variable names from the code.
- **Feature scope** — brief summary of what this persona can do that others cannot, or what is restricted (e.g., "Full admin panel, user management, custom fields", "Read-only dashboard, no exports").
- **Why it is distinct** — the concrete evidence that this persona has a meaningfully different experience, not just a different label (e.g., "14 route-gated features exclusive to this tier", "isMaster checked in 23 components to show admin controls").

---

## Step 6: Compare with existing graph personas

This skill is **analysis-only** — it does NOT write personas to the
graph. Graph writes are the responsibility of downstream skills
(e.g., `/breeze:generate-functional-from-ui`) that consume this
skill's output as input.

1. Call `Get_all_personas` to fetch existing personas from the graph
2. Present a side-by-side comparison table:

| Detected from code | Exists in graph? | Match | Notes |
|---|---|---|---|
| APAC Core Admin | ✅ "Admin" | Partial — graph persona is broader | Consider renaming |
| US Tall User | ❌ | — | New persona detected |

3. Summarize recommendations:
   - Which detected personas are new (not in graph)
   - Which existing personas are too broad or too narrow
   - Which existing personas have no code evidence (possible stale data)

**If the user explicitly asks to create/update personas in the graph**,
then proceed with graph writes:

1. For each confirmed new persona, call `Call_Create_Functional_Node_` with:
   ```
   label: "Persona"
   data: { persona: "<persona name>" }
   uuid: <projectUuid>
   ```
2. Prepare a citation for the analysis:
   - type: `"code"`
   - name: `"Persona detection from frontend UI"`
   - reference: path to the main route file(s) analyzed
   - inputText: summary of the detection analysis
3. Attach the citation to each created persona node

Otherwise, end with the analysis output. Other skills (like
`/breeze:generate-functional-from-ui`) will use the persona matrix
to populate the graph as part of their own workflow.

---

## Appendix: Framework-specific patterns

### React (CRA / Vite / Next.js)
- Routes: `react-router-dom` (`<Route>`, `createBrowserRouter`), Next.js file-based (`app/`, `pages/`)
- Auth: `useAuth()` hooks, `AuthContext`, `PrivateRoute` components
- Guards: HOCs (`withAuth`), route `loader` functions

### Vue (Vue Router / Nuxt)
- Routes: `vue-router` (`routes` array), Nuxt file-based (`pages/`)
- Auth: `navigation guards` (`beforeEach`), `meta.requiresAuth`
- Guards: Route meta fields, middleware

### Angular
- Routes: `app-routing.module.ts`, `Routes[]` array
- Auth: `CanActivate` guards, `AuthGuard`
- Guards: Route `data.roles`, `canActivate` arrays

### Svelte (SvelteKit)
- Routes: File-based (`src/routes/`)
- Auth: `hooks.server.ts`, `+layout.server.ts` load functions
- Guards: `+page.server.ts` redirect logic

 