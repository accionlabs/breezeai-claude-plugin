#!/usr/bin/env python3
"""
Generate a functional specification Markdown document from the graph JSON.

Usage:
    # Plain mode (no enrichments)
    python3 generate-markdown.py <graph-json-file> <output.md>

    # Full mode with AI enrichments
    python3 generate-markdown.py <graph-json-file> <output.md> --enrichments enrichments.json

Input:  Saved MCP tool response JSON (nested wrapper format)
        Optional: enrichments.json for AI-synthesized content
Output: Markdown functional specification document
"""

import json
import sys
from datetime import datetime


def extract_graph(raw):
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


def get_citations(node):
    """Extract citation document names from a node."""
    citations = []
    for c in node.get("citations", []):
        if isinstance(c, dict):
            doc_name = c.get("documentName", c.get("name", ""))
        else:
            doc_name = str(c)
        if doc_name and doc_name not in citations:
            citations.append(doc_name)
    return citations


def slugify(text):
    """Create a markdown anchor from text."""
    return text.lower().replace(" ", "-").replace("/", "-")


def escape_pipe(text):
    """Escape pipe characters for markdown tables."""
    return text.replace("|", "\\|")


def generate_plain(personas, project_name):
    """Generate plain mode markdown (tabular, no enrichments)."""
    generated = datetime.now().strftime("%B %d, %Y")
    lines = []

    lines.append(f"# Functional Specification: {project_name}")
    lines.append("")
    lines.append(f"**Generated:** {generated}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])
        lines.append(f"### {persona_name} ({len(outcomes)} outcomes)")
        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            lines.append(f"- [{outcome_name}](#{slugify(persona_name + '-' + outcome_name)})")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Per-persona sections
    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])

        lines.append(f"## {persona_name}")
        lines.append("")

        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            citations = get_citations(o)
            scenarios = o.get("scenarios", [])

            anchor = slugify(persona_name + "-" + outcome_name)
            lines.append(f'### {outcome_name} {{#{anchor}}}')
            lines.append("")

            if citations:
                sources = ", ".join(f"`{c}`" for c in citations)
                lines.append(f"> **Sources:** {sources}")
                lines.append("")

            # Workflow table
            lines.append("| # | Scenario | Step | Actions | Source |")
            lines.append("|---|----------|------|---------|--------|")

            if not scenarios:
                lines.append("| | *(No scenarios defined)* | | | |")
            else:
                for si, scenario in enumerate(scenarios):
                    scenario_name = escape_pipe(scenario.get("scenario", "Scenario"))
                    steps = scenario.get("steps", [])
                    first_scenario_row = True

                    if not steps:
                        snum = str(si + 1) if first_scenario_row else ""
                        sname = scenario_name if first_scenario_row else ""
                        lines.append(f"| {snum} | {sname} | *(No steps defined)* | | |")
                        continue

                    for sti, step in enumerate(steps):
                        step_name = escape_pipe(step.get("step", "Step"))
                        actions = step.get("actions", [])
                        step_citations = get_citations(step)
                        first_step_row = True

                        if not actions:
                            snum = str(si + 1) if first_scenario_row else ""
                            sname = scenario_name if first_scenario_row else ""
                            stname = step_name if first_step_row else ""
                            source = f"`{step_citations[0]}`" if step_citations else ""
                            lines.append(f"| {snum} | {sname} | {stname} | *(No actions defined)* | {source} |")
                            first_scenario_row = False
                            continue

                        for action in actions:
                            action_name = escape_pipe(action.get("action", ""))
                            action_citations = get_citations(action)

                            snum = str(si + 1) if first_scenario_row else ""
                            sname = scenario_name if first_scenario_row else ""
                            stname = step_name if first_step_row else ""

                            # Source: deepest citation wins
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


