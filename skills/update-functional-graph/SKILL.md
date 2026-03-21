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
                     └─ Action (what user provides/decides OR system processes)

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
- Steps do NOT require descriptions (the name is sufficient)
- Steps require a `scenarioId` (the parent Scenario's ID)

**Good Step names:**
- "Specify date range"
- "Review validation results"
- "Apply filters"
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
      "scenarioId": "<parent scenario ID>"
    }

**How to derive Steps from different inputs:**

- **Figma/Design:** Each distinct section or interaction zone
- **Document/Requirements:** Each numbered step or phase in the
  user journey
- **Source Code:** Methods -> processing phases
  (validate -> transform -> persist -> notify)

### 7. Create Actions

Actions are the **atomic operations or user inputs** within a Step.

**Action rules by persona type:**

#### HUMAN PERSONA actions
- Actions describe what the user PROVIDES, DECIDES, or OBSERVES
- Actions MUST be platform-agnostic — they must work for web,
  mobile, CLI, or voice without rewriting
- FORBIDDEN words in actions: click, tap, swipe, hover, scroll,
  drag, drop, toggle, button, dropdown, modal, dialog, popup,
  panel, checkbox, radio, slider, tooltip, menu, sidebar, navbar,
  tab, icon
- Instead use intent verbs: Provide, Choose, Confirm, Review,
  Dismiss, Open, Close, Submit, Cancel, Specify, Indicate,
  Acknowledge, Request
- description = null, unless the context specifies a constraint
  (e.g., "Minimum 20 characters", "Blocked until all files uploaded")

#### SYSTEM PERSONA actions
- Actions describe single atomic internal operations
- description is REQUIRED on every System action. Provide one of:
  - Formula or calculation
  - Threshold or limit
  - Field names involved
  - Condition or branching logic
  - Error message
  - Data format or transformation
  - Input/output shape of the operation
- When the context lacks a specific value, describe the operation's
  input -> output contract instead of setting null
- null is acceptable ONLY for trivial glue actions (e.g., "Log completion")

#### EXTERNAL SYSTEM PERSONA actions
- Actions describe single atomic API/integration operations
- description = endpoint, payload shape, or auth mechanism when
  known; otherwise null

**Quantity guidelines:**
- A Step typically has 1-5 Actions
- If more than 5, consider splitting the parent Step

**Action data format for `Call_Create_Functional_Node_`:**

    label: "Action"
    data: {
      "action": "<specific interaction or operation>",
      "description": "<precision detail or null per persona rules>",
      "stepId": "<parent step ID>"
    }

**How to derive Actions from different inputs:**

- **Document/Requirements:** Each specific user input or system
  response in acceptance criteria
- **Source Code:** Translate code to functional language —
  conditionals -> business rules, queries -> data operations,
  calculations -> formulas. Never reproduce raw code.
- **Figma/Design:** Each user decision point or data entry

**Example -- full hierarchy for a dashboard filter:**

    Persona: Media Analyst
      └─ Outcome: Manage Dashboard Configuration
           └─ Scenario: Apply Filters and Date Range
                └─ Step: Specify date range
                     ├─ Action: Provide start date
                     │    description: null
                     ├─ Action: Provide end date
                     │    description: null
                └─ Step: Apply keyword filter
                     ├─ Action: Specify search keyword
                     │    description: null
                     ├─ Action: Choose title-only search scope
                     │    description: null

**Example -- System persona with descriptions:**

    Persona: System
      └─ Outcome: Manage Validation Process
           └─ Scenario: Check share class return divergence
                └─ Step: Calculate daily returns
                     ├─ Action: Compute daily return per share class
                     │    description: "Return = (NAV_D1 / NAV_D0) - 1"
                     ├─ Action: Calculate absolute divergence
                     │    description: "Divergence = |Return_ClassA - Return_ClassB| × 10,000 (bps)"
                └─ Step: Flag significant divergences
                     ├─ Action: Check divergence against threshold
                     │    description: "> 20 bps = BREACH (Red), > 10 bps = WARNING (Amber)"

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

## Functional Graph Principles

Refer to `../functional-analysis/references/guide.md` for the
complete shared specification:
- Persona resolution rules (priority order, forbidden names)
- Outcome rules (reuse-first, business language)
- Scenario rules (testable, clear start/end)
- Step rules (sequential, no description needed)
- **Action rules (PERSONA-AWARE):**
  - Human personas: platform-agnostic, intent verbs only
  - System persona: description REQUIRED with business logic
  - External System: API/integration operations
- Context type handling (documents, code, Figma)
- Data model and MCP tools

These rules are shared across all Breeze skills that create or
modify functional graph nodes.

---

## Input-Type Handling

### Document/Requirements

- Persona = Actor of intent stated or implied
- Outcome = Business capability described
- Scenario = User journeys described
- Step = Each phase or numbered step in the journey
- Action = Each specific user input or system response

### Source Code

- Translate code to functional language; never reproduce raw code
- Map: classes -> service boundaries, methods -> processing phases,
  conditionals -> business rules, queries -> data operations
- Frontend code: Persona = Human user, routes -> outcomes,
  components -> scenarios, sections -> steps
- Backend code (serves UI): Persona = Human who triggers the API,
  controllers -> scenarios, service methods -> steps
- Backend code (internal): Persona = System or External System,
  processing flows -> scenarios, pipeline stages -> steps

### Figma/Design

- Persona = Human user of the UI
- Outcome = Group by page/feature area
- Scenario = Each screen/interaction flow
- Step = Each section or interaction zone
- Action = Each user decision point or data entry

### Technical/Infrastructure Content

- Do NOT create Personas like "Developer" or "DevOps Engineer"
- Ask: "What user-facing capability does this support?"
- If it supports no direct user capability, it may not need
  functional graph nodes

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