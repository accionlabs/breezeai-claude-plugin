---
name: validate-scenario-feedback
description: >
  Validate scenario feedback on a functional-graph review sheet against the knowledge graph, the
  code, and the role/permission entitlement data, then write that analysis into the Accion
  Comments column. Handles both directions: business-team (KLC) objections to a scenario, and our
  own team's "Incorrect" rejections of a mapping — for the latter, establishing whether the
  scenario is in fact correctly mapped. Reports findings with named evidence and does not
  prescribe fixes.
  Use when: "validate these scenarios", "KLC marked these incorrect", "check this validation
  sheet", "is the business team right about X", "why is this scenario under this persona",
  "fill in the Accion Comments", "adjudicate the KLC feedback".
---

## What this decides

The business team (KLC) marks scenarios **Incorrect** and says why. This skill establishes what
the system actually does — **claim by claim, with named evidence** — and writes that analysis
into **Accion Comments**. That column is the deliverable. A verdict with no visible reasoning is
a failed run, however sound the verdict.

**We establish what is true; the business team decides what to do about it.** The comment
presents evidence and names the deviation. It does not argue with the reviewer and it does not
prescribe the fix — both are gated (Step 5).

Three things make this harder than it looks, and the whole method follows from them:

- **One KLC comment usually contains several claims, and they often have different verdicts.**
  The worked example's comment is one paragraph carrying a *terminology* claim (true) and a
  *persona-parentage* claim (false). Adjudicating the paragraph as a unit gets it half wrong
  either way. **Atomise first** — this is the single highest-value step in the skill.
- **A business objection is usually right about the business and wrong about the system**, or
  the reverse. KLC know what their teams do; they do not know what the permission tables
  enforce. Expect to concede vocabulary and contest parentage.
- **"The business would not say it that way" is not evidence that the scenario is wrong.**
  Wording defects and capability defects are different findings with different fixes. Never let
  a naming complaint delete a real capability.

## Ground truth, in precedence order

| Rank | Source | Answers |
|---|---|---|
| 1 | `reconcile-state.json` — `matrix.roles`, `bindings.pairs`, `codemap.modules` | Who is *entitled* to this, and through which role |
| 2 | Code graph (`Code_Graph_Search`) + the local checkout | Does the capability exist, and where |
| 3 | Functional graph (`Functional_Graph_Search`) | What the graph currently claims, and whether a sibling subtree already says it better |
| 4 | The KLC comment | What the business believes |

Entitlement outranks everything on *persona* questions. The functional graph is the artifact
under review — it is never its own evidence, **except** when a sibling subtree independently
names the same capability, which is strong corroboration on *terminology* questions.

**The sheet's Description column is excluded from the analysis entirely.** It is generated prose
describing the very scenario under review, so citing it to validate that scenario is circular,
and it can be stale in ways the graph and the code are not. `parse` drops the column before
emitting rows, and the gate rejects any evidence or comment that argues from it. When you need
to know what a scenario claims, resolve it in the functional graph by Scenario # and read the
Scenario/Step/Action nodes (`Get_all_steps_actions_for_a_scenario_id`) — that is the record of
record. The Scenario **name**, Outcome and Persona columns stay in play; only Description goes.

**Precondition.** `reconcile-state.json` must exist with `bindings.confirmed: true`. If it is
missing or unconfirmed, stop and run [`reconcile-entitlements`](../reconcile-entitlements/SKILL.md)
— every persona verdict below is unsound without a confirmed role→persona binding table.

Paths below are relative to the repo root (`kindercare/`). Project uuid:
`9e9b104f-6e0d-4298-a2f0-aab538377de3`.

## The driver

`validate.py` in this skill folder does the parsing, the entitlement arithmetic, the gate, and
the write-back. Read its docstring for exact shapes; never hand-compute what it computes.

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py --help
```

| Command | Does |
|---|---|
| `parse [--all] [--mode M] < sheet.tsv` | Sheet → rows JSON, triaged and stamped with `review_mode`. Handles quoted fields with embedded newlines |
| `territory --state S --cite PATH` | Citation/url → the permission module whose territory owns it |
| `reach --state S --module M [--verb write]` | Every role holding M, and the personas they bind to |
| `adjudicate --state S --persona P --modules M [--verb write]` | The headline: is P entitled, and who else is |
| `gate < findings.json` | **Blocks** on thin reasoning. Exit 2 = fix it |
| `render --sheet sheet.tsv < findings.json` | Sheet back out with **only** Accion Comments filled, prior notes preserved |
| `report.py --sheet sheet.tsv < findings.json` | Standalone TSV analysis document, one row per finding (Step 7) |

---

## Step 1 — Parse and triage

Save the pasted sheet verbatim to `sheet.tsv` in the scratchpad — **do not retype it**, and do
not strip the quotes; KLC comments contain embedded newlines that only survive as quoted TSV.

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py parse < sheet.tsv > rows.json
```

