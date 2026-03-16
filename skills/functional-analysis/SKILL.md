---
name: functional-analysis
description: >
  analyze the functional against the existing functional graph which can be access using breezeAi mcp tools.
  Identifies coverage gaps, conflicts, dependencies, and impact.
  Use when: "analyze this requirement", "is this covered", "impact
  of this change", "break down this user story".
---
## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

# requirement-analysis:

## Instructions

### Step 1: Gather Requirement Input

Check if the user provided a Jira ticket link/key (e.g., `https://...atlassian.net/browse/PROJ-123` or `PROJ-123`).

**If Jira link/key provided:**
- Use the Jira MCP tools to fetch the ticket details (summary, description, acceptance criteria, comments)
- Extract the requirement from the ticket content
- Remember that a Jira ticket was provided — store the ticket key for later (Step 7)

**If no Jira link:**
- Ask user to define the requirement properly
- Remember that no Jira ticket was provided — a new ticket will be created later (Step 7)

Identify functional intents from the input text.

### Step 2: Refine Requirement

Format the given requirement, check if there are any missing details or ambiguity, and take confirmation from user. According to feedback update the requirement.

**Repeat this step in a loop**: after each update, present the revised requirement and ask the user to confirm whether the requirement is complete. Keep asking for feedback and refining until the user explicitly confirms that the requirement is complete. Only then proceed to Step 3.

Once confirmed, search existing graph using functional graph search mcp.

### Step 3: Resolve Persona

Identify persona for the given requirement and check if this exists in the current functional graph using get persona mcp tool. If a new persona is detected then ask user for confirmation if he wants to use a new persona or wants to use an existing persona.

### Step 4: Resolve Conflicts

If any conflict detected in the functional graph (means any scenario/outcome already exists for the given requirement) ask user if he wants to update existing scenario/outcome or wants to create new. For those scenarios create step and action.

### Step 5: Present Functional Graph

Show the functional graph for the requirement user has given in tabular format.

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

Save all nodes to the functional graph using create functional node mcp tool following the hierarchy order (Persona → Outcome → Scenario → Step → Action). If user chose to update existing nodes in Step 4, use update functional node mcp instead. Refer to `references/guide.md` for data model and required fields.
