#!/usr/bin/env python3
"""
Backend Flow-Structuring Agent — payload validators.

Reads a sub-agent response object from stdin: { "payload": {...}, "audit": {...} }
Extracts the "payload" field (and "audit" for the coverage pass) and runs one of
several validation passes.

NOTE: These are standalone debugging helpers. The skill does NOT invoke them —
the backend-flow-structuring-agent self-validates in Phase 6. Use these only for
manual inspection of be_ep{NN}_{name}.json files on disk.

Exit codes:
  0 — pass (or warning-only)
  2 — fail
  3 — bootstrap error (missing dependency, missing file, etc.)

Usage:
  python3 validate.py schema                                  < response.json
  python3 validate.py rule-a                                  < response.json
  python3 validate.py persona                                 < response.json
  python3 validate.py citations  --repo-name construction-api < response.json
  python3 validate.py coverage                                < response.json

All commands emit a single JSON object to stdout:
  { "ok": bool, "errors": [...], "warnings": [...], "stats": {...} }
"""

import argparse
import json
import os
import re
import sys

try:
    from jsonschema import Draft202012Validator
except ImportError:
    print(json.dumps({
        "ok": False,
        "errors": [{
            "message": "jsonschema package not installed.",
            "fix": "pip install -r " + os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "requirements.txt"
            )
        }],
        "bootstrap_error": True,
    }))
    sys.exit(3)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Backend side-effect verbs — the first word of an action whose presence
# requires either apis[] OR a DB/ES/S3 identifier in the description.
SIDE_EFFECT_VERBS = {
    "receive", "publish", "consume", "send", "submit", "persist", "save",
    "insert", "update", "delete", "index", "upload", "download", "fetch",
    "query", "push", "pull", "forward", "notify", "invoke", "call",
    "resolve", "retrieve", "sync", "import", "export",
}

ALLOWED_PERSONAS = {"system", "external system"}

