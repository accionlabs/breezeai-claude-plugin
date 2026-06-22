#!/usr/bin/env python3
"""Backend pass validator — SHIM. Delegates to the single source of truth at
skills/shared/functional/validate.py (ADR 0001). This file holds NO rules of its
own; word lists live in shared/functional/verbs.json, the schema in
shared/functional/upsert.schema.json.

The backend pass writes only System / External System personas, so this shim injects
`--kind system` for the kind-taking checks when the caller omits it — preserving the
old behaviour (rule-a = side-effect verbs + identifier fallback; persona asserts
System/External; coverage = audit.sideEffects ratio). Existing agent invocations
(`validate.py rule-a`, `validate.py persona`, `validate.py coverage`) keep working
unchanged.
"""
import os, sys, runpy

SHARED = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "shared", "functional"))
DEFAULT_KIND = "system"
KIND_CHECKS = {"rule-a", "persona", "coverage"}

argv = sys.argv[1:]
if argv and argv[0] in KIND_CHECKS and "--kind" not in argv:
    argv += ["--kind", DEFAULT_KIND]

shared_validate = os.path.join(SHARED, "validate.py")
sys.argv = [shared_validate] + argv
sys.path.insert(0, SHARED)
runpy.run_path(shared_validate, run_name="__main__")
