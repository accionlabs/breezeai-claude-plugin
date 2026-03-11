---
name: search
description: >
  Search the functional graph or code graph to answer questions about the system.
  Use for: feature discovery, impact analysis, "who handles X", "how does Y work",
  finding code implementations, and cross-cutting queries. Default entry point
  for any question about the project.
---

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:init`.  
Extract `apiKey` and `projectUuid`.

---

## Decision Logic

Determine which search to perform based on `$ARGUMENTS`.

### Behavior, Features, Workflows
→ `Functional_Graph_Search`  
Examples:
- "how does login work"
- "what does admin do"

### Who / Roles / Personas
→ `Get_all_personas` then drill down  
Examples:
- "who manages invoices"
- "what roles exist"

### Code Structure, Implementations
→ `Code_Graph_Search`  
Examples:
- "find auth middleware"
- "where is validation"

### Both (Feature → Code)
→ `Functional_Graph_Search` **FIRST**, then `Code_Graph_Search`  
Examples:
- "find code for payment processing"

### Raw Requirements / Formulas
→ `Documents`  
Examples:
- "NAV tolerance threshold"
- "acceptance criteria for X"

---

## Search Priority

1. **Functional_Graph_Search** — always try **FIRST** for behavior questions  
2. **Hierarchy drill-down**
   - `Get_all_personas`
   - `Get_all_outcomes`
   - `Get_all_scenarios`
   - `Get_all_steps_actions`
   → Used for structured traversal of a persona or feature  
3. **Code_Graph_Search** — for implementation or code questions  
4. **Documents** — **ONLY** when the functional graph lacks detail  
   (formulas, thresholds, acceptance criteria)

---

## Multi-Perspective Search

For end-to-end or process questions:

Examples:
- "what happens when..."
- "how does X process work"
- "explain the flow of Y"

1. **First search — User perspective**
   - UI interactions
   - user actions

2. **Second search — System perspective**
   Re-query using terms like:
   - "System processes..."
   - "backend handles..."
   - "External System..."

   This captures:
   - backend processing
   - validations
   - integrations
   - async jobs

   These are typically modeled under **System** or **External System** personas.

3. **Combine both result sets** into a single sequential narrative.

⚠️ Always perform **both searches** for process/workflow questions.  
UI-only results are incomplete.

---

## Auto Drill-Down

When `Functional_Graph_Search` returns results:

- If top results are **Scenarios** (relevance > 0.5)  
  → Call `Get_all_steps_actions` on those scenario IDs to obtain the full step-by-step flow.

- If top results are **Actions/Steps** (fragmented, relevance < 0.6)  
  → Identify their **parent Scenario** and drill down from there.

- If results reference a **Persona**  
  → Use `Get_all_outcomes` to understand the full scope before drilling deeper.

⚠️ Do **NOT** present raw search results as the final answer.  
Always drill down to build a complete picture.

---

## Output

Present results as a **coherent narrative**.

### Process Questions
Provide a **numbered sequential flow**:
- Trigger
- UI interaction
- Backend/system processing
- Completion

### Discovery Questions
Provide a **ranked list** including:
- Entity type
- Name
- Description
- Relevance score
- Suggested drill-down paths

### Always Include
- Personas involved
- Linkage between **frontend actions** and **backend processing**
