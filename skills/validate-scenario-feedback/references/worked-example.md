# Worked example — the five NBC reservation rows

The run this skill was built from. Persona **Operations Support**, outcomes 4.2 / 4.3, scenarios
4.2.1 and 4.3.1–4.3.4. All five carried Accion `Unsure` + KLC `Incorrect` and the same comment:

> NBC is not a term the business uses. These scenarios appear to be pulling that from the schema
> structure itself, however the business would simply refer to this process as backup care.
> We should understand which role is driving the references for backup care to this persona.
> These processes and scenarios are better aligned with Family Support

## Step 2 — atomised

Two claims, and they do **not** get the same verdict:

| # | Claim | Kind |
|---|---|---|
| A | "NBC" is schema jargon; the business says backup care | `terminology` |
| B | These scenarios belong under Family Support | `persona-parentage` |

## Step 3 — the commands, and what came back

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py territory --state reconcile-state.json \
  --cite "CMS/Controls/BUCCMVP/NBCReservation/SearchNbcReservation.ascx"
```
→ `NCBRESERVATION` (matched on `paths`). That is the module gating these screens.

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py adjudicate --state reconcile-state.json \
  --persona "Operations Support" --modules "NCBRESERVATION" --verb write
```
→ `"verdict": "entitled"`, via role **Business System Administrator** (score 0.33), read+write.

```bash
python3 .claude/skills/validate-scenario-feedback/validate.py adjudicate --state reconcile-state.json \
  --persona "Family Support" --modules "NCBRESERVATION" --verb write
```
→ `"verdict": "unentitled"`, `via_roles: []`. Re-running with `--verb read` is also `unentitled`
— Family Support cannot even open the screen.

Family Support's three bound roles and their backup-care footprint:

| Role | Backup-care footprint |
|---|---|
| Family Support | `Backup Child Care` read |
| Enrollment Center Specialist | `BUCC Reservatoin Details` r/w, `Reservation Request` read, `Backup Child Care` read |
| Enrollment Center Manager | same as Specialist |

**None hold `NCBRESERVATION`.**

## The findings

**Claim A — `klc-correct`.** "NBC" appears only in system internals: the permission module is
literally `NCBRESERVATION` (transposed), the code lives under
`CMS/Controls/BUCCMVP/NBCReservation/`, the proc is `NBC_GetReservations`, and the service method
is `UpdateBackupCareNbcReservation` — which carries *both* "BackupCare" and "Nbc", confirming
they name the same process. The business-facing permission modules are `Backup Child Care` and
`Reservation Request`. Nothing customer-facing says NBC.

Corroboration from a sibling subtree: **System Administrator** already has
`Process In-Home Backup Care Reservations`, describing this same screen in business language.
So the rename target is not just "backup care" but **In-Home Backup Care** — the precise term,
which keeps it distinct from center-based backup care.

**Claim B — `klc-incorrect`.** Family Support holds nothing on `NCBRESERVATION`; Operations
Support holds read+write. Re-parenting would produce an edge the entitlement data contradicts.

**Why KLC thought otherwise** — and this belongs in the comment: Family Support *does* handle
backup care, the **center-based** kind, through `BUCC Reservatoin Details` (read+write). Two
different queues, one business phrase. That is the whole misunderstanding.

**Roll-up: `klc-partially-correct`** for all five rows.

## The defect neither party raised

Recorded on 4.3.3 as an `unresolved` `process-detail` claim: System Administrator's
`Process In-Home Backup Care Reservations` / `Process an in-home reservation request` carries the
same approve, deny and cancel actions against the same `EnrollmentFacade.UpdateBackupCareNbcReservation`.
The capability is documented **twice**, under two personas that are **both** entitled — so
entitlement cannot settle the owner. Needs a business decision, not more evidence.

## The comment that shipped (4.2.1)

Accion Validation: **Partially confirmed**

> The term 'NBC' appears only in system internals: the permission module is named
> NCBRESERVATION, the stored procedure is NBC_GetReservations, and the code sits under
> CMS/Controls/BUCCMVP/NBCReservation/. Nothing business-facing carries the term — the
> business-facing permission modules are named Backup Child Care and Reservation Request. The
> same screen is already described as 'In-Home Backup Care Reservations' under the System
> Administrator persona, and that fuller phrasing distinguishes it from the centre-based
> reservations, which are a separate queue. On access: this screen is gated by the
> NCBRESERVATION module. Operations Support reaches it only through the Business System
> Administrator role — the broadest role in the system, bound to this persona at a weak 0.33
> confidence score — and none of the persona's business roles hold NCBRESERVATION at all. Family
> Support holds no permission on NCBRESERVATION either, so the screen is not reachable by those
> roles; the modules Family Support does hold are BUCC Reservatoin Details and Reservation
> Request, which cover the centre-based backup care queue.

Note what it does and does not do. It names the module, the role and the procedure, spells out
what each *means*, states the access facts plainly, and explains what the business was seeing
(Family Support really does do backup care — a different queue). It never says who was right,
and it never says what to change. Those live in the Accion Validation column and in the internal
`action` field respectively. That is the bar the gate is calibrated to.

The `action` recorded internally for this row, never written to the sheet:

> Rename 'NBC' to 'In-Home Backup Care'. Re-parent to BUCC Admin / System Administrator, not
> Family Support. Review the Business System Administrator binding to Operations Support.

## Caveat carried forward

`Business System Administrator` binds to Operations Support at **0.33** — the weakest link in
the chain. The entitlement is real; the binding is the assumption. If the business disputes the
persona further, re-examine that binding before re-examining the entitlement.
