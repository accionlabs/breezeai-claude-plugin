---
name: generate-doc
description: >
  Generate a functional specification document from the functional graph.
  Outputs structured Markdown grouped by persona with citations.
  Use when: "generate spec", "generate document", "functional spec",
  "create specification", "export functional graph".
---

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

---

## Scope Resolution

Determine scope from `$ARGUMENTS`:

### No arguments — show options guide

If `$ARGUMENTS` is empty or missing, do NOT generate anything.
Instead, present the user with a guide:

```
**What would you like to generate?**

| Option | Command | Description |
|--------|---------|-------------|
| **Plain Markdown** | `--plain` | Concise tabular spec with scenarios, steps, and actions grouped by persona. Best for: quick reference, sharing in PRs, lightweight documentation. |
| **Rich Markdown** | `--full` | Everything in plain + AI-synthesized executive summary, business objectives, stakeholders, capabilities, per-outcome business value, business rules, and mermaid diagrams. Best for: stakeholder reviews, proposals, comprehensive documentation. |
| **Plain HTML** | `--html` | Interactive single-file viewer with sidebar navigation, search, collapsible accordions, light/dark theme. Best for: team browsing, client demos, embedding in wikis. |
| **Rich HTML** | `--html --full` | Everything in plain HTML + all AI enrichments rendered visually — stakeholder cards, capability accordions, mermaid diagrams, persona descriptions. Best for: client deliverables, executive presentations, full specification review. |

**Scope options** (append to any command above):
- Full project (default): all personas and outcomes
- Single persona: `/breeze:generate-doc --plain "Financial Institution User"`
- Single outcome: `/breeze:generate-doc --html --full "Manage Integrations"`

**Export to other formats** (after generating markdown):
- Word: `/breeze:generate-doc --export docx`
- PDF:  `/breeze:generate-doc --export pdf`

**After generation**, you can review and give feedback to improve any section — I'll update and regenerate instantly.

What would you like to generate?
```

Wait for the user to choose before proceeding.

### Export (`--export`)

When `$ARGUMENTS` contains `--export docx` or `--export pdf`:

1. Check if `functional-spec.md` exists in the project root.
   If not, tell the user to generate the markdown first.

2. Check if `pandoc` is installed:
   ```bash
   which pandoc
   ```
   If not found, tell the user:
   "pandoc is required for export. Install it with:
   `sudo apt install pandoc` (Linux) or `brew install pandoc` (Mac)"

3. Pre-render mermaid diagrams:
   ```bash
   python3 {SKILL_BASE_DIR}/scripts/render-mermaid.py functional-spec.md functional-spec-export.md
   ```
   - If mermaid blocks exist and rendering succeeds, use `functional-spec-export.md` for conversion
   - If no mermaid blocks found, use `functional-spec.md` directly
   - If rendering fails (no chromium/mmdc), warn the user and proceed with `functional-spec.md`
     ("Mermaid diagrams will appear as code blocks. Install chromium for rendered diagrams.")

4. Run the conversion:
   ```bash
   # For DOCX
   pandoc <source.md> -o functional-spec.docx --from=gfm

   # For PDF (requires a LaTeX engine)
   pandoc <source.md> -o functional-spec.pdf --from=gfm --pdf-engine=xelatex
   ```

5. Clean up temporary files:
   ```bash
   rm -rf _mermaid_images/ functional-spec-export.md
   ```

6. Print: "Exported to functional-spec.docx" (or .pdf)

Note: The `--full` markdown works best for export since it includes
all the enrichment content (including mermaid diagrams rendered as
images). Plain markdown exports work too but will be more concise.

### With arguments — resolve scope

- **"all" / "full"** -> Generate for the entire project (all personas)
- **Persona name** (e.g., "Financial Institution User") -> Generate for that persona only
- **Outcome name** (e.g., "Manage Integrations") -> Generate for that outcome only

If the scope is ambiguous, ask the user to clarify.

---

## Data Collection

### Full Project Scope

Call `Get_complete_functional_graph` with the project UUID.
This returns the **entire hierarchy** in a single call:

```
{
  project: { ... },
  personas: [
    {
      id, persona, outcomes: [
        {
          id, outcome, description, citations, scenarios: [
            {
              id, scenario, description, steps: [
                {
                  id, step, description, actions: [
                    { id, action, description }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  summary: { ... }
}
```

The response will be large (often 500K+ characters) and will be
auto-saved to a file on disk. This is expected — NOT an error.
The file path will be shown in the tool result message.

To process the data, use Bash with `python3` or `jq` to:
1. Parse the saved JSON file
2. Extract the `personas` array from the nested wrapper:
   `data[0].text` → parse JSON → `[0].text` → parse JSON → `[0].data.personas`
