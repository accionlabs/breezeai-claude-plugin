#!/usr/bin/env python3
"""
Validate a design graph exported from Breeze MCP.

Usage:
    python3 validate-design.py <design-nodes-json-file> [output-json-file] [--functional <functional-graph-json>]

Input:
    design-nodes-json-file: JSON file with all design nodes (UserJourney, Flow, Page, Component).
    output-json-file:       Where to write the report (default: stdout).
    --functional:           Optional functional graph JSON to cross-validate linkage.

Output: A JSON report with all validation results.

Exit codes:
    0 = validation complete (may have findings)
    1 = input error (file not found, parse failure)
"""

import json
import re
import sys
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations


# --- Valid enum values ---
VALID_MODALITIES = {"WEB", "MOBILE", "TABLET", "DESKTOP", "VOICE", "API", "KIOSK", "WATCH", "TV"}
VALID_PAGE_TYPES = {"LIST", "DETAIL", "FORM", "DASHBOARD"}
VALID_COMPONENT_TYPES = {"ATOM", "MOLECULE", "ORGANISM", "TEMPLATE"}
VALID_LAYOUT_TYPES = {"GRID", "FLEX", "SIDEBAR", "FULL"}

EXPECTED_TEMPLATES = {
    "FORM": "FormPageLayout",
    "LIST": "ListPageLayout",
    "DETAIL": "DetailPageLayout",
    "DASHBOARD": "DashboardLayout",
}

MIN_SUPPORTING_COMPONENTS = {
    "TEMPLATE": 2,
    "ORGANISM": 2,
    "MOLECULE": 2,
    "ATOM": 0,
}

# Synonyms for near-duplicate detection — word pairs that are semantically
# equivalent in UI/design contexts. Checked bidirectionally.
SYNONYM_PAIRS = [
    ("login", "signin"), ("login", "sign-in"), ("signin", "sign-in"),
    ("logout", "signout"), ("logout", "sign-out"), ("signout", "sign-out"),
    ("register", "signup"), ("register", "sign-up"), ("signup", "sign-up"),
    ("search", "find"), ("delete", "remove"),
    ("edit", "modify"), ("edit", "update"),
    ("list", "table"), ("detail", "details"), ("detail", "view"),
    ("form", "input"), ("dialog", "modal"), ("drawer", "panel"),
    ("btn", "button"), ("nav", "navigation"), ("img", "image"),
    ("pwd", "password"), ("auth", "authentication"),
    ("config", "configuration"), ("info", "information"),
]
_SYNONYM_MAP = defaultdict(set)
for a, b in SYNONYM_PAIRS:
    _SYNONYM_MAP[a].add(b)
    _SYNONYM_MAP[b].add(a)


def _tokenize(name):
    """Split a PascalCase/camelCase/kebab/snake name into lowercase tokens."""
    # Insert space before uppercase runs: "LoginForm" -> "Login Form"
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    # Split on non-alphanumeric
    tokens = re.split(r'[^a-zA-Z0-9]+', s.lower())
    return set(t for t in tokens if t)


def _replace_synonyms(tokens):
    """Expand each token with its synonyms for comparison."""
    canonical = set()
    for t in tokens:
        canonical.add(t)
        canonical.update(_SYNONYM_MAP.get(t, set()))
    return canonical


def _similarity(name_a, name_b):
    """
    Token-set similarity with synonym expansion.
    Returns a float 0.0–1.0.
    """
    tokens_a = _tokenize(name_a)
    tokens_b = _tokenize(name_b)
    if not tokens_a or not tokens_b:
        return 0.0

    # Direct token overlap
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    direct = len(intersection) / len(union) if union else 0.0

    # Synonym-expanded overlap
    expanded_a = _replace_synonyms(tokens_a)
    expanded_b = _replace_synonyms(tokens_b)
    syn_intersection = expanded_a & expanded_b
    syn_union = expanded_a | expanded_b
    synonym = len(syn_intersection) / len(syn_union) if syn_union else 0.0

    # Use the higher score
    return max(direct, synonym)


def _find_near_duplicates(nodes, name_key="name", group_keys=None, threshold=0.6):
    """
    Find near-duplicate nodes by fuzzy name matching.

    Args:
        nodes: list of node dicts
        name_key: field to compare
        group_keys: optional list of fields to include in output for context
        threshold: similarity threshold (0.6 = 60% token overlap)

    Returns list of near-duplicate pairs with similarity scores.
    """
    near_dupes = []
    seen_exact = set()

    # Build (name, node) pairs, skip empty names
    named = [(n.get(name_key, ""), n) for n in nodes if n.get(name_key)]

    for (name_a, node_a), (name_b, node_b) in combinations(named, 2):
        # Skip exact duplicates (caught by CHECK 3)
        if name_a.lower() == name_b.lower():
            continue

        sim = _similarity(name_a, name_b)
        if sim >= threshold:
            pair_key = tuple(sorted([name_a.lower(), name_b.lower()]))
            if pair_key in seen_exact:
                continue
            seen_exact.add(pair_key)

            entry = {
                "name_a": name_a,
                "name_b": name_b,
                "id_a": node_a.get("id"),
                "id_b": node_b.get("id"),
                "similarity": round(sim, 2),
            }
            if group_keys:
                for gk in group_keys:
                    entry[f"{gk}_a"] = node_a.get(gk)
                    entry[f"{gk}_b"] = node_b.get(gk)
            near_dupes.append(entry)

    # Sort by similarity descending
    near_dupes.sort(key=lambda x: x["similarity"], reverse=True)
    return near_dupes


