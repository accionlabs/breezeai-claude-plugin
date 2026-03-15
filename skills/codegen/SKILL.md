---
name: codegen
description: >
  Generate code and test cases informed by the functional graph and
  code graph. Ensures implementations align with requirements and
  existing patterns. Use when: "generate code for X", "write tests
  for Y", "implement this scenario", "scaffold the API for Z".
  Basic generation guided by functional requirements.
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

## Generation Workflow

### 1. UNDERSTAND — Get the functional spec

- Call `Functional_Graph_Search` with the feature/scenario name
- Call `Get_all_steps_actions_for_a_scenario_id` for matched
  scenarios
- This gives you the WHAT: steps, actions, expected user
  interactions

### 2. DISCOVER — Find existing code patterns

- Call `Code_Graph_Search` with related terms
- Call `Get_Code_File_Details` on the most relevant files to inspect
  class structure, methods, and patterns
- Find existing files, functions, patterns, utilities
- This gives you the HOW: conventions, imports, patterns to follow

### 3. REFERENCE — Get business rules

- Call `Documents` for formulas, thresholds, validation rules
- This gives you the CONSTRAINTS: exact rules the code must enforce

### 4. GENERATE — Write code

- Follow existing code patterns found in step 2
- Align with functional steps from step 1
- Reuse existing utilities/components from code graph
- Apply business rules from step 3
- Add comments referencing functional graph node IDs for
  traceability

### 5. TEST — Generate test cases from scenarios

Map functional hierarchy to test structure:

    For each Scenario:
      describe("[Scenario Name]")
        For each Step:
          it("[Step Name]")
            For each Action:
              → Assert the expected behavior

- One test suite per scenario
- Test cases map 1:1 to steps
- Edge cases derived from action descriptions
- Include both happy path and error scenarios
