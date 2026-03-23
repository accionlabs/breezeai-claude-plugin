---
name: analyze-design
description: >
  Analyze UI/UX designs from Figma frames. Extracts functional
  summary, identifies components, maps to functional graph, flags
  gaps. Use when: user shares a Figma URL, "analyze this design",
  "what does this screen do", "map Figma to functional graph".
  Requires Figma MCP server.
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

## Analysis Flow

### 1. Fetch Design

If a Figma URL is provided, extract fileKey and nodeId:

- URL format: figma.com/design/:fileKey/:fileName?node-id=:nodeId
- Convert "-" to ":" in nodeId

Call `get_design_context` (Figma MCP) with fileKey and nodeId.
Review the screenshot and generated code.

### 2. Extract Functional Summary

From the design, identify:

- Page purpose and context
- Navigation structure (tabs, sidebar, breadcrumbs)
- Data displays (charts, tables, KPI cards)
- User actions (buttons, forms, filters, toggles)
- Interactive elements (modals, dropdowns, selectors)

### 3. Search Existing Coverage

Call `Functional_Graph_Search` with key terms from the design.
Call `Get_all_personas` → drill down to check existing mapping.

### 4. Cross-Reference Documents

Call `Documents` to find related requirement text.

### 5. Identify Gaps & Recommend

Compare design components against functional graph coverage.
Flag functionality in design not captured, and graph items missing
from design.

### 6. Optionally Update Graph

Ask: "Would you like me to update the functional graph with the
new findings?"

If yes → use `Call_Create_Functional_Node_` following
update-graph rules.

## Output Format

Present your analysis using this structure:

**Design Analysis: [Frame Name]**

**1. Functional Summary**
Page purpose and key interactions.

**2. Component Inventory**
Table with columns: Component, Type, Functionality.

**3. Functional Graph Mapping**
Persona (matched or new), Outcomes (list), Scenarios (list).

**4. Gaps**
In design but not in graph. In graph but not in design.

**5. Recommendations**
Nodes to create or update.
