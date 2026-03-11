---
name: requirements
description: >
  Analyze requirements by cross-referencing with the functional graph.
  Identifies coverage gaps, conflicts, dependencies, and impact.
  Use when: "analyze this requirement", "is this covered", "impact
  of this change", "break down this user story".
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

## Analysis Flow

### 1. Search Existing Coverage

Call `Functional_Graph_Search` with the requirement's key concepts.
If matches found, drill down:
Get_all_personas → Get_all_outcomes → Get_all_scenarios.

### 2. Search Source Documents

Call `Documents` to find related raw requirement text, acceptance
criteria, formulas, and threshold values.

### 3. Identify Gaps

Compare the requirement against existing graph coverage:

- What personas/outcomes/scenarios already cover this?
- What is NOT yet captured?

### 4. Assess Impact

Identify existing features affected by this requirement using
`Functional_Graph_Search` with impact-oriented queries.

### 5. Optionally Update Graph

If gaps found, ask user:
"Would you like me to create the missing nodes?"

If yes → use `Call_Create_Functional_Node_` following the
update-graph rules.

## Output Format

Present your analysis using this structure:

**Requirement Analysis: [Title]**

**1. Existing Coverage**
List matched personas, outcomes, scenarios with IDs.

**2. Gap Analysis**
List what is NOT covered — missing personas, outcomes, scenarios.

**3. Impact Analysis**
List existing features affected, cross-cutting concerns.

**4. Dependencies**
List prerequisites and related requirements.

**5. Recommended Actions**
List nodes to create or update in the functional graph.
