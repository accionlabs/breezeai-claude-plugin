---
name: visual-to-text
description: >
  Generate user stories from UI design visuals (Figma frames, PDF screens, or images)
  that describe the functional intent behind the visual design, expressed in terms of
  personas, outcomes, scenarios, steps, and actions. Outputs structured user stories
  aligned with the functional graph and saves them to a Markdown file.
  Use when: user shares a Figma URL, PDF, or image design and wants functional user
  stories, "convert design to user stories", "visual to text", "extract functional
  intent from design".
---

**Before generating the functional graph, read `./references/guide.md` to understand the full definition and rules for each node type: Persona, Outcome, Scenario, Step, and Action.**

## Visual-to-Text Flow

### 1. Fetch Design

#### From Figma URL

If a Figma URL is provided, extract fileKey and nodeId:

- URL format: figma.com/design/:fileKey/:fileName?node-id=:nodeId
- Convert "-" to ":" in nodeId

Call Figma MCP with fileKey and nodeId.
Review the screenshot and generated code to understand the UI structure.

#### From PDF File

If a PDF file is provided:
- Read the PDF file using the Read tool (supports .pdf files)
- Analyze each page/screen visually to identify UI components
- Extract text and visual elements from the design

#### From Image Files

If PNG, JPG, or other image files are provided:
- Read the image file using the Read tool
- Analyze the visual design to identify components and layout

### 2. Analyze UI Components

From the design (Figma, PDF, or image), identify:

**Input Elements:**
- Text fields (email, password, name, search, etc.)
- Dropdowns and selectors
- Checkboxes and radio buttons
- Date/time pickers
- File upload components
- Text areas

**Interactive Elements:**
- Primary action buttons (Login, Submit, Save, etc.)
- Secondary action buttons (Cancel, Back, etc.)
- Links and navigation items
- Tabs and accordions
- Modals and dialogs
- Toggles and switches

**Display Elements:**
- Headers and titles
- Labels and descriptions
- Data tables and lists
- Cards and panels
- Charts and visualizations
- Status indicators
- Error/success messages

**Navigation:**
- Navigation bars (top, side, bottom)
- Breadcrumbs
- Pagination
- Menu items

**Layout & Structure:**
- Page sections and containers
- Responsive breakpoints
- Grid layouts

### 3. Extract Functional Intents from Design

Translate the visual design into functional language — extract WHAT the design enables, not HOW it looks. Use the mapping defined in `./references/guide.md`:

- **Persona:** Identify every role-based actor implied by the design (who fills this form, who sees this dashboard). A Persona is a behavioral category, not an individual user.
- **Outcome:** Identify the complete objectives the design enables a Persona to achieve. Outcome defines WHAT success means from the actor's perspective.
- **Scenario:** Identify the variations of how each Outcome can be completed. Scenario answers: "Under what condition or approach is the Outcome completed?" (e.g., purchase with saved address vs. new address vs. guest checkout).
- **Step:** Identify the configuration-level variations within each Scenario. A Step is NOT a workflow stage — it represents a complete requirement slice describing how the Scenario itself is completed (e.g., "with coupon" vs. "without coupon" vs. "with wallet payment").
- **Action:** Identify the named logical activities required to fulfill each Step. Actions collectively complete the Step. Each Action may involve multiple interactions but is modeled as a single logical activity.

Then check for the following issues within the design itself:

**A. Ambiguous persona references**
- Extract every actor/role implied by the design
- If the design implies a generic term like "user" that could map to multiple distinct roles, flag it as ambiguous
- Identify all distinct personas the design serves

**B. Conflicting requirements**
- Check if the design contains contradictory behaviors within itself (e.g., a form that requires login but also shows anonymous access)

**C. Incomplete scenario definitions**
- Check if any intent from the design describes a goal but lacks enough detail to define steps and actions (e.g., a "payments" section without visible validation, confirmation, or failure states)

