### Functional Graph

The functional graph consists of 5 components in a strict hierarchy:

**Persona → Outcome → Scenario → Step → Action**

1. **Persona** - Who is going to use this functional requirement (user roles)
2. **Outcome** - What are the high-level goals the persona needs to achieve
3. **Scenario** - What are the different paths/flows to achieve an outcome
4. **Step** - What sequential stages are needed to complete a scenario
5. **Action** - What specific UI interactions or system operations complete a step

---

### Data Model Samples

#### 1. Persona
Represents a distinct user role that interacts with the system.

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


```json
{
  "id": "1772548165210-4mw256a",
  "persona": "Developer",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "functionalId": "1771956593277-8837ppj",
  "embeddingPlatform": "AWSBEDROCK",
  "createdAt": "2026-03-03T14:29:25.210Z",
  "updatedAt": "2026-03-03T14:29:25.210Z"
}
```

**Key fields:**
- `id` — Unique identifier for the persona
- `persona` — Name of the role (e.g., Developer, Admin, User, System)
- `functionalId` — Links to the functional ontology

---

#### 2. Outcome
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

```json
{
  "id": "1772550159202-u3bid4o",
  "outcome": "Manage Code Ontology Imports",
  "description": "Developer can import and manage code ontology data from various file formats",
  "personaId": "1772548165210-4mw256a",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "embeddingPlatform": "AWSBEDROCK",
  "citations": "[{\"documentId\":5183,\"documentName\":\"BreezeAI Backend Cluster 4\"}]",
  "documentIds": [5183],
  "createdAt": "2026-03-03T15:02:39.202Z",
  "updatedAt": "2026-03-03T15:02:39.202Z"
}
```

**Key fields:**
- `id` — Unique identifier for the outcome
- `outcome` — Name of the goal/capability
- `description` — Detailed description of what this outcome achieves
- `personaId` — Links back to the parent persona

---

#### 3. Scenario
Represents a specific user flow or path to achieve an outcome.

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

```json
{
  "id": "1772550622135-ht19r9a",
  "scenario": "Import Code Ontology from JSON",
  "description": "Developer can import a code ontology from a JSON file, including project and repository information",
  "outcomeId": "1772550159202-u3bid4o",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "embeddingPlatform": "AWSBEDROCK",
  "citations": "[{\"documentId\":5183,\"documentName\":\"BreezeAI Backend Cluster 4\"}]",
  "documentIds": [5183],
  "createdAt": "2026-03-03T15:10:22.135Z",
  "updatedAt": "2026-03-03T15:10:22.135Z"
}
```

**Key fields:**
- `id` — Unique identifier for the scenario
- `scenario` — Name describing the user flow
- `description` — End-to-end summary of this flow
- `outcomeId` — Links back to the parent outcome

---

#### 4. Step
Represents a sequential stage within a scenario.

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


```json
{
  "id": "1772550622147-ksxqcg2",
  "step": "Upload JSON file",
  "scenarioId": "1772550622135-ht19r9a",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "embeddingPlatform": "AWSBEDROCK",
  "citations": "[{\"documentId\":5183,\"documentName\":\"BreezeAI Backend Cluster 4\"}]",
  "documentIds": [5183],
  "createdAt": "2026-03-03T15:10:22.147Z",
  "updatedAt": "2026-03-03T15:10:22.147Z"
}
```

**Key fields:**
- `id` — Unique identifier for the step
- `step` — Name describing this stage (e.g., "Upload JSON file", "Enter project information")
- `scenarioId` — Links back to the parent scenario
- `description` — Detailed description of what this step achieves(optional)

---

#### 5. Action
Represents a granular UI interaction or system operation within a step.

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

```json
{
  "id": "1772550622210-gzwjqdm",
  "action": "Click 'Choose File' button",
  "stepId": "1772550622147-ksxqcg2",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "embeddingPlatform": "AWSBEDROCK",
  "citations": "[{\"documentId\":5183,\"documentName\":\"BreezeAI Backend Cluster 4\"}]",
  "documentIds": [5183],
  "createdAt": "2026-03-03T15:10:22.210Z",
  "updatedAt": "2026-03-03T15:10:22.210Z"
}
```

**Key fields:**
- `id` — Unique identifier for the action
- `action` — name of the specific interaction (e.g., "Click button", "Enter value", "View message")
- `stepId` — Links back to the parent step
- `description` — Detailed description of what this action achieves(optional)

---

### Hierarchy Relationship Summary

```
Persona (1) ──HAS_OUTCOME──► Outcome (many)
Outcome (1) ──HAS_SCENARIO──► Scenario (many)
Scenario (1) ──HAS_STEP──► Step (many, ordered)
Step (1) ──HAS_ACTION──► Action (many)
```

### MCP Tools Mapping

| Component | List Tool | Search Tool |
|-----------|-----------|-------------|
| Persona | `Get_all_personas` | `Functional_Graph_Search` |
| Outcome | `Get_all_outcomes_for_a_persona_id` | `Functional_Graph_Search` |
| Scenario | `Get_all_scenarios_for_a_outcome_id` | `Functional_Graph_Search` |
| Step | `Get_all_steps_actions_for_a_scenario_id` | `Functional_Graph_Search` |
| Action | `Get_all_steps_actions_for_a_scenario_id` | `Functional_Graph_Search` |

---

### Functional Graph Mutation Tools

#### `Call_Create_Functional_Node_`
Create a new node in the functional graph.

**Required params:** `uuid` (project UUID), `label` (node type)

**`label`** must be one of: `Persona`, `Outcome`, `Scenario`, `Step`, `Action`

**`data` object by label:**
- **Persona**: `{ persona: <string>, description: <string> }`
- **Outcome**: `{ outcome: <string>, description: <string>, personaId: <id> }`
- **Scenario**: `{ scenario: <string>, description: <string>, outcomeId: <id> }`
- **Step**: `{ step: <string>, description: <string>, scenarioId: <id> }`
- **Action**: `{ action: <string>, description: <string>, stepId: <id> }`

---

#### `Call_Update_Functional_Node_`
Update an existing node in the functional graph.

**Required params:** `uuid` (project UUID), `label` (node type), `id` (node ID to update), `apiKey`

**`data` object by label:** Same structure as create (see above).

