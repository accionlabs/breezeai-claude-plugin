#!/usr/bin/env python3
"""
Build the persona->roles / outcome->modules metadata patch plan for the
functional graph, from the DB roles-and-permissions reconcile state.

Two subcommands, run in this order:

  plan     reconcile-state.json + nav_leaf_to_outcome.json  ->  plan.json
           (name-keyed: which roles belong to which persona, which modules
            belong to which outcome). No graph access needed.

  resolve  plan.json + nodes.json (Persona/Outcome nodes dumped from MCP)
           ->  patches.json (one entry per REAL node id) + a coverage report.

Usage:
    python3 build_patches.py plan \
        --state reconcile-state.json \
        --nav   nav_leaf_to_outcome.json \
        --out   plan.json

    python3 build_patches.py resolve \
        --plan  plan.json \
        --nodes nodes.json \
        --key   roles:modules \
        --out   patches.json

`--key` selects the payload shape settled by the probe (see SKILL.md step 3):
    roles:modules          -> data = {"roles": [...]}     / {"modules": [...]}
    metadata.roles:...     -> data = {"metadata": {"roles": [...]}}

nodes.json is whatever `Get_Functional_Nodes_By_Label` returned, in any of:
    {"personas": [...], "outcomes": [...]}          (preferred)
    {"Persona": [...],  "Outcome": [...]}
each list item needing at least `id` plus `persona` / `outcome` (or `nameKey`).

Nothing here writes to Breeze. It only produces JSON for the agent to apply.
"""

import argparse
import json
import sys
from collections import defaultdict


def norm(s):
    """Same normalization Breeze uses for nameKey: trim + lowercase."""
    return (s or "").strip().lower()


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(args):
    state = json.load(open(args.state))
    nav = json.load(open(args.nav))

    report = {"warnings": []}

    # ---- persona -> roles ------------------------------------------------
    # Source: bindings.pairs (role -> persona). bindings.unbound_roles are
    # unbound BY DESIGN (zero-grant roles, or roles whose persona was deleted)
    # and must never be re-attached.
    bindings = state.get("bindings", {})
    pairs = bindings.get("pairs", [])
    if not pairs:
        sys.exit("ERROR: bindings.pairs is empty — nothing to map. Wrong state file?")

    unbound = {p["role"] for p in bindings.get("unbound_roles", [])}
    deleted_personas = {norm(p["persona"]) for p in bindings.get("unbound_personas", [])}

    persona_roles = defaultdict(set)
    needs_confirmation = []
    for p in pairs:
        role, persona = p["role"], p["persona"]
        if role in unbound:
            report["warnings"].append(
                f"role '{role}' appears in bindings.pairs AND unbound_roles — skipped (unbound wins)")
            continue
        if norm(persona) in deleted_personas:
            report["warnings"].append(
                f"pair {role} -> {persona}: persona is listed as deleted/unbound — skipped")
            continue
        persona_roles[persona].add(role)
        if p.get("needs_confirmation"):
            needs_confirmation.append({"role": role, "persona": persona,
                                       "score": p.get("score"),
                                       "evidence": p.get("evidence")})

    personas = [{"persona": name,
                 "nameKey": norm(name),
                 "roles": sorted(persona_roles[name])}
                for name in sorted(persona_roles)]

    # ---- outcome -> modules ---------------------------------------------
    # MANY-TO-ONE: several nav leaves (each with its own module) can point at
    # the same outcome, e.g. "Session (catalog)"/PROGRAM and
    # "Session (Admin)"/SESSION both -> "Manage Session Types".
    # Accumulate into a set; never assign.
    outcome_modules = defaultdict(set)
    outcome_leaves = defaultdict(list)
    dead_leaves = []
    for leaf in nav.get("leaves", []):
        outcome, module = leaf.get("outcome"), leaf.get("module")
        if not outcome:
            dead_leaves.append({"label": leaf.get("label"), "module": module,
                                "note": leaf.get("_note")})
            continue
        if not module:
            report["warnings"].append(f"leaf '{leaf.get('label')}' has an outcome but no module — skipped")
            continue
        outcome_modules[outcome].add(module)
        outcome_leaves[outcome].append(leaf.get("label"))

    outcomes = [{"outcome": name,
                 "nameKey": norm(name),
                 "modules": sorted(outcome_modules[name]),
                 "from_leaves": sorted(outcome_leaves[name])}
                for name in sorted(outcome_modules)]

    plan = {
        "source": {"state": args.state, "nav": args.nav,
                   "project_uuid_in_state": state.get("meta", {}).get("project", {}).get("uuid")},
        "personas": personas,
        "outcomes": outcomes,
        "report": {
            "personas_with_roles": len(personas),
            "roles_mapped": sum(len(p["roles"]) for p in personas),
            "roles_deliberately_unbound": sorted(unbound),
            "pairs_needing_confirmation": needs_confirmation,
            "outcomes_with_modules": len(outcomes),
            "multi_module_outcomes": [o["outcome"] for o in outcomes if len(o["modules"]) > 1],
            "nav_leaves_total": len(nav.get("leaves", [])),
            "nav_leaves_dead_no_outcome": dead_leaves,
            "warnings": report["warnings"],
        },
    }

    json.dump(plan, open(args.out, "w"), indent=2)
    r = plan["report"]
    print(f"plan -> {args.out}")
    print(f"  personas: {r['personas_with_roles']} carrying {r['roles_mapped']} roles "
          f"({len(r['roles_deliberately_unbound'])} roles intentionally unbound)")
    print(f"  outcomes: {r['outcomes_with_modules']} from {r['nav_leaves_total']} nav leaves "
          f"({len(r['nav_leaves_dead_no_outcome'])} leaves have no outcome — dead modules)")
    if r["multi_module_outcomes"]:
        print(f"  outcomes carrying >1 module: {', '.join(r['multi_module_outcomes'])}")
    if r["pairs_needing_confirmation"]:
        print(f"  !! {len(r['pairs_needing_confirmation'])} role->persona pairs flagged "
              f"needs_confirmation — show these to the user before applying")
    for w in r["warnings"]:
        print(f"  WARN: {w}")


