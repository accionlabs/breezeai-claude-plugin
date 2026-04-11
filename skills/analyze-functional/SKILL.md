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

### Step 1: Gather and Analyze Requirement

First, check if the user's input contains visual content — images, screenshots, Figma URLs, or UI design files (PNG, JPG, SVG, PDF with visual screens, etc.). If visual input is detected:
- **Do NOT proceed** with this skill.
- Inform the user: _"It looks like you've provided a visual input. Please use the `/breeze:visual-to-text` skill first to convert your design into structured text-based user stories. You can then use `/breeze:analyze-functional` to analyze the generated output against the functional graph."_
- Stop here and wait for the user to act.

If the input is text-based, accept it in any of the following formats:

**A. Jira ticket link/key** (e.g., `https://...atlassian.net/browse/PROJ-123` or `PROJ-123`)
- Use the Jira MCP tools to fetch the ticket details (summary, description, acceptance criteria, comments)
- Extract the requirement from the ticket content

**B. Document or specification text** (pasted text, PDF reference, uploaded doc)
- Extract functional intents from the document text
- Use `Documents` MCP to find related source material in the project

**C. Source code** (file paths, code snippets, class/method references)
- Use `Code_Graph_Search` and `Get_Code_File_Details` to understand the code
- Translate code to functional language — extract WHAT the code does, not HOW
- Map: classes → service boundaries, methods → processing phases,
  conditionals → business rules, queries → data operations
- Do NOT reproduce raw code in the requirement

**D. Free-text requirement** (no external reference)
- Accept the text as-is

Format the requirement into a clear, structured statement. Then identify functional intents — the discrete capabilities or behaviors the system must support (e.g., "authenticate user", "send notification", "generate report").

Next, search the existing functional graph using `Functional_Graph_Search` MCP and fetch all existing personas using `Get_all_personas` MCP. Compare the input against the existing graph and check for the following issues:

**A. Ambiguous persona references**
- Extract every actor/role mentioned in the input (e.g., "user", "admin", "customer")
- For each actor, match it to an existing persona in the graph
- If the input uses a generic term like "user" that could map to multiple existing personas, flag it as ambiguous
- If a referenced actor does not match any existing persona, flag it as a potentially new persona

**B. Conflicting requirements**
- Check if the input contains contradictory behaviors within itself (e.g., "require login" and "allow anonymous access" for the same flow)
- Check if any identified intent contradicts an existing scenario already in the graph (e.g., input says "email is optional" but an existing scenario enforces "email is required")

**C. Incomplete scenario definitions**
- Check if any intent describes a goal but lacks enough detail to define steps and actions (e.g., "handle payments" without specifying trigger, validation, or success/failure behavior)

**D. Terminology misalignment**
- Compare key terms in the input (entity names, action verbs, status values) against the vocabulary used in the existing functional graph
- Flag terms that mean the same thing as existing graph terms but are worded differently (e.g., "purchase" vs existing "order", "client" vs existing "customer")

Present all findings from A–D to the user in a summary. If no issues are found, state that the requirement is clear and proceed to Step 2.

### Step 2: Clarify Issues with User

If any issues were identified in Step 1, present them to the user and ask for clarification:

- **Ambiguous personas**: Ask which specific persona is intended, or whether to create a new one
- **Conflicts**: Present each conflict with the existing graph node details and ask how to resolve — keep existing behavior, replace it, or support both as separate scenarios
- **Incomplete definitions**: Ask the user to provide the missing details for each flagged intent
- **Terminology mismatches**: Suggest adopting the existing graph term and ask for confirmation, or let the user introduce a new term

**Repeat this step**: after each round of clarification, re-check the updated requirement for remaining issues. Continue until all issues are resolved. Only then proceed to Step 3.

### Step 3: Generate Functional Graph

Using the clarified requirement, generate the functional graph following the hierarchy: **Persona → Outcome → Scenario → Step → Action**.

**Resolve Personas:**
- Reuse existing personas from the graph wherever possible
- Apply persona resolution rules from `../shared/functional-graph-rules.md` (priority order, forbidden names, resolution tiebreakers)
- If the requirement involves backend processing (API endpoints, credential validation, token generation, email sending, database operations, background jobs, etc.), automatically include the **System persona** alongside the user-facing persona. Build separate scenarios for each:
  - **User-facing persona** — scenarios covering the interaction flow
  - **System persona** — scenarios covering the internal backend processing behavior

**Resolve Conflicts:**
- If any scenario/outcome already exists in the graph for the given requirement (detected in Step 1B), apply the user's resolution choice from Step 2 — update existing nodes or create new ones

