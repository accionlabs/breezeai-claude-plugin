#!/usr/bin/env python3
"""Unified functional-graph validator — the ONE engine for ui / backend / metadata / aspx.

Reads a {payload, audit} object (or a bare payload) from STDIN and runs ONE check,
returning {"ok": bool, "errors": [...], "warnings": [...]} on STDOUT.

Word lists come from verbs.json (the single source of truth) — never inline them here.
Persona-conditional checks take --kind {human, system}; persona-agnostic ones don't.

Hard gates exit 2 when ok is False:   schema, rule-a, forbidden, persona,
                                       citations, field-coverage, citation-completeness,
                                       path-linked, descriptions
Advisory checks always exit 0:         coverage, atomicity, api-urls

Usage:
  cat payload.json | validate.py schema
  cat payload.json | validate.py rule-a --kind human|system
  cat payload.json | validate.py forbidden
  cat payload.json | validate.py persona --kind human|system
  cat payload.json | validate.py citations --repo-name <repo>
  cat payload.json | validate.py field-coverage
  cat payload.json | validate.py citation-completeness
  cat payload.json | validate.py coverage --kind system            # audit.sideEffects ratio
  cat payload.json | validate.py coverage --kind human --seed-file jsx.txt
  cat payload.json | validate.py atomicity
  cat payload.json | validate.py api-urls --repo-root <path>
  cat payload.json | validate.py path-linked                       # verb+route/URI in action name ⇒ apis[] required
  cat payload.json | validate.py descriptions                      # every scenario AND action must have a non-empty description
  cat body.json    | validate.py wrapper                           # HTTP body must be {payload,project:{uuid,name},skipStepAndAction} not bare {personas:[…]}
"""
import sys, os, json, re, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
VERBS = json.load(open(os.path.join(HERE, "verbs.json"), encoding="utf-8"))
SCHEMA_PATH = os.path.join(HERE, "upsert.schema.json")

FORBIDDEN_UI_WORDS   = set(VERBS["forbidden_ui_words"])
NETWORK_VERBS        = set(VERBS["network_verbs"])
SIDE_EFFECT_VERBS    = set(VERBS["side_effect_verbs"])
INPUT_VERBS          = set(VERBS["input_verbs"])
SYSTEM_PERSONAS      = set(VERBS["system_personas"])
FORBIDDEN_PERSONAS   = set(VERBS["forbidden_persona_names"])
IDENTIFIER_PATTERNS  = VERBS["identifier_patterns"]
WIDGET_PATTERNS      = VERBS["widget_patterns"]

# A route / broker-URI / cron token spelled out in an action name or description.
# Deliberately conservative — matches HTTP "METHOD /path", a scheme://… URI
# (http/sqs/kafka/rabbit/…), a cron:<expr>, or a method-less API route
# (/api, /v1, /internal, /admin, /webhooks, /graphql). It does NOT match bare
# filesystem paths (/tmp, /var, ./x) so local file effects are not false-flagged.
ROUTE_URI_RE = re.compile(
    r"(?:\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/\S+)"
    r"|(?:\b(?:https?|sqs|sns|kafka|rabbit|amqp|servicebus|pubsub|grpc|wss?|s3)://\S+)"
    r"|(?:\bcron:\S+)"
    r"|(?:(?:^|\s)/(?:api|internal|admin|webhooks?|graphql|v\d+)\b[\w\-./{}:]*)",
    re.I,
)


# ---------------------------------------------------------------- input
def load_full():
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except Exception as e:
        emit(False, [f"STDIN is not valid JSON: {e}"]); sys.exit(2)

def get_payload(full):
    if isinstance(full, dict) and isinstance(full.get("payload"), dict):
        return full["payload"]
    return full

def get_audit(full):
    if isinstance(full, dict) and isinstance(full.get("audit"), dict):
        return full["audit"]
    return {}

def personas(payload):
    return payload.get("personas", []) if isinstance(payload, dict) else []

def iter_actions(payload):
    """Yield (persona_name_lower, action_dict) for every action."""
    for p in personas(payload):
        pname = str(p.get("persona", "")).strip().lower()
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                for st in s.get("steps", []):
                    for a in st.get("actions", []):
                        yield pname, a

def first_word(name):
    return re.split(r"\s+", str(name).strip())[0].lower() if name else ""