def parse_design_file(filepath):
    """Parse the design graph JSON file into a list of nodes."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle MCP tool output wrapping: [{type, text}] -> text -> ...
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        if "text" in data[0]:
            text = data[0]["text"]
            data = json.loads(text)
            if isinstance(data, list) and len(data) > 0 and "text" in data[0]:
                data = json.loads(data[0]["text"])
            if isinstance(data, list) and len(data) > 0:
                result = data[0]
                data = result.get("data", result)
    return data


def parse_nodes_by_label(data):
    """
    Extract nodes grouped by label from the design graph data.
    Handles multiple input formats:
    - Dict with label keys: {"UserJourney": [...], "Flow": [...], ...}
    - List of nodes with a "label" field
    - Dict with "nodes" key containing a list
    """
    labels = {"UserJourney": [], "Flow": [], "Page": [], "Component": []}

    if isinstance(data, dict):
        for label in labels:
            if label in data:
                items = data[label]
                if isinstance(items, list):
                    labels[label] = items
        if all(len(v) == 0 for v in labels.values()):
            # Try "nodes" key
            nodes = data.get("nodes", data.get("data", []))
            if isinstance(nodes, list):
                for n in nodes:
                    lbl = n.get("label", n.get("type", ""))
                    if lbl in labels:
                        labels[lbl].append(n)
    elif isinstance(data, list):
        for n in data:
            if isinstance(n, dict):
                lbl = n.get("label", n.get("type", ""))
                if lbl in labels:
                    labels[lbl].append(n)

    return labels


def run_checks(nodes_by_label, functional_graph=None):
    """Run all validation checks and return structured results."""
    user_journeys = nodes_by_label["UserJourney"]
    flows = nodes_by_label["Flow"]
    pages = nodes_by_label["Page"]
    components = nodes_by_label["Component"]

    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "summary": {
            "userJourneys": len(user_journeys),
            "flows": len(flows),
            "pages": len(pages),
            "components": len(components),
            "atoms": 0,
            "molecules": 0,
            "organisms": 0,
            "templates": 0,
        },
        "checks": {},
    }

    # Count component types
    comp_type_counts = Counter(c.get("type", "UNKNOWN") for c in components)
    report["summary"]["atoms"] = comp_type_counts.get("ATOM", 0)
    report["summary"]["molecules"] = comp_type_counts.get("MOLECULE", 0)
    report["summary"]["organisms"] = comp_type_counts.get("ORGANISM", 0)
    report["summary"]["templates"] = comp_type_counts.get("TEMPLATE", 0)

    # Build lookup maps
    flow_by_id = {f.get("id"): f for f in flows if f.get("id")}
    page_by_id = {p.get("id"): p for p in pages if p.get("id")}
    comp_by_id = {c.get("id"): c for c in components if c.get("id")}
    comp_by_name = defaultdict(list)
    for c in components:
        comp_by_name[c.get("name", "").lower()].append(c)

    # === CHECK 1: Orphan Nodes (no parent linkage) ===
    orphan_flows = []
    for f in flows:
        uj_ids = f.get("userJourneyIds") or []
        if not uj_ids:
            orphan_flows.append({
                "name": f.get("name", "N/A"),
                "id": f.get("id"),
                "issue": "Flow has no parent UserJourney (empty userJourneyIds)",
            })

    orphan_pages = []
    for p in pages:
        flow_ids = p.get("flowIds") or []
        if not flow_ids:
            orphan_pages.append({
                "name": p.get("name", "N/A"),
                "id": p.get("id"),
                "issue": "Page has no parent Flow (empty flowIds)",
            })

    orphan_components = []
    for c in components:
        page_ids = c.get("pageIds") or []
        if not page_ids:
            orphan_components.append({
                "name": c.get("name", "N/A"),
                "id": c.get("id"),
                "type": c.get("type", "N/A"),
                "issue": "Component has no parent Page (empty pageIds)",
            })

    report["checks"]["orphan_nodes"] = {
        "severity": "P1",
        "orphan_flows": len(orphan_flows),
        "orphan_pages": len(orphan_pages),
        "orphan_components": len(orphan_components),
        "total": len(orphan_flows) + len(orphan_pages) + len(orphan_components),
        "items": (orphan_flows + orphan_pages + orphan_components)[:30],
    }

    # === CHECK 1b: Dangling Parent References ===
    # Parent ID arrays reference IDs that don't exist in the graph
    uj_id_set = {uj.get("id") for uj in user_journeys if uj.get("id")}
    flow_id_set = {f.get("id") for f in flows if f.get("id")}
    page_id_set = {p.get("id") for p in pages if p.get("id")}

    dangling_refs = []

    for f in flows:
        for uid in (f.get("userJourneyIds") or []):
            if uid not in uj_id_set:
                dangling_refs.append({
                    "node": "Flow",
                    "name": f.get("name", "N/A"),
                    "id": f.get("id"),
                    "field": "userJourneyIds",
                    "dangling_id": uid,
                    "issue": f"References UserJourney '{uid}' which does not exist",
                })

    for p in pages:
        for fid in (p.get("flowIds") or []):
            if fid not in flow_id_set:
                dangling_refs.append({
                    "node": "Page",
                    "name": p.get("name", "N/A"),
                    "id": p.get("id"),
                    "field": "flowIds",
                    "dangling_id": fid,
                    "issue": f"References Flow '{fid}' which does not exist",
                })

    for c in components:
        for pid in (c.get("pageIds") or []):
            if pid not in page_id_set:
                dangling_refs.append({
                    "node": "Component",
                    "name": c.get("name", "N/A"),
                    "id": c.get("id"),
                    "field": "pageIds",
                    "dangling_id": pid,
                    "issue": f"References Page '{pid}' which does not exist",
                })

    report["checks"]["dangling_parent_refs"] = {
        "severity": "P0",
        "count": len(dangling_refs),
        "items": dangling_refs[:30],
    }

    # === CHECK 1c: Broken Hierarchy Chains ===
    # Verify full chain: Component → Page → Flow → UserJourney is unbroken.
    # A component on Page P, where P is in Flow F, where F is in UserJourney UJ
    # — if any link in that chain is broken, the node is effectively unreachable.
    broken_chains = []

    for c in components:
        cname = c.get("name", "N/A")
        c_page_ids = c.get("pageIds") or []
        if not c_page_ids:
            continue  # already caught by orphan check

        for pid in c_page_ids:
            page = page_by_id.get(pid)
            if not page:
                continue  # already caught by dangling refs

            p_flow_ids = page.get("flowIds") or []
            if not p_flow_ids:
                broken_chains.append({
                    "component": cname,
                    "page": page.get("name", "N/A"),
                    "issue": f"Component '{cname}' → Page '{page.get('name', 'N/A')}' → (no Flow) — chain broken at Page level",
                })
                continue

            for fid in p_flow_ids:
                flow = flow_by_id.get(fid)
                if not flow:
                    continue  # dangling ref

                f_uj_ids = flow.get("userJourneyIds") or []
                if not f_uj_ids:
                    broken_chains.append({
                        "component": cname,
                        "page": page.get("name", "N/A"),
                        "flow": flow.get("name", "N/A"),
                        "issue": f"Component '{cname}' → Page → Flow '{flow.get('name', 'N/A')}' → (no UserJourney) — chain broken at Flow level",
                    })
                    continue

                has_valid_uj = any(uid in uj_id_set for uid in f_uj_ids)
                if not has_valid_uj:
                    broken_chains.append({
                        "component": cname,
                        "page": page.get("name", "N/A"),
                        "flow": flow.get("name", "N/A"),
                        "issue": f"Flow '{flow.get('name', 'N/A')}' references UserJourney IDs that don't exist — chain broken",
                    })

    # Deduplicate broken chains (same issue reported via multiple paths)
    seen_chain_issues = set()
    unique_broken = []
    for bc in broken_chains:
        key = bc["issue"]
        if key not in seen_chain_issues:
            seen_chain_issues.add(key)
            unique_broken.append(bc)

    report["checks"]["broken_chains"] = {
        "severity": "P0",
        "count": len(unique_broken),
        "items": unique_broken[:30],
    }

    # === CHECK 1d: Duplicate Linkage (same parent ID repeated in array) ===
    dup_links = []

    def _check_dup_ids(node, node_type, field):
        ids = node.get(field) or []
        if len(ids) != len(set(ids)):
            counts = Counter(ids)
            dupes = {k: v for k, v in counts.items() if v > 1}
            dup_links.append({
                "node": node_type,
                "name": node.get("name", "N/A"),
                "id": node.get("id"),
                "field": field,
                "duplicates": dupes,
                "issue": f"{field} contains duplicate IDs: {list(dupes.keys())}",
            })

    for f in flows:
        _check_dup_ids(f, "Flow", "userJourneyIds")
        _check_dup_ids(f, "Flow", "stepIds")
    for p in pages:
        _check_dup_ids(p, "Page", "flowIds")
        _check_dup_ids(p, "Page", "stepIds")
    for c in components:
        _check_dup_ids(c, "Component", "pageIds")
        _check_dup_ids(c, "Component", "actionIds")

    report["checks"]["duplicate_linkage"] = {
        "severity": "P1",
        "count": len(dup_links),
        "items": dup_links[:30],
    }

    # === CHECK 2: Empty Hierarchy (nodes with no children) ===
    # UserJourneys with no Flows
    uj_ids_in_flows = set()
    for f in flows:
        for uid in (f.get("userJourneyIds") or []):
            uj_ids_in_flows.add(uid)

    empty_journeys = []
    for uj in user_journeys:
        uid = uj.get("id")
        if uid and uid not in uj_ids_in_flows:
            empty_journeys.append({
                "name": uj.get("name", "N/A"),
                "id": uid,
                "issue": "UserJourney has no Flows",
            })

    # Flows with no Pages
    flow_ids_in_pages = set()
    for p in pages:
        for fid in (p.get("flowIds") or []):
            flow_ids_in_pages.add(fid)

    empty_flows = []
    for f in flows:
        fid = f.get("id")
        if fid and fid not in flow_ids_in_pages:
            empty_flows.append({
                "name": f.get("name", "N/A"),
                "id": fid,
                "issue": "Flow has no Pages",
            })

    # Pages with no Components
    page_ids_in_comps = set()
    for c in components:
        for pid in (c.get("pageIds") or []):
            page_ids_in_comps.add(pid)

    empty_pages = []
    for p in pages:
        pid = p.get("id")
        if pid and pid not in page_ids_in_comps:
            empty_pages.append({
                "name": p.get("name", "N/A"),
                "id": pid,
                "issue": "Page has no Components",
            })

    report["checks"]["empty_hierarchy"] = {
        "severity": "P0",
        "empty_journeys": len(empty_journeys),
        "empty_flows": len(empty_flows),
        "empty_pages": len(empty_pages),
        "total": len(empty_journeys) + len(empty_flows) + len(empty_pages),
        "items": (empty_journeys + empty_flows + empty_pages)[:30],
    }

    # === CHECK 3: Duplicate Names ===
    uj_name_counts = Counter(uj.get("name", "") for uj in user_journeys)
    dup_journeys = [
        {"name": name, "count": count}
        for name, count in uj_name_counts.items()
        if count > 1 and name
    ]

    flow_name_modal = Counter(
        (f.get("name", ""), f.get("modality", ""))
        for f in flows
    )
    dup_flows = [
        {"name": nm, "modality": mod, "count": count}
        for (nm, mod), count in flow_name_modal.items()
        if count > 1 and nm
    ]

    page_name_type = Counter(
        (p.get("name", ""), p.get("pageType", ""))
        for p in pages
    )
    dup_pages = [
        {"name": nm, "pageType": pt, "count": count}
        for (nm, pt), count in page_name_type.items()
        if count > 1 and nm
    ]

    comp_names = Counter(c.get("name", "") for c in components)
    dup_components = [
        {"name": name, "count": count}
        for name, count in comp_names.items()
        if count > 1 and name
    ]

    report["checks"]["duplicate_names"] = {
        "severity": "P1",
        "duplicate_journeys": len(dup_journeys),
        "duplicate_flows": len(dup_flows),
        "duplicate_pages": len(dup_pages),
        "duplicate_components": len(dup_components),
        "total": len(dup_journeys) + len(dup_flows) + len(dup_pages) + len(dup_components),
        "items": {
            "userJourneys": dup_journeys[:10],
            "flows": dup_flows[:10],
            "pages": dup_pages[:10],
            "components": dup_components[:10],
        },
    }

    # === CHECK 3b: Near-Duplicate Names (fuzzy matching) ===
    near_dup_flows = _find_near_duplicates(
        flows, name_key="name", group_keys=["modality"], threshold=0.6,
    )
    near_dup_pages = _find_near_duplicates(
        pages, name_key="name", group_keys=["pageType"], threshold=0.6,
    )
    near_dup_components = _find_near_duplicates(
        components, name_key="name", group_keys=["type"], threshold=0.6,
    )

    report["checks"]["near_duplicate_names"] = {
        "severity": "P1",
        "near_duplicate_flows": len(near_dup_flows),
        "near_duplicate_pages": len(near_dup_pages),
        "near_duplicate_components": len(near_dup_components),
        "total": len(near_dup_flows) + len(near_dup_pages) + len(near_dup_components),
        "items": {
            "flows": near_dup_flows[:15],
            "pages": near_dup_pages[:15],
            "components": near_dup_components[:15],
        },
    }

    # === CHECK 4: Missing scenarioId on UserJourneys ===
    missing_scenario_id = []
    for uj in user_journeys:
        if not uj.get("scenarioId"):
            missing_scenario_id.append({
                "name": uj.get("name", "N/A"),
                "id": uj.get("id"),
            })

    report["checks"]["missing_scenario_id"] = {
        "severity": "P0",
        "count": len(missing_scenario_id),
        "items": missing_scenario_id[:20],
    }

    # === CHECK 5: Invalid Enum Values ===
    invalid_enums = []

    for f in flows:
        mod = f.get("modality", "")
        if mod and mod not in VALID_MODALITIES:
            invalid_enums.append({
                "node": "Flow",
                "name": f.get("name", "N/A"),
                "field": "modality",
                "value": mod,
                "valid": sorted(VALID_MODALITIES),
            })

    for p in pages:
        pt = p.get("pageType", "")
        if pt and pt not in VALID_PAGE_TYPES:
            invalid_enums.append({
                "node": "Page",
                "name": p.get("name", "N/A"),
                "field": "pageType",
                "value": pt,
                "valid": sorted(VALID_PAGE_TYPES),
            })

    for c in components:
        ct = c.get("type", "")
        if ct and ct not in VALID_COMPONENT_TYPES:
            invalid_enums.append({
                "node": "Component",
                "name": c.get("name", "N/A"),
                "field": "type",
                "value": ct,
                "valid": sorted(VALID_COMPONENT_TYPES),
            })
        lt = c.get("layoutType", "")
        if lt and lt not in VALID_LAYOUT_TYPES:
            invalid_enums.append({
                "node": "Component",
                "name": c.get("name", "N/A"),
                "field": "layoutType",
                "value": lt,
                "valid": sorted(VALID_LAYOUT_TYPES),
            })

    # Check for lowercase enum values (common mistake)
    lowercase_enums = []
    for f in flows:
        mod = f.get("modality", "")
        if mod and mod != mod.upper() and mod.upper() in VALID_MODALITIES:
            lowercase_enums.append({
                "node": "Flow",
                "name": f.get("name", "N/A"),
                "field": "modality",
                "value": mod,
                "should_be": mod.upper(),
            })
    for p in pages:
        pt = p.get("pageType", "")
        if pt and pt != pt.upper() and pt.upper() in VALID_PAGE_TYPES:
            lowercase_enums.append({
                "node": "Page",
                "name": p.get("name", "N/A"),
                "field": "pageType",
                "value": pt,
                "should_be": pt.upper(),
            })
    for c in components:
        ct = c.get("type", "")
        if ct and ct != ct.upper() and ct.upper() in VALID_COMPONENT_TYPES:
            lowercase_enums.append({
                "node": "Component",
                "name": c.get("name", "N/A"),
                "field": "type",
                "value": ct,
                "should_be": ct.upper(),
            })

    report["checks"]["invalid_enums"] = {
        "severity": "P0",
        "invalid_count": len(invalid_enums),
        "lowercase_count": len(lowercase_enums),
        "items": invalid_enums[:20],
        "lowercase_items": lowercase_enums[:20],
    }

    # === CHECK 6: Template Compliance ===
    # Every page must have exactly one TEMPLATE component
    templates_by_page_id = defaultdict(list)
    for c in components:
        if c.get("type") == "TEMPLATE":
            for pid in (c.get("pageIds") or []):
                templates_by_page_id[pid].append(c.get("name", "N/A"))

    pages_missing_template = []
    pages_multiple_templates = []
    for p in pages:
        pid = p.get("id")
        if not pid:
            continue
        tpls = templates_by_page_id.get(pid, [])
        if len(tpls) == 0:
            pages_missing_template.append({
                "name": p.get("name", "N/A"),
                "id": pid,
                "pageType": p.get("pageType", "N/A"),
            })
        elif len(tpls) > 1:
            pages_multiple_templates.append({
                "name": p.get("name", "N/A"),
                "id": pid,
                "templates": tpls,
            })

    # Check template naming matches pageType
    wrong_template_name = []
    for p in pages:
        pid = p.get("id")
        pt = p.get("pageType", "")
        if not pid or not pt:
            continue
        expected = EXPECTED_TEMPLATES.get(pt)
        if not expected:
            continue
        tpls = templates_by_page_id.get(pid, [])
        for tname in tpls:
            if tname != expected:
                wrong_template_name.append({
                    "page": p.get("name", "N/A"),
                    "pageType": pt,
                    "template": tname,
                    "expected": expected,
                })

    report["checks"]["template_compliance"] = {
        "severity": "P0",
        "pages_missing_template": len(pages_missing_template),
        "pages_multiple_templates": len(pages_multiple_templates),
        "wrong_template_name": len(wrong_template_name),
        "missing_items": pages_missing_template[:20],
        "multiple_items": pages_multiple_templates[:10],
        "wrong_name_items": wrong_template_name[:10],
    }

    # === CHECK 7: supportingComponents Validation ===
    sc_violations = []
    all_component_names = {c.get("name", "").lower() for c in components}

    for c in components:
        ctype = c.get("type", "")
        cname = c.get("name", "N/A")
        sc = c.get("supportingComponents") or []
        min_req = MIN_SUPPORTING_COMPONENTS.get(ctype, 0)

        if len(sc) < min_req:
            sc_violations.append({
                "name": cname,
                "type": ctype,
                "supportingComponents": sc,
                "count": len(sc),
                "minimum": min_req,
                "issue": f"{ctype} requires >= {min_req} supportingComponents, has {len(sc)}",
            })

        # Check if referenced components actually exist
        for ref_name in sc:
            if ref_name.lower() not in all_component_names:
                sc_violations.append({
                    "name": cname,
                    "type": ctype,
                    "issue": f"supportingComponent '{ref_name}' does not exist in the graph",
                    "missing_ref": ref_name,
                })

    # Check TEMPLATE only references ORGANISMs
    template_ref_violations = []
    comp_type_by_name = {c.get("name", "").lower(): c.get("type", "") for c in components}
    for c in components:
        if c.get("type") != "TEMPLATE":
            continue
        sc = c.get("supportingComponents") or []
        for ref_name in sc:
            ref_type = comp_type_by_name.get(ref_name.lower(), "")
            if ref_type and ref_type != "ORGANISM":
                template_ref_violations.append({
                    "template": c.get("name", "N/A"),
                    "references": ref_name,
                    "ref_type": ref_type,
                    "issue": f"TEMPLATE should only reference ORGANISMs, but references {ref_type} '{ref_name}'",
                })

    report["checks"]["supporting_components"] = {
        "severity": "P1",
        "minimum_violations": sum(1 for v in sc_violations if "requires >=" in v.get("issue", "")),
        "missing_ref_violations": sum(1 for v in sc_violations if "does not exist" in v.get("issue", "")),
        "template_ref_violations": len(template_ref_violations),
        "total": len(sc_violations) + len(template_ref_violations),
        "items": sc_violations[:20],
        "template_items": template_ref_violations[:10],
    }

    # === CHECK 8: actionIds on Pages (should be empty) ===
    pages_with_actions = []
    for p in pages:
        action_ids = p.get("actionIds") or []
        if action_ids:
            pages_with_actions.append({
                "name": p.get("name", "N/A"),
                "id": p.get("id"),
                "actionIds_count": len(action_ids),
                "issue": "Pages must NOT have actionIds — actions map to Components only",
            })

    report["checks"]["action_ids_on_pages"] = {
        "severity": "P1",
        "count": len(pages_with_actions),
        "items": pages_with_actions[:20],
    }

    # === CHECK 8b: Description Coverage ===
    # Every node should have a non-empty description
    def _is_valid_desc(desc):
        if not desc:
            return False
        d = desc.strip()
        if not d or len(d) < 5:
            return False
        # Reject placeholder descriptions
        placeholders = {"n/a", "na", "tbd", "todo", "-", ".", "none", "skip",
                        "description", "desc", "placeholder"}
        if d.lower() in placeholders:
            return False
        return True

    missing_desc = {"UserJourney": [], "Flow": [], "Page": [], "Component": []}

    for uj in user_journeys:
        if not _is_valid_desc(uj.get("description")):
            missing_desc["UserJourney"].append({
                "name": uj.get("name", "N/A"),
                "id": uj.get("id"),
                "description": uj.get("description"),
            })

    for f in flows:
        if not _is_valid_desc(f.get("description")):
            missing_desc["Flow"].append({
                "name": f.get("name", "N/A"),
                "id": f.get("id"),
                "description": f.get("description"),
            })

    for p in pages:
        if not _is_valid_desc(p.get("description")):
            missing_desc["Page"].append({
                "name": p.get("name", "N/A"),
                "id": p.get("id"),
                "description": p.get("description"),
            })

    for c in components:
        if not _is_valid_desc(c.get("description")):
            missing_desc["Component"].append({
                "name": c.get("name", "N/A"),
                "id": c.get("id"),
                "type": c.get("type", "N/A"),
                "description": c.get("description"),
            })

    total_nodes = len(user_journeys) + len(flows) + len(pages) + len(components)
    total_missing = sum(len(v) for v in missing_desc.values())
    total_with_desc = total_nodes - total_missing

    report["checks"]["description_coverage"] = {
        "severity": "P1" if total_missing > 0 else "INFO",
        "total_nodes": total_nodes,
        "with_valid_description": total_with_desc,
        "missing_description": total_missing,
        "coverage_pct": round(total_with_desc / total_nodes * 100, 1) if total_nodes else 0,
        "by_type": {
            "UserJourney": {
                "total": len(user_journeys),
                "missing": len(missing_desc["UserJourney"]),
                "items": missing_desc["UserJourney"][:10],
            },
            "Flow": {
                "total": len(flows),
                "missing": len(missing_desc["Flow"]),
                "items": missing_desc["Flow"][:10],
            },
            "Page": {
                "total": len(pages),
                "missing": len(missing_desc["Page"]),
                "items": missing_desc["Page"][:10],
            },
            "Component": {
                "total": len(components),
                "missing": len(missing_desc["Component"]),
                "items": missing_desc["Component"][:10],
            },
        },
    }

    # === CHECK 9: Modality Coverage ===
    modalities_used = Counter(f.get("modality", "UNKNOWN") for f in flows)
    report["checks"]["modality_coverage"] = {
        "severity": "INFO",
        "modalities": dict(modalities_used),
        "total_flows": len(flows),
    }

    # === CHECK 10: Component Type Distribution ===
    type_dist = dict(comp_type_counts)
    unknown_types = comp_type_counts.get("UNKNOWN", 0) + sum(
        v for k, v in comp_type_counts.items() if k not in VALID_COMPONENT_TYPES
    )
    report["checks"]["component_distribution"] = {
        "severity": "INFO" if unknown_types == 0 else "P1",
        "distribution": type_dist,
        "unknown_or_invalid": unknown_types,
    }

    # === CHECK 11: Functional Graph Cross-Validation (optional) ===
    if functional_graph:
        _run_functional_cross_check(report, nodes_by_label, functional_graph)
    else:
        report["checks"]["functional_linkage"] = {
            "severity": "N/A",
            "note": "No functional graph provided. Use --functional <file.json> to cross-validate.",
        }

    # === OVERALL SCORE ===
    p0_count = (
        report["checks"]["empty_hierarchy"]["total"]
        + report["checks"]["missing_scenario_id"]["count"]
        + report["checks"]["invalid_enums"]["invalid_count"]
        + report["checks"]["template_compliance"]["pages_missing_template"]
        + report["checks"]["dangling_parent_refs"]["count"]
        + report["checks"]["broken_chains"]["count"]
    )

    p1_count = (
        report["checks"]["orphan_nodes"]["total"]
        + report["checks"]["duplicate_names"]["total"]
        + report["checks"]["near_duplicate_names"]["total"]
        + report["checks"]["duplicate_linkage"]["count"]
        + report["checks"]["supporting_components"]["total"]
        + report["checks"]["action_ids_on_pages"]["count"]
        + report["checks"]["invalid_enums"]["lowercase_count"]
        + report["checks"]["description_coverage"]["missing_description"]
    )

    p2_count = (
        report["checks"]["template_compliance"]["wrong_template_name"]
        + report["checks"]["template_compliance"]["pages_multiple_templates"]
    )

    report["overall"] = {
        "p0_issues": p0_count,
        "p1_issues": p1_count,
        "p2_issues": p2_count,
        "health": (
            "HEALTHY" if p0_count == 0 and p1_count <= 3
            else "NEEDS_ATTENTION" if p0_count == 0
            else "CRITICAL"
        ),
    }

    return report


def _run_functional_cross_check(report, nodes_by_label, functional_graph):
    """Cross-validate design graph against functional graph."""
    user_journeys = nodes_by_label["UserJourney"]
    flows = nodes_by_label["Flow"]
    pages = nodes_by_label["Page"]
    components = nodes_by_label["Component"]

    # Extract all IDs from functional graph, plus build step→action map
    func_scenario_ids = set()
    func_step_ids = set()
    func_action_ids = set()
    func_step_to_actions = defaultdict(set)  # stepId → set of actionIds
    func_action_to_step = {}                 # actionId → stepId
    func_action_details = {}                 # actionId → {persona, scenario, step, action}

    system_personas = {"system", "external system"}
    personas = functional_graph.get("personas", [])
    for p in personas:
        pname = p.get("persona", "")
        is_system = pname.lower() in system_personas
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                sid = s.get("id")
                if sid:
                    func_scenario_ids.add(sid)
                for st in s.get("steps", []):
                    stid = st.get("id")
                    if stid:
                        func_step_ids.add(stid)
                    for a in st.get("actions", []):
                        aid = a.get("id")
                        if aid:
                            func_action_ids.add(aid)
                            if stid:
                                func_step_to_actions[stid].add(aid)
                                func_action_to_step[aid] = stid
                            func_action_details[aid] = {
                                "persona": pname,
                                "scenario": s.get("scenario", "N/A"),
                                "step": st.get("step", "N/A"),
                                "action": a.get("action", "N/A"),
                                "is_system": is_system,
                            }

    # --- Scenario coverage ---
    dangling_scenario_refs = []
    for uj in user_journeys:
        sid = uj.get("scenarioId")
        if sid and sid not in func_scenario_ids:
            dangling_scenario_refs.append({
                "userJourney": uj.get("name", "N/A"),
                "scenarioId": sid,
                "issue": "scenarioId not found in functional graph",
            })

    design_scenario_ids = {uj.get("scenarioId") for uj in user_journeys if uj.get("scenarioId")}
    uncovered_scenarios = []
    for p in personas:
        pname = p.get("persona", "")
        if pname.lower() in system_personas:
            continue
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                sid = s.get("id")
                if sid and sid not in design_scenario_ids:
                    uncovered_scenarios.append({
                        "persona": pname,
                        "outcome": o.get("outcome", "N/A"),
                        "scenario": s.get("scenario", "N/A"),
                        "scenarioId": sid,
                    })

    # --- stepIds validation on Flows and Pages ---
    dangling_step_refs = []
    design_step_ids = set()

    for f in flows:
        for stid in (f.get("stepIds") or []):
            design_step_ids.add(stid)
            if stid not in func_step_ids:
                dangling_step_refs.append({
                    "node": "Flow",
                    "name": f.get("name", "N/A"),
                    "stepId": stid,
                    "issue": "stepId not found in functional graph",
                })

    for pg in pages:
        for stid in (pg.get("stepIds") or []):
            design_step_ids.add(stid)
            if stid not in func_step_ids:
                dangling_step_refs.append({
                    "node": "Page",
                    "name": pg.get("name", "N/A"),
                    "stepId": stid,
                    "issue": "stepId not found in functional graph",
                })

    # Steps in covered scenarios that are not referenced by any Flow or Page
    unmapped_steps = []
    for p in personas:
        pname = p.get("persona", "")
        if pname.lower() in system_personas:
            continue
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                sid = s.get("id")
                if sid not in design_scenario_ids:
                    continue
                for st in s.get("steps", []):
                    stid = st.get("id")
                    if stid and stid not in design_step_ids:
                        unmapped_steps.append({
                            "persona": pname,
                            "scenario": s.get("scenario", "N/A"),
                            "step": st.get("step", "N/A"),
                            "stepId": stid,
                        })

    # --- actionIds validation on Components ---
    dangling_action_refs = []
    design_action_ids = set()
    for c in components:
        for aid in (c.get("actionIds") or []):
            design_action_ids.add(aid)
            if aid not in func_action_ids:
                dangling_action_refs.append({
                    "component": c.get("name", "N/A"),
                    "actionId": aid,
                    "issue": "actionId not found in functional graph",
                })

    # Actions in covered scenarios not mapped to any Component
    unmapped_actions = []
    for p in personas:
        pname = p.get("persona", "")
        if pname.lower() in system_personas:
            continue
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                sid = s.get("id")
                if sid not in design_scenario_ids:
                    continue
                for st in s.get("steps", []):
                    for a in st.get("actions", []):
                        aid = a.get("id")
                        if aid and aid not in design_action_ids:
                            unmapped_actions.append({
                                "persona": pname,
                                "scenario": s.get("scenario", "N/A"),
                                "step": st.get("step", "N/A"),
                                "action": a.get("action", "N/A"),
                                "actionId": aid,
                            })

    # --- Step-to-action consistency ---
    # If a Component has actionIds, the parent step of each action should
    # appear in a Flow's stepIds that shares a common ancestor with
    # the Component's page. This is a deep consistency check.
    step_action_mismatches = []
    # Build: pageId → set of flowIds (from page.flowIds)
    page_to_flows = defaultdict(set)
    for pg in pages:
        pid = pg.get("id")
        if pid:
            for fid in (pg.get("flowIds") or []):
                page_to_flows[pid].add(fid)

    # Build: flowId → set of stepIds
    flow_to_steps = defaultdict(set)
    for f in flows:
        fid = f.get("id")
        if fid:
            for stid in (f.get("stepIds") or []):
                flow_to_steps[fid].add(stid)

    for c in components:
        c_action_ids = c.get("actionIds") or []
        c_page_ids = c.get("pageIds") or []
        if not c_action_ids or not c_page_ids:
            continue

        # Collect all stepIds from all flows that the component's pages belong to
        reachable_steps = set()
        for pid in c_page_ids:
            for fid in page_to_flows.get(pid, set()):
                reachable_steps.update(flow_to_steps.get(fid, set()))

        for aid in c_action_ids:
            parent_step = func_action_to_step.get(aid)
            if parent_step and reachable_steps and parent_step not in reachable_steps:
                detail = func_action_details.get(aid, {})
                step_action_mismatches.append({
                    "component": c.get("name", "N/A"),
                    "actionId": aid,
                    "action": detail.get("action", "N/A"),
                    "expected_stepId": parent_step,
                    "step": detail.get("step", "N/A"),
                    "issue": "Action's parent step is not in any Flow that contains this component's page",
                })

    # --- Coverage stats ---
    total_covered = len(func_scenario_ids & design_scenario_ids)
    human_scenario_count = 0
    human_step_count = 0
    human_action_count = 0
    for p in personas:
        if p.get("persona", "").lower() in system_personas:
            continue
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                human_scenario_count += 1
                for st in s.get("steps", []):
                    human_step_count += 1
                    human_action_count += len(st.get("actions", []))

    report["checks"]["functional_linkage"] = {
        "severity": "P1" if (dangling_scenario_refs or uncovered_scenarios
                             or dangling_step_refs or dangling_action_refs) else "INFO",
        "scenario_coverage": {
            "functional_total": len(func_scenario_ids),
            "functional_human": human_scenario_count,
            "design_covered": total_covered,
            "coverage_pct": round(total_covered / human_scenario_count * 100, 1) if human_scenario_count else 0,
            "dangling_refs": len(dangling_scenario_refs),
            "uncovered": len(uncovered_scenarios),
            "dangling_items": dangling_scenario_refs[:10],
            "uncovered_items": uncovered_scenarios[:20],
        },
        "step_coverage": {
            "functional_human_steps": human_step_count,
            "design_step_refs": len(design_step_ids),
            "dangling_refs": len(dangling_step_refs),
            "unmapped": len(unmapped_steps),
            "dangling_items": dangling_step_refs[:10],
            "unmapped_items": unmapped_steps[:15],
        },
        "action_coverage": {
            "functional_human_actions": human_action_count,
            "design_action_refs": len(design_action_ids),
            "dangling_refs": len(dangling_action_refs),
            "unmapped": len(unmapped_actions),
            "dangling_items": dangling_action_refs[:10],
            "unmapped_items": unmapped_actions[:15],
        },
        "step_action_consistency": {
            "mismatches": len(step_action_mismatches),
            "items": step_action_mismatches[:15],
        },
    }


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 validate-design.py <design-json-file> "
            "[output-json-file] [--functional <functional-graph.json>]",
            file=sys.stderr,
        )
        sys.exit(1)

    args = sys.argv[1:]
    input_file = args[0]
    output_file = None
    functional_file = None

    i = 1
    while i < len(args):
        if args[i] == "--functional" and i + 1 < len(args):
            functional_file = args[i + 1]
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
        data = parse_design_file(input_file)
        nodes_by_label = parse_nodes_by_label(data)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error: Failed to parse design file: {e}", file=sys.stderr)
        sys.exit(1)

    functional_graph = None
    if functional_file:
        if not os.path.exists(functional_file):
            print(f"Error: Functional graph file not found: {functional_file}", file=sys.stderr)
            sys.exit(1)
        try:
            from validate_graph import parse_graph_file
            functional_graph = parse_graph_file(functional_file)
        except ImportError:
            # Inline parse
            with open(functional_file, "r", encoding="utf-8") as f:
                fdata = json.load(f)
            if isinstance(fdata, list) and fdata and "text" in fdata[0]:
                text = fdata[0]["text"]
                fdata = json.loads(text)
                if isinstance(fdata, list) and fdata and "text" in fdata[0]:
                    fdata = json.loads(fdata[0]["text"])
                if isinstance(fdata, list):
                    fdata = fdata[0]
                functional_graph = fdata.get("data", fdata)
            else:
                functional_graph = fdata

    report = run_checks(nodes_by_label, functional_graph=functional_graph)

    output = json.dumps(report, indent=2, default=str)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
