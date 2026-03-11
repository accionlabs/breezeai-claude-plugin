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

    Persona (WHO — the actor of intent)
      └─ Outcome (WHAT — high-level business capability)
           └─ Scenario (HOW — specific user/system flow)
                └─ Step (sequential stage within a scenario)
                     └─ Action (granular UI interaction or system op)

## Execution Flow

### 1. Analyze Input

Identify functional intents from the input (Figma frame, document,
code).

### 2. Load Existing Graph

- Call `Get_all_personas` → get all existing personas
- Call `Functional_Graph_Search` with key terms → find nearest
  outcomes/scenarios

### 3. Resolve Personas (REUSE FIRST)

Apply persona resolution rules from `func-prompt-rules.md`:

- **1st priority:** Named human role (Admin, Fund Manager,
  Compliance Officer)
- **2nd priority:** Generic human role (User)
- **3rd priority:** External System (Webhook, Partner API)
- **4th priority:** System (Background job, Scheduler)

**NEVER use:** Developer, Engineer, API, Service, Component, Module,
Backend, Frontend, Database

Reuse an existing Persona if it matches. Create new ONLY if none
fits.

### 4. Resolve Outcomes (REUSE FIRST)

- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent

### 5. Create Scenarios

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- Each Scenario must include a brief description

### 6. Create Steps

Steps are the **sequential stages** within a Scenario. They represent
the major phases a user or system goes through to complete the flow.

**Step rules:**

- Each Step is a distinct stage in the Scenario's flow
- Steps are ORDERED — they represent a sequence (step 1, then 2,
  then 3...)
- A Step name should be a short verb phrase describing the stage
  (e.g., "Select Date Range", "View KPI Cards", "Apply Filters")
- Each Step must include a description explaining what happens
  during this stage
- A Scenario typically has 3–8 Steps. If you have more than 10,
  consider whether some Steps should be merged or the Scenario
  should be split
- Steps require a `scenarioId` (the parent Scenario's ID)

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
- **Backend Code:** Each processing phase (validate → transform →
  persist → notify)

### 7. Create Actions

Actions are the **granular UI interactions or system operations**
within a Step. They represent the atomic things a user clicks, types,
or sees — or the atomic operations a system performs.

**Action rules:**

- Each Action is a single, atomic interaction or operation
- Actions are the MOST DETAILED level of the hierarchy
- An Action name should be specific and concrete
  (e.g., "Click 'Creer un tableau de bord' button",
  "Enter start date in date picker",
  "System validates input against schema")
- Each Action must include a description with expected behavior
  or result
- A Step typically has 1–5 Actions. If you have more, consider
  splitting the parent Step
- Actions require a `stepId` (the parent Step's ID)

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

**Example — full hierarchy for a dashboard filter:**

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
Persona → Outcome → Scenario → Step → Action

Each call requires the parent ID from the previous level:

- Outcome needs `personaId`
- Scenario needs `outcomeId`
- Step needs `scenarioId`
- Action needs `stepId`

Wait for each create call to return the new node's `id` before
creating its children.

Use `Call_Update_Functional_Node_` to refine existing nodes.

### Input-Type Handling

**Figma/Design:**
Persona = Human user of the UI.
Outcome = Group by page/feature area.
Scenario = Each screen/widget/interaction flow.
Step = Each section or interaction zone on the screen.
Action = Each button, input, toggle, chart interaction visible.

**Document/Requirements:**
Persona = Actor of intent stated or implied.
Outcome = Business capability described.
Scenario = User journeys described.
Step = Each phase or numbered step in the journey.
Action = Each specific user action or system response in
acceptance criteria.

**Frontend Code:**
Persona = Human user of the UI.
Outcome = Group by feature/page.
Scenario = Map components to user flows.
Step = Each major UI state change or section render.
Action = Each event handler, form field, or conditional render.

**Backend Code (serves UI):**
Persona = Human who triggers the API.
Outcome = Business domain (not endpoint paths).
Scenario = Infer user-facing flow.
Step = Each processing phase (validate, transform, persist).
Action = Each API call, DB query, or validation check.

**Backend Code (internal):**
Persona = System or External System.
Outcome = Processing capability.
Scenario = Describe processing flow.
Step = Each processing stage in the pipeline.
Action = Each atomic operation (parse, compute, store, emit).

### NO-OP Rule

If the input only elaborates on existing functionality and introduces
no new Persona, Outcome, Scenario, Step, or Action, report:
"No new nodes needed."

## Full Generation Rules

See `func-prompt-rules.md` in this skill directory for the complete
Persona/Outcome/Scenario/Step/Action generation rules including code cluster
handling, technical content handling, and output format.
