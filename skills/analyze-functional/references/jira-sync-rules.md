## Jira Sync Rules Reference

Rules for syncing the functional analysis result back to a Jira ticket
in **Step 6** of the `analyze-functional` skill. Follow these exactly.

---

### When to Apply

Apply this sync **only** when the original input in Step 1 was a Jira
ticket link or key (input format **A**).

- **Apply:** input was a Jira URL (`https://*.atlassian.net/browse/PROJ-123`) or a Jira key (`PROJ-123`)
- **Skip:** input was a document, source code, free text, or any other source

If skipped, end the skill silently after Step 5 — do not mention Jira.

---

### Confirmation Gate ⛔ HARD GATE

Never write to Jira without explicit user confirmation. After Step 5
completes, ask the user exactly:

> _"Would you like me to append this functional analysis to the description of Jira ticket `<TICKET-KEY>`? The existing description will be preserved and this analysis will be appended at the end."_

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
  `Breeze.AI Functional Analysis` blocks, posting as a comment via
  `addCommentToJiraIssue`, or editing any field other than
  `description`.
- **Why:** the ticket description must retain the full history of
  every analysis pass so reviewers see the evolving graph context
  inline with the requirement itself, not buried in the comment
  thread.

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

Use this template literally. Fill placeholders from Steps 1–5 of the
skill. Do NOT change the box-drawing characters, do NOT reorder
lines. This block is what you append to the existing description.

```
── Breeze.AI Functional Analysis ──
Status:   Graph updated (functional-graph@v<version>)
Case:     <New nodes | Updated nodes | Mixed>

Interpretation:
  Persona:  <Persona name>             [existing | NEW]
  Outcome:  <Outcome name>             [existing | NEW]
  Scenario: <Scenario name>            [existing | NEW]
  Steps:    <Step 1> → <Step 2> → ...
  Actions:  <Action 1>, <Action 2>, <Action 3>, ...

Graph impact:
  + <N> Scenario(s), + <N> Action(s)
  ~ Outcome "<Outcome name>" now has <N> scenario branches

Validation:  completeness ✓  consistency ✓  quality ✓  duplicates ✓
Citation:    <TICKET-KEY>
URL:         <Jira ticket URL>
Graph node:  breeze://<projectUuid>/functional/scenario/<scenario-slug>
Version:     functional-graph@v<version>
```

---

### Placeholder Rules

**`Status`** — always `Graph updated (functional-graph@v<version>)`
where `<version>` is the functional-graph version after Step 5 saved
the new nodes.

**`Case`** — pick one:
- `New nodes` — every node in this run was newly created
- `Updated nodes` — every node in this run was an update to an
  existing node (from conflict resolution in Step 2)
- `Mixed` — both new and updated nodes were saved

**`Interpretation` rows** — tag each line with `[existing]` if the
node was reused from the graph, or `[NEW]` if created in Step 5.
Keep the alignment shown in the template (use spaces, not tabs).

**`Steps`** — join with ` → ` (space, arrow, space). Use the Step
names exactly as saved in Step 5.

**`Actions`** — comma-separated list of Action names from Step 5.
Use the action names exactly as saved.

**`Graph impact`** — must reflect the **actual** diff from Step 5:
- `+ <N> Scenario(s)` — count of newly created scenarios
- `+ <N> Action(s)` — count of newly created actions
- `~ Outcome "<name>" now has <N> scenario branches` — only include
  this line if an existing Outcome gained new scenario branches in
  this run; otherwise omit it

**`Validation`** — checkmarks reflect Step 1 checks. If a check
failed initially but was resolved through Step 2 clarification,
still mark it ✓ since the final state passed.

**`Citation`** — the Jira ticket key only (e.g., `PROJ-2245`),
no URL.

**`URL`** — the full Jira ticket URL.

**`Graph node`** — the canonical `breeze://` URI for the primary
scenario node. Format: `breeze://<projectUuid>/functional/scenario/<scenario-slug>`.

**`Version`** — same `functional-graph@v<version>` value used in
the `Status` line.

---

### Multi-Scenario Rule

If Step 5 created more than one scenario, do **not** make multiple
description edits. Bundle every scenario into a **single** analysis
block by repeating the `Interpretation` and `Graph impact` sections
for each scenario, separated by one blank line. The `Status`,
`Validation`, `Citation`, `URL`, and `Version` lines appear only
once at the top and bottom of the block.

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