**Which claim is under test decides everything downstream.** Two review directions, and `parse`
stamps each row with its `review_mode`:

| Direction | Row looks like | The claim under test |
|---|---|---|
| `klc-objection` | Accion blank/`Unsure` **and** KLC `Incorrect`/`Invalid` | KLC's objection to the scenario |
| `accion-rejection` | Accion `Incorrect`/`Invalid` (KLC's column is irrelevant) | **Our own team's** rejection of the mapping |

`--mode both` is the default and handles a mixed sheet in one pass. Everything else is out of
scope for this run — report the count, don't silently drop it. Check `unknown_columns`: a
non-empty list means the sheet has columns this skill doesn't model.

**The two directions invert.** In `accion-rejection` a claim that *holds* means the mapping is
**not** supported, so claim-level and roll-up use deliberately different vocabularies:

| Claim verdict | implies roll-up | Column |
|---|---|---|
| `claim-contradicted` | `mapping-confirmed` | Correctly mapped |
| `claim-supported` | `mapping-not-supported` | Incorrect |
| mixed | `mapping-partially-confirmed` | Partially correct |

The gate enforces the implication. Sharing one vocabulary across both levels reads as though
they should agree and silently produces backwards verdicts — that mistake is why they differ.

**Identical KLC comments repeated across rows are still separate findings.** In the worked
example the same paragraph appears on all five rows, but 4.3.3 additionally surfaced a duplicate
capability the others didn't. Adjudicate per row; reuse evidence, not conclusions.

## Step 2 — Atomise each KLC comment into claims

Split the comment into **independently checkable assertions**. Classify each — the kind
determines which evidence settles it, and a claim you cannot classify is usually two claims.

| Kind | The claim sounds like | Settled by |
|---|---|---|
| `scope` | "it only does half of that", "that option isn't there" | The graph's Action nodes + the module's verbs. Never the sheet's Description |
| `terminology` | "we don't call it that", "that's a schema term" | Does the term appear only in modules/procs/classes, and never in business-facing names? Does a sibling subtree name it better? |
| `persona-parentage` | "this belongs to persona Y", "which role drives this" | `adjudicate` — does the current persona hold the module, does Y? |
| `access` | "persona X can't see that report/screen" | `reach` on the module (+ `rptPath` for Cognos reports) |
| `capability-absent` | "we don't do this at all" | Code graph: does the page/service/proc exist? |
| `process-detail` | "the flow isn't like that", "that field isn't required" | Code graph: read the presenter/validator |

Findings you discover while checking — defects neither party raised — go in as their own claim
rather than being folded into the comment prose. That is how the duplicate-capability defect in
the worked example got recorded.

### When the claim is our own rejection (`accion-rejection`)

These rows are usually **manual test observations** — "greyed out", "no such option visible",
"cannot create X". One distinction settles most of them:

> **A persona's entitlement is the union of its bound roles; a tester signs in as one role.**
> A control missing or greyed out for the account under test shows *that role's* view, not the
> persona's.

So separate three very different situations, because they look identical in a screenshot:

| What the evidence shows | Verdict | Example from the run |
|---|---|---|
| Capability exists, persona holds it, but only via one role the tester wasn't using | `mapping-confirmed` | CLASSROOM write is held by exactly two roles system-wide; a Service Desk account sees greyed-out controls |
| Capability exists but **no role anywhere** holds the verb | `mapping-not-supported` | SITE COMMUNICATION has zero write holders across all 56 roles |
| Capability exists and is entitled, but the scenario overstates its scope or names the wrong screen | `mapping-partially-confirmed` | Scenario claims add/edit/remove; only add exists |

Always check whether the verb is held **anywhere in the system**, not just by this persona — a
module with zero write holders is a much stronger finding than a persona gap, and it usually
means permissions were withdrawn rather than that the scenario was invented.

**These rows are a placement question, and the comment must answer it.** The deliverable is not
"was the tester right" — it is *why this scenario sits under this outcome and this persona*. The
finding carries a required `placement` object, and the gate fails without both legs:

| Leg | Answers | Comes from |
|---|---|---|
| `persona_rationale` | Which **bound role** carries the module — that role is why the scenario landed under this persona | `reach` / `adjudicate` on the module |
| `outcome_rationale` | Which **permission module and screen** groups it under this outcome | `territory` on the citation or url |

Lead the comment with that reasoning ("Why this sits where it does: …"), then the system
evidence. The gate also checks the comment actually carries the placement terms, so the reader
sees the rationale rather than just a conclusion.

Watch for a scenario whose module is **not** the outcome's module — 4.60.8 and 4.60.10 sit under
*Manage Sites* but are gated by PROGRAM and CLASSROOM, each held by just two roles system-wide,
which is a far narrower gate than the SITE module behind the rest of that outcome. That mismatch
is itself the finding.

Watch for the read/write split inside one outcome: five of the six site-communication scenarios
had no entitled writer, while the sixth was read-only and correctly mapped. A blanket rejection
across an outcome is worth testing row by row.

## Step 3 — Gather evidence

Resolve the scenario to its **permission module** first; every persona and access question is
decided there. Take the citation paths and ASMX/page urls from the scenario description and run
them through `territory`:

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py territory --state reconcile-state.json \
  --cite "CMS/Controls/BUCCMVP/NBCReservation/SearchNbcReservation.ascx"
```

Then, for the persona question, the one command that matters — pass `--verb write` whenever the
scenario mutates anything (save, cancel, approve, deny, submit, delete):

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py adjudicate --state reconcile-state.json \
  --persona "Operations Support" --modules "NCBRESERVATION" --verb write
```

Run it **twice** — once for the persona on the sheet, once for the persona KLC proposes. The
second run is what turns "KLC is wrong" into "KLC is wrong *because Family Support holds no
permission on this module at all*", and only the second form belongs in the comment.

`verb` matters more than it looks: a persona with `read` and a scenario that saves is
**over-permissioned**, not entitled. Check the verb the scenario actually needs.

Every claim needs **≥1 concrete artifact** — a module name, role name, file path, stored
procedure, or url. "It seems aligned with X" is not evidence and the gate rejects it.

## Step 4 — Rule on each claim

| Verdict | Column reads | When |
|---|---|---|
| `klc-correct` | Confirmed | Evidence bears the feedback out |
| `klc-incorrect` | Not confirmed | Evidence shows the system behaving otherwise |
| `unresolved` | Unresolved | Evidence is genuinely absent or points both ways. Say what would settle it |

Roll up to the finding: any divergence among decided claims ⇒ **`klc-partially-correct`**
(*Partially confirmed*). The gate enforces this, because collapsing a mixed result to a single
verdict is the most common way these adjudications go wrong.

**When a claim comes out `klc-incorrect`, show what the business was seeing.** They are rarely
confused for no reason, and the reason is usually a real distinction in the system. In the
worked example Family Support genuinely does handle backup care — the *center-based* kind —
which is exactly why in-home looked like theirs. Including that is what makes the comment
useful rather than merely contradictory, and it is often the most valuable sentence in the row.

## Step 5 — Write the Accion Comment

**One flowing analytical paragraph.** Not labelled blocks, not a template — the business team
reads a sheet of these, and anything with the same skeleton in every row stops being read.
Keep the density of a good analyst's note; fix the *language*, not the structure.

The detail stays. Modules, roles, screens, stored procedures and service methods all belong in
the paragraph, worked into sentences where they explain something. Simplifying must never mean
dropping evidence — the gate fails a comment whose evidence names implementation detail the
prose omits.

What every comment must do:

1. **Open on something specific to this row**, in plain words — never on a bare identifier or a
   stored procedure name. Identical openers across rows are a gate failure.
2. **Name both sides of the access contrast** — the role(s) that grant it, and the named roles
   in the persona that do not. This is usually the most useful sentence in the row: *"granted
   only through Ops Super User KCLC — not through the mainstream Center Director or Center
   Director KCLC roles."* Structured in `placement.granted_via` / `not_via`, and gated.
3. **Attach business meaning to each identifier** — "the NCBRESERVATION permission module, which
   controls the backup-care search screen", not the bare name.
4. **Say plainly what could not be determined**, when that is the honest answer.

Sentence discipline is what makes it readable: aim for 15–25 words, and the gate fails two or
more sentences over 42. Expand every acronym on first use.

**Two tone rules, both gated as hard errors:**

- **Present the analysis; do not adjudicate the reviewer.** No "KLC is wrong", no "we disagree".
  Whether the feedback is borne out is carried by the verdict, not the prose.
- **Report findings, not remedies.** No "we will rename", "we recommend re-parenting". The
  remedy goes in the `action` field, which is internal and never written to the sheet.

House jargon is rejected outright: "union of its bound roles", "code territory", "entitled to",
"observed footprint". Say "this persona covers several roles", "has permission to".

Record it all in `findings.json` (shape in the driver docstring: `claims[]`, `verdict`,
`deviation`, `accion_comment`, `action`).

## Step 6 — Gate, then render

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py gate < findings.json
```

**Exit 2 blocks the write-back.** It fails on: a claim with no evidence, a mixed-verdict finding
rolled up wrong, a comment under 20 words, a comment naming none of its own evidence, a missing
`deviation`, prose that adjudicates the reviewer, and prose that prescribes a remedy. Surface
warnings verbatim — they are findings, not noise.

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py render --sheet sheet.tsv \
  < findings.json > sheet.filled.tsv
```

`render` writes **only the Accion Comments column**. Accion Validation is the reviewing team's
own call and is never touched; `verdict`, `deviation` and `action` stay in `findings.json` for
the report. Any note already in Accion Comments — often a tester observation, and in
`accion-rejection` rows the very claim under test — is **preserved**, with the analysis appended
below a `--- Validation analysis ---` separator. Re-rendering replaces that block rather than
stacking a second copy, so render is idempotent. Every other cell and the column order are
untouched, so it pastes straight back over the original range.

Report to the user: the verdict counts, one line per finding, and — separately — any defect
neither party raised. Recommendations belong in that report, where the business team can weigh
them, not in the sheet. Do **not** write to the functional graph in this skill; renames and
re-parenting are `reconcile-entitlements` Step 7 or `update-functional-graph`, and only once the
business team has decided.

## Step 7 — The analysis document

`report.py` (same folder) writes a standalone **TSV** document of the analysis — one row per
finding, opening straight in Excel. Output is always TSV.

```bash
python3 .claude/skills/validate-scenario-feedback/report.py --sheet sheet.tsv \
  --persona "Operations Support" < findings.json > analysis.tsv
```

This is a **different artifact from `render`**, and both are usually wanted:

| | Writes | Shape |
|---|---|---|
| `validate.py render` | The original review sheet, Accion Comments column only | The sheet as the reviewers know it, annotated in place |
| `report.py` | A new file | One row per finding, reasoning broken into its own columns |

Its 13 columns: identity (Scenario #, Scenario, Outcome #, Outcome, Persona), **Review
direction**, **Claim under test** (our note or the business team's, depending on direction),
**Verdict**, both **Why it sits here** legs, **Analysis**, **Deviation**, and **Claims and
evidence** — every claim flattened with its evidence under it, one cell, newline-separated so
it stays readable in a wrapped Excel cell.

**Gate first.** `report.py` does not re-run the gate; it renders whatever it is given. It joins
findings to sheet rows by Scenario # and exits non-zero if any finding has no matching row.

## Gotchas

- **`reconcile-state.json` is 1.1 MB.** Never `Read` it — query it with `validate.py` or a
  `python3 -c` one-liner. Reading it will blow the context window.
- **`Code_Graph_Search` results routinely exceed the tool's token cap** and get spilled to a file
  under `tool-results/`. That is normal. Parse the spill with `python3`
  (`json.load(open(f))['result']` is itself a JSON *string* — parse it twice), don't re-read it.
- **`Functional_Graph_Search`'s `include_labels` rejects a list through this MCP client**
  (`Input should be a valid list` even for a well-formed array). Omit it and filter the results
  yourself.
- **Module names in the permission data contain typos and transpositions** — the real rows are
  `BUCC Reservatoin Details` (sic) and `NCBRESERVATION` (transposed from NBC). Match against
  `matrix.modules` exactly; `reach`/`adjudicate` will suggest near-matches if you miss.
- **Backup care is two different queues.** `NCBRESERVATION` is in-home; `BUCC Reservatoin
  Details` / `Reservation Request` is center-based. Different personas hold them. Conflating
  them produces exactly the wrong verdict on the persona question.
- **Empty cells in the permission exports arrive as the string `'NULL'`**, not empty — already
  handled upstream in `reconcile-state.json`, but relevant if you go back to the workbooks.
- **Multi-line cells are deliberate.** The evidence column embeds newlines; `csv.writer` quotes
  them so Excel keeps one row. Never assemble the TSV by joining strings with tabs by hand —
  reviewer notes and evidence both contain newlines and quotes that only survive real CSV
  quoting.
- **Match persona names EXACTLY — substring matching silently merges personas.** `"Operations"
  in persona` also catches **Field Operations Business Partner (FOBP)**, which pulls the
  `Field Operations Advisor` role into Operations Support's role set. That single slip flipped
  two verdicts in the first run: modules that looked business-role-granted (`BATCH PROGRAM
  UPDATES`, `MANUAL INVOICES`) are in fact admin-role-only. Always filter
  `p["persona"] == name`, and sanity-check the resulting role list against
  `bindings.pairs` before using it as evidence.
- **A low binding score is a caveat, not a disqualifier.** `Business System Administrator` binds
  to Operations Support at 0.33. The entitlement is real; the binding is the weak link. Say so in
  the comment rather than suppressing the finding.

## Worked example

[`references/worked-example.md`](references/worked-example.md) — the five NBC reservation rows,
end to end: the atomised claims, the commands run, the evidence, and the final comments. Read it
before your first run; it is the calibration for how much evidence a comment needs.
