### Functional Graph

The functional graph consists of 5 components in a strict hierarchy:

**Persona → Outcome → Scenario → Step → Action**

1. **Persona** - Who is going to use this functional requirement (user roles)
2. **Outcome** - What are the high-level goals the persona needs to achieve
3. **Scenario** - What are the different paths/flows to achieve an outcome
4. **Step** - What sequential stages are needed to complete a scenario
5. **Action** - What the user provides/decides or the system processes

---

### Persona Rules

Represents a distinct actor that interacts with the system.

**Resolve Personas (REUSE FIRST)**
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

---

### Outcome Rules

Represents a high-level goal or capability a persona needs to accomplish.

**Resolve Outcomes (REUSE FIRST)**
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

**Bad Outcome names (anti-patterns):**
- "Handle API Requests" (technical, not business)
- "Process Database Queries" (implementation detail)
- "Render Components" (frontend implementation)

**Outcome quality checks:**
- Understandable by non-technical stakeholders
- Stable across implementation and code changes
- Broad enough to absorb future Scenarios
- If more than 3-4 new Outcomes appear necessary, re-evaluate
  for over-segmentation

---

### Scenario Rules

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
internal processing behavior, NOT the UI that triggers it.

---

### Step Rules

Steps are the **sequential stages** within a Scenario. They
represent the major phases a user or system goes through to
complete the flow.

- Each Step is a distinct stage in the Scenario's flow
- Steps are ORDERED -- they represent a sequence
- A Step name should be a short verb phrase describing the stage
- Steps do NOT require descriptions (the name is sufficient)
- A Scenario typically has 3-8 Steps (max 10)

---

### Action Rules (PERSONA-AWARE)

Actions are the **atomic operations or user inputs** within a Step.
The rules differ by persona type:

#### HUMAN PERSONA actions (User, Admin, or any named role)
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
- description = null, unless context specifies a constraint
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

#### Quantity guidelines
- A Step typically has 1-5 Actions
- If more than 5, consider splitting the parent Step

---

### Context Type Handling

The input context can be:

**Document** (requirements, specs, user stories)
- Extract business logic, acceptance criteria, formulas, thresholds
  directly from the text

**Source code** (Class → Method → Statements)
- Translate code to functional language; never reproduce raw code
- Map: classes → service boundaries, methods → processing phases,
  conditionals → business rules, queries → data operations
- Action descriptions must include actual field names, thresholds,
  and error messages extracted from code

**Figma design**
- Extract functional intents from UI components and interactions
- Map: pages → outcomes, screens → scenarios, sections → steps,
  user decision points → actions

---

### Data Model

#### Create/Update via `Call_Create_Functional_Node_` / `Call_Update_Functional_Node_`

**Required params:** `uuid` (project UUID), `label` (node type)

**`label`** must be one of: `Persona`, `Outcome`, `Scenario`, `Step`, `Action`

**`data` object by label:**
- **Persona**: `{ persona: <string> }`
- **Outcome**: `{ outcome: <string>, description: <string>, personaId: <id> }`
- **Scenario**: `{ scenario: <string>, description: <string>, outcomeId: <id> }`
- **Step**: `{ step: <string>, scenarioId: <id> }`
- **Action**: `{ action: <string>, description: <string or null>, stepId: <id> }`

**Creation order:** Persona → Outcome → Scenario → Step → Action
(wait for each parent ID before creating children)

---

### MCP Tools Mapping

| Component | List Tool | Search Tool |
|-----------|-----------|-------------|
| Persona | `Get_all_personas` | `Functional_Graph_Search` |
| Outcome | `Get_all_outcomes_for_a_persona_id` | `Functional_Graph_Search` |
| Scenario | `Get_all_scenarios_for_a_outcome_id` | `Functional_Graph_Search` |
| Step | `Get_all_steps_actions_for_a_scenario_id` | `Functional_Graph_Search` |
| Action | `Get_all_steps_actions_for_a_scenario_id` | `Functional_Graph_Search` |