3. Transform it into the Markdown structure
4. Write the result directly to the output file

This approach avoids loading the entire graph into the conversation
context. Use a single Bash script to read, transform, and write.

If scope is a specific **persona**, filter the `personas` array
to that persona only.

If scope is a specific **outcome**, find it within the personas
array and generate only that outcome's section (include the parent
persona name for context).

### Scoped Queries (Single Persona or Outcome)

For scoped queries, you MAY use the individual hierarchy tools
instead to avoid the expensive full-graph call:

- `Get_all_personas` -> `Get_all_outcomes_for_a_persona_id`
  -> `Get_all_scenarios_for_a_outcome_id`
  -> `Get_all_steps_actions_for_a_scenario_id`

Parallelize calls at each level.

### Important

- Extract `citations` from outcome entities. Citations contain
  `documentId` and `documentName`. Collect unique document names
  for the Sources column.
- If a level returns no children, note it as "(No scenarios defined)"
  or "(No steps defined)" in the output.

---

## Document Generation

Once all data is collected, generate a single Markdown document
following the structure below **exactly**.

---

## Output Structure

### Mode 1 — Plain (`--plain` or default)

Use this mode when `$ARGUMENTS` contains `--plain` or does NOT contain `--full`.

Generate a concise tabular document:

```
# Functional Specification: {Project Name}

**Generated:** {current date}

---

## Table of Contents

### {Persona Name} ({N} outcomes)
- [Outcome Name](#anchor)
- ...

---

## {Persona Name}

### {Outcome Name}

> **Sources:** `{document1.pdf}`, `{document2.pdf}`

| # | Scenario | Step | Actions | Source |
|---|----------|------|---------|--------|
| 1 | {Scenario Name} | {Step Name} | {Action 1} | `{doc.pdf}` |
| | | | {Action 2} | |
| | | {Step 2 Name} | {Action 1} | `{doc.pdf}` |
| 2 | {Scenario 2} | {Step Name} | {Action 1} | `{doc.pdf}` |

---
```

**Table rules:**
- Scenario number only on the first row of each scenario
- Step name only on the first row of each step
- Each action gets its own row
- Source column shows the citation document name (from the deepest
  level that has a citation — action > step > scenario > outcome)
- If no actions exist for a step, show the step with "(No actions defined)"
- If no steps exist for a scenario, show the scenario with "(No steps defined)"

---

### Mode 2 — Full (`--full`)

Use this mode when `$ARGUMENTS` contains `--full`.

Generate a rich document with AI-synthesized summaries. This mirrors
the structure of the HTML functional specification viewer.

```
# Functional Specification: {Project Name}

**Version:** 1.0 | **Generated:** {current date}

---

## Executive Summary

{Write a 2-3 paragraph executive summary synthesized from all the
personas, outcomes, and scenarios in the graph. Describe what the
application does, who uses it, and its key capabilities.}

## Key Business Objectives

{Synthesize 4-6 high-level business objectives from the outcomes.}

1. {Objective}
2. {Objective}

## Key Stakeholders

| Role | Interest | Personas |
|------|----------|----------|
| {Stakeholder role} | {What they care about} | {Persona names} |

## Key Capabilities

{Synthesize 5-8 key capabilities from across all outcomes.}

- {Capability}
- {Capability}

---

## Table of Contents

### {Persona Name} ({N} outcomes)
- [Outcome Name](#anchor)
- ...

---

## {Persona Name}

### {Outcome Name}

> **Business Value:** {Synthesize a 1-2 sentence business value
> statement from the outcome's scenarios and actions.}
>
> **Sources:** `{document1.pdf}`, `{document2.pdf}`

<details><summary>Capabilities ({N})</summary>

{Synthesize capabilities from the scenarios and steps under this outcome.}

| Capability | Description |
|------------|-------------|
| {Name} | {Description} |

</details>

<details><summary>Inputs / Outputs</summary>

{Infer inputs and outputs from the steps and actions.}

**Inputs:** {list}
**Outputs:** {list}

</details>

<details><summary>Business Rules ({N})</summary>

{Infer business rules from the actions and steps — constraints,
validations, conditions mentioned.}

| Rule | Description |
|------|-------------|
| BR-{N} | {Description} |

</details>

#### Workflow

##### Scenario: {Scenario Name}

> {Scenario description}

| # | Step | Actions | Source |
|---|------|---------|--------|
| 1 | {Step Name} | {Action 1} | `{doc.pdf}` |
| | | {Action 2} | |
| 2 | {Step 2 Name} | {Action 1} | `{doc.pdf}` |

---
```

**Full mode rules:**
- Executive Summary, Business Objectives, Key Capabilities, and
  Key Stakeholders are **synthesized by you** from the graph data.
  Do NOT call any extra tools for this — derive from collected data.
