#!/usr/bin/env python3
"""Render gated findings into a standalone TSV validation document.

    report.py --sheet sheet.tsv [--persona "Operations Support"] < findings.json > doc.tsv

Output is always TSV — one row per finding, opening directly in Excel. This is a
DIFFERENT artifact from `validate.py render`: render patches the Accion Comments column
of the original review sheet in place, whereas this is a standalone document of the
analysis itself, with the reasoning broken into its own columns.

Columns: identity (Scenario #, Scenario, Outcome #, Outcome, Persona), the review
direction, the claim that was tested, the verdict, both placement legs, the analysis
prose, the deviation, and every claim flattened with its evidence.

Reads the same findings.json `gate` accepts. RUN THE GATE FIRST — this renders whatever
it is given and will happily emit ungated prose. Findings are joined to sheet rows by
Scenario #; a finding with no matching row is a hard error.

The sheet's Description column is never read, per the skill's exclusion rule.
"""
import argparse
import csv
import json
import sys

VERD = {
    "klc-correct": "Confirmed",
    "klc-incorrect": "Not confirmed",
    "klc-partially-correct": "Partially confirmed",
    "mapping-confirmed": "Correctly mapped",
    "mapping-not-supported": "Not supported",
    "mapping-partially-confirmed": "Partially correct",
    "unresolved": "Unresolved",
}
CLAIM_LABEL = {
    "claim-supported": "Claim holds",
    "claim-contradicted": "Claim contradicted",
    "klc-correct": "Borne out",
    "klc-incorrect": "Not borne out",
    "unresolved": "Unresolved",
}
DIRECTION = {
    "accion-rejection": "Internal rejection (our own Incorrect)",
    "klc-objection": "Business team objection",
}
COLS = ["Scenario #", "Scenario", "Outcome #", "Outcome", "Persona",
        "Review direction", "Claim under test", "Verdict",
        "Why it sits here - Persona", "Why it sits here - Outcome",
        "Analysis", "Deviation", "Claims and evidence"]

ANALYSIS_MARK = "--- Validation analysis ---"


def sort_key(f):
    return tuple(int(p) if p.isdigit() else 0
                 for p in str(f.get("scenario_no", "")).split("."))


def load_sheet(path):
    with open(path) as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    if not rows:
        sys.exit(f"sheet {path} is empty")
    h = [c.strip().lower() for c in rows[0]]
    want = ("scenario #", "scenario", "outcome", "outcome #",
            "klc comments", "accion comments")
    i = {k: (h.index(k) if k in h else None) for k in want}
    if i["scenario #"] is None:
        sys.exit("sheet has no 'Scenario #' column")
    out = {}
    for r in rows[1:]:
        r = list(r) + [""] * (len(rows[0]) - len(r))
        out[r[i["scenario #"]].strip()] = {
            k: (r[v] if v is not None else "") for k, v in i.items()}
    return out


def flatten_claims(f):
    """One cell holding every claim, its verdict and its evidence, readable in Excel."""
    out = []
    for n, c in enumerate(f.get("claims") or [], 1):
        label = CLAIM_LABEL.get(c.get("verdict"), c.get("verdict", "?"))
        out.append(f"{n}. [{label} | {c.get('kind','')}] {(c.get('claim') or '').strip()}")
        out += [f"     - {str(e).strip()}" for e in (c.get("evidence") or [])]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--persona", default="")
    a = ap.parse_args()

    try:
        doc = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        sys.exit(f"findings is not valid JSON: {e}")
    F = doc.get("findings") or []
    if not F:
        sys.exit("no findings on stdin")

    sheet = load_sheet(a.sheet)
    missing = [f.get("scenario_no") for f in F if f.get("scenario_no") not in sheet]
    if missing:
        sys.exit(f"findings with no matching sheet row: {missing}")

    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    w.writerow(COLS)
    for f in sorted(F, key=sort_key):
        m = sheet.get(f.get("scenario_no", ""), {})
        pl = f.get("placement") or {}
        mode = f.get("mode", "klc-objection")
        # The claim under test differs by direction: our own note, or the business team's.
        claim_src = (m.get("accion comments", "").split(ANALYSIS_MARK)[0]
                     if mode == "accion-rejection" else m.get("klc comments", ""))
        dev = (f.get("deviation") or "").strip()
        w.writerow([
            f.get("scenario_no", ""), m.get("scenario", ""),
            m.get("outcome #", ""), m.get("outcome", ""),
            f.get("persona", "") or a.persona,
            DIRECTION.get(mode, mode), claim_src.strip(),
            VERD.get(f.get("verdict"), f.get("verdict", "")),
            pl.get("persona_rationale", ""), pl.get("outcome_rationale", ""),
            (f.get("accion_comment") or "").strip(),
            "" if dev.lower() in ("none", "n/a", "-") else dev,
            flatten_claims(f)])


if __name__ == "__main__":
    main()