def detect_kind(payload):
    """Auto-detect persona-kind from the single persona (schema enforces exactly 1).
    Used when --kind is omitted so existing agent calls (which pass no --kind) keep
    working. A per-skill shim may inject a strict --kind to ASSERT a half instead."""
    ps = personas(payload)
    if ps and str(ps[0].get("persona", "")).strip().lower() in SYSTEM_PERSONAS:
        return "system"
    return "human"

def emit(ok, errors=None, warnings=None):
    print(json.dumps({"ok": bool(ok), "errors": errors or [], "warnings": warnings or []}, indent=2))

def finish(ok, errors=None, warnings=None, hard=True):
    emit(ok, errors, warnings)
    sys.exit(0 if (ok or not hard) else 2)


# ---------------------------------------------------------------- checks
def cmd_schema(full, args):
    payload = get_payload(full)
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        # exit 3 — dependency unavailable. Sub-agents treat this as "degrade to prose
        # checks", NOT as a validation failure (exit 2). Do not change this code.
        emit(False, ["jsonschema not installed (pip install jsonschema) — degrade to prose checks"])
        sys.exit(3)
    schema = json.load(open(SCHEMA_PATH, encoding="utf-8"))
    errs = []
    for e in sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.path)):
        errs.append({"path": "/".join(str(x) for x in e.path), "message": e.message})
    finish(not errs, errs)

def cmd_rule_a(full, args):
    payload = get_payload(full)
    kind = args.kind
    verbs = NETWORK_VERBS if kind == "human" else SIDE_EFFECT_VERBS
    allow_identifier = (kind == "system")
    errs = []
    for pname, a in iter_actions(payload):
        if first_word(a.get("action")) not in verbs:
            continue
        if a.get("apis"):
            continue
        if allow_identifier and has_identifier(a.get("description") or ""):
            continue
        hint = ("add apis[] (REST/GraphQL/Event/...) OR name a Repository/table/index in description"
                if allow_identifier else "add a non-empty apis[] block")
        errs.append({"action": a.get("action"), "fix": hint})
    finish(not errs, errs)

def has_identifier(desc):
    return any(re.search(p, desc) for p in IDENTIFIER_PATTERNS)

def cmd_forbidden(full, args):
    payload = get_payload(full)
    errs = []
    for pname, a in iter_actions(payload):
        if pname in SYSTEM_PERSONAS:        # forbidden-UI-words gate the HUMAN half only
            continue
        name = str(a.get("action", "")).lower()
        hits = [w for w in FORBIDDEN_UI_WORDS if re.search(r"\b" + re.escape(w) + r"\b", name)]
        if hits:
            errs.append({"action": a.get("action"), "forbidden": sorted(hits)})
    finish(not errs, errs)

def cmd_persona(full, args):
    payload = get_payload(full)
    ps = personas(payload)
    errs = []
    if len(ps) != 1:
        errs.append(f"exactly 1 persona required, found {len(ps)}")
        finish(False, errs)
    name = str(ps[0].get("persona", "")).strip()
    low = name.lower()
    if args.kind == "system":
        if low not in SYSTEM_PERSONAS:
            errs.append(f"system kind requires persona in {sorted(SYSTEM_PERSONAS)}, got '{name}'")
    else:  # human
        if low in SYSTEM_PERSONAS:
            errs.append(f"human kind must NOT be System/External System, got '{name}'")
        name_words = set(re.findall(r"[a-z]+", low))
        bad = name_words & FORBIDDEN_PERSONAS
        if bad:
            errs.append(f"persona '{name}' uses forbidden tech name(s): {sorted(bad)}")
    finish(not errs, errs)