def generate_full(personas, project_name, enrichments):
    """Generate full mode markdown with AI-synthesized enrichments."""
    generated = datetime.now().strftime("%B %d, %Y")
    lines = []

    lines.append(f"# Functional Specification: {project_name}")
    lines.append("")
    lines.append(f"**Version:** 1.0 | **Generated:** {generated}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    exec_summary = enrichments.get("executiveSummary", "")
    if exec_summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(exec_summary)
        lines.append("")

    # Key Business Objectives
    objectives = enrichments.get("keyBusinessObjectives", [])
    if objectives:
        lines.append("## Key Business Objectives")
        lines.append("")
        for i, obj in enumerate(objectives):
            lines.append(f"{i + 1}. {obj}")
        lines.append("")

    # Key Stakeholders
    stakeholders = enrichments.get("keyStakeholders", [])
    if stakeholders:
        lines.append("## Key Stakeholders")
        lines.append("")
        lines.append("| Role | Interest |")
        lines.append("|------|----------|")
        for s in stakeholders:
            role = escape_pipe(s.get("role", ""))
            interest = escape_pipe(s.get("interest", ""))
            lines.append(f"| {role} | {interest} |")
        lines.append("")

    # Key Capabilities
    capabilities = enrichments.get("keyCapabilities", [])
    if capabilities:
        lines.append("## Key Capabilities")
        lines.append("")
        for cap in capabilities:
            lines.append(f"- {cap}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Table of Contents
    lines.append("## Table of Contents")
    lines.append("")
    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])
        lines.append(f"### {persona_name} ({len(outcomes)} outcomes)")
        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            lines.append(f"- [{outcome_name}](#{slugify(persona_name + '-' + outcome_name)})")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Per-persona sections
    persona_enrichments = enrichments.get("personaEnrichments", {})
    outcome_enrichments = enrichments.get("outcomeEnrichments", {})

    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])

        lines.append(f"## {persona_name}")
        lines.append("")

        # Persona description
        pe = persona_enrichments.get(persona_name, {})
        pdesc = pe.get("description", "")
        if pdesc:
            lines.append(f"> {pdesc}")
            lines.append("")

        for o in outcomes:
            outcome_name = o.get("outcome", "Outcome")
            outcome_id = o.get("id", "")
            citations = get_citations(o)
            scenarios = o.get("scenarios", [])

            anchor = slugify(persona_name + "-" + outcome_name)
            lines.append(f'### {outcome_name} {{#{anchor}}}')
            lines.append("")

            # Business Value + Sources
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

            # Capabilities
            caps = oe.get("capabilities", [])
            if caps:
                lines.append(f"<details><summary>Capabilities ({len(caps)})</summary>")
                lines.append("")
                lines.append("| Capability | Description |")
                lines.append("|------------|-------------|")
                for c in caps:
                    cname = escape_pipe(c.get("capabilityName", ""))
                    cdesc = escape_pipe(c.get("description", ""))
                    lines.append(f"| {cname} | {cdesc} |")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            # Business Rules
            rules = oe.get("businessRules", [])
            if rules:
                lines.append(f"<details><summary>Business Rules ({len(rules)})</summary>")
                lines.append("")
                lines.append("| Rule | Description |")
                lines.append("|------|-------------|")
                for r in rules:
                    rid = escape_pipe(r.get("ruleId", ""))
                    rdesc = escape_pipe(r.get("description", ""))
                    lines.append(f"| {rid} | {rdesc} |")
                lines.append("")
                lines.append("</details>")
                lines.append("")

            # Mermaid diagram
            diagram = oe.get("mermaidDiagram", "")
            if diagram:
                lines.append("```mermaid")
                lines.append(diagram)
                lines.append("```")
                lines.append("")

            # Workflow
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
                        for sti, step in enumerate(steps):
                            step_name = escape_pipe(step.get("step", "Step"))
                            actions = step.get("actions", [])
                            step_citations = get_citations(step)
                            first_step_row = True

                            if not actions:
                                source = f"`{step_citations[0]}`" if step_citations else ""
                                lines.append(f"| {sti + 1} | {step_name} | *(No actions defined)* | {source} |")
                                continue

                            for action in actions:
                                action_name = escape_pipe(action.get("action", ""))
                                action_citations = get_citations(action)

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


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    graph_file = sys.argv[1]
    output_file = sys.argv[2]

    # Parse optional --enrichments flag
    enrichments = None
    if "--enrichments" in sys.argv:
        idx = sys.argv.index("--enrichments")
        if idx + 1 < len(sys.argv):
            with open(sys.argv[idx + 1], "r") as f:
                enrichments = json.load(f)

    with open(graph_file, "r") as f:
        raw = json.load(f)

    data = extract_graph(raw)
    personas = data.get("personas", [])
    project_name = data.get("project", {}).get("name", "Unknown Project")

    if enrichments:
        md = generate_full(personas, project_name, enrichments)
        mode_label = "with AI enrichments"
    else:
        md = generate_plain(personas, project_name)
        mode_label = "plain"

    with open(output_file, "w") as f:
        f.write(md)

    # Count totals
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
