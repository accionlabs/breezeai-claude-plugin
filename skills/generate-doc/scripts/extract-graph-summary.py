#!/usr/bin/env python3
"""
Extract summaries from the full functional graph JSON for AI enrichment synthesis.

Reads the large MCP tool response (~1MB) and produces compact outputs
that Claude Code can consume in conversation context.

Usage:
    # Outline: project overview + persona/outcome/scenario names (~10-15KB)
    # Used by Claude Code to synthesize top-level enrichments
    # (executive summary, objectives, stakeholders, capabilities, persona descriptions)
    python3 extract-graph-summary.py <graph-json> outline <output-file>

    # Outcome detail: full step/action detail for a single outcome (~2-10KB each)
    # Used by Claude Code to synthesize per-outcome enrichments
    # (business value, capabilities, responsibilities, states, business rules, mermaid)
    python3 extract-graph-summary.py <graph-json> outcome <outcome-id> <output-file>

    # Batch: all outcome details as separate JSON objects in one file
    # Each outcome on its own line (JSONL format) for chunked reading
    python3 extract-graph-summary.py <graph-json> batch <output-dir>

Input:  Saved MCP tool response JSON (nested wrapper format)
Output: Compact JSON suitable for AI synthesis
"""

import json
import os
import sys


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
    raw = node.get("citations", [])
    # Handle citations stored as a JSON string
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


# ---------------------------------------------------------------------------
# Outline mode: compact overview for top-level enrichment synthesis
# ---------------------------------------------------------------------------

def build_outline(personas, project_name):
    """Build a compact outline with persona/outcome/scenario names only."""
    outline = {
        "projectName": project_name,
        "personas": [],
    }

    totals = {"outcomes": 0, "scenarios": 0, "steps": 0, "actions": 0}

    for p in personas:
        persona_name = p.get("persona", "Unknown")
        outcomes = p.get("outcomes", [])
        persona_entry = {
            "persona": persona_name,
            "outcomes": [],
        }

        for o in outcomes:
            scenarios = o.get("scenarios", [])
            step_count = sum(len(s.get("steps", [])) for s in scenarios)
            action_count = sum(
                len(st.get("actions", []))
                for s in scenarios
                for st in s.get("steps", [])
            )

            persona_entry["outcomes"].append({
                "id": o.get("id", ""),
                "outcome": o.get("outcome", ""),
                "citations": get_citations(o),
                "scenarios": [
                    {
                        "scenario": s.get("scenario", ""),
                        "stepCount": len(s.get("steps", [])),
                        "stepNames": [st.get("step", "") for st in s.get("steps", [])],
                    }
                    for s in scenarios
                ],
                "stats": {
                    "scenarios": len(scenarios),
                    "steps": step_count,
                    "actions": action_count,
                },
            })

            totals["outcomes"] += 1
            totals["scenarios"] += len(scenarios)
            totals["steps"] += step_count
            totals["actions"] += action_count

        outline["personas"].append(persona_entry)

    outline["totals"] = totals
    return outline


# ---------------------------------------------------------------------------
# Outcome detail mode: full detail for per-outcome enrichment synthesis
# ---------------------------------------------------------------------------

def build_outcome_detail(outcome, persona_name):
    """Build full detail for a single outcome including all steps and actions."""
    scenarios = outcome.get("scenarios", [])

    detail = {
        "id": outcome.get("id", ""),
        "outcome": outcome.get("outcome", ""),
        "description": outcome.get("description", ""),
        "persona": persona_name,
        "citations": get_citations(outcome),
        "scenarios": [],
    }

    for s in scenarios:
        scenario_detail = {
            "scenario": s.get("scenario", ""),
            "description": s.get("description", ""),
            "steps": [],
        }

        for st in s.get("steps", []):
            step_detail = {
                "step": st.get("step", ""),
                "description": st.get("description", ""),
                "actions": [
                    {
                        "action": a.get("action", ""),
                        "description": a.get("description", ""),
                    }
                    for a in st.get("actions", [])
                ],
            }
            scenario_detail["steps"].append(step_detail)

        detail["scenarios"].append(scenario_detail)

    return detail


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 4:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    graph_file = sys.argv[1]
    mode = sys.argv[2]

    with open(graph_file, "r") as f:
        raw = json.load(f)

    data = extract_graph(raw)
    personas = data.get("personas", [])
    project_name = data.get("project", {}).get("name", "Unknown Project")

    # Build flat index of all outcomes
    outcome_index = {}
    for p in personas:
        for o in p.get("outcomes", []):
            outcome_index[o.get("id", "")] = (o, p.get("persona", "Unknown"))

    if mode == "outline":
        output_file = sys.argv[3]
        outline = build_outline(personas, project_name)
        with open(output_file, "w") as f:
            json.dump(outline, f, indent=2)
        size_kb = os.path.getsize(output_file) / 1024
        t = outline["totals"]
        print(f"Written to {output_file}")
        print(f"  {len(personas)} personas, {t['outcomes']} outcomes, "
              f"{t['scenarios']} scenarios, {t['steps']} steps, {t['actions']} actions")
        print(f"  Size: {size_kb:.1f} KB")

    elif mode == "outcome":
        if len(sys.argv) < 5:
            print("Usage: ... outcome <outcome-id> <output-file>", file=sys.stderr)
            sys.exit(1)
        outcome_id = sys.argv[3]
        output_file = sys.argv[4]
        if outcome_id not in outcome_index:
            print(f"Outcome '{outcome_id}' not found", file=sys.stderr)
            sys.exit(1)
        outcome, persona_name = outcome_index[outcome_id]
        detail = build_outcome_detail(outcome, persona_name)
        with open(output_file, "w") as f:
            json.dump(detail, f, indent=2)
        size_kb = os.path.getsize(output_file) / 1024
        print(f"Written to {output_file} ({size_kb:.1f} KB)")
        print(f"  {detail['outcome']} ({persona_name})")
        print(f"  {len(detail['scenarios'])} scenarios")

    elif mode == "batch":
        output_dir = sys.argv[3]
        os.makedirs(output_dir, exist_ok=True)

        manifest = []
        for p in personas:
            persona_name = p.get("persona", "Unknown")
            for o in p.get("outcomes", []):
                outcome_id = o.get("id", "")
                detail = build_outcome_detail(o, persona_name)
                filename = f"{outcome_id}.json"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w") as f:
                    json.dump(detail, f, indent=2)
                size_kb = os.path.getsize(filepath) / 1024
                manifest.append({
                    "id": outcome_id,
                    "outcome": o.get("outcome", ""),
                    "persona": persona_name,
                    "file": filename,
                    "sizeKB": round(size_kb, 1),
                })

        # Write manifest
        manifest_path = os.path.join(output_dir, "_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        total_size = sum(m["sizeKB"] for m in manifest)
        print(f"Written {len(manifest)} outcome files to {output_dir}/")
        print(f"  Total size: {total_size:.1f} KB")
        print(f"  Manifest: {manifest_path}")

    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        print("Modes: outline, outcome, batch", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
