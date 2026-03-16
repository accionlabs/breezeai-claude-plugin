---
name: search
description: >
  Search the functional graph or code graph to answer questions about the system.
  Takes two arguments: type (code/functional) and search query.
  Use for: feature discovery, impact analysis, finding code implementations,
  and cross-cutting queries.
context: fork
agent: Plan
  
---


## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

---

## Arguments

This skill accepts two arguments:
1. **type** — `code` or `functional` (where to search)
2. **query** — the search query text (what to search)

---

## Instructions

### Step 1: Confirm Search Intent

Ask the user to confirm:
1. **Where** do they want to search? (`code` graph or `functional` graph)
2. **What** do they want to search? (the search query)

If arguments are already provided, confirm them with the user before proceeding.
Do not proceed until the user confirms both the search type and query.

### Step 2: Execute Search

Based on the confirmed search type:

#### If type = `code`

- Call `Code_Graph_Search` MCP tool with the user's query.
- Present results in a clear, structured format:
  - File/component name
  - Relevant code snippets or function signatures
  - Description of what each result does
  - How it relates to the search query

#### If type = `functional`

- Call `Functional_Graph_Search` MCP tool with the user's query.
- Present results in a clear, structured format:
  - Entity type (Persona / Outcome / Scenario / Step / Action)
  - Name and description 
  - Parent hierarchy (which Persona/Outcome it belongs to)

### Step 3: Drill-Down (if needed)

After showing results, ask the user if they want to drill deeper into any result.

#### For functional results:
- If top results are **Scenarios** (relevance > 0.5) → Call `Get_all_steps_actions` on those scenario IDs for the full step-by-step flow.
- If top results are **Actions/Steps** (fragmented, relevance < 0.6) → Identify their **parent Scenario** and drill down from there.
- If results reference a **Persona** → Use `Get_all_outcomes` to understand the full scope before drilling deeper.