**Build the graph:**
- Define Outcomes as high-level business capabilities
- Define Scenarios as specific testable flows under each Outcome
- Define Steps as sequential stages within each Scenario
- Define Actions as atomic operations within each Step

When building actions, apply the persona-aware rules from `../shared/functional-graph-rules.md`:
- Human personas: platform-agnostic, intent verbs, no UI widgets
- System persona: description REQUIRED with business logic precision
- External System: API/integration with endpoint details

Present the complete functional graph in **tabular format** to the user and ask for confirmation.

### Step 4: Prepare Citations

After the user confirms the functional graph in Step 3, determine the citation strategy based on the input sources:

**Determine citation type and content for each source:**
- `"jira"` — Jira ticket URL/key. `reference`: the Jira URL. `inputText`: full ticket content.
- `"confluence"` — Confluence page URL. `reference`: the URL. `inputText`: full page content.
- `"figma"` — Figma URL. `reference`: the Figma URL. `inputText`: converted text content.
- `"exDoc"` — document (PDF, uploaded doc, pasted spec). `name`: the actual file name or title of the document as provided by the user (e.g., "requirements.pdf", "Login Spec v2.docx"). Do NOT generate or summarize a name — use the original document name exactly. `inputText`: full document content.
- `"code"` — source code or code graph. `reference`: file path. `name`: file path. `inputText`: full file content.
- `"prompt"` — free-text typed by the user. `name`: generate a unique descriptive name (e.g., "Requirement: <short summary>"). `inputText`: full prompt text.

**Choose one of two strategies:**

**A. Same citation for all nodes** — When all nodes come from a single source (e.g., one Jira ticket, one document, one prompt):
- Call `Call_Create_Citation_` MCP tool once with `projectUuid`, `apiKey`, `name`, `reference`, `type`, and `inputText`.
- Save the returned citation `id` — you will pass it as `citationIds: [<citationId>]` on every node in Step 5.

**B. Different citations per node** — When nodes originate from multiple distinct sources (e.g., part from a Jira ticket, part from a document, part from code):
- Do NOT call `Call_Create_Citation_` separately.
- Instead, for each node in Step 5, pass the `citations` array directly on the create/update call. Each citation object in the array follows this schema:
  ```json
  {
    "type": "document | exDoc | jira | figma | confluence | code | prompt",
    "name": "<string, optional>",
    "inputText": "<string, optional>",
    "reference": "<string, optional>"
  }
  ```
- Populate the fields based on the citation type rules above. Each node gets its own `citations` array with the specific source(s) it came from.

### Step 5: Save Functional Graph

Save all nodes using `Call_Create_Functional_Node_` MCP tool following the hierarchy order (Persona → Outcome → Scenario → Step → Action). Wait for each parent ID before creating children.

**Attach citations to every node** based on the strategy chosen in Step 4:
- **Strategy A (same citation):** pass `citationIds: [<citationId>]` on each `Call_Create_Functional_Node_` call.
- **Strategy B (different citations):** pass the `citations` array on each `Call_Create_Functional_Node_` call with the appropriate citation object(s) for that node's source.

This applies to all node types — Persona, Outcome, Scenario, Step, and Action.

If the user chose to update existing nodes (from conflict resolution in Step 2), use `Call_Update_Functional_Node_` MCP instead for those nodes — same citation rules apply (`citationsIds` for Strategy A, `citations` array for Strategy B).

Refer to `../shared/functional-graph-rules.md` for the data model and required fields.

When creating actions, ensure descriptions follow the persona-aware rules from Step 3.

### Step 6: Sync Analysis Back to Jira

This step runs **only** if the original input in Step 1 was a Jira ticket link/key (input format A). For any other input source, skip Step 6 entirely.

1. Ask the user for explicit confirmation before touching Jira
2. On confirmation, fetch the current ticket via `mcp__plugin_atlassian_atlassian__getJiraIssue` and capture the existing `description` verbatim
3. Build the analysis block from Steps 1–5 and **append** it to the existing description (existing content + blank line + analysis block)
4. Write the combined description back via `mcp__plugin_atlassian_atlassian__editJiraIssue` — never overwrite, never post as a comment, never edit any other field
5. Reply to the user with the Jira URL so they can verify

> **Rules:** see [jira-sync-rules.md](references/jira-sync-rules.md) → "When to Apply", "Confirmation Gate", "Write Protocol", "Description Format Preservation", "Analysis Block Template", "Placeholder Rules", "Multi-Scenario Rule", and "Post-Write Confirmation".
