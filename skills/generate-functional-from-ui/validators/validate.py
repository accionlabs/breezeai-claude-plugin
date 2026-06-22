#!/usr/bin/env python3
"""UI pass validator — SHIM. Delegates to the single source of truth at
skills/shared/functional/validate.py (ADR 0001). No rules live here; word lists are
in shared/functional/verbs.json, the schema in shared/functional/upsert.schema.json.

The UI pass writes only human personas, so this shim injects `--kind human` for the
kind-taking checks when the caller omits it (rule-a = network verbs, apis[] required;
coverage = JSX widget seed-file ratio). Subcommands available: schema, rule-a,
forbidden, citations --repo-name, coverage --seed-file, api-urls --repo-root, plus the
shared field-coverage / citation-completeness / atomicity.
"""
import os, sys, runpy

SHARED = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "..", "shared", "functional"))
DEFAULT_KIND = "human"
KIND_CHECKS = {"rule-a", "persona", "coverage"}

argv = sys.argv[1:]
if argv and argv[0] in KIND_CHECKS and "--kind" not in argv:
    argv += ["--kind", DEFAULT_KIND]

shared_validate = os.path.join(SHARED, "validate.py")
sys.argv = [shared_validate] + argv
sys.path.insert(0, SHARED)
runpy.run_path(shared_validate, run_name="__main__")