- Per-outcome Business Value, Capabilities, Inputs/Outputs, and
  Business Rules are **synthesized by you** from that outcome's
  scenarios, steps, and actions.
- Use `<details>` tags for collapsible sections (Capabilities,
  Inputs/Outputs, Business Rules).
- Workflow tables follow the same rules as Plain mode.
- If an outcome has a Mermaid-compatible flow, include a
  ```mermaid block after the workflow tables.

---

## File Output

After generating the document:

### Markdown output (default)

Use the markdown generator script:

```bash
# Plain mode (no enrichments)
python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> functional-spec.md

# Full mode with enrichments
python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> functional-spec.md --enrichments enrichments.json
```

The script:
- Reads the MCP tool JSON output (handles the nested wrapper format)
- Plain mode: concise tabular document (scenario/step/action tables)
- Full mode: rich document with executive summary, objectives,
  stakeholders, capabilities, persona descriptions, per-outcome
  business value, capabilities, business rules, mermaid diagrams,
  and workflow tables
- Uses `<details>` tags for collapsible sections in full mode

Print a summary:

```
Written to functional-spec.md

  {N} personas, {N} outcomes, {N} scenarios, {N} steps, {N} actions

To convert to other formats:
  docx:  pandoc functional-spec.md -o functional-spec.docx
  pdf:   pandoc functional-spec.md -o functional-spec.pdf
  html:  use --html flag instead
```

### HTML output (`--html`)

When `$ARGUMENTS` contains `--html`:

1. Call `Get_complete_functional_graph` to get the full graph JSON.
   The response will be saved to a file on disk (expected behavior).

2. **If `--full` is also present**, generate AI enrichments using
   the extraction script and AI synthesis:

   a. Run the extraction script to produce a compact outline:

   ```bash
   python3 {SKILL_BASE_DIR}/scripts/extract-graph-summary.py <saved-json-file> outline outline.json
   ```

   This produces a ~60-130 KB JSON with persona/outcome/scenario names
   and step names — small enough to read in conversation context.

   b. Read `outline.json` (in chunks if needed per persona) and
      synthesize the **top-level enrichments**:
      - `executiveSummary`, `keyBusinessObjectives`, `keyStakeholders`,
        `keyCapabilities`, `personaEnrichments`

   c. For **per-outcome enrichments**, use batch extraction:

   ```bash
   python3 {SKILL_BASE_DIR}/scripts/extract-graph-summary.py <saved-json-file> batch outcome-details/
   ```

   This produces one JSON file per outcome (~2-10KB each) in
   `outcome-details/` with a `_manifest.json` index. Read each
   outcome file and synthesize its enrichments.

   Alternatively, for a single outcome:
   ```bash
   python3 {SKILL_BASE_DIR}/scripts/extract-graph-summary.py <saved-json-file> outcome <outcome-id> outcome-detail.json
   ```

   d. Write the combined `enrichments.json` file:

   ```json
   {
     "executiveSummary": "2-3 paragraph overview...",
     "keyBusinessObjectives": ["Objective 1", "Objective 2"],
     "keyStakeholders": [
       {
         "role": "<actual persona name>",
         "interest": "What this persona cares about"
       }
     ],
     "keyCapabilities": ["Capability 1", "Capability 2"],
     "personaEnrichments": {
       "<persona-name>": {
         "description": "1-2 sentence description"
       }
     },
     "outcomeEnrichments": {
       "<outcome-id>": {
         "businessValue": "1-2 sentence value statement",
         "capabilities": [
           { "capabilityName": "Name", "description": "Description" }
         ],
         "businessRules": [
           { "ruleId": "BR-001", "description": "Rule description" }
         ],
         "mermaidDiagram": "graph TD\n  A[Persona] -->|action| B[Feature]"
       }
     }
   }
   ```

   **Synthesis guidelines:**

   *Top-level (from outline):*
   - Executive Summary: What the app does, who uses it, key value.
   - Business Objectives: 4-6 high-level goals from outcome names.
   - Stakeholders: Use ACTUAL persona names as role (not invented).
     Include interest description for each.
   - Capabilities: 5-8 cross-cutting capabilities from outcomes.
   - Persona Descriptions: 1-2 sentences per persona.

   *Per-outcome (from outcome detail files):*
   Synthesize across ALL scenarios — do not document individually.
   - Business Value: What business problem does this outcome solve?
   - Capabilities: Inferred from repeated intents or workflow patterns.
     Each capability must be supported by at least one scenario.
   - Business Rules: Constraints, validations, conditions implied
     by steps/actions. Derived from the workflows, not invented.
   - Mermaid Diagram: `graph TD` format. Represent the outcome as a
     container/subgraph. Show inferred capabilities as nodes, not
     individual scenarios. Show high-level flow and dependencies.
     5-10 nodes max. Avoid UI-level or step-level detail.
     The diagram should explain the module at a glance to a stakeholder.

3. Run the HTML generator script:

```bash
# Without enrichments (--html only)
python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> functional-spec.html

