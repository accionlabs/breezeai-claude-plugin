---
name: update-graph
description: >
  Create or update nodes in the functional graph
  (Persona > Outcome > Scenario > Step > Action) from code,
  documents, or Figma designs. Use when: "update functional graph",
  "add to graph", "capture this in the functional graph", after
  analyzing a Figma frame, document, or code cluster.
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

## Hierarchy

    Persona (WHO -- the actor of intent)
      └─ Outcome (WHAT -- high-level business capability)
           └─ Scenario (HOW -- specific user/system flow)
                └─ Step (sequential stage within a scenario)
                     └─ Action (granular UI interaction or system op)

---

## Execution Flow

### 1. Analyze Input

Identify functional intents from the input (Figma frame, document,
code).

### 2. Load Existing Graph

- Call `Get_all_personas` -> get all existing personas
- Call `Functional_Graph_Search` with key terms -> find nearest
  outcomes/scenarios

### 3. Resolve Personas (REUSE FIRST)

Apply persona resolution in strict priority order:

1. **Named human role** implied by business domain
   (e.g., Admin, Fund Manager, Compliance Officer, Media Analyst)
2. **Generic human role** when domain role cannot be determined
   -> "User", "Customer", "Visitor"
3. **External System** -- trigger originates outside the application
   boundary (webhooks, partner APIs, payment gateways, inbound
   integrations). Do NOT use for internal subsystems.
4. **System** -- ONLY if the behavior is fully internal and automated
   with no human or external system initiating or consuming the
   outcome. Covers: background jobs, queue workers, schedulers,
   cron tasks, internal automation pipelines, script-triggered
   API calls.

**Resolution rules:**

- Always check existing Personas FIRST before creating new ones
- Merge similar roles (e.g., "Admin User" and "Administrator"
  -> reuse one)
- If the actor is ambiguous between User and System, ask:
  "Does a human make a real-time decision that causes this to run?"
  -> YES -> Use the human Persona
  -> NO  -> Use "System"
- If ambiguous between System and External System:
  "Does the trigger originate outside this application's boundary?"
  -> YES -> External System
  -> NO  -> System
- If the triggering actor is truly ambiguous, default to "User",
  not "System"

**Forbidden Persona names -- NEVER use:**

- Developer, Engineer, Programmer, Architect
- API, Service, Component, Module, Worker
- Backend, Frontend, Database
- Controller, Handler, Repository

If you find yourself writing one of these, STOP and re-resolve
using the priority order above.

### 4. Resolve Outcomes (REUSE FIRST)

Outcomes represent **high-level business capabilities**, not
technical functions or API endpoints.

- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent
  without becoming misleading

**Good Outcome names:**
- "Manage Fund Allocations"
- "Monitor Compliance Status"
- "Generate Reports"
- "Manage Code Ontology"

**Bad Outcome names (anti-patterns):**
- "Handle API Requests" (technical, not business)
- "Process Database Queries" (implementation detail)
- "Render Components" (frontend implementation)
- One Outcome per API endpoint (too granular)
- Outcome names matching function/class names (too technical)
- Duplicate Outcomes with slightly different wording

**Outcome quality checks:**
- Understandable by non-technical stakeholders
- Stable across implementation and code changes
- Broad enough to absorb future Scenarios
- If more than 3-4 new Outcomes appear necessary, re-evaluate
  for over-segmentation

### 5. Create Scenarios

A Scenario describes a **specific user or system flow** under an
Outcome. It should be testable -- you can write acceptance criteria
for it. It should have a clear start and end.

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging them
- Each Scenario must include a brief description

**Good Scenario names:**
- "Filter Dashboard by Date Range"
- "Submit Compliance Report"
- "Import code repository"

**Bad Scenario names:**
- "Use the System" (too vague)
- "Do Things with Data" (meaningless)

