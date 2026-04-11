## Jira Sync Rules Reference

Rules for syncing the design analysis result back to a Jira ticket
in **Step 7** of the `analyze-design` skill. Follow these exactly.

---

### When to Apply

Apply this sync **only** when the original input included a Jira
ticket link or key.

- **Apply:** input included a Jira URL (`https://*.atlassian.net/browse/PROJ-123`) or a Jira key (`PROJ-123`)
- **Skip:** input was only a Figma URL with no Jira ticket

If skipped, end the skill silently after Step 6 — do not mention Jira.

---

### Confirmation Gate - HARD GATE

Never write to Jira without explicit user confirmation. After Step 6
completes, ask the user exactly:

> _"Would you like me to append this design analysis to the description of Jira ticket `<TICKET-KEY>`? The existing description will be preserved and this analysis will be appended at the end."_

- If the user declines or is silent → stop. Do not call any Jira tool.
- If the user confirms → proceed to update the description.

---

### Write Protocol

- **Tool:** `mcp__plugin_atlassian_atlassian__editJiraIssue`
- **Field:** `description` only — never modify summary, status, or
  any other field.
- **Mode:** append-only. **Read-modify-write** the description:
  1. Fetch the current ticket via
     `mcp__plugin_atlassian_atlassian__getJiraIssue` and capture the
     existing `description` value verbatim.
  2. Build the new description as
     `<existing description>` + one blank line + `<analysis block>`.
  3. Call `editJiraIssue` with the combined description.
- **FORBIDDEN:** overwriting the description, replacing prior
  `Breeze.AI Design Analysis` blocks, posting as a comment via
  `addCommentToJiraIssue`, or editing any field other than
  `description`.

---

### Description Format Preservation

- If the existing description uses **Atlassian Document Format
  (ADF / JSON)**, append the analysis block as a new code-block node
  at the end of the document tree — do not flatten the existing ADF
  to plain text.
- If the existing description is a **plain string** (Jira wiki or
  Markdown), append the analysis block as a fenced code block (```)
  separated from the prior content by one blank line.
- If the existing description is **empty or null**, set it to the
  analysis block alone (no leading blank line).
- Never strip, reformat, or "tidy" any existing description content.

---

### Analysis Block Template

Use this template literally. Fill placeholders from Steps 1–6 of the
skill. Do NOT change the box-drawing characters, do NOT reorder
lines. This block is what you append to the existing description.

```
── Breeze.AI Design Analysis ──
Source:   Figma: <Figma URL or "N/A"> | Jira: <TICKET-KEY>

Functional Summary:
  Page purpose: <summary>
  Key interactions: <list>

Component Inventory:
  <Component 1> — <Type> — <Functionality>
  <Component 2> — <Type> — <Functionality>
  ...

Functional Graph Mapping:
  Persona:  <Persona name>             [existing | NEW]
  Outcome:  <Outcome name>             [existing | NEW]
  Scenario: <Scenario name>            [existing | NEW]
  Steps:    <Step 1> → <Step 2> → ...
  Actions:  <Action 1>, <Action 2>, <Action 3>, ...

Gaps:
  Design → Graph: <items in design but not in graph>
  Graph → Design: <items in graph but not in design>
  Acceptance criteria: <covered / not covered summary>

Graph updated: <Yes — N new nodes | No>
Citation:    <TICKET-KEY>
URL:         <Jira ticket URL>
```

---

### Placeholder Rules

**`Source`** — show the Figma URL if provided, otherwise "N/A".
Always show the Jira ticket key.

**`Functional Graph Mapping` rows** — tag each line with `[existing]`
if the node was reused from the graph, or `[NEW]` if created in
Step 6. Keep the alignment shown in the template (use spaces, not
tabs).

**`Steps`** — join with ` → ` (space, arrow, space).

**`Actions`** — comma-separated list of Action names.

**`Gaps`** — summarize each gap category. If no gaps, write "None".

**`Graph updated`** — "Yes — N new nodes" if Step 6 created nodes,
"No" if the user declined or no updates were needed.

**`Acceptance criteria`** — only include this line if a Jira ticket
was part of the input. Summarize which criteria are covered by the
design and which are not.

---

### Post-Write Confirmation

After the description is successfully updated:

1. Read the response from the `editJiraIssue` MCP tool to confirm
   success
2. Reply to the user with the Jira URL so they can verify the
   appended analysis
3. If the MCP tool returned an error, surface the error verbatim,
   do NOT retry automatically, and do NOT attempt to roll back the
   description — ask the user how to proceed