# With enrichments (--html --full)
python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> functional-spec.html --enrichments enrichments.json
```

Where `{SKILL_BASE_DIR}` is the base directory of this skill
(provided at the top of the skill prompt).

The script:
- Reads the MCP tool JSON output (handles the nested wrapper format)
- Optionally reads enrichments JSON for AI-synthesized content
- Generates a standalone HTML file with:
  - Executive Summary section (if enrichments provided)
  - Key Business Objectives section (if enrichments provided)
  - Key Stakeholders cards (if enrichments provided)
  - Key Capabilities section (if enrichments provided)
  - Per-outcome Business Value & Capabilities (if enrichments provided)
  - Sidebar navigation with Outcomes/Scenarios tabs
  - Clickable stakeholder cards linking to persona sections
  - Search/filter across outcomes and scenarios
  - Light/dark theme toggle + font size toggle
  - Collapsible scenario accordions (grouped under parent)
  - Workflow steps with numbered indicators
  - Action items with descriptions
  - Source document citations
  - Responsive design (mobile-friendly)
  - Stats dashboard (personas, outcomes, scenarios, steps, actions)
- No build step, no dependencies — single HTML file

4. Print: "Written to functional-spec.html — open in any browser."

---

## Feedback & Customization

After generating a document, the user may want to review and improve it.
The enrichments architecture makes this a simple edit-regenerate loop.

### How it works

The AI-synthesized content lives in `enrichments.json`, separate from
the graph data. The scripts (`generate-html.py`, `generate-markdown.py`)
are pure renderers — they just combine graph + enrichments into output.

So to improve the document:
1. User gives feedback in natural language
2. You update `enrichments.json` (targeted edit, not full regeneration)
3. Re-run the script → updated document in seconds

### Handling feedback

When the user gives feedback after document generation:

1. **Check if `enrichments.json` exists** in the project root.
   If yes, read it — you'll edit it, not regenerate from scratch.

2. **Map feedback to enrichment fields:**

   | User says | Edit in enrichments.json |
   |-----------|--------------------------|
   | "executive summary is too generic" | Update `executiveSummary` |
   | "wrong persona description" | Update `personaEnrichments.<name>.description` |
   | "mermaid for X is wrong" | Update `outcomeEnrichments.<id>.mermaidDiagram` |
   | "add business rules for Y" | Append to `outcomeEnrichments.<id>.businessRules` |
   | "stakeholder interest is inaccurate" | Update `keyStakeholders[].interest` |
   | "add a capability" | Append to `outcomeEnrichments.<id>.capabilities` |
   | "this outcome description doesn't reflect what it does" | Update `outcomeEnrichments.<id>.businessValue` |

3. **For deeper feedback** (e.g., "the Manage Integrations section
   doesn't capture the full workflow"), use the extraction script
   to get the outcome detail, re-read the scenarios, and update
   the relevant enrichment fields with better synthesis:

   ```bash
   python3 {SKILL_BASE_DIR}/scripts/extract-graph-summary.py <saved-json-file> outcome <outcome-id> /tmp/outcome-detail.json
   ```

   Read the detail, re-synthesize, update enrichments.json.

4. **Re-run the generator script** (same command as initial generation):

   ```bash
   # For HTML
   python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> functional-spec.html --enrichments enrichments.json

   # For Markdown
   python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> functional-spec.md --enrichments enrichments.json
   ```

5. **Tell the user** what was changed and that the document has been
   regenerated.

### Important

- Do NOT re-fetch the graph data unless the user says the graph
  has changed. The saved JSON file from the initial generation is
  sufficient for re-renders.
- Do NOT regenerate the entire enrichments.json for a single piece
  of feedback. Make targeted edits.
- If the user provides very specific text (e.g., "change the executive
  summary to: ..."), use their exact wording.
- If the user asks to "regenerate" or "start fresh", then regenerate
  enrichments from scratch using the extraction + synthesis flow.

---

## Error Handling

- If a persona has no outcomes, include it with a note:
  "No outcomes defined for this persona."
- If an outcome has no scenarios, include it with a note:
  "No scenarios defined for this outcome."
- If API calls fail, report which persona/outcome failed and
  continue with the rest. Do NOT abort the entire document.

---

## Future Extensibility (NOT YET IMPLEMENTED)

This skill currently supports `--type functional` only (the default).
Future versions may support:

- `--type architecture` — Generate from architecture ontology
- `--type code` — Generate from code ontology

Do NOT implement these yet. If the user asks for them, inform them
that only functional document generation is currently supported.
