#!/usr/bin/env python3
"""Validate scenario feedback against entitlement + code evidence, in either direction.

Two review directions (see MODES / TRIAGE): `klc-objection` tests the business team's
objection to a scenario; `accion-rejection` re-tests our OWN team's "Incorrect" call on
the mapping. Only the Accion Comments column is ever written.

Every subcommand prints JSON on STDOUT. Exit 0 = pass/clean, 2 = hard-gate failure,
3 = bad input (unparseable, wrong shape). Every exit prints JSON — never a bare traceback.

    validate.py parse        [--all] < sheet.tsv        # sheet -> rows.json (+ triage)
    validate.py reach   --state S --module M [--verb write]
    validate.py adjudicate --state S --persona P --modules M[,M2] [--verb write]
    validate.py territory --state S --cite PATH [--cite PATH2]
    validate.py gate         < findings.json            # gate before you write the sheet back
    validate.py render --sheet sheet.tsv < findings.json # -> sheet back out, comments filled

STATE (`--state`) is reconcile-entitlements' `reconcile-state.json`. Only three keys are
read, all produced by that skill's Steps 2-4:
    matrix.roles    {role: {footprint: [[module, "read"|"write"], ...], features: [...]}}
    codemap.modules {module: {paths: [...], urls: [...], classes: [...], enforcement: [...]}}
    bindings.pairs  [{role, persona, score, evidence}]
If it is missing or its `bindings.confirmed` is false, STOP and run reconcile-entitlements
first — an unconfirmed binding table makes every persona verdict below unsound.

SHEET (`parse`) is tab-separated with a header row, as pasted from Excel. Quoted fields
may contain embedded newlines (KLC comments routinely do) — this is why the sheet is
parsed by csv, never by splitting on "\\n". Recognised headers (case/space-insensitive):
    Persona #, Persona, Outcome #, Outcome, Scenario #, Scenario, Description,
    Special Comments, Accion Validation, Accion Comments, KLC Validation, KLC Comments

TRIAGE — two review directions, set by `--mode` (default `both`). Which claim is under
test decides the direction, and `parse` stamps each row with its `review_mode`:
    klc-objection     Accion Validation blank/"unsure" AND KLC Validation
                      "incorrect"/"invalid" — the claim under test is KLC's.
    accion-rejection  Accion Validation "incorrect"/"invalid" — the claim under test is
                      our OWN team's rejection of the mapping. KLC's column is irrelevant.
`--all` keeps every row instead (`needs_validation` is still set, so you can see what was
skipped and why).

FINDINGS (`gate`, STDIN) — the artifact you build as you work. One file may carry both
directions: set `mode` per finding (or once at the top level as the default).
    {"mode": "<default review direction>",
     "findings": [{
        "scenario_no": "4.2.1",
        "persona": "Operations Support",
        "mode": "klc-objection" | "accion-rejection",   # optional; overrides the default
        "claims": [{"claim": "<the assertion under test, atomised>",
                    "kind": "terminology"|"persona-parentage"|"capability-absent"
                            |"capability-exists"|"access"|"process-detail"|"scope",
                    "verdict": "klc-correct"|"klc-incorrect"|"unresolved"       # klc-objection
                             | "mapping-confirmed"|"mapping-not-supported"|"unresolved",
                    "evidence": ["<>=1 concrete artifact: module, role, path, proc, url>"]}],
        "verdict": "<the mode's roll-up: ...-partially-... when claims diverge>",
        "deviation": "<the gap in one plain sentence: what the sheet says vs what the
                      system does. 'none' only when the graph is confirmed correct.>",
        "placement": {
            # granted_via / not_via are REQUIRED on any finding with a persona-parentage
            # or access claim, in EITHER mode. Naming both sides is the point: "granted
            # through Ops Super User KCLC, not through the Center Director roles" tells
            # the reader exactly why their own account behaved differently.
            "granted_via": ["<exact role name(s) that grant it>"],
            "not_via":     ["<roles in this persona that do NOT>", "or \"none\""],
            # both rationale legs are REQUIRED in accion-rejection mode
            "persona_rationale": "<which role carries the module, hence the persona>",
            "outcome_rationale": "<which permission module / capability groups it under
                                   this outcome>"},
        "accion_comment": "<prose written back to the sheet — see shape below>",
        "action": "<what changes in the graph, or 'none'>"}]}
The gate enforces: >=1 claim per finding, every claim carries >=1 evidence string, the
roll-up verdict is consistent with the claim verdicts (mixed => partially-correct), a
non-empty `deviation`, and an `accion_comment` that names the evidence rather than merely
asserting a conclusion.

ACCION_COMMENT — one flowing analytical paragraph, not a form. Business people read it,
so the language must be plain, but the DETAIL STAYS: modules, roles, screens, procedures
and service methods all belong in it, worked into the sentences where they explain
something. Do not split it into labelled blocks and do not open every row with the same
sentence — both read as boilerplate rather than analysis.

What it must do:
  * open on something specific to THIS row, in plain words — never on a bare identifier
    or a stored procedure name;
  * name both sides of the access contrast (which role grants it, which named roles in
    the persona do not) — that single sentence is usually the most useful in the row;
  * carry the implementation detail inline, with its business meaning attached ("the
    NCBRESERVATION permission module, which controls the backup-care search screen");
  * say plainly what could not be determined, when that is the honest answer.
Expand every acronym on first use.

TONE — two hard rules, both gated:
  * **Present the analysis; do not adjudicate the reviewer.** No "KLC is wrong/right",
    no "we agree/disagree", no "our earlier call was wrong". State what the system shows
    and let the difference speak; the reader draws the conclusion. The `verdict` field
    stays in findings.json for the report and is NEVER written to the sheet.
  * **Report findings, not remedies.** No "we will rename", "we recommend re-parenting",
    "should be moved". Deciding what to change is the business team's call. Keep the
    proposed remedy in the `action` field, which is internal and never written to the
    sheet.
"""
import argparse
import collections
import csv
import io
import json
import re
import sys