def cmd_citations(full, args):
    payload = get_payload(full)
    prefix = args.repo_name.rstrip("/") + "/"
    errs, warns = [], []
    # Citations belong ONLY on the SPECIFIC nodes (scenario / step / action). Outcome and
    # Persona are shared + merged by name across many EPs, so a citation there pollutes the
    # shared node — it is FORBIDDEN, not merely discouraged. Do not author a citations[] on
    # persona/outcome at all (omit the key). This is a HARD gate. (core.md §7.1.)
    #
    # Conversely, scenario / step / action MUST each carry at least one citation — the file
    # that flow / stage / operation came from. A missing citations[] on any of these is a
    # HARD failure (core.md §7.1 / §7.2). persona/outcome remain forbidden (never required).
    HIGH_LEVEL = {"persona", "outcome"}
    REQUIRED   = {"scenario", "step", "action"}
    # human-readable node name for the fix message
    NAMEKEY = {"scenario": "scenario", "step": "step", "action": "action"}
    def check(node, level):
        cites = node.get("citations", []) or []
        # (1) mandatory-presence on the specific levels
        if level in REQUIRED and len(cites) == 0:
            nm = node.get(NAMEKEY.get(level, level)) or node.get("name") or "?"
            errs.append({"level": level, "name": nm, "error": "missing_citation",
                         "fix": f"{level} '{nm}' has no citations[] — add at least one citation to the {level}: "
                                f"the source file (\"<repo>/<relative path>\") this {level} came from (core.md §7.1/§7.2). "
                                f"Do NOT satisfy this by citing the parent outcome/persona (forbidden)."})
        # (2) per-citation prefix + forbidden-placement checks
        for c in cites:
            ref = c.get("reference", "")
            if not ref.startswith(prefix):
                errs.append({"level": level, "reference": ref, "expected_prefix": prefix,
                             "fix": f"citation reference must start with '{prefix}' (the repo name); got '{ref}'"})
            if level in HIGH_LEVEL:
                errs.append({"level": level, "reference": ref,
                             "fix": "citations are forbidden on persona/outcome (shared nodes) — remove this citation; cite the scenario/step/action it describes instead (core.md §7.1)"})
    for p in personas(payload):
        check(p, "persona")
        for o in p.get("outcomes", []):
            check(o, "outcome")
            for s in o.get("scenarios", []):
                check(s, "scenario")
                for st in s.get("steps", []):
                    check(st, "step")
                    for a in st.get("actions", []):
                        check(a, "action")
    finish(not errs, errs, warns)

def _norm(s):
    return re.sub(r"\s+", "", str(s)).lower()

def cmd_field_coverage(full, args):
    payload = get_payload(full)
    declared = get_audit(full).get("declaredFields", [])
    if not declared:
        finish(True, warnings=["audit.declaredFields[] empty — field-coverage not asserted"], hard=False)
    blob = ""
    for pname, a in iter_actions(payload):
        blob += _norm(a.get("action")) + _norm(a.get("description") or "")
    missing = []
    for f in declared:
        label = _norm(f.get("label", ""))
        code  = _norm(f.get("code", ""))
        covered = (label and label in blob) or (code and code in blob)
        if not covered:
            missing.append({"code": f.get("code"), "label": f.get("label"), "source": f.get("source")})
    finish(not missing, missing)

def cmd_citation_completeness(full, args):
    payload = get_payload(full)
    files_read = get_audit(full).get("filesRead", [])
    if not files_read:
        finish(True, warnings=["audit.filesRead[] empty — citation-completeness not asserted"], hard=False)
    cited = set()
    def collect(node):
        for c in node.get("citations", []) or []:
            cited.add(re.sub(r".*/", "", c.get("reference", "")))
    # union across ALL levels — citing a file at action/step/scenario satisfies completeness
    for p in personas(payload):
        collect(p)
        for o in p.get("outcomes", []):
            collect(o)
            for s in o.get("scenarios", []):
                collect(s)
                for st in s.get("steps", []):
                    collect(st)
                    for a in st.get("actions", []):
                        collect(a)
    missing = [f for f in files_read if re.sub(r".*/", "", f) not in cited]
    finish(not missing, [{"read_but_uncited": f} for f in missing])

# ---- advisory ----
def cmd_atomicity(full, args):
    payload = get_payload(full)
    ps = personas(payload)
    if ps and all(str(p.get("persona", "")).strip().lower() in SYSTEM_PERSONAS for p in ps):
        finish(True, warnings=["all personas are System/External — atomicity skipped (per-field atomicity is human-only)"], hard=False)
    declared = get_audit(full).get("declaredFields", [])
    tagged = [f for f in declared if "editable" in f]
    if not tagged:
        finish(True, warnings=["declaredFields[] not tagged with 'editable' — atomicity advisory skipped"], hard=False)
    warns = []
    editable = [f for f in tagged if f.get("editable")]
    # input-verb actions: flag clubbing + apis on an entry action
    covered_codes = set()
    for pname, a in iter_actions(payload):
        if pname in SYSTEM_PERSONAS:
            continue
        if first_word(a.get("action")) not in INPUT_VERBS:
            continue
        blob = _norm(a.get("action")) + _norm(a.get("description") or "")
        refd = [f for f in editable if (_norm(f.get("label", "")) and _norm(f["label"]) in blob)
                or (_norm(f.get("code", "")) and _norm(f["code"]) in blob)]
        for f in refd:
            covered_codes.add(f.get("code"))
        if len(refd) > 1:
            warns.append({"clubbed_input_action": a.get("action"), "fields": [f.get("code") for f in refd]})
        if a.get("apis"):
            warns.append({"input_action_with_apis": a.get("action")})
    no_action = [f.get("code") for f in editable if f.get("code") not in covered_codes]
    if no_action:
        warns.append({"editable_fields_without_dedicated_action": no_action})
    finish(True, warnings=warns, hard=False)

