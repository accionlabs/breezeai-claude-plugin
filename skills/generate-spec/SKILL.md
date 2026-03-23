---
name: generate-spec
description: >
  Generate a functional specification document from the functional graph.
  Outputs structured Markdown grouped by persona with citations.
  Use when: "generate spec", "generate document", "functional spec",
  "create specification", "export functional graph".
---

## Guard

Read `.breeze.json`. If missing or incomplete, tell the user to run `/breeze:setup-project`.
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
| **Plain Markdown** | `--plain` | Functional Requirements Document with numbered sections (FR-001), scenario IDs (SC-01), nested step/action format. Best for: quick reference, sharing in PRs, formal specs. |
| **Rich Markdown** | `--full` | Everything in plain + AI-synthesized document overview, project context, business objectives, stakeholders, per-outcome business value, NFR section, glossary. Best for: stakeholder reviews, client deliverables, comprehensive documentation. |
| **Plain HTML** | `--html` | Interactive single-file viewer with sidebar navigation, search, collapsible accordions, light/dark theme. Best for: team browsing, client demos, embedding in wikis. |
| **Rich HTML** | `--html --full` | Everything in plain HTML + all AI enrichments rendered visually — stakeholder cards, persona descriptions. Best for: client deliverables, executive presentations, full specification review. |

**Additional options** (append to any command above):
- `--mermaid` — Include mermaid workflow diagrams per outcome (requires `--full`)
- Scope: full project (default), single persona, or single outcome

**Examples:**
- `/breeze:generate-spec --plain` — plain FRD markdown
- `/breeze:generate-spec --full --mermaid` — rich FRD with diagrams
- `/breeze:generate-spec --html --full --mermaid` — rich HTML with diagrams
- `/breeze:generate-spec --full "Financial Institution User"` — single persona

**Export to other formats** (after generating markdown):
- Word: `/breeze:generate-spec --export docx`
- PDF:  `/breeze:generate-spec --export pdf`

**After generation**, you can review and give feedback to improve any section — I'll update and regenerate instantly.

What would you like to generate?
```

Wait for the user to choose before proceeding.

### Export (`--export`)

When `$ARGUMENTS` contains `--export docx` or `--export pdf`:

1. Check if `{project-name}-functional-spec.md` exists in the project root.
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
   python3 {SKILL_BASE_DIR}/scripts/render-mermaid.py {project-name}-functional-spec.md {project-name}-functional-spec-export.md
   ```
   - If mermaid blocks exist and rendering succeeds, use `{project-name}-functional-spec-export.md` for conversion
   - If no mermaid blocks found, use `{project-name}-functional-spec.md` directly
   - If rendering fails (no chromium/mmdc), warn the user and proceed with `{project-name}-functional-spec.md`
     ("Mermaid diagrams will appear as code blocks. Install chromium for rendered diagrams.")

4. Run the conversion:
   ```bash
   # For DOCX
   pandoc <source.md> -o {project-name}-functional-spec.docx --from=gfm

   # For PDF (requires a LaTeX engine)
   pandoc <source.md> -o {project-name}-functional-spec.pdf --from=gfm --pdf-engine=xelatex
   ```

5. Clean up temporary files:
   ```bash
   rm -rf _mermaid_images/ {project-name}-functional-spec-export.md
   ```

