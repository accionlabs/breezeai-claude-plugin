---
name: analyze-functional
description: >
  analyze the functional against the existing functional graph which can be access using breezeAi mcp tools.
  Identifies coverage gaps, conflicts, dependencies, and impact.
  Use when: "analyze this requirement", "is this covered", "impact
  of this change", "break down this user story".
---
## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

# requirement-analysis:

## Instructions

### Step 1: Gather Requirement Input

Determine the input type. The user may provide ANY of the following:

**A. Jira ticket link/key** (e.g., `https://...atlassian.net/browse/PROJ-123` or `PROJ-123`)
- Use the Jira MCP tools to fetch the ticket details (summary, description, acceptance criteria, comments)
- Extract the requirement from the ticket content
- Remember that a Jira ticket was provided — store the ticket key for later (Step 7)

**B. Document or specification text** (pasted text, PDF reference, uploaded doc)
- Extract functional intents from the document text
- Use `Documents` MCP to find related source material in the project

**C. Source code** (file paths, code snippets, class/method references)
- Use `Code_Graph_Search` and `Get_Code_File_Details` to understand the code
- Translate code to functional language — extract WHAT the code does, not HOW
- Map: classes → service boundaries, methods → processing phases,
  conditionals → business rules, queries → data operations
- Do NOT reproduce raw code in the requirement

**D. Figma design URL**
- Use Figma MCP `get_design_context` to fetch the design
- Extract functional intents from the UI components and interactions

**E. Free-text requirement** (no external reference)
- Ask user to define the requirement properly
- Remember that no Jira ticket was provided — a new ticket may be created later (Step 7)

Identify functional intents from the input text.

### Step 2: Refine Requirement

Format the given requirement, check if there are any missing details or ambiguity, and take confirmation from user. According to feedback update the requirement.

**Repeat this step in a loop**: after each update, present the revised requirement and ask the user to confirm whether the requirement is complete. Keep asking for feedback and refining until the user explicitly confirms that the requirement is complete. Only then proceed to Step 3.

Once confirmed, search existing graph using functional graph search mcp.

### Step 3: Resolve Persona

Identify **all personas** relevant to the requirement and check if they exist in the current functional graph using the get persona MCP tool. If a new persona is detected, ask the user for confirmation whether to use a new persona or reuse an existing one.

Apply persona resolution rules from `../shared/functional-graph-rules.md` (priority order, forbidden names, resolution tiebreakers).

**Multi-persona resolution:** If the requirement involves backend processing (API endpoints, credential validation, token generation, email sending, database operations, background jobs, etc.), automatically include the **System persona** alongside the user-facing persona. Build separate scenarios for each:
- **User-facing persona** — scenarios covering the interaction flow
- **System persona** — scenarios covering the internal backend processing behavior

### Step 4: Resolve Conflicts

If any conflict detected in the functional graph (means any scenario/outcome already exists for the given requirement) ask user if he wants to update existing scenario/outcome or wants to create new. For those scenarios create step and action.

### Step 5: Present Functional Graph

Show the functional graph for the requirement user has given in tabular format.

When presenting steps and actions, apply the persona-aware action
rules from `../shared/functional-graph-rules.md`:
- Human personas: platform-agnostic, intent verbs, no UI widgets
- System persona: description REQUIRED with business logic precision
- External System: API/integration with endpoint details

### Step 6: Sync to Jira

After user confirms the functional graph in Step 5, ask:
"Would you like to save the refined requirement and functional analysis to Jira?"

If user confirms:

**If a Jira ticket was provided in Step 1:**
- Update the existing Jira ticket using Jira MCP tools
- Update the ticket description with the refined requirement
- Add the functional graph summary (personas, outcomes, scenarios, steps, actions) as a comment or in the description

**If no Jira ticket was provided in Step 1:**
- Create a new Jira ticket using Jira MCP tools
- Ask user for the Jira project key (e.g., `PROJ`) if not already known
- Set the summary from the refined requirement title
- Set the description with the full refined requirement and functional graph summary
- Report the new ticket key/link to the user

If user declines, skip Jira sync.

### Step 7: Update Functional Graph

Save all nodes to the functional graph using create functional node mcp tool following the hierarchy order (Persona → Outcome → Scenario → Step → Action). If user chose to update existing nodes in Step 4, use update functional node mcp instead. Refer to `../shared/functional-graph-rules.md` for data model and required fields.

When creating actions, ensure descriptions follow the persona-aware rules from Step 5.
