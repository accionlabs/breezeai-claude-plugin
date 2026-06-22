#!/usr/bin/env python3
"""
Validate a functional graph exported from Breeze MCP.

Usage:
    python3 validate-graph.py <graph-json-file> [output-json-file] [--sources <sources-json>]

Input:
    graph-json-file:  The raw JSON file saved by Get_complete_functional_graph MCP tool.
    output-json-file: Where to write the report (default: stdout).
    --sources:        Optional JSON file with source document requirements to
                      check coverage against. Format:
                      {
                        "US-001 CSV Upload": ["upload", "csv", "fund"],
                        "VAL-001 Share Class": ["share class", "divergence", "bps"]
                      }

Output: A JSON report with all validation results.

Exit codes:
    0 = validation complete (may have findings)
    1 = input error (file not found, parse failure)
"""

import json
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime


# --- Word lists: imported from the single source of truth (ADR 0001) ---
# skills/shared/functional/verbs.json. A markdown SSOT would never reach this Python
# file, so it loads the JSON directly. Inline values are a fallback only.
_VERBS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "shared", "functional", "verbs.json")
try:
    with open(_VERBS_PATH, encoding="utf-8") as _vf:
        _VERBS = json.load(_vf)
    FORBIDDEN_UI_WORDS = list(_VERBS["forbidden_ui_words"])
    FORBIDDEN_PERSONA_NAMES = list(_VERBS["forbidden_persona_names"])
    SYSTEM_PERSONAS = set(_VERBS["system_personas"])
    OVERLAP_KEYWORDS = list(_VERBS["overlap_keywords"])
except Exception:
    FORBIDDEN_UI_WORDS = [
        "click", "tap", "swipe", "hover", "scroll", "drag", "drop",
        "toggle", "button", "dropdown", "modal", "dialog", "popup",
        "panel", "checkbox", "radio", "slider", "tooltip", "menu",
        "sidebar", "navbar", "tab", "icon",
    ]
    FORBIDDEN_PERSONA_NAMES = [
        "developer", "engineer", "programmer", "architect",
        "api", "service", "component", "module", "worker",
        "backend", "frontend", "database",
        "controller", "handler", "repository",
    ]
    SYSTEM_PERSONAS = {"system", "external system"}
    OVERLAP_KEYWORDS = [
        "bond", "static data", "price", "fx", "p&l", "expense",
        "pdf", "audit", "exception", "waiv", "tolerance", "upload",
        "report", "dashboard", "validation",
    ]


