#!/usr/bin/env python3
"""P3 pass validator — SHIM. Delegates to the single source of truth at
skills/shared/functional/validate.py (ADR 0001). No rules live here; word lists are
in shared/functional/verbs.json, the schema in shared/functional/upsert.schema.json.

P3 builds BOTH halves and runs the validator once per half-file (one persona each), so
this shim injects NO static --kind: the shared engine auto-detects human vs system
from the half's single persona for rule-a/coverage, and the agent passes --kind
explicitly on the `persona` assertion. Subcommands: schema, rule-a, forbidden,
persona --kind, citations --repo-name, field-coverage, citation-completeness, atomicity.
"""
import os, sys, runpy

SHARED = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "shared", "functional"))

shared_validate = os.path.join(SHARED, "validate.py")
sys.argv = [shared_validate] + sys.argv[1:]
sys.path.insert(0, SHARED)
runpy.run_path(shared_validate, run_name="__main__")