CLAIM_KINDS = {"terminology", "persona-parentage", "capability-absent", "capability-exists",
               "access", "process-detail", "scope"}

# Two review directions. In klc-objection the claim under test is KLC's; in
# accion-rejection it is our own team's "Incorrect" call on the mapping.
MODES = {
    "klc-objection": {
        "claim": {"klc-correct", "klc-incorrect", "unresolved"},
        "roll": {"klc-correct", "klc-incorrect", "klc-partially-correct", "unresolved"},
        "partial": "klc-partially-correct",
        "implies": {"klc-correct": "klc-correct", "klc-incorrect": "klc-incorrect"},
        "col": {"klc-correct": "Confirmed",
                "klc-incorrect": "Not confirmed",
                "klc-partially-correct": "Partially confirmed",
                "unresolved": "Unresolved"},
    },
    # NOTE the inversion: a claim that HOLDS means the mapping is NOT supported.
    # Claim-level and roll-up therefore use different vocabularies on purpose.
    "accion-rejection": {
        "claim": {"claim-supported", "claim-contradicted", "unresolved"},
        "roll": {"mapping-confirmed", "mapping-not-supported",
                 "mapping-partially-confirmed", "unresolved"},
        "partial": "mapping-partially-confirmed",
        "implies": {"claim-supported": "mapping-not-supported",
                    "claim-contradicted": "mapping-confirmed"},
        "col": {"mapping-confirmed": "Correctly mapped",
                "mapping-not-supported": "Incorrect",
                "mapping-partially-confirmed": "Partially correct",
                "unresolved": "Unresolved"},
    },
}
DEFAULT_MODE = "klc-objection"

# Implementation detail: meaningless to a business reader without translation. Role and
# permission-module names are NOT in here — those are the shared vocabulary with the
# business and belong in the explanation.
TECHNICAL = re.compile(
    r"[\w./]+\.(?:ascx|aspx|cs)\b"        # file paths
    r"|\bPAGE_[A-Z_]+\b"                   # page urls
    r"|\b[A-Z]\w+\.[A-Z]\w+\b"            # Service.Method / Facade.Method
    r"|\b[A-Z]{3,}_[A-Za-z]\w*\b")         # stored procedures
# Our own vocabulary, not theirs.
JARGON = [
    ("union of its bound roles", "say \"this persona covers several roles\""),
    ("bound role", "say \"role\" or name the role"),
    ("code territory", "say \"the screens this permission covers\""),
    ("roll-up", "state the verdict plainly"),
    ("observed footprint", "say \"what this persona actually touches\""),
    ("entitled to", "say \"has permission to\""),
]

