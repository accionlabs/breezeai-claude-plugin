# Fix Protocols per Category

Apply fixes in hierarchy order: Persona → Outcome → Scenario → Step → Action.

## missing — create new nodes

Use `Call_Create_Functional_Node_` top-down. Apply persona, outcome, scenario, step,
and action rules from `../shared/functional-graph-rules.md`. Attach a citation to
every node:

```json
{ "type": "confluence", "reference": "<page-url>", "inputText": "<relevant excerpt>" }
```

## wrong-persona / misplaced — re-parent or report-only

First check whether `Call_Update_Functional_Node_` accepts a parent-ID field
(`personaId` for Outcomes, `outcomeId` for Scenarios):
→ run `ToolSearch: "Call_Update_Functional_Node"` and inspect the loaded schema.

**If the schema accepts a parent-ID field:** update with the new parent ID + citation.
No duplicate is created.

**If the schema does NOT accept a parent-ID field:** do NOT re-create the node.
Re-creating produces a duplicate — `validate-graph.py` flags this as a P1 defect.
Instead mark as **manual action required** and output the exact
`Call_Create_Functional_Node_` payload so the user can apply it after manually removing
the old node.

## contradicted — update description

Call `Call_Update_Functional_Node_` with the corrected description and a citation.
The citation field name varies across this repo (`citationIds` vs `citations`) —
inspect the tool schema via ToolSearch and use whatever it specifies.

## stale — report only, write nothing

Do NOT modify stale nodes. Do NOT prepend text to descriptions (it corrupts
system-action description fields and is non-idempotent on re-runs). Tell the user:

> *"Finding #N: `<node name>` may be stale — `<url>` supersedes this behaviour.
> Review and remove manually if appropriate."*

## terminology-drift — update node name

Call `Call_Update_Functional_Node_` with the corrected term in the relevant field
(`scenario`, `outcome`, or `action`) and a citation.
