---
name: search
description: >
  Search the functional graph or code graph to answer questions about the system.
  Use for: feature discovery, impact analysis, "who handles X", "how does Y work",
  finding code implementations, and cross-cutting queries. Default entry point
  for any question about the project.
---

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

---

## Decision Logic

Determine which search to perform based on `$ARGUMENTS`.

### Behavior, Features, Workflows

-> `Functional_Graph_Search`
Examples:
- "how does login work"
- "what does admin do"

> For process/workflow questions ("what happens when...", "explain the flow of..."),
> you MUST use **Multi-Perspective Search** (see below). A single search will
> return an incomplete picture.

### Who / Roles / Personas

-> `Get_all_personas` then drill down
Examples:
- "who manages invoices"
- "what roles exist"

### Code Structure, Implementations

-> `Code_Graph_Search`, then `Get_Code_File_Details` to drill into specific files
Examples:
- "find auth middleware"
- "where is validation"

### Both (Feature -> Code)

-> `Functional_Graph_Search` **FIRST**, then `Code_Graph_Search`
Examples:
- "find code for payment processing"

### Raw Requirements / Formulas

-> `Documents`
Examples:
- "NAV tolerance threshold"
- "acceptance criteria for X"

---

## Search Priority

1. **Functional_Graph_Search** -- always try **FIRST** for behavior questions
2. **Hierarchy drill-down**
   - `Get_all_personas`
   - `Get_all_outcomes`
   - `Get_all_scenarios`
   - `Get_all_steps_actions`
   -> Used for structured traversal of a persona or feature
3. **Code_Graph_Search** -- for implementation or code questions; follow up with **Get_Code_File_Details** for file-level detail
4. **Documents** -- **ONLY** when the functional graph lacks detail
   (formulas, thresholds, acceptance criteria)

---

## Multi-Perspective Search

The functional graph uses a **dual-persona architecture**:

- **User / Admin / named roles** capture UI interactions and user-facing flows
- **System** captures backend internals: processing pipelines, async jobs,
  graph DB operations, embedding generation, clustering, validations
- **External System** captures inbound integrations, webhooks, partner APIs

The same Outcome name (e.g., "Manage Code Ontology") may exist under
**multiple Personas**. The User version describes the UI flow; the System
version describes the backend processing triggered by that same flow.

### When to use

Any end-to-end or process question:
- "what happens when..."
- "how does X process work"
- "explain the flow of Y"

### Execution

1. **First search -- User perspective**
   Query with user-centric terms:
   - UI interactions, user actions, clicks, forms

2. **Second search -- System perspective**
   Re-query using backend-centric terms:
   - "System processes..."
   - "backend handles..."
   - "External System..."

   This captures:
   - backend processing pipelines
   - validations and transformations
   - database operations
   - async jobs and workers
   - integrations

3. **Combine both result sets** into a single sequential narrative
   showing the complete flow from UI trigger through backend completion.

> ALWAYS perform **both searches** for process/workflow questions.
> UI-only results are incomplete. Backend-only results lack trigger context.

---

## Auto Drill-Down

When `Functional_Graph_Search` returns results:

- If top results are **Scenarios** (relevance > 0.5)
  -> Call `Get_all_steps_actions` on those scenario IDs to obtain the
  full step-by-step flow.

- If top results are **Actions/Steps** (fragmented, relevance < 0.6)
  -> Identify their **parent Scenario** and drill down from there.

- If results reference a **Persona**
  -> Use `Get_all_outcomes` to understand the full scope before drilling deeper.

### Cross-Persona Drill-Down

When drilling into an Outcome, **check if the same Outcome name exists
under other Personas**. This is common for features that span UI and backend:

1. After finding an Outcome under a User persona, search for the same
   Outcome name under the System persona (and vice versa).
2. Drill into **both** to get the complete picture:
   - User persona Outcome -> user-facing scenarios (UI flows)
   - System persona Outcome -> backend scenarios (processing, storage, async)
3. Merge the results into a unified narrative.

> Do **NOT** present raw search results as the final answer.
> Always drill down to build a complete picture across personas.

---

## Output

Present results as a **coherent narrative**.

### Process Questions

Provide a **numbered sequential flow**:
1. Trigger (what initiates the process)
2. UI interaction (User persona scenarios)
3. Backend/system processing (System persona scenarios)
4. Completion (confirmation, side effects)

### Discovery Questions

Provide a **ranked list** including:
- Entity type (Persona / Outcome / Scenario / Step / Action)
- Name and description
- Relevance score
- Suggested drill-down paths

### Always Include

- All Personas involved (User, System, External System)
- Linkage between **frontend actions** and **backend processing**
- Which Persona owns each part of the flow