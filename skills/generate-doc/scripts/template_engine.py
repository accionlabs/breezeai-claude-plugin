#!/usr/bin/env python3
"""
Shared template engine for generating functional specification documents.

Provides:
- Graph data extraction from MCP tool response JSON
- Jinja2 template rendering with custom filters
- Data preprocessing (flatten table rows, sort by order)
- Common utilities (citations, sorting, escaping)
"""

import json
import os
import sys
import html as html_mod
from datetime import datetime
from urllib.parse import quote as url_encode

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print(
        "Jinja2 is required for template rendering.\n"
        "Install it with: pip install jinja2",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Graph extraction
# ---------------------------------------------------------------------------

def extract_graph(raw):
    """Unwrap nested MCP tool response layers to get graph data."""
    data = raw
    # Layer 1: [{type, text}]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "type" in data[0]:
        data = json.loads(data[0]["text"])
    # Layer 2: [{type, text}] again
    if isinstance(data, list) and data and isinstance(data[0], dict) and "type" in data[0]:
        data = json.loads(data[0]["text"])
    # Layer 3: [{success, data}]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "data" in data[0]:
        data = data[0]["data"]
    # Direct format: {personas, project, summary}
    if isinstance(data, dict) and "personas" in data:
        return data
    # Fallback for deeper nesting
    if isinstance(data, list) and data and isinstance(data[0], dict):
        inner = data[0]
        if "text" in inner:
            parsed = json.loads(inner["text"])
            if isinstance(parsed, list) and parsed:
                inner2 = parsed[0]
                if isinstance(inner2, dict) and "text" in inner2:
                    parsed2 = json.loads(inner2["text"])
                    if isinstance(parsed2, list) and parsed2:
                        return parsed2[0].get("data", parsed2[0])
                    return parsed2
                return parsed
        return data
    return data


def load_graph(path):
    """Load and extract graph data from a JSON file."""
    with open(path, "r") as f:
        raw = json.load(f)
    return extract_graph(raw)


# ---------------------------------------------------------------------------
# Utility / filter functions
# ---------------------------------------------------------------------------

def get_citations(node):
    """Extract citation document names from a node."""
    raw = node.get("citations", [])
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    citations = []
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict):
                doc_name = c.get("documentName", c.get("name", ""))
            elif isinstance(c, str) and len(c) > 1:
                doc_name = c
            else:
                continue
            if doc_name and doc_name not in citations:
                citations.append(doc_name)
    return citations


def sort_by_order(items):
    """Sort items by their 'order' attribute; items without order go last."""
    if not items:
        return items
    return sorted(items, key=lambda x: (x.get("order") is None, x.get("order", 0)))


def slugify(text):
    """Create a markdown-safe anchor from text."""
    return text.lower().replace(" ", "-").replace("/", "-")


def escape_pipe(text):
    """Escape pipe characters for markdown tables."""
    if not text:
        return ""
    return str(text).replace("|", "\\|")


def html_escape(text):
    """HTML-escape a string."""
    return html_mod.escape(str(text)) if text else ""


def count_totals(personas):
    """Count total outcomes, scenarios, steps, actions across all personas."""
    outcomes = scenarios = steps = actions = 0
    for p in personas:
        for o in p.get("outcomes", []):
            outcomes += 1
            for s in o.get("scenarios", []):
                scenarios += 1
                for st in s.get("steps", []):
                    steps += 1
                    actions += len(st.get("actions", []))
    return {
        "personas": len(personas),
        "outcomes": outcomes,
        "scenarios": scenarios,
        "steps": steps,
        "actions": actions,
    }


# ---------------------------------------------------------------------------
# Data preprocessing — flatten hierarchy into template-friendly structures
# ---------------------------------------------------------------------------

