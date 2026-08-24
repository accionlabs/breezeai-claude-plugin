---
name: map-mdule-outcome-perosna-role-functional
description: >
  Enrich an existing functional graph with the DB roles-and-permissions picture:
  stamp each Persona with the security **roles** that compose it, and each Outcome
  with the DB **modules** it is entitled by. Sources are the reconcile state
  produced by the roles/permissions analysis (`reconcile-state.json` — role→persona
  bindings) and the navigation map (`nav_leaf_to_outcome.json` — outcome→module).
  Writes via per-node `Call_Update_Functional_Node_` after a shape probe, dry-run
  first. Use when: "add roles metadata to personas", "map modules to outcomes",
  "enrich functional graph with roles and permissions", "stamp persona roles",
  "which roles make up this persona", "outcome to module mapping".
argument-hint: "[--project <name|uuid>] [--state <path>] [--nav <path>] [--apply]"
---

## Project

This skill is project-bound — resolve `projectUuid` per `CLAUDE.md`:
`--project` flag → bare UUID → natural-language hint → `.breeze.json` fallback →
list projects and ask. Announce: `Project: <name> (<uuid>)`.
Breeze MCP 401 handling: point the user at `/breeze:project auth`.

> The `meta.project.uuid` recorded inside `reconcile-state.json` is **advisory
> only** — it says which project the reconcile ran against. If it disagrees with
> the resolved project, stop and ask which one is intended. Never silently trust
> the file's uuid.

---

## What this writes

| Node label | Key added | Value |
|---|---|---|
| `Persona` | `roles` | every security role bound to that persona, sorted |
| `Outcome` | `modules` | every DB module whose nav leaf resolves to that outcome, sorted |

## Bulk-update answer (settled — do not re-derive)

**There is no bulk metadata endpoint.** `bulk_update_functional_nodes` is the
only bulk writer and it is wrong here twice over:

1. Its accepted fields are fixed per level (Persona: `persona`, `outcomes`,
   `citations`; Outcome: `outcome`, `scenarios`, `citations`). There is no
   metadata slot.
2. It writes `description` unconditionally — resending a subtree without every
   description **nulls them**, across the whole scenario tree.

So the write path is `Call_Update_Functional_Node_`, one call per node, which
patches only the keys passed. That is a few dozen to a few hundred calls; that
is expected and fine. If the user offers a REST bulk endpoint, take it — but
only after step 3 shows what payload shape actually persists.

---

## Execution Flow

### 1. Locate the inputs

Default to the two files sitting next to this skill:

- `reconcile-state.json` — needs `bindings.pairs`, `bindings.unbound_roles`,
  `bindings.unbound_personas`.
- `nav_leaf_to_outcome.json` — needs `leaves[]` with `label` / `module` / `outcome`.

`--state` / `--nav` override. If either is missing, stop and ask for the path —
do not attempt to reconstruct the mapping from the graph or from the `.xlsx`
files in `Fw_ CMS roles and permission/`.

### 2. Build the plan (no graph access)

```bash
python3 scripts/build_patches.py plan \
    --state reconcile-state.json \
    --nav   nav_leaf_to_outcome.json \
    --out   plan.json
```

Three rules the script enforces — restate their results to the user, don't
re-implement them:

- **`unbound_roles` are excluded.** They are unbound by design (zero-grant
  roles that entitle nothing, or roles whose persona was deleted). Re-attaching
  them would resurrect removed mappings.
- **outcome→module is many-to-one.** Several nav leaves can carry different
  modules into the same outcome, so `modules` is always an array.
- **Dead leaves (`outcome: null`) are reported, never written.**

If the script prints `pairs flagged needs_confirmation`, show those role→persona
pairs with their score and evidence and ask the user to confirm or drop each one
before continuing. Regenerate `plan.json` by hand-editing it if they drop any.

### 3. Dump the graph's Persona and Outcome nodes

```
Get_Functional_Nodes_By_Label(uuid=<project>, label="Persona", limit=100)
Get_Functional_Nodes_By_Label(uuid=<project>, label="Outcome", limit=100)
```

Page until `len(data) == total` — the default page size truncates silently.
There is **no `name` field**; filtering on one returns 0 rows with no error, so
match on `nameKey` (already trimmed+lowercased) and let the script normalize.

**Hard gate:** if the Persona list comes back empty, stop and report it. Either
the uuid is wrong or the graph is empty — writing zero nodes is not success.

Write the collected rows to `nodes.json`:

