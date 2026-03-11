# Functional Graph Generation Rules

## Persona Identification

### Priority Order
1. **Named human role** — Admin, Fund Manager, Compliance Officer, Media Analyst
2. **Generic human role** — User, Customer, Visitor
3. **External System** — Webhook, Partner API, Payment Gateway
4. **System** — Background job, Scheduler, Cron task

### Forbidden Persona Names
NEVER use technical identifiers as Personas:
- Developer, Engineer, Programmer
- API, Service, Component, Module
- Backend, Frontend, Database
- Controller, Handler, Repository

### Resolution Rules
- Always check existing Personas FIRST before creating new ones
- Merge similar roles (e.g., "Admin User" and "Administrator" → reuse one)
- If the actor is ambiguous, default to the most specific human role implied by the context

## Outcome Resolution

### Rules
- An Outcome represents a **high-level business capability** (not a technical function)
- Good: "Manage Fund Allocations", "Monitor Compliance Status", "Generate Reports"
- Bad: "Handle API Requests", "Process Database Queries", "Render Components"
- Prefer broader Outcomes — capture variation as Scenarios, not new Outcomes
- Reuse existing Outcomes when the new intent logically fits within them

### Anti-Patterns
- One Outcome per API endpoint (too granular)
- Outcome names matching function/class names (too technical)
- Duplicate Outcomes with slightly different wording

## Scenario Rules

### What Makes a Good Scenario
- A Scenario describes a **specific user or system flow**
- It should be testable — you can write acceptance criteria for it
- It should have a clear start and end
- Good: "Filter Dashboard by Date Range", "Submit Compliance Report"
- Bad: "Use the System", "Do Things with Data"

### When to Create vs Reuse
- **Reuse** if an existing Scenario covers the same flow with minor variation
- **Create new** only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging them

## Step Rules

### What Makes a Good Step
- A Step is a **sequential stage** within a Scenario
- Steps are ordered — they represent a progression
- Each Step should be a short verb phrase
- Good: "Select Date Range", "Review Results", "Confirm Submission"
- Bad: "Step 1", "Processing", "Misc"

### Quantity Guidelines
- A Scenario typically has 3–8 Steps
- If more than 10, consider splitting the Scenario
- If fewer than 2, consider merging with another Scenario

## Action Rules

### What Makes a Good Action
- An Action is the **most granular level** — a single UI interaction or system operation
- Should be specific and concrete
- Good: "Click 'Submit' button", "Enter email in login field", "System validates JWT token"
- Bad: "Interact with form", "Process data", "Handle click"

### Quantity Guidelines
- A Step typically has 1–5 Actions
- If more than 5, consider splitting the parent Step

## Code Cluster Handling

When analyzing code clusters (groups of related files/functions):

1. **Identify the user-facing purpose** — What does this code enable a user to do?
2. **Map to existing Personas** — Who triggers this code path?
3. **Determine the Outcome** — What business capability does this serve?
4. **Trace the flow** — What sequence of operations occurs?
5. **Extract Steps** — What are the major phases?
6. **Detail Actions** — What atomic operations happen in each phase?

### Frontend Code → Functional Mapping
- Components → Scenarios (each major component maps to a flow)
- Event handlers → Actions (onClick, onChange, etc.)
- Page sections → Steps (each section is a stage)
- Routes → Outcomes (each route group serves a capability)

### Backend Code → Functional Mapping
- Controllers/Routes → Scenarios (each endpoint maps to a flow)
- Middleware → Steps (validation, auth, rate limiting)
- Service methods → Steps (business logic phases)
- Database queries → Actions (atomic data operations)

## Technical Content Handling

When encountering purely technical content (config files, build scripts, infrastructure):

- **DO NOT** create Personas like "Developer" or "DevOps Engineer"
- **DO** ask: "What user-facing capability does this support?"
- If it supports no direct user capability, it may not need functional graph nodes
- Infrastructure code → map to the Outcomes it enables, not to its own Outcome

## Output Format

When proposing new nodes, present them in this format:

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