6. Print: "Exported to {project-name}-functional-spec.docx" (or .pdf)

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
                  id, step, description, order, actions: [
                    { id, action, description, order }
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

Use this mode when `$ARGUMENTS` does NOT contain `--full`.

Generates a Functional Requirements Document (FRD) with nested structure:

```
# {Project Name}

## Functional Requirements Document

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | {current date} |
| **Source** | Breeze.AI Functional Graph — {N} personas, {N} outcomes, ... |

---

## Table of Contents

1. [Persona Summary](#persona-summary)
2. [FR-001 — {Persona Name}](#fr-001--{persona-slug})
   - 2.1 [{Outcome Name}](#anchor)

---

## 1. Persona Summary

| ID | Persona | Outcomes | Description |
|----|---------|----------|-------------|
| FR-001 | {Persona Name} | {N} | |

---

## 2. FR-001 — {Persona Name}

### 2.1 {Outcome Name}

> **Sources:** `{document1.pdf}`, `{document2.pdf}`

- **SC-01 {Scenario Name}** — {description}
    - **Step 1: {Step Name}**
        - → {Action 1}
        - → {Action 2}
    - **Step 2: {Step Name}**
        - → {Action 1}
- **SC-02 {Scenario 2}**
    - **Step 1: {Step Name}**
        - → {Action 1}

---
```

**Format rules:**
- Personas are numbered as FR-001, FR-002, etc.
- Outcomes are numbered under their persona (2.1, 2.2, etc.)
- Scenarios are prefixed with SC-01, SC-02, etc.
- Steps and actions are nested list items under their scenario
- Steps and actions are sorted by their `order` attribute when present
- Citations appear as Sources at the outcome level

---

### Mode 2 — Full (`--full`)

Use this mode when `$ARGUMENTS` contains `--full`.

Generates the same FRD structure as plain mode, plus AI-synthesized
enrichment sections:

```
## 1. Document Overview

{Executive summary synthesized from all personas, outcomes, scenarios}

| | |
|---|---|
| **Personas** | {N} |
| **Outcomes** | {N} |
...

## 2. Project Context

### Key Business Objectives
1. {Objective}

### Key Stakeholders
| Role | Interest |
|------|----------|
| {Persona name} | {What they care about} |

### Key Capabilities
- {Capability}
```

The persona summary table includes descriptions, and per-outcome
sections include business value text.

**Full mode rules:**
- Executive Summary, Business Objectives, Key Capabilities, and
  Key Stakeholders are **synthesized by you** from the graph data.
  Do NOT call any extra tools for this — derive from collected data.
- Per-outcome Business Value is **synthesized by you** from that
  outcome's scenarios, steps, and actions.
- Mermaid diagrams are only included when `--mermaid` flag is
  passed. Do NOT generate them otherwise.

---

## File Output

After generating the document:

### Markdown output (default)

Use the project name from the graph data for output filenames.
Lowercase and hyphenate: e.g., "Kinective" → `kinective-functional-spec.md`.

Use the markdown generator script:

```bash
# Plain mode (no enrichments)
python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> {project-name}-functional-spec.md

# Full mode with enrichments
python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> {project-name}-functional-spec.md --enrichments enrichments.json
```

The script generates a Functional Requirements Document (FRD) with:
- Numbered sections per persona (FR-001, FR-002, etc.)
- Numbered outcomes (4.1, 4.2, etc.)
- Scenario IDs (SC-01, SC-02, etc.)
- Nested step/action format with indentation
- Steps and actions sorted by their `order` attribute when present
- Source citations preserved at the outcome level
- Plain mode: scenarios, steps, actions grouped by persona
- Full mode (with `--enrichments`): adds document overview, project
  context, business objectives, stakeholders, persona descriptions,
  per-outcome business value, optional mermaid diagrams, NFR and
  glossary sections

**Custom templates** (requires `pip install jinja2`):

```bash
python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> output.md --template /path/to/custom.md.j2
```

Built-in templates are in `{SKILL_BASE_DIR}/scripts/templates/`:
- `frd-plain.md.j2` — FRD markdown (default, no enrichments)
- `frd-full.md.j2` — FRD with enrichments (overview, context, NFR, glossary)
- `plain.html.j2` — HTML without enrichments
- `full.html.j2` — HTML with enrichments

Templates receive a standard context with `personas` (preprocessed with
`_outcomes`, `_scenarios`, `_sorted_steps`, `_enrichment` etc.),
`project_name`, `generated`, `totals`, `enrichments`, and
`has_enrichments`. See `template_engine.py` for the full context schema
and available Jinja2 filters (`slugify`, `escape_pipe`, `e`, `url_encode`,
`sort_by_order`, `get_citations`).

Print a summary:

```
Written to {project-name}-functional-spec.md

  {N} personas, {N} outcomes, {N} scenarios, {N} steps, {N} actions

To convert to other formats:
  docx:  pandoc {project-name}-functional-spec.md -o {project-name}-functional-spec.docx
  pdf:   pandoc {project-name}-functional-spec.md -o {project-name}-functional-spec.pdf
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
         "mermaidDiagram": "graph TD\n  A[Persona] -->|action| B[Feature]"  // only if --mermaid
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
   - Mermaid Diagram (**only if `--mermaid` flag is present**):
     `graph TD` format. Represent the outcome as a container/subgraph.
     Show high-level flow and dependencies. 5-10 nodes max. Avoid
     UI-level or step-level detail. Skip for straightforward CRUD
     outcomes. Do NOT generate mermaid diagrams unless the user
     explicitly passes `--mermaid`.

3. Run the HTML generator script:

```bash
# Without enrichments (--html only)
python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> {project-name}-functional-spec.html

# With enrichments (--html --full)
python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> {project-name}-functional-spec.html --enrichments enrichments.json

# Custom template (requires pip install jinja2)
python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> output.html --template /path/to/custom.html.j2
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
  - Per-outcome Business Value (if enrichments provided)
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

4. Print: "Written to {project-name}-functional-spec.html — open in any browser."

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
   | "stakeholder interest is inaccurate" | Update `keyStakeholders[].interest` |
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
   python3 {SKILL_BASE_DIR}/scripts/generate-html.py <saved-json-file> {project-name}-functional-spec.html --enrichments enrichments.json

   # For Markdown
   python3 {SKILL_BASE_DIR}/scripts/generate-markdown.py <saved-json-file> {project-name}-functional-spec.md --enrichments enrichments.json
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