# A confirmation has to rest on a real artifact, not on absence of contradiction.
ARTIFACT = re.compile(
    r"(?:\.ascx|\.aspx|\.cs\b|PAGE_[A-Z_]+|\b[A-Z][A-Z ]{3,}\b|\b\w+_\w+\b|/|\.\w+\("
    r"|\b[A-Z]\w+\.[A-Z]\w+"
    r"|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b)")   # title-case module/role names

WRITE_HINTS = ("write", "update", "save", "cancel", "deny", "approve", "delete",
               "create", "submit", "process", "edit")

# Columns as they appear in the sheet, normalised -> our key.
COLS = {
    "persona #": "persona_no", "persona": "persona",
    "outcome #": "outcome_no", "outcome": "outcome",
    "scenario #": "scenario_no", "scenario": "scenario",
    "description": "description", "special comments": "special_comments",
    "accion validation": "accion_validation", "accion comments": "accion_comments",
    "klc validation": "klc_validation", "klc comments": "klc_comments",
    # Later sheet revisions add these; recognised so they are not flagged unknown.
    "klc owner": "klc_owner",
    "accion graph validation": "accion_graph_validation",
}

# The Description column is the generated prose UNDER REVIEW, not evidence about the
# system. Citing it to validate itself is circular, and it can be stale in ways the
# graph and the code are not. It is recognised on parse (so it is not reported as an
# unknown column) and then dropped before rows are emitted — what a scenario claims must
# come from the functional graph's own Scenario/Step/Action nodes, resolved by Scenario #.
DROP_COLS = {"description"}


def out(obj, code=0):
    json.dump(obj, sys.stdout, indent=2)
    sys.stdout.write("\n")
    sys.exit(code)


def die(msg):
    out({"ok": False, "errors": [msg], "warnings": []}, 3)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def load_state(path):
    try:
        with open(path) as fh:
            st = json.load(fh)
    except FileNotFoundError:
        die(f"state file not found: {path} — run reconcile-entitlements first")
    except json.JSONDecodeError as e:
        die(f"state file is not valid JSON: {e}")
    for k in ("matrix", "bindings"):
        if k not in st:
            die(f"state file has no '{k}' key — not a reconcile-state.json")
    return st


def role_persona_index(st):
    idx = {}
    for p in st["bindings"].get("pairs", []):
        idx.setdefault(p["role"], []).append((p["persona"], p.get("score")))
    return idx


def module_holders(st, module, verb=None):
    """-> [{role, verbs, personas:[{persona,score}]}] for every role holding `module`."""
    r2p = role_persona_index(st)
    rows = []
    for role, info in st["matrix"].get("roles", {}).items():
        verbs = sorted({v for m, v in info.get("footprint", []) if m == module})
        if not verbs:
            continue
        if verb and verb not in verbs:
            continue
        rows.append({
            "role": role,
            "verbs": verbs,
            "personas": [{"persona": p, "score": s} for p, s in r2p.get(role, [])] or None,
        })
    return sorted(rows, key=lambda r: r["role"])


def persona_reach(st, module, verb=None):
    """-> {persona: {verbs, via_roles}} union across each persona's bound roles."""
    agg = {}
    for row in module_holders(st, module):
        for pr in (row["personas"] or []):
            e = agg.setdefault(pr["persona"], {"verbs": set(), "via_roles": []})
            e["verbs"] |= set(row["verbs"])
            e["via_roles"].append({"role": row["role"], "score": pr["score"],
                                   "verbs": row["verbs"]})
    for e in agg.values():
        e["verbs"] = sorted(e["verbs"])
    if verb:
        agg = {p: e for p, e in agg.items() if verb in e["verbs"]}
    return agg


