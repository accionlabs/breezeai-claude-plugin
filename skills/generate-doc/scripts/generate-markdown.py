#!/usr/bin/env python3
"""
Generate a functional specification Markdown document from the graph JSON.

Usage:
    # Plain mode (no enrichments)
    python3 generate-markdown.py <graph-json-file> <output.md>

    # Full mode with AI enrichments
    python3 generate-markdown.py <graph-json-file> <output.md> --enrichments enrichments.json

    # Custom template
    python3 generate-markdown.py <graph-json-file> <output.md> --template my-template.md.j2

Input:  Saved MCP tool response JSON (nested wrapper format)
        Optional: enrichments.json for AI-synthesized content
        Optional: custom Jinja2 template file
Output: Markdown functional specification document
"""

import json
import sys
import os

# Try to import the template engine (requires Jinja2)
try:
    from template_engine import load_graph, build_context, render_template, count_totals
    HAS_TEMPLATE_ENGINE = True
except ImportError:
    HAS_TEMPLATE_ENGINE = False

# ---------------------------------------------------------------------------
# Fallback functions (used when Jinja2 is not installed)
# ---------------------------------------------------------------------------

from datetime import datetime


def _extract_graph(raw):
    """Unwrap nested MCP tool response layers."""
    if isinstance(raw, list) and len(raw) > 0:
        inner = raw[0]
        if isinstance(inner, dict) and "text" in inner:
            parsed = json.loads(inner["text"])
            if isinstance(parsed, list) and len(parsed) > 0:
                inner2 = parsed[0]
                if isinstance(inner2, dict) and "text" in inner2:
                    parsed2 = json.loads(inner2["text"])
                    if isinstance(parsed2, list) and len(parsed2) > 0:
                        return parsed2[0].get("data", parsed2[0])
                    return parsed2
                return parsed
        return raw
    return raw


def _get_citations(node):
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


def _slugify(text):
    return text.lower().replace(" ", "-").replace("/", "-")


def _escape_pipe(text):
    return text.replace("|", "\\|")


def _sort_by_order(items):
    return sorted(items, key=lambda x: (x.get("order") is None, x.get("order", 0)))


