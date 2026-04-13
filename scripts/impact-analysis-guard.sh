#!/bin/bash
# ─────────────────────────────────────────────────────────────────────
# impact-analysis-guard.sh
# UserPromptSubmit hook — spawns a deep analysis agent that searches
# all 3 Breeze graphs, presents findings, asks user if they want a
# detailed doc with diagrams, and generates it if requested.
# ─────────────────────────────────────────────────────────────────────

INPUT=$(cat)

# Extract the user prompt text
PROMPT=$(echo "$INPUT" | grep -o '"prompt"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"prompt"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

# If we can't extract prompt, let it pass through
[ -z "$PROMPT" ] && exit 0

# ── Skip trivial / short prompts ────────────────────────────────────
WORD_COUNT=$(echo "$PROMPT" | wc -w)
if [ "$WORD_COUNT" -lt 4 ]; then
  exit 0
fi

# Skip common non-analytical prompts (greetings, confirmations, slash commands)
LOWER_PROMPT=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')
case "$LOWER_PROMPT" in
  hi|hello|hey|yes|no|ok|okay|thanks|thank*|sure|y|n|quit|exit|help|/*)
    exit 0
    ;;
esac

# Skip action/mutation intents
if echo "$LOWER_PROMPT" | grep -qE "(create|add|update|delete|remove|build|implement|fix|change|modify|generate|write|deploy)"; then
  exit 0
fi

# ── Guard: .breeze.json must exist with apiKey + projectUuid ────────
if [ ! -f ".breeze.json" ]; then
  exit 0
fi

if ! grep -q '"apiKey"' .breeze.json || ! grep -q '"projectUuid"' .breeze.json; then
  exit 0
fi

# ── Pre-compute timestamp and paths ────────────────────────────────
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR=".breeze/analysis-reports"
REPORT_FILE="${REPORT_DIR}/${TIMESTAMP}-analysis.md"

# ── Emit full agent + doc-generation instructions ──────────────────
cat <<INSTRUCTIONS
<breeze-deep-analysis-hook>
BEFORE processing this prompt, you MUST perform a Breeze Deep Analysis in two phases.

═══════════════════════════════════════════════════════════════
PHASE 1 — DEEP ANALYSIS (mandatory)
═══════════════════════════════════════════════════════════════

Spawn an agent using the Agent tool with these parameters:

description: "Breeze Deep Analysis"
prompt: (use the full prompt below)

--- START AGENT PROMPT ---
You are the Breeze Deep Analysis agent. Search the Breeze knowledge graphs to deeply analyse what the user is asking about.

USER PROMPT TO ANALYZE: "${PROMPT}"

STEP 1: Read .breeze.json to get the projectUuid. If missing, return "No Breeze project configured."

STEP 2: Use ToolSearch with query "select:mcp__plugin_breeze_breeze-mcp__Functional_Graph_Search,mcp__plugin_breeze_breeze-mcp__Design_Graph_Search,mcp__plugin_breeze_breeze-mcp__Code_Graph_Search" to load the MCP tool schemas.

STEP 3: Call all three search tools IN PARALLEL with queries derived from the user prompt:
  a) mcp__plugin_breeze_breeze-mcp__Functional_Graph_Search — find personas, outcomes, scenarios, steps, actions
  b) mcp__plugin_breeze_breeze-mcp__Design_Graph_Search — find user journeys, flows, pages, components
  c) mcp__plugin_breeze_breeze-mcp__Code_Graph_Search — find files, classes, methods, modules

STEP 4: Perform deep analysis across all results:
  - What does this mean FUNCTIONALLY? Which personas, outcomes, scenarios, business logic?
  - What does this mean for DESIGN? Which UI journeys, flows, pages, components?
  - What does this mean for CODE? Which files, modules, classes, methods?
  - How are these CONNECTED? Trace functional requirement → design element → code implementation.
  - What are the DEPENDENCIES and RISKS? Upstream/downstream effects, shared components.

STEP 5: Return the analysis in this format:

Breeze Deep Analysis

Query: <user's prompt>

Functional Context:
  - Personas: <list>
  - Scenarios: <list with IDs>
  - Key Actions: <most relevant actions/steps>

Design Context:
  - User Journeys: <related journeys>
  - Flows/Pages: <related flows and pages>
  - Components: <related UI components>

Code Context:
  - Files: <related source files with paths>
  - Modules/Classes: <related modules>
  - Key Methods: <relevant methods/functions>

Cross-Graph Connections:
  <how functional → design → code are linked>

Risk Level: <Low/Medium/High> — <justification>
--- END AGENT PROMPT ---

After the agent returns, display its full analysis summary to the user in the terminal.

Then ASK the user:
"Would you like me to generate a detailed analysis document with diagrams for this? (yes/no)"

WAIT for the user's response. Do NOT generate the document automatically.

═══════════════════════════════════════════════════════════════
PHASE 2 — DOCUMENT GENERATION (only if user says yes)
═══════════════════════════════════════════════════════════════

If the user says yes, generate a comprehensive analysis document. Use the agent's results you already have (do NOT re-search the graphs).

STEP A: Create the directory:
  mkdir -p ${REPORT_DIR}

STEP B: Use the Write tool to write the document to: ${REPORT_FILE}

The document MUST include ALL of the following sections:

# Deep Analysis: <short title derived from prompt>

**Query**: ${PROMPT}
**Generated**: $(date '+%Y-%m-%d %H:%M:%S')

---

## 1. Executive Summary
A 3-5 sentence overview of what this prompt touches across the system.

## 2. Functional Analysis

### 2.1 Personas Involved
Table: | Persona | Role | Relevance |

### 2.2 Outcomes & Scenarios
For each relevant scenario:
- Scenario name + ID
- Steps and actions within it
- How it relates to the user's prompt

### 2.3 Functional Flow Diagram
Generate a Mermaid diagram showing the functional flow:
\`\`\`mermaid
flowchart TD
    A[Persona] --> B[Outcome]
    B --> C[Scenario]
    C --> D[Step 1]
    D --> E[Step 2]
    ... (use actual data from search results)
\`\`\`

## 3. Design Analysis

### 3.1 User Journeys
List each journey with its flows and pages.

### 3.2 Pages & Components
Table: | Page | Components | Purpose |

### 3.3 Design Flow Diagram
Generate a Mermaid diagram showing the UI flow:
\`\`\`mermaid
flowchart LR
    A[User Journey] --> B[Flow 1]
    B --> C[Page 1]
    C --> D[Component A]
    C --> E[Component B]
    ... (use actual data from search results)
\`\`\`

## 4. Code Analysis

### 4.1 Affected Files
Table: | File Path | Type | Purpose |

### 4.2 Classes & Methods
For each relevant file:
- Class/module name
- Key methods
- What they do

### 4.3 Code Dependency Diagram
Generate a Mermaid diagram showing code dependencies:
\`\`\`mermaid
graph TD
    A[Module/File] --> B[Module/File]
    B --> C[Class.method]
    ... (use actual data from search results)
\`\`\`

## 5. Cross-Graph Traceability

### 5.1 Traceability Matrix
Table: | Functional (Scenario) | Design (Page/Component) | Code (File/Method) |

### 5.2 End-to-End Flow Diagram
Generate a Mermaid diagram showing the full trace from functional → design → code:
\`\`\`mermaid
flowchart TD
    subgraph Functional
        F1[Scenario] --> F2[Step/Action]
    end
    subgraph Design
        D1[Flow/Page] --> D2[Component]
    end
    subgraph Code
        C1[File] --> C2[Method]
    end
    F2 --> D1
    D2 --> C1
    ... (use actual data from search results)
\`\`\`

## 6. Risk Assessment
- **Risk Level**: Low/Medium/High
- **Justification**: Why
- **Affected Areas**: List
- **Mitigation**: Suggestions

## 7. Recommendations
Numbered list of actionable recommendations.

---

STEP C: After writing, verify the file exists:
  ls -la ${REPORT_FILE}

STEP D: Tell the user:
  "Analysis document saved to \`${REPORT_FILE}\`"

═══════════════════════════════════════════════════════════════
PHASE 3 — PROCESS ORIGINAL PROMPT (always)
═══════════════════════════════════════════════════════════════

After Phase 1 (and Phase 2 if triggered), proceed to handle the user's original prompt. USE the analysis context:
- Scope your work based on affected areas from the analysis.
- Reference specific scenarios, components, files from the results.
- If risk is High, warn the user before making changes.
- Factor cross-graph dependencies into your decisions.

The agent's results are your ground truth about the system.
</breeze-deep-analysis-hook>
INSTRUCTIONS

exit 0
