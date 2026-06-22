This document defines how to express the functional intent behind a visual design as structured user stories, using the canonical functional graph model.

> **Single source of truth.** The node model, persona rules, action language (platform-agnostic intent verbs, forbidden UI words), citations, and validation are defined in `../../shared/functional/core.md` + `../../shared/functional/human-overlay.md`. **Read those first.** This file adds ONLY the visual-design → functional-graph mapping. Do not restate or override the canonical definitions here. (ADR 0001.)

### Functional Graph

Core hierarchy (see `core.md §1` for the authoritative definitions):

**Persona → Outcome → Scenario → Step → Action**

**Modeling rule (canonical — this corrects an earlier draft of this file):**
- **Outcome** = a high-level business capability the persona needs.
- **Scenario** = a *specific, testable flow* under that Outcome — a distinct interaction path with a clear start and end. **Distinct paths are distinct Scenarios** (not "variation layers").
- **Step** = a *sequential stage* within a Scenario — an **ordered** phase of the flow. A Step is a workflow stage, **not** a configuration variation.
- **Action** = an atomic operation or input within a Step.

When a design shows a variation (with coupon / without coupon, saved address / new address), model it as a **sibling Scenario** under the same Outcome — never as a Step. Steps are the ordered stages every run of that Scenario passes through.

---

### Persona

A role-based actor — WHO performs the requirement (a behavioural category, not an individual). Examples: Buyer, Guest User, Admin, Seller, Support Agent. A Persona can perform multiple Outcomes; multiple Personas may share an Outcome. Visual-to-text produces **human** personas — apply the persona-derivation and forbidden-name rules in `human-overlay.md §1`.

---

### Outcome

A high-level business capability the persona wants to achieve — WHAT success means. Examples: Purchase Product, Register Account, Track Order, Reset Password. Prefer broad Outcomes; capture variation as Scenarios, not new Outcomes (see `core.md §2`).

Example — Outcome `Purchase Product` with sibling Scenarios:
- Purchase using a saved address
- Purchase using a new address
- Purchase via guest checkout
- Purchase via express checkout

---

### Scenario

A specific, testable flow under an Outcome — you can write acceptance criteria for it, and it has a clear start and end. Scenarios are distinct **interaction paths**, captured as siblings under the Outcome. Reuse an existing Scenario when the flow is semantically similar; if two share >70% of their steps, consider merging.

Example — Outcome `Purchase Product`, Scenario `Purchase using a saved address`.

---

### Step

A **sequential stage** within a Scenario — the ordered phases the user passes through to complete the flow. A Step name is a short verb phrase; Steps do not require descriptions. A Scenario typically has 3–8 Steps.

Example — Scenario `Purchase using a saved address`, Steps (in order):
1. Review cart contents
2. Confirm shipping address
3. Apply promotions
4. Choose payment method
5. Place order

---

### Action

An atomic operation or input within a Step. For human personas, actions describe what the user **provides, decides, or observes** and must be **platform-agnostic** — use intent verbs (Provide, Choose, Confirm, Review, Submit, …) and never UI words (click, button, modal, …). See `human-overlay.md §2`. `description = null` unless there is a real user-facing constraint. The only leaf below Action is `apis[]` — there is **no** `Action TRIGGERED_BY Component` relationship in the functional graph (that belongs to the design graph).

---

### Functional Graph Example

```
Buyer                                  (Persona)
  └─ Purchase Product                  (Outcome)
       └─ Purchase using a saved address   (Scenario — one specific flow)
            ├─ Review cart contents        (Step 1 — sequential stage)
            │    └─ Review line items and order total
            ├─ Confirm shipping address    (Step 2)
            │    └─ Confirm the saved shipping address
            ├─ Apply promotions            (Step 3)
            │    └─ Provide promotion code
            ├─ Choose payment method       (Step 4)
            │    └─ Select payment method
            └─ Place order                 (Step 5)
                 └─ Submit order
```

"Purchase with coupon" vs "without coupon" are **sibling Scenarios** under `Purchase Product`, not Steps.

---

### Visual Design → Functional Graph Mapping

| Design element | Maps to | Guidance |
|---|---|---|
| Entire page/screen purpose, or a multi-screen journey | **Outcome** | What business capability does this serve? |
| A distinct user flow / path through the design | **Scenario** | A specific, testable path with a clear start and end. Variations (with/without coupon) = sibling Scenarios. |
| A sequential stage within that flow (a section the user completes before moving on) | **Step** | An ordered phase of the Scenario. |
| User inputs, selections, confirmations | **Action** | Platform-agnostic intent activity (one atomic action per editable field — see `human-overlay.md §3`). |
| Success state / happy path vs an alternate path | **Scenario** | Distinct flows under the Outcome. |
| Error / validation state within a flow | **Step** or **Action** | A stage (e.g. "Resolve validation errors") or an action within one. |
| Navigation between screens of one flow | **Step** boundary | The transition between sequential stages of the same Scenario. |

**Key principle:** extract WHAT the design enables the user to achieve, not HOW it looks or WHERE elements sit.
