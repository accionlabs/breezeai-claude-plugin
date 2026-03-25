---
name: generate-userstory-from-uidesign
description: >
  Generate user stories from UI design visuals (Figma frames or PDF screens).
  Extracts UI components, interactions, and flows to create structured user
  stories with acceptance criteria. Use when: user shares a Figma URL or PDF
  design, "create user stories from design", "convert Figma to user stories",
  "generate stories from screens". Supports Figma MCP server and PDF files.
---


## User Story Generation Flow

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

### 3. Identify User Flows

Analyze the design to understand:

- **Primary user goal:** What is the main action/outcome?
- **User journey:** Step-by-step flow through the interface
- **Entry points:** How does the user arrive at this screen?
- **Exit points:** Where does the user go after completing actions?
- **Validation rules:** What constraints exist on inputs?
- **Error scenarios:** What can go wrong and how is it handled?
- **Success scenarios:** What happens when actions complete successfully?

### 4. Generate User Stories

For each distinct user flow or feature area, create a user story following this structure:

```
## User Story: [Story Title]

**As a** [persona/user type]
**I want to** [action/goal]
**So that** [benefit/outcome]

### Acceptance Criteria

- [ ] [Criterion 1: specific, testable requirement]
- [ ] [Criterion 2: specific, testable requirement]
- [ ] [Criterion 3: specific, testable requirement]
...

### User Flow

1. [Step 1: User action or system state]
2. [Step 2: User action or system state]
3. [Step 3: User action or system state]
...

### Validation Rules

- [Field name]: [Validation requirement]
- [Field name]: [Validation requirement]

### Error Scenarios

- **[Error type]:** [Error message and handling]
- **[Error type]:** [Error message and handling]

### Success Criteria

- [What indicates successful completion]
- [Post-action state or navigation]
```

### 5. Acceptance Criteria Guidelines

Write acceptance criteria that are:

- **Specific:** Clearly defined with no ambiguity
- **Testable:** Can be verified through testing
- **User-focused:** Written from user perspective
- **Complete:** Cover happy path, edge cases, and error states

**Examples of good acceptance criteria:**

✓ User can enter a valid email address (format: name@domain.com)
✓ Password field must accept minimum 8 characters including 1 number
✓ Login button is disabled until both email and password are filled
✓ System displays "Invalid credentials" error if login fails
✓ User is redirected to dashboard page on successful login
✓ "Forgot password?" link navigates to password reset page

**Examples of bad acceptance criteria:**

✗ Login should work
✗ Good user experience
✗ System behaves correctly

### 6. Group Related Stories

If the design contains multiple screens or complex flows:

- Group related user stories by feature area or user journey
- Create epic-level summaries for complex features
- Show dependencies between stories
- Prioritize stories (Must Have, Should Have, Could Have)

### 7. Optional: Link to Functional Graph

## Output Format

Present your user stories using this structure:

```
# User Stories: [Design Name/Screen Name]

**Source:** [Figma URL or PDF filename]
**Date Generated:** [Current date]

---

## Overview

[Brief description of what this design represents and its purpose]

**Total User Stories:** [N]

---

## Epic: [Epic Name] (if applicable)

[Description of the epic or feature group]

---

### Story 1: [Story Title]

**As a** [persona]
**I want to** [action]
**So that** [benefit]

**Acceptance Criteria:**

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

**UI Components:**

| Component | Type | Purpose |
|-----------|------|---------|
| [Component name] | [Input/Button/Display/etc] | [What it does] |

**User Flow:**

1. [Step 1: User action or system state]
2. [Step 2: User action or system state]
3. [Step 3: User action or system state]

**Validation Rules:**

- [Field name]: [Validation requirement]
- [Field name]: [Validation requirement]


---

### Story 2: [Story Title]

[Repeat structure for each story]

---

## Summary

[Recap of all stories generated, priority suggestions, implementation notes]
```

## Best Practices

1. **Be specific with component names:** Use actual labels/text from the design
2. **Include all states:** Default, hover, disabled, loading, error, success
3. **Cover accessibility:** Note any accessibility features visible in design
4. **Reference design patterns:** Call out common patterns (e.g., "standard login form")
5. **Note responsive behavior:** If visible in design, mention mobile/tablet variations
6. **Include data sources:** Specify where data comes from (API, local storage, etc.)
7. **Document interactions:** Hover effects, animations, transitions
8. **Specify timing:** Loading states, timeouts, debouncing requirements

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
10. **Dark mode:** Theme variations if shown in design


## Error Handling

- If Figma URL is invalid, ask user to verify the URL format
- If Figma MCP is not available, tell user to install it or use PDF/image
- If PDF cannot be read, ask user to verify file path and permissions
- If design is unclear or ambiguous, ask clarifying questions before generating stories
- If no interactive elements are found, ask if this is a static design mockup

## Notes

- Prioritize clarity and completeness over brevity
- Use actual text/labels from the design when possible
- Include screenshots references if helpful (e.g., "See login form, top-right corner")
- Format output as markdown for easy copy/paste into project management tools
- User stories should be independently testable and implementable
- Each story should deliver value to the user
