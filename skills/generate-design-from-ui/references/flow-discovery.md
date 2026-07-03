# Flow Discovery — Grep Strategy & Evidence Rules

## Grep-First Rule (⛔ MANDATORY)

**All grep-based discovery MUST be done UPFRONT for all scenarios
in a batch/outcome BEFORE processing any individual scenario.**

1. Identify all unique target pages across all scenarios
2. Run Type A + Type B + page nav greps ONCE per unique page
3. Read the page files to map all modals, drawers, conditional UI
4. Analyze each scenario's actions against the grep results
5. Compile into a Grep Evidence Cache with per-scenario breakdown
6. THEN process scenarios — each pulls from the cache

**Why:** Prevents grep-skipping drift after the first scenario.
Also more efficient — one grep covers all same-page scenarios.

**What differs per scenario is the ACTION ANALYSIS, not the greps.**
Same page, same grep results — but "Save Search" triggers a modal
while "Sort Results" doesn't. The per-scenario analysis maps each
action to the specific UI element (modal, drawer, conditional
section) it activates.

---

## How Flows Are Discovered from UI Code

The functional graph captures WHAT the user does. The UI code reveals
HOW MANY WAYS they can do it. There are **two types** of flow discovery:

### Type A: Entry-point flows (different ways to reach the target page)

Grep the ENTIRE repo for `navigate()`, `<Link>`, `router.push()` calls
pointing to the scenario's target route. Each hit identifies a source
page. Classify:

| Pattern | Separate Flow? |
|---|---|
| Different source pages with different preceding steps | **Yes** |
| Dashboard shortcut that skips listing page | **Yes** |
| Deep link with different page behavior | **Yes** |
| Same source page, different trigger component | **No** |
| Breadcrumb/back navigation | **No** |

Also check if the target page reads `from`, `source`, `location.state`
to render differently per entry point — confirms separate flows.

### Type B: On-page flows (conditional paths on the target page)

Grep the page directory for branching patterns. Classify:

| Pattern | Separate Flow? |
|---|---|
| Ternary rendering different component trees | **Yes** |
| Tab group with self-contained workflows | **Yes** |
| Wizard with express/skip mode | **Yes** |
| Modal vs full-page for same operation | **Yes** |
| Bulk vs single operation | **Yes** |
| Show/hide optional fields | **No** |
| Loading/error states | **No** |
| Permission-gated sections | **No** |
| Responsive layout switches | **No** |

### Combine Type A + Type B

Entry-point flows × on-page flows × modalities = total flows.
If no signals from either type → one default flow per modality.

---

## Source-of-Truth Hierarchy

| Tool | When to use | Why |
|---|---|---|
| **Outcome citations** | **Preferred first step** — read the cited source files before grepping | Citations point to the exact UI files the scenario was generated from — most accurate starting point |
| `Glob` / `Read` / `Grep` on the UI folder | **Fallback** — when citations are missing or incomplete | Filesystem has literal JSX, component hierarchy, props |
| `Code_Graph_Search` on the UI repo | **Optional accelerator** — locate pages or trace imports | Faster than blind globbing, but always confirm by `Read` |
| `Design_Graph_Search` | **Dedup check only** — never as source of UI knowledge | Step 2 dedup |
| Functional graph tools | **Scenario/step/action structure** — the skeleton to enrich | Fetch incrementally per scenario |

---

## Frontend Repo Detection

A valid frontend repo has `package.json` AND at least one of:
`src/router/`, `src/routes/`, `app/routes`, `pages/`, `src/pages/`,
`app/`, or React/Vue/Angular Router imports under `src/`.

---

## Persona Filtering

**Only human persona scenarios are eligible for design generation.**

| Persona Type | Process? | Reason |
|---|---|---|
| Human roles (User, Admin, etc.) | **Yes** | Has UI to design |
| System | **No — skip** | Background jobs, no UI |
| External System | **No — skip** | Webhooks/integrations, no UI |

**How to filter (blocklist approach) — ⛔ BLOCKING GATE:**

> You MUST NOT fetch, display, or process any scenario until the
> blocklist is fully built. No exceptions.

1. `Get_all_personas(uuid)` — get all personas
2. Identify non-human personas: `System`, `External System`
3. For each non-human persona:
   `Get_all_outcomes_for_a_persona_id(uuid, personaId)` → collect outcome IDs
4. Store all collected outcome IDs in `blockedOutcomeIds` set
5. **Verify** the set was built — if zero personas returned, STOP
6. Check each scenario's `outcomeId` against the blocklist before processing