def build_plain_table_rows(scenarios, outcome_citations):
    """Flatten scenarios/steps/actions into a list of table row dicts.

    Each row has:
      scenario_num, scenario_name, step_name, action_name, source
    Empty string means "don't show" (merged cell in the table).
    """
    rows = []
    if not scenarios:
        rows.append({
            "scenario_num": "",
            "scenario_name": "*(No scenarios defined)*",
            "step_name": "",
            "action_name": "",
            "source": "",
        })
        return rows

    for si, scenario in enumerate(scenarios):
        scenario_name = escape_pipe(scenario.get("scenario", "Scenario"))
        steps = sort_by_order(scenario.get("steps", []))
        first_scenario_row = True

        if not steps:
            rows.append({
                "scenario_num": str(si + 1),
                "scenario_name": scenario_name,
                "step_name": "*(No steps defined)*",
                "action_name": "",
                "source": "",
            })
            continue

        for sti, step in enumerate(steps):
            step_name = escape_pipe(step.get("step", "Step"))
            actions = sort_by_order(step.get("actions", []))
            step_citations = get_citations(step)
            first_step_row = True

            if not actions:
                source = ""
                if step_citations:
                    source = f"`{step_citations[0]}`"
                rows.append({
                    "scenario_num": str(si + 1) if first_scenario_row else "",
                    "scenario_name": scenario_name if first_scenario_row else "",
                    "step_name": step_name,
                    "action_name": "*(No actions defined)*",
                    "source": source,
                })
                first_scenario_row = False
                continue

            for action in actions:
                action_name = escape_pipe(action.get("action", ""))
                action_citations = get_citations(action)

                source = ""
                if action_citations:
                    source = f"`{action_citations[0]}`"
                elif step_citations:
                    source = f"`{step_citations[0]}`"
                elif outcome_citations:
                    source = f"`{outcome_citations[0]}`"

                rows.append({
                    "scenario_num": str(si + 1) if first_scenario_row else "",
                    "scenario_name": scenario_name if first_scenario_row else "",
                    "step_name": step_name if first_step_row else "",
                    "action_name": action_name,
                    "source": source,
                })
                first_scenario_row = False
                first_step_row = False

    return rows


def build_full_table_rows(steps, outcome_citations):
    """Flatten steps/actions into rows for the full-mode per-scenario table.

    Each row has:
      step_num, step_name, action_name, source
    """
    rows = []
    sorted_steps = sort_by_order(steps)

    if not sorted_steps:
        rows.append({
            "step_num": "",
            "step_name": "*(No steps defined)*",
            "action_name": "",
            "source": "",
        })
        return rows

    for sti, step in enumerate(sorted_steps):
        step_name = escape_pipe(step.get("step", "Step"))
        actions = sort_by_order(step.get("actions", []))
        step_citations = get_citations(step)
        first_step_row = True

        if not actions:
            source = ""
            if step_citations:
                source = f"`{step_citations[0]}`"
            rows.append({
                "step_num": str(sti + 1),
                "step_name": step_name,
                "action_name": "*(No actions defined)*",
                "source": source,
            })
            continue

        for action in actions:
            action_name = escape_pipe(action.get("action", ""))
            action_citations = get_citations(action)

            source = ""
            if action_citations:
                source = f"`{action_citations[0]}`"
            elif step_citations:
                source = f"`{step_citations[0]}`"
            elif outcome_citations:
                source = f"`{outcome_citations[0]}`"

            rows.append({
                "step_num": str(sti + 1) if first_step_row else "",
                "step_name": step_name if first_step_row else "",
                "action_name": action_name,
                "source": source,
            })
            first_step_row = False

    return rows


def aggregate_outcome_citations(outcome):
    """Collect all unique citation document names from an outcome and all its children."""
    docs = []
    seen = set()

    def _add(names):
        for n in names:
            if n and n not in seen:
                seen.add(n)
                docs.append(n)

    _add(get_citations(outcome))
    for s in outcome.get("scenarios", []):
        _add(get_citations(s))
        for st in s.get("steps", []):
            _add(get_citations(st))
            for a in st.get("actions", []):
                _add(get_citations(a))
    return docs