```json
{"personas": [{"id": 11, "persona": "Analyst", "nameKey": "analyst"}, ...],
 "outcomes": [{"id": 91, "outcome": "Manage Session Types", "nameKey": "..."}, ...]}
```

### 4. Probe the payload shape (once per project, before any bulk write)

The graph's accepted key shape is not documented — settle it empirically rather
than guessing between a top-level `roles` and a nested `metadata.roles`. This
API validates strictly (a numeric-string `order` is rejected 400, an `apis`
array inside an Action's `data` 500), so **probe one key at a time** — a
combined payload yields one opaque error that names no key.

1. Pick a probe persona that appears in **both** `nodes.json` and
   `plan.json` — it must have a real `roles` value to restore.
2. `Call_Update_Functional_Node_(label="Persona", node_id=<id>,
   data={"roles": ["__probe__"]})`.
3. Read it back: `Get_Functional_Nodes_By_Label(label="Persona",
   filters={"nameKey": {"$eq": "<that persona lowercased>"}})`.
   - `roles: ["__probe__"]` present → shape is `--key roles:modules`.
   - Call errored, or the key is absent from the read-back → retry once with
     `data={"metadata": {"roles": ["__probe__"]}}` and read back again. Present
     → shape is `--key metadata.roles:metadata.modules`.
4. **Immediately** re-patch that persona with its real `roles` from `plan.json`
   in the surviving shape, and confirm by read-back. Do not defer this to
   step 6 — the run can abort at the dry-run gate or mid-apply, and a stranded
   `__probe__` in a live graph is the worst outcome here.

**If neither key survives**, stop. Report exactly this: the graph rejects
arbitrary keys on `Call_Update_Functional_Node_`; print one sample payload
(`{"label":"Persona","node_id":…,"data":{"roles":[…]}}`) plus the total patch
count — run step 5 with `--key roles:modules` just to produce it; `resolve` is
offline and writes nothing — and ask for the REST endpoint the user offered. Do not invent
an endpoint, and do not smuggle the data into `description`. Confirm the probe
persona was left clean before stopping.

### 5. Resolve to real node ids (dry run)

```bash
python3 scripts/build_patches.py resolve \
    --plan plan.json --nodes nodes.json \
    --key roles:modules \
    --out patches.json
```

The same outcome name exists as **several distinct nodes** under different
personas — the script patches every matching id, which is intended.

Present the coverage block before writing anything:

```
Project: <name> (<uuid>)

Persona → roles     N patches over M graph personas
Outcome → modules   N patches over M graph outcomes

Planned but not in graph   personas: …   outcomes: …     ← name drift, investigate
In graph but unmapped      personas: …   outcomes: …     ← no source mapping, left alone
Outcomes patched under multiple personas: …
Roles intentionally unbound (not written): …
Nav leaves with no outcome (dead modules): …
```

Never collapse the unmatched lists into a count alone — partial coverage
presented as a single number reads as "done". Then ask:
*"Apply these N updates? (`yes` / `no` / a subset)"*. Skip the prompt only when
`--apply` was passed.

### 6. Apply

For each entry in `patches.json`:

```
Call_Update_Functional_Node_(uuid=<project>, label=<label>,
                            node_id=<node_id>, data=<data>)
```

Send only the mapping key — no `persona`/`outcome`/`description` alongside it,
so nothing else is touched. Batch ~10 concurrently. Record each failure with its
node id and error; do not abort the run on a single failure.

### 7. Verify and report

Re-read 3–5 patched nodes (one Persona, one Outcome, one multi-module Outcome)
and confirm the key is present with the expected array. Then report:

```
Applied: <n> Persona, <n> Outcome    Failed: <n> (listed with node ids + errors)
Verified: <sample node> roles=[…] / modules=[…]
Unmapped and untouched: <n> personas, <n> outcomes
```

State plainly if any part was skipped. Re-running is safe — every patch is a
full replacement of the key, so the second run converges to the same state.

---

## Notes

- Re-running after the source files change is the supported update path; there
  is no incremental merge (the key is replaced wholesale, so a role removed from
  `bindings.pairs` disappears from the persona on the next run — which is
  correct).
- The `.xlsx` files under `Fw_ CMS roles and permission/` are the raw upstream
  export. They are **not** read by this skill; `reconcile-state.json` is the
  reconciled, user-confirmed derivative of them and is the only accepted source.
- `matrix.roles[*].footprint` (role → [module, verb] pairs) is available in the
  state file if the user later wants module entitlement stamped on the persona
  too. Not written today — ask before extending scope.
