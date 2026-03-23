---
name: generate-code
description: >
  Generate code and test cases informed by the functional graph and
  code graph. Ensures implementations align with requirements and
  existing patterns. Use when: "generate code for X", "write tests
  for Y", "implement this scenario", "scaffold the API for Z",
  "generate frontend", "generate backend", "build the UI",
  "scaffold the full app". Supports both selective (single scenario)
  and full-project generation.
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

---

## Determine Generation Scope

Parse $ARGUMENTS to determine scope:

**Selective generation** (single scenario or feature):
- "generate code for login", "implement VAL-001", "scaffold the upload page"
- → Go to **Workflow A: Selective Generation**

**Full frontend generation:**
- "generate frontend", "build the UI", "create React app", "scaffold frontend"
- → Go to **Workflow B: Full Frontend Generation**

**Full backend generation:**
- "generate backend", "build the API", "scaffold backend", "create Express app"
- → Go to **Workflow C: Full Backend Generation**

**Full-stack:**
- "generate full app", "build everything", "scaffold full-stack"
- → Run Workflow B then Workflow C sequentially

If ambiguous, ask the user which scope they want.

---

## Workflow A: Selective Generation

For generating code for a specific feature, scenario, or user story.

### A1. UNDERSTAND — Get the functional spec

- Call `Functional_Graph_Search` with the feature/scenario name
- Call `Get_all_steps_actions_for_a_scenario_id` for matched scenarios
- This gives you the WHAT: steps, actions, expected user interactions

### A2. DISCOVER — Find existing code patterns

- Call `Code_Graph_Search` with related terms
- Call `Get_Code_File_Details` on the most relevant files to inspect
  class structure, methods, and patterns
- Find existing files, functions, patterns, utilities
- This gives you the HOW: conventions, imports, patterns to follow

### A3. REFERENCE — Get business rules

- Call `Documents` for formulas, thresholds, validation rules
- This gives you the CONSTRAINTS: exact rules the code must enforce

### A4. GENERATE — Write code

- Follow existing code patterns found in step A2
- Align with functional steps from step A1
- Reuse existing utilities/components from code graph
- Apply business rules from step A3
- Add comments referencing functional graph node IDs for traceability

### A5. TEST — Generate test cases from scenarios

Map functional hierarchy to test structure:

    For each Scenario:
      describe("[Scenario Name]")
        For each Step:
          it("[Step Name]")
            For each Action:
              → Assert the expected behavior

- One test suite per scenario
- Test cases map 1:1 to steps
- Edge cases derived from action descriptions
- Include both happy path and error scenarios

---

## Workflow B: Full Frontend Generation

For generating an entire frontend application from the functional graph.
This follows the **Graph-to-UI pattern**: Persona → Auth, Outcome → Nav,
Scenario → Page sections, Step → Component interactions, Action → UI elements.

### B1. EXTRACT — Build the persona-to-UI map

Call `Get_all_personas` with the project UUID.

For each persona returned, call `Get_all_outcomes_for_a_persona_id`.

Build a **persona-outcome map** — this drives the entire UI structure:

```
Persona → Outcomes[]
  Fund Operations User → [Manage CSV File Uploads, ...]
  Fund Operations Analyst → [Review Validation Results, Generate Reports, ...]
  Admin → [Configure Settings, Manage Audit Log, ...]
  System → [internal processing — no UI needed]
```

**Skip the System persona** — it has no UI. Also skip External System
personas. Only human personas generate UI.

### B2. CONSOLIDATE — Map personas to auth roles

Multiple graph personas often map to fewer auth roles based on
**permission boundaries**, not 1:1 persona-to-login mapping.

Rules for consolidation:
- Group personas that share the same permission level
- The graph models WHO DOES WHAT (behavioral roles)
- Auth models WHO IS ALLOWED TO DO WHAT (permission boundaries)
- A single user may act as multiple personas (e.g., upload files as
  "Fund Operations User" and review dashboard as "Fund Operations Analyst")

Present the proposed mapping to the user for confirmation:

```
| Graph Persona           | Auth Role  | Why                                    |
|-------------------------|------------|----------------------------------------|
| Fund Operations User    | analyst    | Uploads files, triggers validation     |
| Fund Operations Analyst | analyst    | Reviews dashboard, adds comments       |
| Fund Controller         | analyst    | Reviews specific rule results           |
| Fund Reviewer           | reviewer   | Can approve/waive/reject exceptions    |
| Admin                   | admin      | System configuration, audit access     |
| Compliance Officer      | admin      | Audit log access (restricted view)     |
| System                  | (no UI)    | Backend automation                     |
```

### B3. DERIVE — Map outcomes to navigation and routes

Each outcome becomes a page or section in the navigation.
Group outcomes by auth role visibility:

```
Outcome → Route → Visible to roles
─────────────────────────────────────
"Manage CSV File Uploads"     → /upload           → [all roles]
"Review Validation Results"   → /dashboard        → [all roles]
"Generate Validation Reports" → button on dashboard → [all roles]
"Configure Validation Settings" → /admin/settings  → [admin]
"Manage Audit Log"            → /admin/audit-log   → [admin]
```

Present the proposed navigation structure to the user.

### B4. DETAIL — Get scenarios for each page

For each outcome that maps to a page, call
`Get_all_scenarios_for_a_outcome_id`.

This tells you what features each page must support. For example,
the Dashboard page might need:
- "View RAG Exception Summary Dashboard" → KPI cards + grid
- "Filter and sort exception grid" → filter bar
- "View exception details in drill-down panel" → slide-in panel
- "Add commentary to exceptions" → comment form
- "Change exception status" → status dropdown (reviewer/admin only)

### B5. DEEP DIVE — Get steps and actions for key scenarios

For the most complex scenarios, call
`Get_all_steps_actions_for_a_scenario_id` to get the exact
UI interactions needed.

This reveals:
- What form fields are needed (from "Provide..." actions)
- What displays are needed (from "Observe..." actions)
- What validation rules apply (from action descriptions)
- What role-gating is needed (from persona ownership)
- What error messages to show (from action descriptions)

### B6. DATA — Build dummy payloads from source documents

Call `Documents` with broad queries to find:
- Sample data values (prices, dates, amounts, names)
- Business rules (thresholds, formulas, materiality levels)
- Validation rules and error messages
- Acceptance criteria with expected values

Create JSON data files that:
- Cover all entity types referenced in the functional graph
- Include realistic values from source documents
- Have a clear structure matching the graph's entity model
- Are easily replaceable with backend API calls

Mark all data imports with a comment:
```
// TODO: Replace with API call — GET /api/exceptions
import exceptions from '../data/exceptions.json';
```

### B7. SCAFFOLD — Generate the project

Ask the user for tech stack preferences, or suggest based on any
existing code in the repo (check via `Code_Graph_Search`).

**Default frontend stack:** React + TypeScript + Vite + Tailwind CSS

Generate files in this order:

1. **Project setup** — package.json, vite.config, tsconfig, CSS
2. **Types** — TypeScript interfaces from graph entity model
3. **Data files** — Dummy JSON from step B6
4. **Auth context** — From persona→role map (step B2)
5. **Shared components** — Badges, inputs, tables derived from
   common patterns across scenarios
6. **Layout + Navigation** — From outcome→route map (step B3)
7. **Pages** — One per route, covering all scenarios (step B4)
8. **Route wiring** — App.tsx with protected routes per role

For each page, use the scenarios as a checklist:
- Each scenario = a section or interaction on the page
- Each step = a sequential phase in the interaction
- Each action = a specific UI element or behavior

### B8. VERIFY — Build and test

Run the project's build command (e.g., `npx tsc --noEmit && npx vite build`)
to verify zero errors.

If errors found, fix them and re-verify.

Present the file manifest to the user with:
- File path and size
- Which graph personas/outcomes/scenarios it covers
- How to run the dev server

---

## Workflow C: Full Backend Generation

For generating an entire backend application from the functional graph.
This follows the **Graph-to-API pattern**: Persona → Auth middleware,
Outcome → Resource/Controller, Scenario → Endpoint, Step → Handler logic,
Action → Business rule implementation.

### C1. EXTRACT — Build the persona-to-API map

Same as B1: Call `Get_all_personas` then `Get_all_outcomes_for_a_persona_id`
for each persona.

Additionally, pay special attention to the **System persona** — its
scenarios define background jobs, cron tasks, and internal processing
pipelines that need backend implementation.

