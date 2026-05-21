#!/usr/bin/env python3
"""
Flow-Structuring Agent v2 — payload validators.

Reads a sub-agent response object from stdin: { "payload": {...}, "audit": {...} }
Extracts the "payload" field and runs one of several validation passes.

Exit codes:
  0 — pass (or warning-only)
  2 — fail
  3 — bootstrap error (missing dependency, missing file, etc.)

Usage:
  python3 validate.py schema                                          < response.json
  python3 validate.py rule-a                                          < response.json
  python3 validate.py forbidden                                       < response.json
  python3 validate.py citations  --repo-name BREEZE.AI_WEBUI          < response.json
  python3 validate.py coverage   --seed-file /abs/path/to/page.tsx    < response.json

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

FORBIDDEN_WORDS = {
    "click", "tap", "swipe", "hover", "scroll", "drag", "drop", "toggle",
    "button", "dropdown", "modal", "dialog", "popup", "panel", "checkbox",
    "radio", "slider", "tooltip", "menu", "sidebar", "navbar", "tab", "icon",
}

NETWORK_VERBS = {
    "submit", "generate", "upload", "download", "delete", "save", "send",
    "fetch", "retrieve", "publish", "persist", "sync", "import", "export",
    "share", "subscribe", "unsubscribe", "authenticate", "authorize",
    "refresh", "poll",
}

# Mechanical JSX widget patterns for the coverage check.
# Imperfect by design — used only as a sanity-check ratio.
WIDGET_PATTERNS = [
    r"<Button\b",
    r"<IconButton\b",
    r"<Input\b",
    r"<TextField\b",
    r"<TextArea\b",
    r"<Textarea\b",
    r"<Select\b",
    r"<MenuItem\b",
    r"<Checkbox\b",
    r"<Switch\b",
    r"<Toggle\b",
    r"<Radio\b",
    r"<Autocomplete\b",
    r"<DatePicker\b",
    r"<TimePicker\b",
    r"<Slider\b",
    r"<Tabs\b",
    r"<Stepper\b",
    r"<Dialog\b",
    r"<Drawer\b",
    r"<Sheet\b",
    r"<Popover\b",
    r"<DropdownMenu\b",
    r"<ContextMenu\b",
    r"<Form\b",
]

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(SKILL_ROOT, "schemas", "upsert.schema.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_input():
    """Read stdin, parse JSON, return the payload (extract from {payload, audit} if wrapped)."""
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        emit({
            "ok": False,
            "errors": [{"message": f"stdin is not valid JSON: {e}"}],
        })
        sys.exit(2)
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


# ---------------------------------------------------------------------------
# Subcommand: schema
# ---------------------------------------------------------------------------

def cmd_schema():
    payload = load_input()

    if not os.path.exists(SCHEMA_PATH):
        emit({
            "ok": False,
            "errors": [{"message": f"schema file not found at {SCHEMA_PATH}"}],
        })
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
# Subcommand: rule-a
# ---------------------------------------------------------------------------

def cmd_rule_a():
    payload = load_input()
    errors = []

    for persona, outcome, scenario, step, action in walk_actions(payload):
        action_name = (action.get("action") or "").strip()
        if not action_name:
            continue

        first_word = re.split(r"\s+", action_name)[0].lower()
        if first_word in NETWORK_VERBS:
            apis = action.get("apis") or []
            if len(apis) == 0:
                errors.append({
                    "persona":  persona.get("persona"),
                    "outcome":  outcome.get("outcome"),
                    "scenario": scenario.get("scenario"),
                    "step":     step.get("step"),
                    "action":   action_name,
                    "message":  f"Network-verb action '{first_word.title()}' must have a non-empty apis[]",
                })

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: forbidden
# ---------------------------------------------------------------------------

def cmd_forbidden():
    payload = load_input()
    errors = []

    for persona, outcome, scenario, step, action in walk_actions(payload):
        persona_name = (persona.get("persona") or "").lower().strip()
        # FORBIDDEN words apply only to human personas. System / External System
        # personas legitimately use technical vocabulary.
        if persona_name in ("system", "external system"):
            continue

        action_name = (action.get("action") or "").lower()
        words = set(re.findall(r"\b[a-z]+\b", action_name))
        hits = sorted(words & FORBIDDEN_WORDS)
        if hits:
            errors.append({
                "persona":  persona.get("persona"),
                "scenario": scenario.get("scenario"),
                "step":     step.get("step"),
                "action":   action.get("action"),
                "forbidden_words": hits,
                "message":  f"Human persona action contains FORBIDDEN UI words: {hits}",
            })

    ok = len(errors) == 0
    emit({"ok": ok, "errors": errors, "warnings": []})
    sys.exit(0 if ok else 2)


# ---------------------------------------------------------------------------
# Subcommand: citations
# ---------------------------------------------------------------------------

def cmd_citations(repo_name):
    payload = load_input()
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
# Subcommand: coverage (warning-only — never blocks upsert)
# ---------------------------------------------------------------------------

def cmd_coverage(seed_file):
    payload = load_input()

    if not os.path.exists(seed_file):
        emit({
            "ok": True,  # coverage is warning-only
            "errors": [],
            "warnings": [{"message": f"seed file not found: {seed_file} — coverage skipped"}],
            "stats": {},
        })
        sys.exit(0)

    with open(seed_file, encoding="utf-8", errors="ignore") as f:
        content = f.read()

    widget_hits = {}
    total_widgets = 0
    for pat in WIDGET_PATTERNS:
        n = len(re.findall(pat, content))
        if n > 0:
            widget_hits[pat] = n
            total_widgets += n

    action_count = sum(1 for _ in walk_actions(payload))
    # Coverage is the ratio of (actions emitted) / (widgets seen). A ratio
    # below 0.9 doesn't mean failure — it's a hint that fields may have been
    # missed. The skill logs the warning and keeps going.
    ratio = action_count / total_widgets if total_widgets > 0 else 1.0

    warnings = []
    if ratio < 0.90 and total_widgets > 0:
        warnings.append({
            "message":  f"JSX coverage {ratio:.0%} below 90% threshold",
            "action_count":   action_count,
            "widget_count":   total_widgets,
            "widget_hits":    widget_hits,
        })

    emit({
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "stats": {
            "action_count":   action_count,
            "widget_count":   total_widgets,
            "coverage_ratio": round(ratio, 3),
            "widget_hits":    widget_hits,
        },
    })
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="v2 payload validators")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("schema",    help="validate payload against upsert.schema.json")
    sub.add_parser("rule-a",    help="every network-verb action has apis[]")
    sub.add_parser("forbidden", help="no FORBIDDEN UI words in human-persona action names")

    p_cite = sub.add_parser("citations", help="every citation.reference starts with <repo_name>/")
    p_cite.add_argument("--repo-name", required=True)

    p_cov = sub.add_parser("coverage", help="JSX widget coverage (warning only)")
    p_cov.add_argument("--seed-file", required=True)

    args = parser.parse_args()

    if args.cmd == "schema":
        cmd_schema()
    elif args.cmd == "rule-a":
        cmd_rule_a()
    elif args.cmd == "forbidden":
        cmd_forbidden()
    elif args.cmd == "citations":
        cmd_citations(args.repo_name)
    elif args.cmd == "coverage":
        cmd_coverage(args.seed_file)
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