**D. Terminology consistency**
- Ensure consistent terminology across the design (e.g., don't mix "purchase" and "order" for the same concept)

Present all findings from A–D to the user in a summary. If no issues are found, state that the design's functional intent is clear and proceed to Step 4.

### 4. Clarify Issues with User

If any issues were identified in Step 3, present them to the user and ask for clarification:

- **Ambiguous personas**: Ask which specific persona is intended
- **Conflicts**: Present each contradiction and ask how to resolve
- **Incomplete definitions**: Ask the user to provide the missing details for each flagged intent
- **Terminology inconsistencies**: Suggest a consistent term and ask for confirmation

**Repeat this step**: after each round of clarification, re-check the updated intents for remaining issues. Continue until all issues are resolved. Only then proceed to Step 5.

### 5. Generate Functional Graph

Using the clarified intents from the design, generate the functional graph following the hierarchy defined in `./references/guide.md`: **Persona → Outcome → Scenario → Step → Action**.

**Relationships (from guide.md):**
- Persona PERFORMS Outcome
- Outcome HAS_SCENARIO Scenario
- Scenario HAS_STEP Step
- Step HAS_ACTION Action

**Resolve Personas:**
- Persona is a role-based actor, not an individual user
- A Persona can perform multiple Outcomes
- Multiple Personas may perform the same Outcome
- If the design involves backend processing (form submissions, data validation, API calls, email sending, etc.), include a **System persona** alongside the user-facing persona

**Build Outcomes:**
- Each Outcome represents a complete objective the Persona wants to achieve
- Outcome defines WHAT success means from the actor's perspective
- Outcome is the highest-level capability completion state

**Build Scenarios:**
- Each Scenario is a variation of how an Outcome can be completed
- Scenario defines execution context differences
- Scenarios are independent from each other
- Ask: "Under what condition or approach is the Outcome completed?"

**Build Steps:**
- Each Step is a variation inside a Scenario (NOT a workflow stage)
- Step represents a configuration-level variation describing how the Scenario is completed
- Each Step is an independently complete requirement slice
- Ask: "What are the different ways this Scenario can be configured/completed?"

**Build Actions:**
- Each Action is a named logical activity required to fulfill a Step
- Actions are the lowest level of requirement definition
- Actions may involve multiple interactions internally but are modeled as a single logical activity
- All Actions belonging to a Step must be completed for Step completion
- Actions collectively fulfill the Step → Step realizes Scenario → Scenario achieves Outcome

Present the complete functional graph to the user and ask for confirmation before saving.

### 6. Save Output to File

After the user confirms, save the complete functional graph to a `.md` file using the Write tool.

- **Location:** Project root (current working directory)
- **Filename format:** `user-stories-[screen-name].md` (e.g., `user-stories-login-page.md`)
- Derive `[screen-name]` from the design title, file name, or page heading — use lowercase, hyphen-separated words
- Confirm to the user: "Saved to `user-stories-[screen-name].md`"

## Output Format

Present the functional graph using this structure:

```
# Functional Graph: [Design Name/Screen Name]

**Source:** [Figma URL, PDF filename, or image filename]
**Date Generated:** [Current date]

---

## Overview

[Brief description of the functional intent behind this design — what complete objectives it enables and for whom]

**Personas:** [List of personas]
**Outcomes:** [List of outcomes]

---

## Persona: [Persona Name]

### Outcome: [Outcome Name]

[What success means from this persona's perspective]

#### Scenario: [Scenario Name]

[Under what condition or approach is the Outcome completed?]

##### Step: [Step Name]

[Configuration-level variation — how is this Scenario completed?]

| Action | Description |
|--------|-------------|
| [Action name — logical activity] | [Details or —] |
| [Action name — logical activity] | [Details or —] |
| [Action name — logical activity] | [Details or —] |

##### Step: [Step Name — another variation]

[Another complete requirement slice of the same Scenario]

| Action | Description |
|--------|-------------|
| [Action name] | [Details or —] |
| [Action name] | [Details or —] |

#### Scenario: [Another Scenario Name]

[Different condition or approach for the same Outcome]

##### Step: [Step Name]

| Action | Description |
|--------|-------------|
| [Action name] | [Details or —] |

---

## Summary

**Functional Coverage:**
- [List of outcomes and scenarios covered]

**Gaps Identified:**
- [Any functionality implied by the design but not fully captured]

**Recommendations:**
- [Priority suggestions, missing variations, implementation notes]
```

## Best Practices

1. **Extract intent, not layout:** Focus on WHAT the user achieves, not WHERE things are on screen
2. **Step is a variation, not a stage:** Each Step is a complete requirement slice — a configuration of the Scenario, not a sequential workflow phase
3. **Actions are logical activities:** Each Action may involve multiple UI interactions but is modeled as one logical activity
4. **Be specific with data:** Use actual labels/text from the design for field names and values
5. **Include all states:** Default, loading, error, success, empty, disabled — these become Scenarios or Steps
6. **Separate human and system personas:** If backend processing is involved, create distinct System persona outcomes
7. **Include data sources:** Specify where data comes from (API, local storage, etc.)

## Edge Cases to Consider

When analyzing designs, look for and document:

1. **Empty states:** What appears when there's no data?
2. **Loading states:** Spinners, skeletons, progress indicators
3. **Error states:** Inline errors, toast notifications, error pages
4. **Permission states:** Disabled features, locked content
5. **Multi-step flows:** Wizards, progress indicators, back/next navigation
6. **Bulk actions:** Select all, multi-delete, batch operations
7. **Search/filter:** Query inputs, filter chips, sort controls
8. **Pagination:** Page numbers, infinite scroll, load more
9. **Responsive layouts:** Mobile, tablet, desktop variations

## Error Handling

- If Figma URL is invalid, ask user to verify the URL format
- If Figma MCP is not available, tell user to install it or use PDF/image
- If PDF cannot be read, ask user to verify file path and permissions
- If design is unclear or ambiguous, ask clarifying questions before generating
- If no interactive elements are found, ask if this is a static design mockup
- If the design contains internal contradictions, present them before proceeding

## Notes

- The functional graph describes functional intent — it must be platform-agnostic and implementation-independent
- Every node aligns to the Persona → Outcome → Scenario → Step → Action hierarchy as defined in `./references/guide.md`
- Outcome = complete objective, Scenario = variation of completion, Step = configuration variation within scenario, Action = logical activity to fulfill step
- Format output as markdown for easy use in project management tools
