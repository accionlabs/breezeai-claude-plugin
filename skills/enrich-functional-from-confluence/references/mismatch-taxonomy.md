# Mismatch Taxonomy

## Categories

| Category | Severity | Meaning | Evidence to collect |
|---|---|---|---|
| `missing` | P0 | Doc requirement has no corresponding graph node | Requirement key, missing keyword count |
| `wrong-persona` | P1 | Outcome/scenario owned by wrong persona per the doc | Node name, current persona, persona the doc implies |
| `misplaced` | P1 | Scenario sits under the wrong outcome | Scenario name, current outcome, correct outcome per doc |
| `contradicted` | P1 | Action description conflicts with a rule, threshold, or field stated in the doc | Action text, graph description, doc excerpt |
| `stale` | P1 | Graph asserts behaviour the doc positively supersedes or removes | Node name, doc excerpt that contradicts it |
| `terminology-drift` | P2 | Graph uses different words for the same concept as the doc | Graph term, doc term |

## Detection approach per category

**`missing`** — covered by Step 4 coverage check (MISSING/PARTIAL items). Carry those
findings forward; do not re-detect here.

**`wrong-persona`** — for each Outcome and Scenario in the working subgraph, find which
persona the doc attributes that capability to. Flag mismatches.

**`misplaced`** — check whether the Scenario's parent Outcome name matches the doc section
the Scenario's keywords fit best. If a different doc section heading is a better match,
flag as misplaced.

**`contradicted`** — for every System-persona action with a description (threshold, formula,
field list, limit), locate the same rule in the doc. If values differ, flag with both versions.

**`stale`** — only flag when the doc **actively** contradicts or supersedes the node.
Doc silence is NOT staleness — a node the page doesn't mention may cover functionality
outside this page's scope.

**`terminology-drift`** — compare entity and status names used in the graph against the
doc's vocabulary. Flag synonyms (e.g. graph says "purchase", doc says "order").

## Finding object schema

Each finding must carry:

```
id           — integer, 1-based
category     — one of the six above
severity     — P0 / P1 / P2
location     — "Persona > Outcome > Scenario > Step > Action" (as applicable)
node_id      — graph node ID (for MCP update calls)
evidence     — short excerpt from both the graph and the doc
proposed_fix — one-line concrete change
```
