# Functional ID Linkage Integrity — stepIds & actionIds

**Date:** 2026-10-15  
**Scope:** `generate-design-from-ui` skill + `validate-design-graph` validator  
**Question:** Since Flows, Pages, and Components are reusable (multi-parent), can the same functional `stepId` or `actionId` land on multiple design nodes incorrectly — and how do we stop it?

---

## 1. Background — What Reusability Means for Functional IDs

The design ontology supports multi-parent reuse:

| Node | Reused via | Backend behaviour on upsert |
|---|---|---|
| Flow | `userJourneyIds[]` | Appends new UJ ID + **appends new `stepIds`** |
| Page | `flowIds[]` | Appends new Flow ID + **appends new `stepIds`** |
| Component | `pageIds[]` | Appends new Page ID + **appends new `actionIds`** |

**The critical word is _appends_.** Every time a reused node appears in a new scenario's payload, the backend merges the new `stepIds`/`actionIds` arrays into the existing node. Over many scenarios this silently accumulates IDs from unrelated journeys onto the same node.

---

## 2. Four Corruption Scenarios

### Scenario A — stepId on both a Flow and a Page (P0 violation)

**What the pitfalls doc says:** _"Mapping step to BOTH Flow and Page — Schema violation — Exclusive: Flow OR Page"_

**How it happens with reuse:**

```
Scenario 1 (creates nodes):
  Flow "Login Flow"    → stepIds: [step-1, step-2]
  Page "LoginPage"     → stepIds: [step-3]

Scenario 2 (reuses Flow, creates new Page):
  Flow "Login Flow"    → stepIds: [step-1, step-2]   ← reused, same steps included again
  Page "VerifyPage"    → stepIds: [step-1]            ← step-1 also on this page

After backend merge:
  Flow "Login Flow"    → stepIds: [step-1, step-2]   ← step-1 here
  Page "VerifyPage"    → stepIds: [step-1]            ← AND step-1 here ← VIOLATION
```

The sub-agent in Scenario 2 included step-1 in the reused Flow's stepIds (because the ontology says "shared steps can appear in multiple flows") AND also placed it on the new page. The step is now on both a Flow and a Page — a schema violation that no check currently catches.

---

### Scenario B — actionId on multiple Components (P1 ambiguity)

**How it happens:**

```
Scenario 1:
  SearchInputComponent (ATOM)  → actionIds: [action-enter-query]

Scenario 2 (reuses same page, different component scope):
  SearchBarOrganism (ORGANISM) → actionIds: [action-enter-query]
  (SearchBarOrganism contains SearchInputComponent)

After merge:
  SearchInputComponent  → actionIds: [action-enter-query]
  SearchBarOrganism     → actionIds: [action-enter-query]
```

One functional action is now implemented by two components. Queries like "which component handles this action?" return two answers. Impact analysis becomes unreliable.

---

### Scenario C — actionId accumulation on global ATOMs/TEMPLATEs

**How it happens:**

`PrimaryButton` (ATOM, GLOBAL scope) is reused on 80 pages across 200 scenarios. Each scenario that has a "click submit / confirm / save" action maps that actionId to `PrimaryButton`. After 200 scenarios the component has 200 actionIds from completely unrelated user journeys — payment confirmation, profile save, search submit, CPD module completion, etc.

```
PrimaryButton.actionIds = [
  action-confirm-payment,     ← from Purchase flow
  action-save-profile,        ← from Profile flow
  action-submit-search,       ← from Search flow
  action-complete-module,     ← from CPD flow
  ... (196 more)
]
```

The actionIds on `PrimaryButton` are now meaningless — they represent every button-click in the entire application, not the specific semantics of this component.

---

### Scenario D — stepId accumulation on a reused Flow across many scenarios

**How it happens:**

`Email Login Flow` is reused across 15 scenarios (e.g., login from product page, login from CPD, login from newsletter redirect, etc.). Each scenario adds its own stepIds:

```
After 15 scenarios:
  Flow "Email Login Flow" → stepIds: [
    step-login-1, step-login-2,       ← Scenario 1 (login from homepage)
    step-cpd-login-1,                 ← Scenario 2 (login from CPD)
    step-redirect-login-1,            ← Scenario 3 (login from redirect)
    ... (30+ stepIds from 15 scenarios)
  ]
```

The flow now carries steps from contexts it was never designed for. A step from "CPD login" on the generic "Email Login Flow" is factually incorrect — that step belongs in a CPD-specific scenario context, not on a shared flow.