# Heuristic markers that a description names a DB / ES / S3 / queue identifier.
# Imperfect by design — a debugging sanity check, not the agent's Phase 6.
IDENTIFIER_PATTERNS = [
    r"\bRepository\b",
    r"\btable\b",
    r"\bentity\b",
    r"\bindex\b",
    r"\bbucket\b",
    r"\bcollection\b",
    r"s3://",
    r"sqs://",
    r"kafka://",
    r"rabbit://",
    r"->",
    r"→",
]

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(SKILL_ROOT, "schemas", "upsert.schema.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_full():
    """Read stdin, parse JSON, return the full {payload, audit} object."""
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        emit({"ok": False, "errors": [{"message": f"stdin is not valid JSON: {e}"}]})
        sys.exit(2)


def get_payload(data):
    """Extract the payload from a {payload, audit} wrapper, else assume top-level."""
    if isinstance(data, dict) and "payload" in data and isinstance(data["payload"], dict):
        return data["payload"]
    return data


def walk_actions(payload):
    """Yield (persona, outcome, scenario, step, action) tuples."""
    for persona in payload.get("personas", []) or []:
        for outcome in persona.get("outcomes", []) or []:
            for scenario in outcome.get("scenarios", []) or []:
                for step in scenario.get("steps", []) or []:
                    for action in step.get("actions", []) or []:
                        yield persona, outcome, scenario, step, action


def emit(result):
    print(json.dumps(result, indent=2))


def has_identifier(description):
    text = description or ""
    return any(re.search(p, text) for p in IDENTIFIER_PATTERNS)


# ---------------------------------------------------------------------------
# Subcommand: schema
# ---------------------------------------------------------------------------

def cmd_schema():
    payload = get_payload(load_full())

    if not os.path.exists(SCHEMA_PATH):
        emit({"ok": False, "errors": [{"message": f"schema file not found at {SCHEMA_PATH}"}]})
        sys.exit(3)

    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    validator = Draft202012Validator(schema)
    errors = []
    for err in validator.iter_errors(payload):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append({
            "path": path,
            "message": err.message,
            "schema_path": ".".join(str(p) for p in err.schema_path),
        })

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: rule-a  (apis[] OR DB/ES/S3 identifier for side-effect verbs)
# ---------------------------------------------------------------------------

def cmd_rule_a():
    payload = get_payload(load_full())
    errors = []

    for persona, outcome, scenario, step, action in walk_actions(payload):
        action_name = (action.get("action") or "").strip()
        if not action_name:
            continue

        first_word = re.split(r"\s+", action_name)[0].lower()
        if first_word in SIDE_EFFECT_VERBS:
            apis = action.get("apis") or []
            if len(apis) == 0 and not has_identifier(action.get("description")):
                errors.append({
                    "persona":  persona.get("persona"),
                    "outcome":  outcome.get("outcome"),
                    "scenario": scenario.get("scenario"),
                    "step":     step.get("step"),
                    "action":   action_name,
                    "message":  (f"Side-effect-verb action '{first_word.title()}' must have "
                                 "either a non-empty apis[] or a DB/ES/S3 identifier "
                                 "(Repository, table, index, bucket, →) in its description"),
                })

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: persona  (only System / External System allowed)
# ---------------------------------------------------------------------------

def cmd_persona():
    payload = get_payload(load_full())
    errors = []

    personas = payload.get("personas", []) or []
    if len(personas) != 1:
        errors.append({"message": f"backend payload must have exactly 1 persona, found {len(personas)}"})

    for persona in personas:
        name = (persona.get("persona") or "").strip()
        if name.lower() not in ALLOWED_PERSONAS:
            errors.append({
                "persona": name,
                "message": "backend pass persona must be 'System' or 'External System' — "
                           "never a human role",
            })

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: citations
# ---------------------------------------------------------------------------

def cmd_citations(repo_name):
    payload = get_payload(load_full())
    errors = []
    prefix = repo_name.rstrip("/") + "/"

    def check_one(cites, location):
        for c in cites or []:
            ref = c.get("reference") or ""
            if not ref.startswith(prefix):
                errors.append({
                    "location":  location,
                    "reference": ref,
                    "expected_prefix": prefix,
                    "message":   f"Citation reference must start with '{prefix}'",
                })

    for persona in payload.get("personas", []) or []:
        check_one(persona.get("citations"), f"persona[{persona.get('persona')}]")
        for outcome in persona.get("outcomes", []) or []:
            check_one(outcome.get("citations"), f"outcome[{outcome.get('outcome')}]")
            for scenario in outcome.get("scenarios", []) or []:
                check_one(scenario.get("citations"), f"scenario[{scenario.get('scenario')}]")

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: coverage  (side-effect coverage — warning-only, never blocks)
# ---------------------------------------------------------------------------

def cmd_coverage():
    data = load_full()
    audit = data.get("audit", {}) if isinstance(data, dict) else {}
    side_effects = audit.get("sideEffects", []) or []

    total = len(side_effects)
    matched = sum(1 for s in side_effects if s.get("matchedToAction"))
    ratio = matched / total if total > 0 else 1.0

    warnings = []
    if total > 0 and ratio < 0.90:
        warnings.append({
            "message": f"side-effect coverage {ratio:.0%} below 90% threshold",
            "matched": matched,
            "total":   total,
            "unmatched": [s.get("identifier") for s in side_effects if not s.get("matchedToAction")],
        })

    emit({
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "stats": {
            "side_effects_total":   total,
            "side_effects_matched": matched,
            "coverage_ratio":       round(ratio, 3),
        },
    })
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="backend pass payload validators")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("schema",  help="validate payload against upsert.schema.json")
    sub.add_parser("rule-a",  help="every side-effect-verb action has apis[] or a DB/ES/S3 identifier")
    sub.add_parser("persona", help="exactly one persona, System or External System only")

    p_cite = sub.add_parser("citations", help="every citation.reference starts with <repo_name>/")
    p_cite.add_argument("--repo-name", required=True)

    sub.add_parser("coverage", help="side-effect coverage from audit.sideEffects (warning only)")

    args = parser.parse_args()

    if args.cmd == "schema":
        cmd_schema()
    elif args.cmd == "rule-a":
        cmd_rule_a()
    elif args.cmd == "persona":
        cmd_persona()
    elif args.cmd == "citations":
        cmd_citations(args.repo_name)
    elif args.cmd == "coverage":
        cmd_coverage()
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