def cmd_parse(args):
    raw = sys.stdin.read()
    if not raw.strip():
        die("no input on STDIN — pipe the pasted sheet in")
    rows_in = list(csv.reader(io.StringIO(raw), delimiter="\t"))
    rows_in = [r for r in rows_in if any((c or "").strip() for c in r)]
    if len(rows_in) < 2:
        die("need a header row plus at least one data row (is it tab-separated?)")

    header = [norm(c) for c in rows_in[0]]
    unknown = [h for h in header if h and h not in COLS]
    mapping = [COLS.get(h) for h in header]
    if "scenario" not in [m for m in mapping if m]:
        die(f"no 'Scenario' column found in header: {header}")

    rows, triaged = [], 0
    for raw_row in rows_in[1:]:
        rec = {v: "" for v in COLS.values()}
        for i, key in enumerate(mapping):
            if key and i < len(raw_row):
                rec[key] = (raw_row[i] or "").strip()
        if not rec["scenario"]:
            continue
        for k in DROP_COLS:
            rec.pop(k, None)
        acc, klc = norm(rec["accion_validation"]), norm(rec["klc_validation"])
        # Which claim is under test decides the review direction.
        rejected = acc in ("incorrect", "invalid")            # our own team's call
        objected = acc in ("", "unsure") and klc in ("incorrect", "invalid")
        rec["review_mode"] = ("accion-rejection" if rejected
                              else "klc-objection" if objected else None)
        rec["needs_validation"] = bool(
            rejected if args.mode == "accion-rejection"
            else objected if args.mode == "klc-objection"
            else (rejected or objected))          # --mode both
        rec["triage_reason"] = (
            "accion=%s / klc=%s" % (acc or "blank", klc or "blank")
        )
        triaged += bool(rec["needs_validation"])
        rows.append(rec)

    kept = rows if args.all else [r for r in rows if r["needs_validation"]]
    out({"ok": True, "mode": args.mode, "parsed": len(rows),
         "needs_validation": triaged, "returned": len(kept),
         "unknown_columns": unknown, "excluded_columns": sorted(DROP_COLS),
         "note": "Description is excluded by design — resolve what the scenario claims "
                 "from the functional graph (Get_all_steps_actions_for_a_scenario_id), "
                 "never from the sheet's prose.",
         "rows": kept})


def cmd_reach(args):
    st = load_state(args.state)
    mods = st["matrix"].get("modules", [])
    if args.module not in mods:
        near = [m for m in mods if norm(args.module) in norm(m)
                or norm(m) in norm(args.module)]
        die(f"module {args.module!r} not in matrix.modules. Did you mean: {near or mods[:15]}")
    out({"ok": True, "module": args.module, "verb": args.verb,
         "holders": module_holders(st, args.module, args.verb),
         "personas": persona_reach(st, args.module, args.verb),
         "unconfirmed_bindings": not st["bindings"].get("confirmed", False)})


def cmd_adjudicate(args):
    st = load_state(args.state)
    mods = [m.strip() for m in args.modules.split(",") if m.strip()]
    known = set(st["matrix"].get("modules", []))
    missing = [m for m in mods if m not in known]
    if missing:
        die(f"modules not in matrix.modules: {missing}")

    verb = args.verb
    per_module, claimed_ok = {}, []
    for m in mods:
        reach = persona_reach(st, m)
        mine = reach.get(args.persona)
        holds = bool(mine and (not verb or verb in mine["verbs"]))
        per_module[m] = {
            "persona_holds": holds,
            "persona_verbs": mine["verbs"] if mine else [],
            "via_roles": mine["via_roles"] if mine else [],
            "other_personas": {p: e["verbs"] for p, e in reach.items()
                               if p != args.persona},
        }
        if holds:
            claimed_ok.append(m)

    entitled = bool(claimed_ok)
    out({
        "ok": True,
        "persona": args.persona,
        "verb": verb,
        "modules": per_module,
        # The headline: can this persona actually do this, and who else can?
        "verdict": "entitled" if entitled else "unentitled",
        "entitled_on": claimed_ok,
        "reparent_candidates": sorted({
            p for m in mods for p in per_module[m]["other_personas"]
            if not verb or verb in per_module[m]["other_personas"][p]
        }),
        "unconfirmed_bindings": not st["bindings"].get("confirmed", False),
    })


def cmd_territory(args):
    """Resolve citation paths / urls to the modules whose territory contains them."""
    st = load_state(args.state)
    cm = st.get("codemap", {}).get("modules", {})
    if not cm:
        die("state has no codemap.modules — run reconcile-entitlements Step 3")
    res = {}
    for cite in args.cite:
        c = norm(cite)
        hits = []
        for mod, terr in cm.items():
            for field in ("paths", "urls", "classes"):
                for t in terr.get(field) or []:
                    if norm(t) in c or c in norm(t):
                        hits.append({"module": mod, "matched": t, "via": field})
        res[cite] = hits or None
    unresolved = [c for c, h in res.items() if not h]
    out({"ok": not unresolved, "resolved": res, "unresolved": unresolved,
         "note": "unresolved citations fall back to name-match evidence — flag them"})