---

## 3. What the Current Validator Catches (and Doesn't)

### In `validate-design.py` (offline — no functional graph required)

| Check | What it catches | Covers these scenarios? |
|---|---|---|
| CHECK 1d `duplicate_linkage` | Same ID repeated **within** one node's array (e.g., `stepIds: ["a","a"]`) | ❌ Cross-node, not intra-node |
| CHECK 4 `missing_scenario_id` | UJ has no `scenarioId` | ❌ Different problem |
| CHECK 4b `duplicate_scenario_ids` *(new)* | Same scenarioId on two UJs | ❌ Different problem |

### In `_run_functional_cross_check` (only runs with `--functional`)

| Check | What it catches | Covers these scenarios? |
|---|---|---|
| `dangling_step_refs` | stepId not in functional graph | ❌ Doesn't flag cross-node duplication |
| `unmapped_steps` | Functional step not in any design node | ❌ Uses a flat set — dedups silently |
| `dangling_action_refs` | actionId not in functional graph | ❌ Doesn't flag cross-component duplication |
| `unmapped_actions` | Functional action not in any design node | ❌ Uses a flat set — dedups silently |
| `step_action_consistency` | Action's parent step not reachable from component's page | ⚠️ Partially catches Scenario A side-effects, misses direct Flow+Page overlap |

### Critical gap — the flat `set()` problem

Lines 1094 and 1141 in the validator:

```python
design_step_ids = set()   # line 1094 — merges Flow stepIds + Page stepIds into one set
design_action_ids = set() # line 1141 — merges all Component actionIds into one set
```

Because both collect into a flat set:
- A stepId on both a Flow and a Page looks "covered once" — no violation flagged
- An actionId on two Components looks "covered once" — no violation flagged
- The `unmapped_steps` check passes even when a step is double-mapped

---

## 4. Prevention — Rules for the Generation Skill

### Rule 1: stepIds are exclusive to either Flow OR Page — never both

When a step is a **navigation step** (user moves between screens) → place on the **Flow**.  
When a step is an **interaction step** (user acts on a page) → place on the **Page**.  
Never include the same stepId in both a Flow's `stepIds[]` and a Page's `stepIds[]`.

The sub-agent's self-validate (Phase 3d) must enforce this before every upsert.

### Rule 2: When reusing a Flow or Page, pass empty stepIds

If a Flow or Page is being included in a payload **only to create the parent edge** (reuse case), pass it with `stepIds: []`. Do NOT re-include the original scenario's stepIds in the reuse payload.

```json
// CORRECT — reuse for edge only, no stepId accumulation:
{
  "name": "Email Login Flow",
  "modality": "WEB",
  "userJourneyIds": [],
  "stepIds": [],
  "pages": []
}

// WRONG — re-including stepIds causes accumulation:
{
  "name": "Email Login Flow",
  "modality": "WEB",
  "stepIds": ["step-1", "step-2"],
  "pages": []
}
```

The first scenario to create the Flow sets the canonical stepIds. Subsequent reuses just link parents without touching stepIds.

### Rule 3: actionId belongs to exactly one Component per scenario

Within a single scenario's payload, each `actionId` must appear on at most one Component. If an action is logically implemented by a child component inside an organism, place the actionId on the **most specific** component (lowest in the hierarchy), not the parent.

```
// WRONG — same actionId on both:
SearchBarOrganism.actionIds   = [action-enter-query]
SearchInputComponent.actionIds = [action-enter-query]

// CORRECT — most specific component only:
SearchBarOrganism.actionIds   = []
SearchInputComponent.actionIds = [action-enter-query]
```

### Rule 4: Do not map generic actions to global ATOMs

Actions on global ATOMs (TEMPLATE, ATOM, global-scope MOLECULE) should only be mapped when the action is **specific to that component's unique function**. A generic "click" or "submit" action that could apply to any button should NOT be mapped to `PrimaryButton` — it should map to the ORGANISM that contains the button and owns the submit context (e.g., `LoginFormComponent.actionIds = [action-submit-login]`).

---

## 5. Detection — New Validator Checks Needed

### Check A: stepId on both Flow AND Page (P0)