def parse_graph_file(filepath):
    """Parse the nested MCP tool output format into a clean graph dict."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Unwrap: [{type, text}] -> text -> [{type, text}] -> text -> [{success, data}]
    text = data[0]["text"]
    wrapper = json.loads(text)
    if isinstance(wrapper, list) and len(wrapper) > 0 and "text" in wrapper[0]:
        wrapper = json.loads(wrapper[0]["text"])
    result = wrapper[0] if isinstance(wrapper, list) else wrapper
    return result.get("data", result)


def run_checks(graph, sources=None):
    """Run all validation checks and return structured results."""
    personas = graph.get("personas", [])
    summary = graph.get("summary", {})
    report = {
        "timestamp": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        "summary": {
            "personas": len(personas),
            "outcomes": 0,
            "scenarios": 0,
            "steps": 0,
            "actions": 0,
        },
        "checks": {},
    }

    # --- Flatten hierarchy ---
    all_outcomes = []
    all_scenarios = []
    all_steps = []
    all_actions = []

    for p in personas:
        pname = p.get("persona", "N/A")
        is_system = pname.lower() in SYSTEM_PERSONAS
        for o in p.get("outcomes", []):
            oname = o.get("outcome", "N/A")
            all_outcomes.append({
                "persona": pname,
                "outcome": oname,
                "id": o.get("id"),
                "citations": o.get("citations") or o.get("citationRefs"),
                "description": o.get("description"),
            })
            for s in o.get("scenarios", []):
                sname = s.get("scenario", "N/A")
                steps = s.get("steps", [])
                action_count = sum(len(st.get("actions", [])) for st in steps)
                all_scenarios.append({
                    "persona": pname,
                    "outcome": oname,
                    "scenario": sname,
                    "id": s.get("id"),
                    "description": s.get("description"),
                    "citations": s.get("citations") or s.get("citationRefs"),
                    "step_count": len(steps),
                    "action_count": action_count,
                    "is_system": is_system,
                })
                for st in steps:
                    all_steps.append({
                        "persona": pname,
                        "scenario": sname,
                        "step": st.get("step", "N/A"),
                        "id": st.get("id"),
                        "description": st.get("description"),
                    })
                    for a in st.get("actions", []):
                        all_actions.append({
                            "persona": pname,
                            "scenario": sname,
                            "step": st.get("step", "N/A"),
                            "action": a.get("action", "N/A"),
                            "id": a.get("id"),
                            "description": a.get("description"),
                            "is_system": is_system,
                        })

    report["summary"]["outcomes"] = len(all_outcomes)
    report["summary"]["scenarios"] = len(all_scenarios)
    report["summary"]["steps"] = len(all_steps)
    report["summary"]["actions"] = len(all_actions)

    # === CHECK 1: Empty Nodes ===
    empty_scenarios = [
        {
            "persona": s["persona"],
            "outcome": s["outcome"],
            "scenario": s["scenario"],
        }
        for s in all_scenarios
        if s["step_count"] == 0
    ]
    report["checks"]["empty_nodes"] = {
        "severity": "P0",
        "count": len(empty_scenarios),
        "items": empty_scenarios,
    }

    # === CHECK 2: Duplicate Scenario Names ===
    scenario_names = [s["scenario"] for s in all_scenarios]
    name_counts = Counter(scenario_names)
    duplicate_scenarios = []
    for name, count in name_counts.items():
        if count > 1:
            locations = [
                {"persona": s["persona"], "outcome": s["outcome"]}
                for s in all_scenarios
                if s["scenario"] == name
            ]
            duplicate_scenarios.append({
                "scenario": name,
                "count": count,
                "locations": locations,
            })
    report["checks"]["duplicate_scenarios"] = {
        "severity": "P1",
        "count": len(duplicate_scenarios),
        "items": duplicate_scenarios,
    }

    # === CHECK 3: Duplicate Outcome Names ===
    outcome_by_name = defaultdict(list)
    for o in all_outcomes:
        outcome_by_name[o["outcome"]].append(o["persona"])
    duplicate_outcomes = []
    for name, persona_list in outcome_by_name.items():
        if len(persona_list) > 1:
            same_persona = len(set(persona_list)) < len(persona_list)
            duplicate_outcomes.append({
                "outcome": name,
                "count": len(persona_list),
                "personas": persona_list,
                "severity": "P1" if same_persona else "P2",
                "same_persona_duplicate": same_persona,
            })
    report["checks"]["duplicate_outcomes"] = {
        "count": len(duplicate_outcomes),
        "items": duplicate_outcomes,
    }

    # === CHECK 4: Citation Coverage ===
    total_citable = len(all_outcomes) + len(all_scenarios)
    cited = sum(1 for o in all_outcomes if o["citations"]) + \
            sum(1 for s in all_scenarios if s["citations"])
    uncited = []
    for o in all_outcomes:
        if not o["citations"]:
            uncited.append({
                "type": "outcome",
                "persona": o["persona"],
                "name": o["outcome"],
            })
    for s in all_scenarios:
        if not s["citations"]:
            uncited.append({
                "type": "scenario",
                "persona": s["persona"],
                "name": s["scenario"],
            })
    report["checks"]["citation_coverage"] = {
        "severity": "P1",
        "total_nodes": total_citable,
        "cited": cited,
        "percentage": round(cited / total_citable * 100, 1) if total_citable else 0,
        "uncited_items": uncited[:20],  # cap to avoid huge output
        "uncited_total": len(uncited),
    }

    # === CHECK 5: Description Coverage ===
    scenario_with_desc = sum(1 for s in all_scenarios if s["description"])
    system_actions = [a for a in all_actions if a["is_system"]]
    human_actions = [a for a in all_actions if not a["is_system"]]
    system_with_desc = sum(1 for a in system_actions if a["description"])
    human_with_desc = sum(1 for a in human_actions if a["description"])

    # Sample system actions missing descriptions
    system_missing_samples = [
        {
            "persona": a["persona"],
            "scenario": a["scenario"],
            "action": a["action"],
        }
        for a in system_actions
        if not a["description"]
    ][:15]

    report["checks"]["description_coverage"] = {
        "severity": "P1",
        "scenarios": {
            "total": len(all_scenarios),
            "with_description": scenario_with_desc,
            "percentage": round(scenario_with_desc / len(all_scenarios) * 100, 1) if all_scenarios else 0,
        },
        "system_actions": {
            "total": len(system_actions),
            "with_description": system_with_desc,
            "percentage": round(system_with_desc / len(system_actions) * 100, 1) if system_actions else 0,
            "missing_samples": system_missing_samples,
        },
        "human_actions": {
            "total": len(human_actions),
            "with_description": human_with_desc,
            "note": "Human actions don't require descriptions unless there's a constraint",
        },
    }

    # === CHECK 6: Platform-Agnostic Violations ===
    violations = []
    for a in human_actions:
        action_lower = (a["action"] or "").lower()
        matched_words = [w for w in FORBIDDEN_UI_WORDS if w in action_lower]
        if matched_words:
            violations.append({
                "persona": a["persona"],
                "scenario": a["scenario"],
                "action": a["action"],
                "forbidden_words": matched_words,
            })

    total_human = len(human_actions)
    compliant = total_human - len(violations)
    report["checks"]["platform_agnostic"] = {
        "severity": "P1",
        "total_human_actions": total_human,
        "violations": len(violations),
        "compliance_percentage": round(compliant / total_human * 100, 1) if total_human else 100,
        "items": violations[:20],  # cap output
        "total_violations": len(violations),
    }

    # === CHECK 7: Persona Quality ===
    persona_stats = []
    total_scenarios_count = len(all_scenarios)
    total_actions_count = len(all_actions)

    for p in personas:
        pname = p.get("persona", "N/A")
        p_outcomes = len(p.get("outcomes", []))
        p_scenarios = sum(
            len(o.get("scenarios", []))
            for o in p.get("outcomes", [])
        )
        p_actions = sum(
            len(a.get("actions", []))
            for o in p.get("outcomes", [])
            for s in o.get("scenarios", [])
            for a in s.get("steps", [])
        )

        flags = []

        # Bloated check
        if total_scenarios_count > 0 and p_scenarios / total_scenarios_count > 0.4:
            pct = round(p_scenarios / total_scenarios_count * 100, 1)
            flags.append(f"BLOATED: holds {pct}% of all scenarios")

        # Thin check
        if p_scenarios <= 1 and p_actions < 5:
            flags.append(f"THIN: only {p_scenarios} scenario(s), {p_actions} actions")

        # Forbidden name check — exact word match only
        # "Fund Controller" is a business role, not a code term
        pname_lower = pname.lower()
        name_words = set(pname_lower.split())
        for forbidden in FORBIDDEN_PERSONA_NAMES:
            if forbidden in name_words and name_words == {forbidden}:
                # Only flag if the persona name IS the forbidden word
                # (not just contains it as part of a business role)
                flags.append(f"FORBIDDEN: persona name is '{forbidden}'")
                break

        persona_stats.append({
            "persona": pname,
            "outcomes": p_outcomes,
            "scenarios": p_scenarios,
            "steps": sum(
                len(s.get("steps", []))
                for o in p.get("outcomes", [])
                for s in o.get("scenarios", [])
            ),
            "actions": p_actions,
            "scenario_share": round(p_scenarios / total_scenarios_count * 100, 1) if total_scenarios_count else 0,
            "flags": flags,
        })

    flagged_personas = [p for p in persona_stats if p["flags"]]
    report["checks"]["persona_quality"] = {
        "severity": "P1",
        "personas": persona_stats,
        "flagged_count": len(flagged_personas),
    }

    # === CHECK 8: Cross-Persona Overlap ===
    keyword_personas = defaultdict(set)
    overlap_keywords = OVERLAP_KEYWORDS  # from verbs.json (project-tunable)
    for s in all_scenarios:
        sname_lower = s["scenario"].lower()
        for kw in overlap_keywords:
            if kw in sname_lower:
                keyword_personas[kw].add(s["persona"])

    overlaps = [
        {"keyword": kw, "personas": sorted(pset), "count": len(pset)}
        for kw, pset in sorted(keyword_personas.items())
        if len(pset) >= 3
    ]
    report["checks"]["cross_persona_overlap"] = {
        "severity": "P2",
        "count": len(overlaps),
        "items": overlaps,
    }

    # === CHECK 9: Source Document Coverage (optional) ===
    if sources:
        # Build searchable text from entire graph
        combined_parts = []
        for p in personas:
            pname = p.get("persona", "")
            for o in p.get("outcomes", []):
                oname = o.get("outcome", "")
                odesc = o.get("description", "") or ""
                for s in o.get("scenarios", []):
                    sname = s.get("scenario", "")
                    sdesc = s.get("description", "") or ""
                    step_text = " ".join(st.get("step", "") for st in s.get("steps", []))
                    action_text = " ".join(a.get("action", "") for st in s.get("steps", []) for a in st.get("actions", []))
                    desc_text = " ".join((a.get("description", "") or "") for st in s.get("steps", []) for a in st.get("actions", []))
                    combined_parts.append(f"{pname} {oname} {odesc} {sname} {sdesc} {step_text} {action_text} {desc_text}".lower())
        combined = " ".join(combined_parts)

        coverage_results = []
        for story_id, keywords in sources.items():
            found = sum(1 for kw in keywords if kw.lower() in combined)
            total = len(keywords)
            pct = (found / total * 100) if total else 0
            status = "FULL" if pct >= 60 else "PARTIAL" if pct > 0 else "MISSING"
            missing = [kw for kw in keywords if kw.lower() not in combined]
            coverage_results.append({
                "story": story_id,
                "status": status,
                "found": found,
                "total": total,
                "missing_keywords": missing,
            })

        full_count = sum(1 for c in coverage_results if c["status"] == "FULL")
        partial_count = sum(1 for c in coverage_results if c["status"] == "PARTIAL")
        missing_count = sum(1 for c in coverage_results if c["status"] == "MISSING")

        report["checks"]["source_coverage"] = {
            "severity": "P0",
            "total_stories": len(sources),
            "full": full_count,
            "partial": partial_count,
            "missing": missing_count,
            "items": coverage_results,
        }
    else:
        report["checks"]["source_coverage"] = {
            "severity": "N/A",
            "note": "No sources file provided. Use --sources <file.json> or let Claude check via Documents MCP.",
        }

    # === OVERALL SCORE ===
    p0_count = report["checks"]["empty_nodes"]["count"]
    p0_count += sum(1 for p in persona_stats if any("FORBIDDEN" in f for f in p["flags"]))

    p1_count = (
        report["checks"]["duplicate_scenarios"]["count"]
        + report["checks"]["platform_agnostic"]["total_violations"]
        + (1 if report["checks"]["citation_coverage"]["percentage"] < 100 else 0)
        + (1 if report["checks"]["description_coverage"]["system_actions"]["percentage"] < 80 else 0)
        + sum(1 for p in persona_stats if any("BLOATED" in f or "THIN" in f for f in p["flags"]))
    )

    p2_count = (
        report["checks"]["cross_persona_overlap"]["count"]
        + sum(1 for o in duplicate_outcomes if o["severity"] == "P2")
    )

    report["overall"] = {
        "p0_issues": p0_count,
        "p1_issues": p1_count,
        "p2_issues": p2_count,
        "health": "HEALTHY" if p0_count == 0 and p1_count <= 3 else
                  "NEEDS_ATTENTION" if p0_count == 0 else "CRITICAL",
    }

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validate-graph.py <graph-json-file> [output-json-file] [--sources <sources.json>]", file=sys.stderr)
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    input_file = args[0]
    output_file = None
    sources_file = None

    i = 1
    while i < len(args):
        if args[i] == "--sources" and i + 1 < len(args):
            sources_file = args[i + 1]
            i += 2
        elif output_file is None and not args[i].startswith("--"):
            output_file = args[i]
            i += 1
        else:
            i += 1

    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    try:
        graph = parse_graph_file(input_file)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error: Failed to parse graph file: {e}", file=sys.stderr)
        sys.exit(1)

    # Load sources if provided
    sources = None
    if sources_file:
        if not os.path.exists(sources_file):
            print(f"Error: Sources file not found: {sources_file}", file=sys.stderr)
            sys.exit(1)
        with open(sources_file, "r", encoding="utf-8") as f:
            sources = json.load(f)

    report = run_checks(graph, sources=sources)

    output = json.dumps(report, indent=2, default=str)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