def cmd_gate(args):
    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        die(f"findings is not valid JSON: {e}")
    if not isinstance(doc, dict) or "findings" not in doc:
        die("expected an object with a 'findings' key")
    doc_mode = doc.get("mode", DEFAULT_MODE)
    if doc_mode not in MODES:
        die(f"mode {doc_mode!r} not in {sorted(MODES)}")

    errors, warnings = [], []
    seen = set()
    for i, f in enumerate(doc["findings"]):
        tag = f.get("scenario_no") or f"#{i}"
        # A sheet can carry both review directions; each finding names its own.
        mode = f.get("mode", doc_mode)
        if mode not in MODES:
            errors.append(f"{tag}: mode {mode!r} not in {sorted(MODES)}")
            continue
        CLAIM_VERDICTS = MODES[mode]["claim"]
        PARTIAL = MODES[mode]["partial"]
        ROLL_VERDICTS = MODES[mode]["roll"]
        IMPLIES = MODES[mode]["implies"]
        if tag in seen:
            errors.append(f"{tag}: duplicate finding for the same scenario")
        seen.add(tag)
        for req in ("scenario_no", "verdict", "accion_comment", "claims", "deviation"):
            if not str(f.get(req) or "").strip():
                errors.append(f"{tag}: missing required field '{req}'")
        claims = f.get("claims") or []
        if not claims:
            errors.append(f"{tag}: no claims — atomise the KLC comment into >=1 claim")
        cvs = []
        for j, c in enumerate(claims):
            ct = f"{tag} claim[{j}]"
            if c.get("kind") not in CLAIM_KINDS:
                errors.append(f"{ct}: kind {c.get('kind')!r} not in {sorted(CLAIM_KINDS)}")
            if c.get("verdict") not in CLAIM_VERDICTS:
                errors.append(f"{ct}: verdict {c.get('verdict')!r} not in {sorted(CLAIM_VERDICTS)}")
            else:
                cvs.append(c["verdict"])
            ev = [e for e in (c.get("evidence") or []) if str(e).strip()]
            if not ev:
                errors.append(f"{ct}: no evidence — every claim needs >=1 concrete artifact")
            if not c.get("claim", "").strip():
                errors.append(f"{ct}: empty claim text")
            desc_ref = [m.group(0) for e in ev for m in re.finditer(
                r"\b(?:the\s+)?(?:scenario\s+)?description\b[^.]{0,40}", str(e), re.I)]
            if desc_ref:
                errors.append(
                    f"{ct}: evidence cites the sheet's Description column "
                    f"({desc_ref[:2]}) — that prose is the artifact under review, not "
                    f"evidence. Cite the functional graph's Scenario/Step/Action nodes, "
                    f"the permission data, or the code instead")
            # Guard against rubber-stamping: upholding something must rest on a
            # positive artifact, never on the mere absence of contradiction.
            if c.get("verdict") not in (None, "unresolved") and ev and not any(
                    ARTIFACT.search(str(e)) for e in ev):
                errors.append(
                    f"{ct}: decided verdict but no evidence names a concrete artifact "
                    f"(module, path, url, role, class.method or procedure) — absence of "
                    f"contradiction is not evidence")
        # Roll-up consistency: mixed claim verdicts must surface as partially-correct.
        v = f.get("verdict")
        if v and v not in ROLL_VERDICTS:
            errors.append(f"{tag}: verdict {v!r} not in {sorted(ROLL_VERDICTS)}")
        elif cvs:
            distinct = set(cvs)
            decided = distinct - {"unresolved"}
            # Map claim verdicts to what they imply for the roll-up. In
            # accion-rejection this inverts: a claim that holds means the
            # mapping is NOT supported.
            implied = {IMPLIES[d] for d in decided}
            if len(implied) > 1 and v != PARTIAL:
                errors.append(
                    f"{tag}: claims diverge ({sorted(distinct)} imply {sorted(implied)}) "
                    f"so verdict must be {PARTIAL!r}, got {v!r}")
            if len(implied) == 1 and v not in (next(iter(implied)), PARTIAL):
                errors.append(
                    f"{tag}: claim verdict(s) {sorted(decided)} imply "
                    f"{next(iter(implied))!r} but roll-up is {v!r}")
            if "unresolved" in distinct and v not in ("unresolved", PARTIAL):
                warnings.append(f"{tag}: an unresolved claim is hidden by roll-up {v!r}")
        # The comment IS the deliverable. A verdict with no visible reasoning fails.
        ac = str(f.get("accion_comment") or "")
        dev = str(f.get("deviation") or "")
        if ac and len(ac.split()) < 20:
            errors.append(
                f"{tag}: accion_comment is {len(ac.split())} words — too thin to explain "
                "the deviation. State agreement, deviation, evidence, and action.")
        allev = [str(e) for c in claims for e in (c.get("evidence") or [])]
        if ac and allev and not any(
                tok.lower() in ac.lower()
                for e in allev for tok in re.findall(r"[A-Za-z_][\w.]{3,}", e)[:6]):
            errors.append(
                f"{tag}: accion_comment names none of the evidence artifacts "
                f"({allev[:3]}...) — the reader must see WHY without opening the graph")
        # Any finding that turns on WHO can do something must name both sides of the
        # contrast: the role(s) that grant it, and the roles in the persona that do not.
        # Naming only the grant leaves the reader unable to see why their own account
        # behaves differently — that contrast is the single most useful line in the row.
        kinds = {c.get("kind") for c in claims}
        if kinds & {"persona-parentage", "access"}:
            pl = f.get("placement") or {}
            granted = [r for r in (pl.get("granted_via") or []) if str(r).strip()]
            notvia = [r for r in (pl.get("not_via") or []) if str(r).strip()]
            if not granted:
                errors.append(
                    f"{tag}: placement.granted_via missing — name the exact role(s) that "
                    f"grant this, since that is why the scenario sits under this persona")
            if not notvia:
                errors.append(
                    f"{tag}: placement.not_via missing — name the roles in this persona "
                    f"that do NOT grant it (use [\"none\"] if every role does). The "
                    f"contrast is what explains why a tester's account behaved differently")
            for lst, leg in ((granted, "granted_via"), (notvia, "not_via")):
                # "none" (optionally with an explanation after it) is a sentinel, not
                # a role name to look for in the prose.
                named = [r for r in lst
                         if not str(r).strip().lower().startswith("none")]
                if ac and named and not any(str(r).strip().lower() in ac.lower()
                                            for r in named):
                    errors.append(
                        f"{tag}: accion_comment names none of placement.{leg} "
                        f"({named[:3]}) — the reader must see which roles do and do not "
                        f"carry this")
        # accion-rejection also asks where the scenario belongs: why THIS outcome?
        if mode == "accion-rejection":
            pl = f.get("placement") or {}
            for leg, why in (("persona_rationale",
                              "which role carries the module, hence the persona"),
                             ("outcome_rationale",
                              "which permission module / capability groups it under "
                              "this outcome")):
                if not str(pl.get(leg) or "").strip():
                    errors.append(
                        f"{tag}: placement.{leg} missing — state {why}")
            toks = [t for leg in pl.values()
                    for t in re.findall(r"[A-Z][\w .]{3,}", str(leg))[:8]]
            if ac and toks and not any(t.strip().lower() in ac.lower() for t in toks):
                errors.append(
                    f"{tag}: accion_comment does not carry the placement reasoning "
                    f"({[t.strip() for t in toks[:3]]}) — the reader must see why this "
                    f"scenario sits under this outcome and persona")
        # The Description column is under review, so the comment must not lean on it.
        if ac and re.search(r"\b(?:the\s+)?(?:scenario\s+)?description\s+"
                            r"(?:lists|states|says|claims|omits|presents|describes|"
                            r"mentions|does not|doesn't)\b", ac, re.I):
            errors.append(
                f"{tag}: accion_comment argues from the sheet's Description column — "
                f"that prose is under review. Say what the graph records and what the "
                f"system does")
        # Readability gate: the comment is read by the business team, so it must lead
        # with the answer in plain words and quarantine implementation detail at the end.
        if ac:
            sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", ac) if x.strip()]
            first = sents[0] if sents else ""
            ftech = TECHNICAL.findall(first)
            if ftech:
                errors.append(
                    f"{tag}: accion_comment opens with implementation detail "
                    f"({ftech[:2]}) — the first sentence must answer the reviewer in "
                    f"plain words; move file paths, procedures and service methods "
                    f"below a '{DETAIL_MARK}' line")
            if len(first.split()) > 42:
                warnings.append(
                    f"{tag}: opening sentence is {len(first.split())} words — long openers "
                    f"lose a business reader; split it")
            # Readability must never cost detail: if the evidence names implementation
            # artifacts, the comment has to carry them — cleanly separated, not dropped.
            ev_tech = sorted({m for c in claims for e in (c.get("evidence") or [])
                              for m in TECHNICAL.findall(str(e))})
            missing = [t for t in ev_tech if t not in ac]
            if ev_tech and len(missing) == len(ev_tech):
                errors.append(
                    f"{tag}: evidence names implementation detail ({ev_tech[:3]}) that the "
                    f"comment drops — plain language must not cost detail; work it into "
                    f"the explanation")
            # Cheap copy defects that betray string assembly rather than writing.
            if re.search(r"\b(\w+) \1\b", ac, re.I):
                errors.append(
                    f"{tag}: doubled word in accion_comment "
                    f"({re.search(r'\\b(\\w+) \\1\\b', ac, re.I).group(0)!r}) — reads as "
                    f"assembled text, not written text")
            if re.search(r"\b(are|through|by|including|and)\s*[.,]", ac):
                errors.append(
                    f"{tag}: empty enumeration in accion_comment (a list rendered to "
                    f"nothing) — drop the clause when the list is empty")
            for phrase, fix in JARGON:
                if phrase in ac.lower():
                    errors.append(f"{tag}: house jargon {phrase!r} — {fix}")
            longs = [len(x.split()) for x in sents if len(x.split()) > 42]
            if len(longs) > 1:
                errors.append(
                    f"{tag}: {len(longs)} sentences over 42 words ({longs}) — a business "
                    f"reader loses the thread; split them")
            elif longs:
                warnings.append(f"{tag}: one sentence of {longs[0]} words — consider splitting")
        # Tone gate 1: present the analysis, don't adjudicate the reviewer.
        adversarial = [m.group(0) for m in re.finditer(
            r"\b(?:we\s+(?:dis)?agree\w*"
            r"|KLC(?:'s)?\s+(?:is|are|was|were)\s+\w+"
            r"|(?:they|KLC)\s+(?:are|is)\s+(?:wrong|right|mistaken|correct|incorrect)"
            r"|(?:KLC|they)\s+(?:got|has|have)\s+(?:this|it)\s+\w+"
            r"|their\s+(?:claim|objection|comment)\s+is\s+(?:wrong|incorrect|right|correct)"
            r")\b", ac, re.I)]
        if adversarial:
            errors.append(
                f"{tag}: accion_comment adjudicates the reviewer ({adversarial[:3]}) — "
                "present what the system shows; the Accion Validation column carries "
                "whether the feedback is borne out")
        # Tone gate 2: report findings, not remedies. The remedy lives in `action`.
        prescriptive = [m.group(0) for m in re.finditer(
            r"\b(?:we\s+(?:will|would|recommend|propose|suggest|plan\s+to)"
            r"|should\s+be\s+(?:renamed|re-?parented|moved|deleted|removed|marked|"
            r"updated|changed|rewritten)"
            r"|needs?\s+to\s+be\s+(?:renamed|re-?parented|moved|deleted|removed|changed)"
            r"|the\s+(?:correct|right)\s+fix\s+is"
            r")\b", ac, re.I)]
        if prescriptive:
            errors.append(
                f"{tag}: accion_comment prescribes a remedy ({prescriptive[:3]}) — "
                "deciding the change is the business team's call; move it to 'action'")
        if (mode == "klc-objection" and dev and norm(dev) in ("none", "n/a", "-")
                and v in ("klc-correct", PARTIAL)):
            errors.append(
                f"{tag}: verdict {v!r} concedes a KLC point, so 'deviation' cannot be 'none'")
        # In accion-rejection the reverse holds: upholding the mapping means nothing
        # deviates, so a stated deviation must be a real residual caveat.
        if (mode == "accion-rejection" and v == "mapping-confirmed" and dev
                and norm(dev) not in ("none", "n/a", "-") and len(dev.split()) < 6):
            warnings.append(
                f"{tag}: mapping confirmed but 'deviation' is a fragment — write 'none' "
                f"or state the residual caveat in full")
        if not f.get("action"):
            warnings.append(f"{tag}: no 'action' — say what changes in the graph, or 'none'")

    # Boilerplate openers make a sheet read like a form rather than analysis.
    firsts = collections.Counter()
    for f in doc["findings"]:
        ac = str(f.get("accion_comment") or "")
        first = re.split(r"(?<=[.!?])\s+", ac.strip())[0] if ac.strip() else ""
        if first:
            firsts[first] += 1
    for text, n in firsts.items():
        if n > 3 and n > len(doc["findings"]) * 0.15:
            errors.append(
                f"{n} findings open with the identical sentence {text[:60]!r} — vary the "
                f"opening to the specific finding; identical openers read as a template")

    ok = not errors
    out({"ok": ok, "findings": len(doc["findings"]), "errors": errors,
         "warnings": warnings}, 0 if ok else 2)