# --------------------------------------------------------------------------
# resolve
# --------------------------------------------------------------------------

def _nodes_for(nodes, *keys):
    for k in keys:
        if k in nodes and isinstance(nodes[k], list):
            return nodes[k]
    return []


def _index(rows, name_field):
    """nameKey -> [node ids]. One name can own SEVERAL ids (the same outcome
    exists under multiple personas), so this is a list, never a scalar."""
    idx = defaultdict(list)
    for row in rows:
        key = norm(row.get("nameKey") or row.get(name_field))
        if not key:
            continue
        if row.get("id") is None:
            continue
        idx[key].append(str(row["id"]))
    return idx


def cmd_resolve(args):
    plan = json.load(open(args.plan))
    nodes = json.load(open(args.nodes))

    persona_rows = _nodes_for(nodes, "personas", "Persona", "persona")
    outcome_rows = _nodes_for(nodes, "outcomes", "Outcome", "outcome")

    if not persona_rows:
        sys.exit("ERROR: nodes.json contains 0 Persona nodes. Either the project has an "
                 "empty functional graph or the wrong uuid was used. Refusing to proceed — "
                 "writing 0 nodes is not success.")

    persona_key, outcome_key = args.key.split(":", 1)

    def wrap(key, values):
        """key is either 'roles'/'modules' or 'metadata.roles'/'metadata.modules'."""
        if "." in key:
            outer, inner = key.split(".", 1)
            return {outer: {inner: values}}
        return {key: values}

    p_idx = _index(persona_rows, "persona")
    o_idx = _index(outcome_rows, "outcome")

    patches = []
    unmatched_personas, unmatched_outcomes = [], []
    multi_id_outcomes = []

    for p in plan["personas"]:
        ids = p_idx.get(p["nameKey"], [])
        if not ids:
            unmatched_personas.append(p["persona"])
            continue
        for nid in ids:
            patches.append({"label": "Persona", "node_id": nid, "name": p["persona"],
                            "data": wrap(persona_key, p["roles"])})

    for o in plan["outcomes"]:
        ids = o_idx.get(o["nameKey"], [])
        if not ids:
            unmatched_outcomes.append(o["outcome"])
            continue
        if len(ids) > 1:
            multi_id_outcomes.append({"outcome": o["outcome"], "node_ids": ids})
        for nid in ids:
            patches.append({"label": "Outcome", "node_id": nid, "name": o["outcome"],
                            "data": wrap(outcome_key, o["modules"])})

    planned_persona_keys = {p["nameKey"] for p in plan["personas"]}
    planned_outcome_keys = {o["nameKey"] for o in plan["outcomes"]}
    graph_personas_untouched = sorted(
        {norm(r.get("nameKey") or r.get("persona")) for r in persona_rows} - planned_persona_keys)
    graph_outcomes_untouched = sorted(
        {norm(r.get("nameKey") or r.get("outcome")) for r in outcome_rows} - planned_outcome_keys)

    out = {
        "key_shape": args.key,
        "patches": patches,
        "coverage": {
            "graph_personas": len(persona_rows),
            "graph_outcomes": len(outcome_rows),
            "persona_patches": sum(1 for x in patches if x["label"] == "Persona"),
            "outcome_patches": sum(1 for x in patches if x["label"] == "Outcome"),
            "planned_but_not_in_graph_personas": unmatched_personas,
            "planned_but_not_in_graph_outcomes": unmatched_outcomes,
            "in_graph_but_no_mapping_personas": graph_personas_untouched,
            "in_graph_but_no_mapping_outcomes": graph_outcomes_untouched,
            "outcomes_hit_under_multiple_personas": multi_id_outcomes,
        },
    }
    json.dump(out, open(args.out, "w"), indent=2)

    c = out["coverage"]
    print(f"patches -> {args.out}  ({len(patches)} update calls, shape '{args.key}')")
    print(f"  Persona: {c['persona_patches']} patches over {c['graph_personas']} graph personas")
    print(f"  Outcome: {c['outcome_patches']} patches over {c['graph_outcomes']} graph outcomes")
    if multi_id_outcomes:
        print(f"  {len(multi_id_outcomes)} outcome names exist under several personas "
              f"— every id gets patched")
    if unmatched_personas:
        print(f"  !! planned personas NOT found in graph ({len(unmatched_personas)}): "
              f"{', '.join(unmatched_personas)}")
    if unmatched_outcomes:
        print(f"  !! planned outcomes NOT found in graph ({len(unmatched_outcomes)}): "
              f"{', '.join(unmatched_outcomes)}")
    print(f"  left untouched: {len(graph_personas_untouched)} personas, "
          f"{len(graph_outcomes_untouched)} outcomes (no mapping in the source files)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="build the name-keyed mapping plan")
    p.add_argument("--state", required=True)
    p.add_argument("--nav", required=True)
    p.add_argument("--out", default="plan.json")
    p.set_defaults(func=cmd_plan)

    r = sub.add_parser("resolve", help="join the plan against real graph node ids")
    r.add_argument("--plan", required=True)
    r.add_argument("--nodes", required=True)
    r.add_argument("--key", default="roles:modules",
                   help="persona_key:outcome_key, e.g. 'roles:modules' or "
                        "'metadata.roles:metadata.modules'")
    r.add_argument("--out", default="patches.json")
    r.set_defaults(func=cmd_resolve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
