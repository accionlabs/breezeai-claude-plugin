#!/usr/bin/env python3
"""
Generate a Functional Requirements Document (FRD) in Markdown from the graph JSON.

Usage:
    # Plain FRD (no enrichments)
    python3 generate-markdown.py <graph-json-file> <output.md>

    # Full FRD with AI enrichments
    python3 generate-markdown.py <graph-json-file> <output.md> --enrichments enrichments.json

    # Custom template
    python3 generate-markdown.py <graph-json-file> <output.md> --template my-template.md.j2

Input:  Saved MCP tool response JSON (nested wrapper format)
        Optional: enrichments.json for AI-synthesized content
        Optional: custom Jinja2 template file
Output: Markdown functional requirements document
"""

import json
import sys

from template_engine import load_graph, build_context, render_template


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

    graph_data = load_graph(graph_file)
    context = build_context(graph_data, enrichments)
    totals = context["totals"]

    if custom_template:
        template_name = custom_template
        mode_label = f"template: {template_name}"
    elif enrichments:
        template_name = "frd-full.md.j2"
        mode_label = "FRD with AI enrichments"
    else:
        template_name = "frd-plain.md.j2"
        mode_label = "FRD plain"

    md = render_template(template_name, context)

    with open(output_file, "w") as f:
        f.write(md)

    print(f"Written to {output_file} ({mode_label})")
    print(f"  {totals['personas']} personas, {totals['outcomes']} outcomes, "
          f"{totals['scenarios']} scenarios, {totals['steps']} steps, {totals['actions']} actions")


if __name__ == "__main__":
    main()