def preprocess_personas(personas, enrichments=None):
    """Preprocess personas with flattened table rows and enrichment data.

    Returns a list of persona dicts augmented with:
    - outcomes[]._citations: aggregated citations (outcome + all children)
    - outcomes[]._plain_rows: flattened rows for plain mode
    - outcomes[]._scenarios[]._table_rows: flattened rows for full mode
    - outcomes[]._enrichment: per-outcome enrichment data
    - persona.enrichment: persona enrichment data
    """
    enrichments = enrichments or {}
    outcome_enrichments = enrichments.get("outcomeEnrichments", {})
    persona_enrichments = enrichments.get("personaEnrichments", {})
    result = []

    for pi, p in enumerate(personas):
        persona_name = p.get("persona", "Unknown")
        persona_data = dict(p)
        persona_data["_index"] = pi
        persona_data["enrichment"] = persona_enrichments.get(persona_name, {})

        processed_outcomes = []
        for oi, o in enumerate(p.get("outcomes", [])):
            outcome_data = dict(o)
            outcome_data["_index"] = oi
            citations = aggregate_outcome_citations(o)
            outcome_data["_citations"] = citations
            scenarios = o.get("scenarios", [])

            # Plain mode: flat table rows across all scenarios
            outcome_data["_plain_rows"] = build_plain_table_rows(scenarios, citations)

            # Full mode: per-scenario flat table rows
            processed_scenarios = []
            for si, s in enumerate(scenarios):
                scenario_data = dict(s)
                scenario_data["_index"] = si
                steps = s.get("steps", [])
                scenario_data["_table_rows"] = build_full_table_rows(steps, citations)

                # Sorted steps with sorted actions (for HTML template)
                sorted_steps = sort_by_order(steps)
                html_steps = []
                for sti, st in enumerate(sorted_steps):
                    step_data = dict(st)
                    step_data["_index"] = sti
                    step_data["_actions"] = sort_by_order(st.get("actions", []))
                    step_data["_citations"] = get_citations(st)
                    html_steps.append(step_data)
                scenario_data["_sorted_steps"] = html_steps
                scenario_data["_step_count"] = len(steps)
                scenario_data["_action_count"] = sum(
                    len(st.get("actions", [])) for st in steps
                )
                processed_scenarios.append(scenario_data)

            outcome_data["_scenarios"] = processed_scenarios

            # Enrichment
            outcome_id = o.get("id", "")
            outcome_data["_enrichment"] = outcome_enrichments.get(outcome_id, {})

            # Counts
            outcome_data["_scenario_count"] = len(scenarios)
            outcome_data["_step_count"] = sum(
                len(s.get("steps", [])) for s in scenarios
            )
            outcome_data["_action_count"] = sum(
                len(st.get("actions", []))
                for s in scenarios
                for st in s.get("steps", [])
            )

            processed_outcomes.append(outcome_data)

        persona_data["_outcomes"] = processed_outcomes
        result.append(persona_data)

    return result


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _build_env(template_dir):
    """Create a Jinja2 environment with custom filters and globals."""
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # Filters
    env.filters["slugify"] = slugify
    env.filters["escape_pipe"] = escape_pipe
    env.filters["get_citations"] = get_citations
    env.filters["sort_by_order"] = sort_by_order
    env.filters["e"] = html_escape
    env.filters["url_encode"] = url_encode

    # Globals (callable from templates)
    env.globals["get_citations"] = get_citations
    env.globals["sort_by_order"] = sort_by_order
    env.globals["count_totals"] = count_totals
    env.globals["html_escape"] = html_escape
    return env


def render_template(template_path, context):
    """Render a Jinja2 template file with the given context.

    template_path can be:
    - A filename inside the built-in templates/ directory (e.g. "plain.md.j2")
    - An absolute or relative path to a custom template file
    """
    builtin_dir = os.path.join(os.path.dirname(__file__), "templates")

    # Check if it's a built-in template name
    builtin_path = os.path.join(builtin_dir, template_path)
    if os.path.isfile(builtin_path):
        env = _build_env(builtin_dir)
        template = env.get_template(template_path)
    elif os.path.isfile(template_path):
        # Custom template — use its parent directory as loader root
        template_dir = os.path.dirname(os.path.abspath(template_path))
        template_name = os.path.basename(template_path)
        env = _build_env(template_dir)
        template = env.get_template(template_name)
    else:
        raise FileNotFoundError(f"Template not found: {template_path}")

    return template.render(**context)


def build_context(graph_data, enrichments=None):
    """Build the standard template context from graph data and enrichments."""
    personas = graph_data.get("personas", [])
    project = graph_data.get("project", {})
    project_name = project.get("name", "Unknown Project")
    generated = datetime.now().strftime("%B %d, %Y")
    totals = count_totals(personas)

    # Preprocess personas with flattened rows and enrichments
    processed_personas = preprocess_personas(personas, enrichments)

    # Collect all unique source documents across the entire graph
    all_docs = []
    seen_docs = set()
    for p in personas:
        for o in p.get("outcomes", []):
            for doc in aggregate_outcome_citations(o):
                if doc and doc not in seen_docs:
                    seen_docs.add(doc)
                    all_docs.append(doc)
    sorted_docs = sorted(all_docs)

    # Build doc_name → number index (1-based)
    doc_index = {name: i + 1 for i, name in enumerate(sorted_docs)}

    SUPERSCRIPT_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

    def cite_refs(node):
        """Return tiny superscript linked references for a node's own citations."""
        cites = get_citations(node)
        if not cites:
            return ""
        nums = sorted(set(doc_index[c] for c in cites if c in doc_index))
        if not nums:
            return ""
        refs = "˙".join(
            f'<a href="#src-{n}" style="text-decoration:none;color:#6366f1;font-size:0.65em;vertical-align:super;">{str(n).translate(SUPERSCRIPT_DIGITS)}</a>'
            for n in nums
        )
        return f" {refs}"

    return {
        "personas": processed_personas,
        "project": project,
        "project_name": project_name,
        "generated": generated,
        "totals": totals,
        "enrichments": enrichments or {},
        "has_enrichments": bool(enrichments),
        "source_documents": sorted_docs,
        "doc_index": doc_index,
        "cite_refs": cite_refs,
    }
