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

## Output

Present results as a ranked list with:

- Entity type (Persona / Outcome / Scenario / Step / Action / File /
  Function / Class)
- Name and description
- Relevance score
- Suggested drill-down paths