**For System Persona scenarios**, the description MUST describe the
internal processing behavior, NOT the UI that triggers it:
- Good: "System processes embedding generation request, calls
  Bedrock API, stores vectors, and runs clustering."
- Bad: "Generate embeddings for code ontology and perform
  clustering analysis in the background."

### 6. Create Steps

Steps are the **sequential stages** within a Scenario. They
represent the major phases a user or system goes through to
complete the flow.

**Step rules:**

- Each Step is a distinct stage in the Scenario's flow
- Steps are ORDERED -- they represent a sequence
- A Step name should be a short verb phrase describing the stage
- Each Step must include a description explaining what happens
- Steps require a `scenarioId` (the parent Scenario's ID)

**Good Step names:**
- "Select Date Range"
- "View KPI Cards"
- "Apply Filters"
- "Validate uploaded data"

**Bad Step names:**
- "Step 1" (not descriptive)
- "Processing" (too vague)
- "Misc" (meaningless)

**Quantity guidelines:**
- A Scenario typically has 3-8 Steps
- If more than 10, consider splitting the Scenario
- If fewer than 2, consider merging with another Scenario

**Step data format for `Call_Create_Functional_Node_`:**

    label: "Step"
    data: {
      "step": "<short verb phrase>",
      "description": "<what happens during this stage>",
      "scenarioId": "<parent scenario ID>"
    }

**How to derive Steps from different inputs:**

- **Figma/Design:** Each distinct section or interaction zone on the
  screen (e.g., "View Header Navigation", "Configure Date Filters",
  "Review Chart Widgets")
- **Document/Requirements:** Each numbered step or phase described
  in the user journey
- **Frontend Code:** Each major UI state change, page section
  render, or user interaction handler
- **Backend Code:** Each processing phase
  (validate -> transform -> persist -> notify)

### 7. Create Actions

Actions are the **granular UI interactions or system operations**
within a Step. They represent the atomic things a user clicks,
types, or sees -- or the atomic operations a system performs.

**Action rules:**

- Each Action is a single, atomic interaction or operation
- Actions are the MOST DETAILED level of the hierarchy
- An Action name should be specific and concrete
- Each Action must include a description with expected behavior
  or result
- Actions require a `stepId` (the parent Step's ID)

**Good Action names:**
- "Click 'Submit' button"
- "Enter email in login field"
- "System validates JWT token"
- "Click 'Creer un tableau de bord' button"

**Bad Action names:**
- "Interact with form" (too vague)
- "Process data" (not specific)
- "Handle click" (implementation term)

**Quantity guidelines:**
- A Step typically has 1-5 Actions
- If more than 5, consider splitting the parent Step

**Action data format for `Call_Create_Functional_Node_`:**

    label: "Action"
    data: {
      "action": "<specific interaction or operation>",
      "description": "<expected behavior or result>",
      "stepId": "<parent step ID>"
    }

**How to derive Actions from different inputs:**

- **Figma/Design:** Each button, input field, toggle, dropdown,
  link, or interactive element visible in the design
  (e.g., "Click download icon on widget", "Toggle 'Titre
  uniquement' switch", "Hover over pie chart segment to see
  tooltip")
- **Document/Requirements:** Each specific user action or system
  response mentioned in acceptance criteria
- **Frontend Code:** Each event handler (onClick, onChange,
  onSubmit), form field, or conditional render
- **Backend Code:** Each API call, database query, validation
  check, or transformation operation

**Example -- full hierarchy for a dashboard filter:**

    Persona: Media Analyst
      └─ Outcome: Manage Dashboard Configuration
           └─ Scenario: Apply Filters and Date Range
                └─ Step: Configure Date Range
                     ├─ Action: Click 'Du' date picker input
                     ├─ Action: Select start date from calendar
                     ├─ Action: Click 'Au' date picker input
                     └─ Action: Select end date from calendar
                └─ Step: Apply Keyword Filter
                     ├─ Action: Type keyword in 'Filtrer par
                     │  mot-cles' input
                     └─ Action: Toggle 'Titre uniquement' switch

### 8. Create Nodes Top-Down

Use `Call_Create_Functional_Node_` in strict order:
Persona -> Outcome -> Scenario -> Step -> Action

Each call requires the parent ID from the previous level:

- Outcome needs `personaId`
- Scenario needs `outcomeId`
- Step needs `scenarioId`
- Action needs `stepId`

Wait for each create call to return the new node's `id` before
creating its children.

Use `Call_Update_Functional_Node_` to refine existing nodes.

---

## Input-Type Handling

### Figma/Design

- Persona = Human user of the UI
- Outcome = Group by page/feature area
- Scenario = Each screen/widget/interaction flow
- Step = Each section or interaction zone on the screen
- Action = Each button, input, toggle, chart interaction visible

### Document/Requirements

- Persona = Actor of intent stated or implied
- Outcome = Business capability described
- Scenario = User journeys described
- Step = Each phase or numbered step in the journey
- Action = Each specific user action or system response in
  acceptance criteria

### Frontend Code

- Persona = Human user of the UI
- Outcome = Group by feature/page
- Scenario = Map components to user flows
- Step = Each major UI state change or section render
- Action = Each event handler, form field, or conditional render

Mapping guide:
- Components -> Scenarios (each major component maps to a flow)
- Event handlers -> Actions (onClick, onChange, etc.)
- Page sections -> Steps (each section is a stage)
- Routes -> Outcomes (each route group serves a capability)

### Backend Code (serves UI)

- Persona = Human who triggers the API
- Outcome = Business domain (not endpoint paths)
- Scenario = Infer user-facing flow
- Step = Each processing phase (validate, transform, persist)
- Action = Each API call, DB query, or validation check

Mapping guide:
- Controllers/Routes -> Scenarios (each endpoint maps to a flow)
- Middleware -> Steps (validation, auth, rate limiting)
- Service methods -> Steps (business logic phases)
- Database queries -> Actions (atomic data operations)

### Backend Code (internal/automated)

- Persona = System or External System
- Outcome = Processing capability
- Scenario = Describe processing flow (not user flow)
- Step = Each processing stage in the pipeline
- Action = Each atomic operation (parse, compute, store, emit)

Do NOT invent fictional UI interactions for pure backend code.
If no human triggers the functionality, use "System" as Persona.

### Technical/Infrastructure Content

When encountering purely technical content (config files, build
scripts, infrastructure code):

- Do NOT create Personas like "Developer" or "DevOps Engineer"
- Ask: "What user-facing capability does this support?"
- If it supports no direct user capability, it may not need
  functional graph nodes
- Infrastructure code -> map to the Outcomes it enables, not to
  its own Outcome

---

## NO-OP Rule

If the input only elaborates on existing functionality and
introduces no new Persona, Outcome, Scenario, Step, or Action,
report: "No new nodes needed."

This applies when the input:
- Only adds detail to existing nodes
- Contains ONLY API endpoint definitions with no inferable
  business intent
- Contains ONLY internal utility/helper functions with no
  user-facing behavior
- Contains ONLY data models, schemas, or type definitions

---

## Output Format

When proposing new nodes, present them in this format for user
approval:

```
[CREATE/REUSE] Persona: <name> (ID: <id if reusing>)
  [CREATE/REUSE] Outcome: <name> (ID: <id if reusing>)
    [CREATE] Scenario: <name>
      Description: <brief description>
      [CREATE] Step 1: <name>
        Description: <what happens>
        [CREATE] Action: <specific interaction>
          Description: <expected behavior>
        [CREATE] Action: <specific interaction>
          Description: <expected behavior>
      [CREATE] Step 2: <name>
        Description: <what happens>
        ...
```

Always present the plan to the user for approval before calling
`Call_Create_Functional_Node_`.