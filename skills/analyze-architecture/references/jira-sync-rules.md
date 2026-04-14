## Jira Sync Rules Reference

Rules for syncing the architecture analysis result back to a Jira
ticket in **Step 8** of the `analyze-architecture` skill. Follow
these exactly.

---

### When to Apply

Apply this sync **only** when the skill was invoked with
`--jira <jira-url>` in Step 1.

- **Apply:** invocation included `--jira` with a valid Jira URL or key
- **Skip:** ad-hoc invocation (document, diagram, image, free-form
  text, or current-state capture with no ticket)

If skipped, return the analysis as a structured summary artifact
instead. Optionally ask the user whether they'd like to mirror the
analysis into a Jira ticket; only proceed if they supply one.

---

### Confirmation Gate ⛔ HARD GATE

Never write to Jira without explicit user confirmation. After Step 7
completes (graph commit or blocker report), ask the user exactly:

> _"Would you like me to post this architecture analysis as a comment on Jira ticket `<TICKET-KEY>`? The ticket description and other fields will not be touched — the analysis will be added as a new comment."_

- If the user declines or is silent → stop. Do not call any Jira tool.
- If the user confirms → proceed to post the comment.

---

### Write Protocol

- **Tool:** `mcp__plugin_atlassian_atlassian__addCommentToJiraIssue`
- **Mode:** comment-only. Architecture analysis is ephemeral context
  that sits alongside the requirement — it belongs in the comment
  thread, not in the description.
- **FORBIDDEN:**
  - Editing the ticket description via `editJiraIssue`
  - Modifying summary, status, labels, assignee, or any other field
  - Overwriting or deleting prior `Breeze.AI Architecture Analysis`
    comments — each run produces a new comment so reviewers can see
    the evolution across analysis passes
  - Resolving, transitioning, or linking issues as a side effect
- **Why:** the description describes *what the ticket is*; analysis
  runs describe *how we interpreted it against the current graph
  state* — a temporal, append-only record that fits the comment
  thread semantics.

---

### Comment Format Preservation

- If the Jira instance uses **Atlassian Document Format (ADF / JSON)**
  for comments, wrap the analysis block as a single `codeBlock` node
  so the fixed-width layout (box-drawing characters, aligned columns)
  is preserved.