def cmd_coverage(full, args):
    payload = get_payload(full)
    warns = []
    if args.kind == "system":
        se = get_audit(full).get("sideEffects", [])
        if not se:
            finish(True, warnings=["audit.sideEffects[] empty — coverage not asserted"], hard=False)
        matched = sum(1 for s in se if s.get("matchedToAction"))
        ratio = matched / len(se)
        if ratio < 0.90:
            unmatched = [s.get("identifier") for s in se if not s.get("matchedToAction")]
            warns.append({"side_effect_coverage": round(ratio, 3), "unmatched": unmatched})
    else:  # human — JSX widget seed-file
        if not args.seed_file or not os.path.exists(args.seed_file):
            finish(True, warnings=["--seed-file missing — JSX coverage not asserted"], hard=False)
        src = open(args.seed_file, encoding="utf-8", errors="ignore").read()
        total = sum(len(re.findall(p, src)) for p in WIDGET_PATTERNS)
        action_count = sum(1 for _ in iter_actions(payload))
        ratio = 1.0 if total == 0 else action_count / total
        if total > 0 and ratio < 0.90:
            warns.append({"jsx_coverage": round(ratio, 3), "widgets": total, "actions": action_count})
    finish(True, warnings=warns, hard=False)

def _url_needle(url):
    u = re.split(r"\s*\(", str(url))[0]
    u = re.split(r"[?#]", u)[0]
    segs = [s for s in u.split("/") if s and not s.startswith("{") and not s.startswith(":")]
    return "/".join(segs[-3:]) if segs else None

def cmd_api_urls(full, args):
    payload = get_payload(full)
    root = args.repo_root
    if not root or not os.path.isdir(root):
        finish(True, warnings=["--repo-root missing — api-urls not asserted"], hard=False)
    src = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("node_modules", ".git", "dist", "build")]
        for f in fn:
            if f.endswith((".js", ".jsx", ".ts", ".tsx", ".vue")):
                try:
                    src.append(open(os.path.join(dp, f), encoding="utf-8", errors="ignore").read())
                except Exception:
                    pass
    blob = "\n".join(src)
    warns = []
    for pname, a in iter_actions(payload):
        for api in a.get("apis", []) or []:
            needle = _url_needle(api.get("url", ""))
            if needle and needle not in blob:
                warns.append({"action": a.get("action"), "url": api.get("url"), "needle_not_found": needle})
    finish(True, warnings=warns, hard=False)


def _route_token(text):
    m = ROUTE_URI_RE.search(text or "")
    return m.group(0).strip() if m else None