ANALYSIS_MARK = "--- Validation analysis ---"


def cmd_render(args):
    """Re-emit the original sheet with ONLY the Accion Comments column filled in.

    Accion Validation is the reviewing team's own call and is never touched — the
    verdicts stay in findings.json for the report. Any note already in Accion Comments
    (a tester's observation, often the very claim under test) is preserved: the analysis
    is appended below an ANALYSIS_MARK separator. Re-rendering replaces the previous
    analysis block rather than stacking a second copy, so render is idempotent.

    Writes TSV to STDOUT, preserving column order and every untouched cell, so the
    result pastes straight back over the original range in Excel.
    """
    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        die(f"findings is not valid JSON: {e}")
    by_no = {str(f.get("scenario_no", "")).strip(): f for f in doc.get("findings", [])}
    if not by_no:
        die("no findings to render")

    # Verdict -> what goes in the Accion Validation column. Neutral and factual: it
    # states whether the evidence bears the claim out, not who was right. The
    # vocabulary differs by review direction (see MODES).
    doc_mode = doc.get("mode", DEFAULT_MODE)
    if doc_mode not in MODES:
        die(f"mode {doc_mode!r} not in {sorted(MODES)}")
    with open(args.sheet) as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    if not rows:
        die(f"sheet {args.sheet} is empty")
    header = [norm(c) for c in rows[0]]
    try:
        i_no = header.index("scenario #")
    except ValueError:
        die("sheet has no 'Scenario #' column — cannot match findings to rows")
    target = norm(args.column)
    i_com = header.index(target) if target in header else None
    if i_com is None:
        die(f"sheet has no {args.column!r} column — nothing to write into. "
            f"Columns present: {[c for c in header if c]}")

    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    w.writerow(rows[0])
    matched = set()
    for r in rows[1:]:
        r = list(r) + [""] * (len(rows[0]) - len(r))
        key = (r[i_no] or "").strip()
        f = by_no.get(key)
        if f:
            matched.add(key)
            # Preserve whatever the reviewer already wrote; drop only our own prior
            # analysis block so repeated renders stay idempotent.
            existing = (r[i_com] or "").split(ANALYSIS_MARK)[0].strip()
            analysis = f.get("accion_comment", "").strip()
            r[i_com] = (f"{existing}\n\n{ANALYSIS_MARK}\n{analysis}"
                        if existing else analysis)
        w.writerow(r)
    unmatched = sorted(set(by_no) - matched)
    if unmatched:
        sys.stderr.write(
            f"WARNING: findings with no matching sheet row: {unmatched}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse"); p.add_argument("--all", action="store_true")
    p.add_argument("--mode", default="both",
                   choices=["klc-objection", "accion-rejection", "both"])
    p.set_defaults(fn=cmd_parse)

    p = sub.add_parser("reach")
    p.add_argument("--state", required=True); p.add_argument("--module", required=True)
    p.add_argument("--verb", choices=["read", "write"])
    p.set_defaults(fn=cmd_reach)

    p = sub.add_parser("adjudicate")
    p.add_argument("--state", required=True); p.add_argument("--persona", required=True)
    p.add_argument("--modules", required=True)
    p.add_argument("--verb", choices=["read", "write"])
    p.set_defaults(fn=cmd_adjudicate)

    p = sub.add_parser("territory")
    p.add_argument("--state", required=True)
    p.add_argument("--cite", action="append", required=True)
    p.set_defaults(fn=cmd_territory)

    p = sub.add_parser("gate"); p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("render"); p.add_argument("--sheet", required=True)
    p.add_argument("--column", default="Accion Comments",
                   help="target column to write into (default: Accion Comments; some "
                        "sheet revisions use 'Accion Graph Validation')")
    p.set_defaults(fn=cmd_render)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