- If the instance accepts **plain string / wiki markup**, wrap the
  analysis block in a fenced code block (```) so monospace alignment
  survives rendering.
- Never flatten, reflow, or "tidy" the box-drawing characters or the
  column alignment — reviewers rely on the fixed layout to scan the
  report.

---

### Analysis Block Template

Use this template literally. Fill placeholders from Steps 1–7 of the
skill. Do NOT change the box-drawing characters, do NOT reorder
sections. This block is what you post as the comment body.

```
── Breeze.AI Architecture Analysis ──
Status:   Architecture Graph updated (architecture-graph@v<version>)
Case:     <classification summary>

IMPACT ANALYSIS
  Direct code impact (<count> files):
    • <file path> (<function name> L<start>-<end>)
  Indirect impact (via call graph): <count> files
  Architecture nodes touched: <count>
    <diff summary per node>

REUSE OPPORTUNITIES
  ✓ <existing component> — <reuse rationale>
  ⚠ <missing capability> — <suggestion>

CROSS-ONTOLOGY ALIGNMENT
  Functional anchors (confirmed):
    ✓ "<outcome/scenario>" (id: <functional_node_id>) [cited]
  Missing action coverage:
    ⚠ <gap>

GAPS & CONSISTENCY
  ⚠ <gap or inconsistency>
  ✓ <passed check>

COMMITTED TO GRAPH
  <layer>:
    + <node name> (new)
       code_ontology_id: <id>
       scenario: [<ids>]
       citations: [<ids or inline refs>]
    ~ <node name> (modified)

Citation:    <Jira key>
URL:         <Jira URL>
Version:     architecture-graph@v<version>
```

---

### Placeholder Rules

**`Status`** — always `Architecture Graph updated (architecture-graph@v<version>)`
where `<version>` is the architecture-graph version after Step 7
committed the nodes. For blocked runs use
`Architecture Graph NOT updated — blockers present`.

**`Case`** — pick one summary phrase:
- `New component, reuses existing library`
- `New service with confirmed scenario anchor`
- `New library-level component (topology change)`
- `Modifies existing node(s)`
- `Baseline documentation — current-state capture`
- `BLOCKED — <short reason>`

**`IMPACT ANALYSIS`** — populate from Step 4a:
- Direct files: list each affected file with the impacted
  function/class and line range as returned by `Code_Graph_Search` /
  `Get_Code_File_Details`. Cap the list at 10 entries; if there are
  more, add `... and <N> more` on its own line.
- Indirect impact: count of files reached via `calls` traversal.
- Architecture nodes touched: one short line per node summarizing
  the delta (e.g., `+ UserExperience "Voice App" (new)`).

**`REUSE OPPORTUNITIES`** — populate from Step 4b:
- `✓` for reuse candidates the analysis found
- `⚠` for capabilities that *should* already exist but don't
- Omit the whole section if the run is a current-state capture
  (there's nothing to compare against yet)

**`CROSS-ONTOLOGY ALIGNMENT`** — populate from Step 4c:
- List each UX / ApiGateway / Services node's confirmed scenario
  anchors (from Step 5 user confirmation)
- Tag each entry `[cited]` once the citation is attached in Step 7
- Flag unanchored nodes as blockers (these should have stopped the
  commit in Step 7 — record them in BLOCKERS below, not here)

**`GAPS & CONSISTENCY`** — populate from Step 4d. Mark gaps with `⚠`
and passed checks with `✓`. Include layer-boundary violations,
naming-convention drift, missing observability / backup policies,
technology-stack divergence.

**`COMMITTED TO GRAPH`** — populate from Step 7:
- Group entries by layer, in the commit order: UserExperience →
  ApiGateway → Services → Agents → EventQueue → DataLake →
  ObservabilityMonitoring → Infrastructure
- Prefix new nodes with `+`, modified nodes with `~`
- Under each node, show `code_ontology_id`, `scenario` (for the
  three anchoring layers), and `citations` — the citation IDs from
  Strategy A or a short `<type>:<name>` summary for Strategy B
  inline citations
- For **blocked runs**, replace this whole section with a `BLOCKERS`
  section listing each blocker with its resolution requirement. Do
  not show any `+`/`~` entries if the commit was blocked.

**`Citation`** — the Jira ticket key only (e.g., `PROJ-2245`),
no URL.

**`URL`** — the full Jira ticket URL.

**`Version`** — same `architecture-graph@v<version>` value used in
the `Status` line. Omit or set to `n/a` for blocked runs where no
commit occurred.

---

### Current-State Capture Rule

When Step 2 flagged the run as a current-state capture (empty or
sparse Architecture Graph + input describes an existing system):

- Change the first line to `── Breeze.AI Architecture Analysis — Baseline documentation ──`
- Set `Case` to `Baseline documentation — current-state capture`
- **Skip** the `REUSE OPPORTUNITIES` and `GAPS & CONSISTENCY`
  sections entirely — there's no prior state to compare against
- Keep `IMPACT ANALYSIS` scoped to "code scanned to infer the
  baseline", not "files this change touches"
- `COMMITTED TO GRAPH` lists every baseline node created in this run

---

### Blocked-Run Rule

If Step 7 blocked the commit (unanchored UX / ApiGateway / Services
node, layer boundary violation, duplicate-of-existing, or missing
citation):

- Set `Status` to `Architecture Graph NOT updated — blockers present`
- Set `Case` to `BLOCKED — <short reason>`
- Replace `COMMITTED TO GRAPH` with a `BLOCKERS` section:
  ```
  BLOCKERS
    ⛔ <blocker description>
       requires: <what the user must do to unblock>
  ```
- Set `Version` to `n/a` or omit the line
- Still post the comment — blocked runs are informative for the
  reviewer and document why no graph change occurred

---

### Multi-Node Rule

One analysis pass can commit multiple architecture nodes across
multiple layers. Do **not** post multiple comments. Bundle every
committed node into a **single** analysis comment:

- The `IMPACT ANALYSIS`, `REUSE OPPORTUNITIES`,
  `CROSS-ONTOLOGY ALIGNMENT`, and `GAPS & CONSISTENCY` sections
  appear once
- Under `COMMITTED TO GRAPH`, repeat the per-layer grouping for every
  affected layer in commit order
- The `Status`, `Case`, `Citation`, `URL`, and `Version` lines appear
  only once at the top and bottom of the block

---

### Post-Write Confirmation

After the comment is successfully posted:

1. Read the response from the `addCommentToJiraIssue` MCP tool to
   confirm success and capture the returned comment ID
2. Reply to the user with the Jira ticket URL so they can verify the
   appended analysis in the comment thread
3. If the MCP tool returned an error, surface the error verbatim,
   do NOT retry automatically, and do NOT attempt to delete any
   partial comment — ask the user how to proceed