def _route_needle(tok):
    """Reduce a matched route/URI token to a comparable needle for the apis[].url check."""
    t = re.sub(r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+", "", tok, flags=re.I).strip()
    t = re.split(r"[?#]", t)[0]
    if "://" in t:
        return t.lower().rstrip("/")          # brokers/URLs: compare whole URI
    segs = [s for s in t.split("/") if s and not s.startswith("{") and not s.startswith(":")]
    return ("/".join(segs[-2:])).lower() if segs else None

def cmd_path_linked(full, args):
    """HARD gate: an action whose first word is a network/side-effect verb AND that
    spells out a route / broker-URI / cron token MUST carry a non-empty apis[].
    (Soft warning if the named route isn't found in any apis[].url.) Persona-agnostic:
    catches `Receive POST /api/x` / `Publish sqs://q` left with apis=[] — the
    join-key drift that breaks human→system and system→system tracing."""
    payload = get_payload(full)
    verbs = NETWORK_VERBS | SIDE_EFFECT_VERBS
    errs, warns = [], []
    for pname, a in iter_actions(payload):
        name = a.get("action") or ""
        if first_word(name) not in verbs:
            continue
        tok = _route_token(name) or _route_token(a.get("description") or "")
        if not tok:
            continue
        apis = a.get("apis") or []
        if not apis:
            errs.append({"action": name, "path": tok,
                         "fix": "action names a route/URI but apis[] is empty — attach it as an apis[] entry {type, method, url}"})
            continue
        needle = _route_needle(tok)
        urls = " ".join(str(x.get("url", "")) for x in apis).lower()
        if needle and needle not in urls:
            warns.append({"action": name, "path": tok,
                          "note": "named route/URI not present in any apis[].url — verify the action links to the right interface"})
    finish(not errs, errs, warns)

def cmd_descriptions(full, args):
    """HARD gate: every SCENARIO and every ACTION must carry a non-empty `description`.
    (Scenario description is also schema-required; this additionally enforces it on every
    action — both halves. A null/blank/whitespace description fails.)"""
    payload = get_payload(full)
    def blank(d): return not (isinstance(d, str) and d.strip())
    errs = []
    for p in personas(payload):
        for o in p.get("outcomes", []):
            for s in o.get("scenarios", []):
                if blank(s.get("description")):
                    errs.append({"level": "scenario", "name": s.get("scenario"),
                                 "fix": "add a non-empty description (what the scenario accomplishes)"})
                for st in s.get("steps", []):
                    for a in st.get("actions", []):
                        if blank(a.get("description")):
                            errs.append({"level": "action", "name": a.get("action"),
                                         "fix": "add a non-empty description (field metadata / constraint / input→output of the operation)"})
    finish(not errs, errs)


def cmd_wrapper(full, args):
    """HARD gate: the upsert HTTP body must be the full wrapper shape
    { "payload": {…}, "project": {"uuid": "…", "name": "…"}, "skipStepAndAction": bool }
    not a bare { "personas": […] }. A bare payload returns HTTP 500 — the server cannot
    resolve the project. Run this on BODY_PATH (the file sent to curl), not on the
    internal {payload,audit} object used in Phase 6."""
    errs = []
    if not isinstance(full, dict):
        finish(False, [{"missing": "root", "fix": "body must be a JSON object"}])
        return
    if not isinstance(full.get("payload"), dict):
        errs.append({"missing": "payload",
                     "fix": "wrap personas: {\"payload\":{\"personas\":[...]},\"project\":{\"uuid\":\"…\",\"name\":\"…\"},\"skipStepAndAction\":false}"})
    proj = full.get("project")
    if not isinstance(proj, dict):
        errs.append({"missing": "project",
                     "fix": "add \"project\":{\"uuid\":\"<projectUuid>\",\"name\":\"<projectName>\"}"})
    else:
        if not (isinstance(proj.get("uuid"), str) and proj["uuid"].strip()):
            errs.append({"missing": "project.uuid", "fix": "project.uuid must be a non-empty string"})
        if not (isinstance(proj.get("name"), str) and proj["name"].strip()):
            errs.append({"missing": "project.name", "fix": "project.name must be a non-empty string"})
    if "skipStepAndAction" not in full:
        errs.append({"missing": "skipStepAndAction", "fix": "add \"skipStepAndAction\":false"})
    finish(not errs, errs)


COMMANDS = {
    "schema": cmd_schema, "rule-a": cmd_rule_a, "forbidden": cmd_forbidden,
    "persona": cmd_persona, "citations": cmd_citations,
    "field-coverage": cmd_field_coverage, "citation-completeness": cmd_citation_completeness,
    "atomicity": cmd_atomicity, "coverage": cmd_coverage, "api-urls": cmd_api_urls,
    "path-linked": cmd_path_linked, "descriptions": cmd_descriptions,
    "wrapper": cmd_wrapper,
}

def main():
    ap = argparse.ArgumentParser(description="Unified functional-graph validator")
    ap.add_argument("check", choices=list(COMMANDS))
    ap.add_argument("--kind", choices=["human", "system"])
    ap.add_argument("--repo-name")
    ap.add_argument("--repo-root")
    ap.add_argument("--seed-file")
    args = ap.parse_args()
    if args.check == "citations" and not args.repo_name:
        print(json.dumps({"ok": False, "errors": ["citations requires --repo-name"]})); sys.exit(2)
    full = load_full()
    # --kind is OPTIONAL: when a kind-taking check omits it, auto-detect from the
    # single persona. A per-skill shim injects a strict --kind to assert a half.
    if args.check in ("rule-a", "persona", "coverage") and not args.kind:
        args.kind = detect_kind(get_payload(full))
    COMMANDS[args.check](full, args)

if __name__ == "__main__":
    main()
