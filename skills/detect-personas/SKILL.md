---
name: detect-personas
description: >
  Detect user personas from a frontend UI repository by analyzing routes, layouts,
  subscription tiers, roles, feature flags, and access control patterns. Optionally
  create or update personas in the Breeze functional graph.
  Use when: "detect personas", "identify personas", "who uses this app",
  "find user types", "analyze personas from UI", "persona detector".
---

## Guard

1. Read `.breeze.json` in the current working directory. If missing or incomplete, tell the user to run `/breeze:setup-project`.
2. Extract `apiKey` and `projectUuid`.
3. **Validate this is a frontend UI repo.** Check for ANY of these markers:
   - `package.json` exists AND contains one or more of: `react`, `vue`, `angular`, `svelte`, `next`, `nuxt`, `gatsby`, `remix`, `solid`, `lit`, `ember`, `backbone`
   - Directories like `src/pages/`, `src/views/`, `src/screens/`, `src/routes/`, `src/app/`, `app/`, `pages/`
   - Route definition files (e.g., `routes.ts`, `router.ts`, `routes.tsx`, `router.tsx`, `app-routing.module.ts`)

   If NONE of these markers are found, **stop** and tell the user:
   _"This doesn't appear to be a frontend UI repository. The persona detector skill needs to run against a frontend codebase (React, Vue, Angular, etc.). Please cd into the frontend repo and try again."_

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

Read `package.json` to identify the frontend framework and key dependencies.

Then use `Glob` and `Grep` to locate:

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

## Step 5: Present findings

Present the analysis in this structured format:

### 5.1 Framework & Detection Summary

Brief summary: framework, number of route files found, total routes, layout variants.

### 5.2 Dimensions Discovered

For each of the 5 dimensions, present what was found (or "Not detected"):

**Routes & Layouts:**
- Table of route files → route count → how they're selected

**Subscription Tiers:**
- Table of tier name → constant → feature count → description

**Roles:**
- Table of role name → defined where → actually checked (count) → what it gates

**Feature Flags / Modules:**
- Table of flag name → what it enables → tier-dependent or independent

**Special Flags:**
- Table of flag → what it means → impact on UX

### 5.3 Interaction Analysis

How dimensions relate (orthogonal / coupled / redundant) with evidence.

### 5.4 Persona Matrix

A table showing the recommended personas with:

| # | Persona name | Tier | Role (if relevant) | Region (if relevant) | Feature scope | Why it's distinct |
|---|---|---|---|---|---|---|

### 5.5 Feature Access Table

A comprehensive table showing features × personas (✅/❌), similar to:

| Feature | Persona 1 | Persona 2 | Persona 3 | ... | Gated by |
|---|---|---|---|---|---|

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