### C2. CONSOLIDATE — Map personas to auth middleware

Same consolidation as B2, but output as middleware/guard definitions:

```
Auth Role   → Middleware         → Allowed endpoints
analyst     → requireRole('analyst')  → GET /api/exceptions, POST /api/upload
reviewer    → requireRole('reviewer') → PATCH /api/exceptions/:id/status
admin       → requireRole('admin')    → ALL /api/admin/*
```

### C3. DERIVE — Map outcomes to API resources

Each outcome becomes an API resource or controller:

```
Outcome → Resource → Endpoints
──────────────────────────────
"Manage CSV File Uploads"       → /api/upload      → POST, GET /status
"Review Validation Results"     → /api/exceptions   → GET, GET/:id
"Configure Validation Settings" → /api/admin/config → GET, PUT
"Manage Audit Log"              → /api/admin/audit  → GET, GET/export
```

### C4. DETAIL — Get scenarios for each resource

For each outcome, call `Get_all_scenarios_for_a_outcome_id`.

Map scenarios to HTTP endpoints:
- "Upload CSV files" → POST /api/upload
- "View exception details" → GET /api/exceptions/:id
- "Change exception status" → PATCH /api/exceptions/:id/status
- "Export PDF Validation Report" → GET /api/reports/pdf

### C5. DEEP DIVE — Get business logic from steps/actions

For System persona scenarios, call `Get_all_steps_actions_for_a_scenario_id`
to extract:
- Validation formulas (from action descriptions)
- Threshold values and business rules
- Error messages and status codes
- Data transformation logic
- Database query requirements

### C6. REFERENCE — Get constraints from documents

Call `Documents` for:
- Database schema requirements
- API contract specifications
- Business rule formulas and thresholds
- Error handling requirements

### C7. SCAFFOLD — Generate the backend

Ask the user for tech stack preferences.

**Default backend stack:** Node.js + Express + TypeScript

Generate files in this order:

1. **Project setup** — package.json, tsconfig
2. **Types/Models** — From graph entity model + System persona actions
3. **Database schema** — From entity relationships in the graph
4. **Auth middleware** — From persona→role map (step C2)
5. **Routes** — From outcome→resource map (step C3)
6. **Controllers** — One per resource, with endpoint handlers from C4
7. **Services** — Business logic from System persona steps/actions (C5)
8. **Validators** — Input validation from action descriptions
9. **Dummy data/seeds** — From Documents (step C6)
10. **Tests** — Map scenarios to API test suites

### C8. VERIFY — Build and test

Run the build command and verify zero errors.

---

## Reference: Graph-to-Code Mapping Cheatsheet

```
FUNCTIONAL GRAPH          FRONTEND                BACKEND
─────────────────         ─────────────           ──────────────
Persona                   Auth role               Auth middleware
Outcome                   Nav section / Page      API resource / Controller
Scenario                  Page feature / Section  Endpoint handler
Step                      User interaction phase  Processing phase
Action (human)            UI element / Form field Request parameter
Action (system)           (not in UI)             Business logic / Service
Action (system desc)      (not in UI)             Formula / Threshold / Rule
```

## Reference: Dummy Data Pattern

When building dummy data files, always:

1. Shape data from source documents (real business values, not lorem ipsum)
2. Cover all entity types in the functional graph
3. Include edge cases (nulls, empty arrays, boundary values)
4. Add TODO comments for API replacement:
   ```typescript
   // TODO: Replace with API call — GET /api/exceptions
   const exceptions = await fetch('/api/exceptions').then(r => r.json());
   ```
5. Store in `/src/data/*.json` (frontend) or `/seeds/*.json` (backend)
6. Match the TypeScript interfaces exactly

## Reference: Auth Role Consolidation Rules

When mapping graph personas to auth roles:

1. **Permission boundaries drive roles, not persona count**
   - Multiple personas can share one role if permissions are identical
2. **System persona = no auth role** (backend automation)
3. **External System persona = API key auth** (not user login)
4. **Look for escalation patterns** in the graph:
   - "Can only view" → base role
   - "Can view + modify status" → elevated role
   - "Can configure system" → admin role
5. **Present the mapping to the user** — they know the org structure
