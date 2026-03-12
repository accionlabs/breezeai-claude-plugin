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

### Step 1:
ask user to define requirment properly. Identify functional intents from the input text.

### Step 2:
format given user requirement, check in requirement if there is any missing details, any ambiguity in requirement, and take confirmation from user. According to feedback update the requirement.
**Repeat this step in a loop**: after each update, present the revised requirement and ask the user to confirm whether the requirement is complete. Keep asking for feedback and refining until the user explicitly confirms that the requirement is complete. Only then proceed to Step 3.
Once confirmed, search existing graph using functional graph search mcp.

### Step 3:
identify persona for the given requirement and check if this exists in current fuctional graph using get persona mcp tool, if new persona is detected then ask user for confirmation if he wants to use new persona or want to use existing persona.

### Step 4: 
if any conflict detected in the functional graph (means any scenario/ outcome already exists for the given requirement) ask user if he want to update existing sceanrio/outcome or want to create new. for those sceanrios create step and action.

### Step 5: 
now show the functional graph for requirement user has given in tabular format.

### Step 6: Update Functional Graph

after user confirms the functional graph, save all nodes to the functional graph using create functional node mcp tool following the hierarchy order (Persona → Outcome → Scenario → Step → Action). If user chose to update existing nodes in Step 5, use update functional node mcp instead. Refer to `references/guide.md` for data model and required fields.
