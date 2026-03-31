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

### 4. Assess Design Complexity

Before generating user stories, analyze the design to determine if it represents a **simple screen** or a **complex feature**:

**Simple Screen (Create ONE comprehensive user story):**
- Single-purpose page with one primary action (e.g., Login, Registration, Contact Form)
- All UI elements support the same user goal
- Related interactions are part of the same workflow (e.g., login includes forgot password, remember me)
- Typically 1-10 interactive elements

**Examples of Simple Screens:**
- Login page (includes login form, forgot password link, remember me checkbox)
- Contact form (includes form fields, submit button, validation)
- Profile view page (displays user info with edit button)
- Single product detail page
- Search results page

**Complex Design (Create MULTIPLE user stories):**
- Dashboard with multiple independent widgets or sections
- Page with distinct feature areas serving different user goals
- Multi-step workflows or wizards
- Page combining multiple CRUD operations (e.g., user management with create, edit, delete, search)
- More than 15 interactive elements with different purposes

**Examples of Complex Designs:**
- Admin dashboard with analytics, user management, and settings sections
- E-commerce checkout (shipping → payment → review → confirmation)
- Project management board with multiple lists, cards, and actions
- Settings page with multiple tabs (Profile, Security, Notifications, Billing)

### 5. Generate User Stories

Based on the complexity assessment:

**For Simple Screens:** Create ONE comprehensive user story that covers all UI elements and interactions on that screen.
- Include all related features in the acceptance criteria (e.g., for login: main login flow, forgot password, remember me, validation, errors)
- The story should represent the complete user experience for that screen
- All secondary actions (like "Forgot password?") should be acceptance criteria, NOT separate stories

**For Complex Designs:** Create separate user stories for each distinct user flow or feature area.
- Each story should address an independent user goal
- Stories should be independently testable and implementable
- Group related stories into epics if needed

Use this structure for each story:

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
```

**Example: Login Page (Simple Screen → ONE Story)**

```markdown
## User Story: User Login

**As a** registered user
**I want to** securely log into the application
**So that** I can access my account and personalized features

### Acceptance Criteria

- [ ] User can enter email address in email field (format: name@domain.com)
- [ ] User can enter password in password field (masked input)
- [ ] "Remember me" checkbox allows user to stay logged in across sessions
- [ ] Login button is enabled only when both email and password are filled
- [ ] Clicking "Login" button authenticates the user credentials
- [ ] On successful login, user is redirected to the dashboard
- [ ] On failed login, system displays "Invalid email or password" error message
- [ ] "Forgot password?" link navigates to password reset page
- [ ] Email field validates format before submission
- [ ] Password field shows/hides toggle icon for visibility
- [ ] Form prevents submission with empty fields
- [ ] Loading spinner appears on login button during authentication

### User Flow

1. User lands on login page
2. User enters email address
3. User enters password
4. User optionally checks "Remember me" checkbox
5. User clicks "Login" button
6. System validates credentials
7. On success: User is redirected to dashboard
8. On failure: Error message is displayed, user can retry

### Validation Rules

- Email: Must be valid email format (contains @ and domain)
- Password: Required field, minimum 8 characters
```

**Note:** This is ONE comprehensive story covering all login page functionality. Do NOT create separate stories for "Forgot Password", "Remember Me", or "Form Validation" - these are acceptance criteria within the main login story.


### 6. Acceptance Criteria Guidelines

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

### 7. Group Related Stories

If the design contains multiple screens or complex flows:

- Group related user stories by feature area or user journey
- Create epic-level summaries for complex features
- Show dependencies between stories
- Prioritize stories (Must Have, Should Have, Could Have)


### 8. Present User Stories and Ask to Save

**Step 1: Present the user stories**
- Display the complete user stories output in markdown format to the user

**Step 2: Ask user if they want to save**
- After presenting the user stories, ASK the user if they want to save the output as a markdown file
- Use this exact question: "Would you like me to save these user stories as a markdown (.md) file?"

**Step 3: Only save if user confirms**
- If user says yes, save the file using the Write tool
- **Filename format:** `user-stories-[screen-name].md` (e.g., `user-stories-login-page.md`)
- Derive `[screen-name]` from the design title, file name, or page heading — use lowercase, hyphen-separated words
- **Location:** Project root directory (from `<env>Working directory: ...</env>`)

**Step 4: Display the FULL ABSOLUTE PATH to the user**

After saving, you MUST display the complete file path in this exact format:

```
✅ User stories saved successfully!

📁 File location: /Users/sandeshbirwadkar/Documents/projects/breezeai-claude-plugin/user-stories-[screen-name].md

You can find your user stories at the above location.
```

**CRITICAL RULES:**
- ❌ DO NOT say: "Saved to user-stories-form.md"
- ❌ DO NOT say: "Saved to `user-stories-form.md`"
- ✅ DO say: "📁 File location: /Users/sandeshbirwadkar/Documents/projects/breezeai-claude-plugin/user-stories-form.md"
- The path MUST be the FULL ABSOLUTE PATH starting with `/` (root directory)
- Construct the path by combining: `<env>Working directory</env>` + `/` + filename

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