```python
# Build separate sets for flow stepIds and page stepIds
flow_step_ids = defaultdict(list)   # stepId → list of flow names
page_step_ids = defaultdict(list)   # stepId → list of page names

for f in flows:
    for stid in (f.get("stepIds") or []):
        flow_step_ids[stid].append(f.get("name", "N/A"))

for p in pages:
    for stid in (p.get("stepIds") or []):
        page_step_ids[stid].append(p.get("name", "N/A"))

# Intersection = violation
overlap = set(flow_step_ids) & set(page_step_ids)
violations = [
    {
        "stepId": stid,
        "on_flows": flow_step_ids[stid],
        "on_pages": page_step_ids[stid],
        "issue": "stepId appears on both Flow and Page — exclusive mapping violated"
    }
    for stid in overlap
]
# Severity: P0
```

### Check B: actionId on multiple Components (P1)

```python
action_id_to_components = defaultdict(list)  # actionId → list of component names

for c in components:
    for aid in (c.get("actionIds") or []):
        action_id_to_components[aid].append({
            "name": c.get("name", "N/A"),
            "type": c.get("type", "N/A"),
        })

dup_action_ids = [
    {
        "actionId": aid,
        "count": len(comps),
        "components": comps,
        "issue": "actionId mapped to multiple Components — ambiguous implementation"
    }
    for aid, comps in action_id_to_components.items()
    if len(comps) > 1
]
# Severity: P1
```

### Check C: actionId accumulation on global ATOMs/TEMPLATEs (P1)

```python
GLOBAL_TYPES = {"ATOM", "TEMPLATE"}
ACTION_ACCUMULATION_THRESHOLD = 5  # more than 5 actionIds on a global component is suspicious

accumulation_violations = []
for c in components:
    if c.get("type") in GLOBAL_TYPES:
        aids = c.get("actionIds") or []
        if len(aids) > ACTION_ACCUMULATION_THRESHOLD:
            accumulation_violations.append({
                "name": c.get("name", "N/A"),
                "type": c.get("type"),
                "actionId_count": len(aids),
                "issue": f"Global {c.get('type')} has {len(aids)} actionIds — likely accumulation from reuse across scenarios"
            })
# Severity: P1
```

### Check D: stepId appearing on more than N Flows (P1)

```python
STEP_FLOW_THRESHOLD = 3  # same step on > 3 flows is suspicious

step_flow_count = Counter()
step_flow_names = defaultdict(list)
for f in flows:
    for stid in (f.get("stepIds") or []):
        step_flow_count[stid] += 1
        step_flow_names[stid].append(f.get("name", "N/A"))

over_shared_steps = [
    {
        "stepId": stid,
        "flow_count": count,
        "flows": step_flow_names[stid],
        "issue": f"stepId appears in {count} Flows — may indicate cross-scenario stepId accumulation"
    }
    for stid, count in step_flow_count.items()
    if count > STEP_FLOW_THRESHOLD
]
# Severity: P1
```

---

## 6. Summary — Gaps vs. Fixes

| Problem | Currently caught? | Prevention (generation) | Detection (validator) |
|---|---|---|---|
| stepId on both Flow AND Page | ❌ Never | Self-validate Phase 3d: check intersection before upsert | New Check A — P0 |
| actionId on multiple Components | ❌ Never | Phase 3 rule: most-specific component wins | New Check B — P1 |
| actionId accumulation on global ATOMs | ❌ Never | Rule: no generic actions on ATOMs/TEMPLATEs | New Check C — P1 |
| stepId accumulation on reused Flow | ❌ Never | Reuse rule: pass `stepIds: []` for link-only includes | New Check D — P1 |
| stepId on multiple Flows intentionally | ✅ Allowed by design (shared navigation steps) | No change needed | Check D threshold-based, not hard-block |
| Cross-node checks require `--functional` | ⚠️ Checks A–D work without functional graph | n/a | Checks A–D are standalone — no `--functional` needed |

---

## 7. Files to Change

| File | Change |
|---|---|
| `skills/validate-design-graph/scripts/validate-design.py` | Add Checks A, B, C, D to `run_checks()` |
| `agents/design-from-ui-structuring-agent.md` | Phase 3d self-validate: add stepId exclusivity check; add Rule 3 (actionId to most-specific component) |
| `skills/generate-design-from-ui/references/design-ontology.md` | Clarify: "Shared steps can appear in multiple flows' `stepIds[]`" is for intentional shared navigation steps only — not for reuse payloads |
| `skills/generate-design-from-ui/references/reusability.md` | Add Rule 2: when reusing Flow/Page for edge only, pass `stepIds: []` |
| `skills/generate-design-from-ui/references/pitfalls.md` | Add rows for actionId accumulation and stepId-on-reused-flow |
