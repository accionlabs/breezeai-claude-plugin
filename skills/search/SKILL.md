 ---
  name: search
  description: >
    Search the functional graph or code graph to answer questions about
    the system. Use for: feature discovery, impact analysis, "who
    handles X", "how does Y work", finding code implementations,
    cross-cutting queries. Default entry point for any question about
    the project.
  ---

  ## Guard

  Read `.breeze.json`. If missing or incomplete, tell user to run
  `/breeze:init`. Extract `apiKey` and `projectUuid`.

  ## Decision Logic

  Determine which search to perform based on $ARGUMENTS:

  **Behavior, features, workflows:**
  → `Functional_Graph_Search`
  Examples: "how does login work", "what does admin do"

  **Who / roles / personas:**
  → `Get_all_personas` then drill down
  Examples: "who manages invoices", "what roles exist"

  **Code structure, implementations:**
  → `Code_Graph_Search`
  Examples: "find auth middleware", "where is validation"

  **Both (feature → code):**
  → `Functional_Graph_Search` FIRST, then `Code_Graph_Search`
  Examples: "find code for payment processing"

  **Raw requirements, formulas:**
  → `Documents`
  Examples: "NAV tolerance threshold", "acceptance criteria for X"

  ## Search Priority

  1. **Functional_Graph_Search** — always try FIRST for behavior
     questions
  2. **Hierarchy drill-down** (Get_all_personas → Get_all_outcomes →
     Get_all_scenarios → Get_all_steps_actions) — for structured
     traversal of a specific persona or feature
  3. **Code_Graph_Search** — for implementation/code questions
  4. **Documents** — ONLY when functional graph lacks detail (formulas,
     thresholds, acceptance criteria)

  ## Multi-Perspective Search

  For end-to-end or process questions ("what happens when...", "how
  does X process work", "explain the flow of Y"):

  1. **First search** — user-facing perspective (UI interactions,
     user actions)
  2. **Second search** — system perspective. Re-query with terms like
     "System processes...", "backend handles...", or "External System..."
     Backend processing, validations, integrations, and async jobs
     are captured under **System** or **External System** personas.
  3. **Combine** both result sets into a single sequential narrative.

  Always perform BOTH searches for process/workflow questions. UI-only
  results are incomplete.

  ## Auto Drill-Down

  When `Functional_Graph_Search` returns results:

  - If top results are **Scenarios** (relevance > 0.5) → call
    `Get_all_steps_actions` on those scenario IDs to get the full
    step-by-step flow
  - If top results are **Actions/Steps** (fragmented, relevance < 0.6)
    → identify their parent Scenario and drill down from there
  - If results reference a **Persona** → use `Get_all_outcomes` to
    understand the full scope before drilling deeper

  Do NOT present raw search results as the final answer. Always
  drill down to build a complete picture.

  ## Output

  Present results as a coherent narrative:

  - For process questions: a **numbered sequential flow** from trigger
    to completion, covering both UI and system sides
  - For discovery questions: a **ranked list** with entity type,
    name, description, relevance score, and suggested drill-down paths
  - Always include: which personas are involved, and linkage between
    frontend actions and backend processing