def _generate_plain(personas, project_name):
    """Generate plain mode markdown (tabular, no enrichments)."""
    generated = datetime.now().strftime("%B %d, %Y")
    lines = []

    lines.append(f"# Functional Specification: {project_name}")
    lines.append("")
    lines.append(f"**Generated:** {generated}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])
        lines.append(f"### {persona_name} ({len(outcomes)} outcomes)")
        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            lines.append(f"- [{outcome_name}](#{_slugify(persona_name + '-' + outcome_name)})")
        lines.append("")

    lines.append("---")
    lines.append("")

    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])

        lines.append(f"## {persona_name}")
        lines.append("")

        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            citations = _get_citations(o)
            scenarios = o.get("scenarios", [])

            anchor = _slugify(persona_name + "-" + outcome_name)
            lines.append(f'### {outcome_name} {{#{anchor}}}')
            lines.append("")

            if citations:
                sources = ", ".join(f"`{c}`" for c in citations)
                lines.append(f"> **Sources:** {sources}")
                lines.append("")

            lines.append("| # | Scenario | Step | Actions | Source |")
            lines.append("|---|----------|------|---------|--------|")

            if not scenarios:
                lines.append("| | *(No scenarios defined)* | | | |")
            else:
                for si, scenario in enumerate(scenarios):
                    scenario_name = _escape_pipe(scenario.get("scenario", "Scenario"))
                    steps = scenario.get("steps", [])
                    first_scenario_row = True

                    if not steps:
                        lines.append(f"| {si + 1} | {scenario_name} | *(No steps defined)* | | |")
                        continue

                    for sti, step in enumerate(_sort_by_order(steps)):
                        step_name = _escape_pipe(step.get("step", "Step"))
                        actions = _sort_by_order(step.get("actions", []))
                        step_citations = _get_citations(step)
                        first_step_row = True

                        if not actions:
                            snum = str(si + 1) if first_scenario_row else ""
                            sname = scenario_name if first_scenario_row else ""
                            source = f"`{step_citations[0]}`" if step_citations else ""
                            lines.append(f"| {snum} | {sname} | {step_name} | *(No actions defined)* | {source} |")
                            first_scenario_row = False
                            continue

                        for action in actions:
                            action_name = _escape_pipe(action.get("action", ""))
                            action_citations = _get_citations(action)

                            snum = str(si + 1) if first_scenario_row else ""
                            sname = scenario_name if first_scenario_row else ""
                            stname = step_name if first_step_row else ""

                            source = ""
                            if action_citations:
                                source = f"`{action_citations[0]}`"
                            elif step_citations:
                                source = f"`{step_citations[0]}`"
                            elif citations:
                                source = f"`{citations[0]}`"

                            lines.append(f"| {snum} | {sname} | {stname} | {action_name} | {source} |")
                            first_scenario_row = False
                            first_step_row = False

            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def _generate_full(personas, project_name, enrichments):
    """Generate full mode markdown with AI-synthesized enrichments."""
    generated = datetime.now().strftime("%B %d, %Y")
    lines = []

    lines.append(f"# Functional Specification: {project_name}")
    lines.append("")
    lines.append(f"**Version:** 1.0 | **Generated:** {generated}")
    lines.append("")
    lines.append("---")
    lines.append("")

    exec_summary = enrichments.get("executiveSummary", "")
    if exec_summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(exec_summary)
        lines.append("")

    objectives = enrichments.get("keyBusinessObjectives", [])
    if objectives:
        lines.append("## Key Business Objectives")
        lines.append("")
        for i, obj in enumerate(objectives):
            lines.append(f"{i + 1}. {obj}")
        lines.append("")

    stakeholders = enrichments.get("keyStakeholders", [])
    if stakeholders:
        lines.append("## Key Stakeholders")
        lines.append("")
        lines.append("| Role | Interest |")
        lines.append("|------|----------|")
        for s in stakeholders:
            role = _escape_pipe(s.get("role", ""))
            interest = _escape_pipe(s.get("interest", ""))
            lines.append(f"| {role} | {interest} |")
        lines.append("")

    capabilities = enrichments.get("keyCapabilities", [])
    if capabilities:
        lines.append("## Key Capabilities")
        lines.append("")
        for cap in capabilities:
            lines.append(f"- {cap}")
        lines.append("")

    lines.append("---")
    lines.append("")

    lines.append("## Table of Contents")
    lines.append("")
    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])
        lines.append(f"### {persona_name} ({len(outcomes)} outcomes)")
        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            lines.append(f"- [{outcome_name}](#{_slugify(persona_name + '-' + outcome_name)})")
        lines.append("")

    lines.append("---")
    lines.append("")

    persona_enrichments = enrichments.get("personaEnrichments", {})
    outcome_enrichments = enrichments.get("outcomeEnrichments", {})

    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])

        lines.append(f"## {persona_name}")
        lines.append("")

        pe = persona_enrichments.get(persona_name, {})
        pdesc = pe.get("description", "")
        if pdesc:
            lines.append(f"> {pdesc}")
            lines.append("")

        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            outcome_id = o.get("id", "")
            citations = _get_citations(o)
            scenarios = o.get("scenarios", [])

            anchor = _slugify(persona_name + "-" + outcome_name)
            lines.append(f'### {outcome_name} {{#{anchor}}}')
            lines.append("")

            oe = outcome_enrichments.get(outcome_id, {})
            bv = oe.get("businessValue", "")
            if bv:
                lines.append(f"> **Business Value:** {bv}")
                if citations:
                    sources = ", ".join(f"`{c}`" for c in citations)
                    lines.append(f">")
                    lines.append(f"> **Sources:** {sources}")
                lines.append("")
            elif citations:
                sources = ", ".join(f"`{c}`" for c in citations)
                lines.append(f"> **Sources:** {sources}")
                lines.append("")

            caps = oe.get("capabilities", [])
            if caps:
                lines.append(f"<details><summary>Capabilities ({len(caps)})</summary>")
                lines.append("")
                lines.append("| Capability | Description |")
                lines.append("|------------|-------------|")
                for c in caps:
                    cname = _escape_pipe(c.get("capabilityName", ""))
                    cdesc = _escape_pipe(c.get("description", ""))
                    lines.append(f"| {cname} | {cdesc} |")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            rules = oe.get("businessRules", [])
            if rules:
                lines.append(f"<details><summary>Business Rules ({len(rules)})</summary>")
                lines.append("")
                lines.append("| Rule | Description |")
                lines.append("|------|-------------|")
                for r in rules:
                    rid = _escape_pipe(r.get("ruleId", ""))
                    rdesc = _escape_pipe(r.get("description", ""))
                    lines.append(f"| {rid} | {rdesc} |")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            diagram = oe.get("mermaidDiagram", "")
            if diagram:
                lines.append("```mermaid")
                lines.append(diagram)
                lines.append("```")
                lines.append("")

            lines.append("#### Workflow")
            lines.append("")

            if not scenarios:
                lines.append("*(No scenarios defined)*")
                lines.append("")
            else:
                for si, scenario in enumerate(scenarios):
                    scenario_name = scenario.get("scenario", "Scenario")
                    scenario_desc = scenario.get("description", "")
                    steps = scenario.get("steps", [])

                    lines.append(f"##### Scenario: {scenario_name}")
                    lines.append("")

                    if scenario_desc:
                        lines.append(f"> {scenario_desc}")
                        lines.append("")

                    lines.append("| # | Step | Actions | Source |")
                    lines.append("|---|------|---------|--------|")

                    if not steps:
                        lines.append("| | *(No steps defined)* | | |")
                    else:
                        for sti, step in enumerate(_sort_by_order(steps)):
                            step_name = _escape_pipe(step.get("step", "Step"))
                            actions = _sort_by_order(step.get("actions", []))
                            step_citations = _get_citations(step)
                            first_step_row = True

                            if not actions:
                                source = f"`{step_citations[0]}`" if step_citations else ""
                                lines.append(f"| {sti + 1} | {step_name} | *(No actions defined)* | {source} |")
                                continue

                            for action in actions:
                                action_name = _escape_pipe(action.get("action", ""))
                                action_citations = _get_citations(action)

                                stnum = str(sti + 1) if first_step_row else ""
                                stname = step_name if first_step_row else ""

                                source = ""
                                if action_citations:
                                    source = f"`{action_citations[0]}`"
                                elif step_citations:
                                    source = f"`{step_citations[0]}`"
                                elif citations:
                                    source = f"`{citations[0]}`"

                                lines.append(f"| {stnum} | {stname} | {action_name} | {source} |")
                                first_step_row = False

                    lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    graph_file = args[0]
    output_file = args[1]

    # Parse optional flags
    enrichments = None
    custom_template = None
    i = 2
    while i < len(args):
        if args[i] == "--enrichments" and i + 1 < len(args):
            with open(args[i + 1], "r") as f:
                enrichments = json.load(f)
            i += 2
        elif args[i] == "--template" and i + 1 < len(args):
            custom_template = args[i + 1]
            i += 2
        else:
            i += 1

    # Template-based rendering (preferred)
    if HAS_TEMPLATE_ENGINE and (custom_template is not None or True):
        graph_data = load_graph(graph_file)
        context = build_context(graph_data, enrichments)
        totals = context["totals"]

        if custom_template:
            template_name = custom_template
        elif enrichments:
            template_name = "full.md.j2"
        else:
            template_name = "plain.md.j2"

        md = render_template(template_name, context)
        mode_label = f"template: {template_name}"
        if enrichments and not custom_template:
            mode_label = "with AI enrichments"
        elif not custom_template:
            mode_label = "plain"

        with open(output_file, "w") as f:
            f.write(md)

        print(f"Written to {output_file} ({mode_label})")
        print(f"  {totals['personas']} personas, {totals['outcomes']} outcomes, "
              f"{totals['scenarios']} scenarios, {totals['steps']} steps, {totals['actions']} actions")
        return

    # Fallback: direct Python rendering (no Jinja2 needed)
    with open(graph_file, "r") as f:
        raw = json.load(f)

    data = _extract_graph(raw)
    personas = data.get("personas", [])
    project_name = data.get("project", {}).get("name", "Unknown Project")

    if enrichments:
        md = _generate_full(personas, project_name, enrichments)
        mode_label = "with AI enrichments"
    else:
        md = _generate_plain(personas, project_name)
        mode_label = "plain"

    with open(output_file, "w") as f:
        f.write(md)

    total_outcomes = 0
    total_scenarios = 0
    total_steps = 0
    total_actions = 0
    for p in personas:
        for o in p.get("outcomes", []):
            total_outcomes += 1
            for s in o.get("scenarios", []):
                total_scenarios += 1
                for st in s.get("steps", []):
                    total_steps += 1
                    total_actions += len(st.get("actions", []))

    print(f"Written to {output_file} ({mode_label})")
    print(f"  {len(personas)} personas, {total_outcomes} outcomes, "
          f"{total_scenarios} scenarios, {total_steps} steps, {total_actions} actions")


if __name__ == "__main__":
    main()
