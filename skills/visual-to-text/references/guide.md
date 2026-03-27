This document defines the functional graph model used to express functional intent behind visual designs as structured user stories.

### Functional Graph

Core hierarchy:

**Persona → Outcome → Scenario → Step → Action**

**Important Modeling Rule:**
Outcome, Scenario, and Step represent variation layers.
Action represents the execution-level logical activity that fulfills the Step, which ultimately enables completion of the Scenario and Outcome.

---

### Persona

**Definition:**
Persona represents a role-based actor interacting with the system.
Persona defines WHO performs a requirement.
A Persona is not an individual user, but a behavioral category of system users.

**Examples:**
- Buyer
- Guest User
- Admin
- Seller
- Support Agent

**Characteristics:**
- A Persona can perform multiple Outcomes
- Multiple Personas may perform the same Outcome
- Persona defines the requirement ownership context

**Relationship:**
Persona PERFORMS Outcome

**Example:**
Buyer PERFORMS Purchase Product

---

### Outcome

**Definition:**
Outcome represents a complete objective that a Persona wants to achieve.
Outcome defines WHAT success means from the actor's perspective.
Outcome represents the highest-level capability completion state.

**Examples:**
- Purchase Product
- Register Account
- Track Order
- Cancel Order
- Reset Password

**Characteristics:**
- Outcome represents a completed task objective
- Outcome contains multiple execution variations
- Outcome may belong to multiple Personas

**Relationship:**
Outcome HAS_SCENARIO Scenario

**Example:**
Outcome: Purchase Product
Possible Scenarios:
- Purchase using saved address
- Purchase using new address
- Purchase using guest checkout
- Purchase using express checkout

---

### Scenario

**Definition:**
Scenario represents a variation of how an Outcome can be completed.
Scenario defines execution context differences.
Scenario answers the question:
"Under what condition or approach is the Outcome completed?"

**Example:**
Outcome: Purchase Product
Scenario: Purchase using saved address

**Characteristics:**
- Scenario is a variation of Outcome
- Scenario contains multiple Steps
- Scenarios are independent from each other

**Relationship:**
Scenario HAS_STEP Step

---

### Step

**Definition:**
Step represents a variation inside a Scenario.
A Step is not a workflow stage.
Step represents a configuration-level variation describing how the Scenario itself is completed.
Each Step represents a complete requirement slice.

**Variation Model:**
- Scenario = variation layer 1
- Step = variation layer 2

**Example:**
Outcome: Purchase Product
Scenario: Purchase using saved address
Steps:
- Purchase using saved address with coupon
- Purchase using saved address without coupon
- Purchase using saved address with wallet payment
- Purchase using saved address with default payment method

Each Step represents a valid completion configuration of the Scenario.

**Characteristics:**
- Step is a variation of Scenario
- Step is an independently complete requirement slice
- Step contains multiple Actions

**Relationship:**
Step HAS_ACTION Action

---

### Action

**Definition:**
Action represents a named logical activity required to fulfill a Step.
Actions represent the execution-level activities necessary to complete the requirement.
Each Action may involve multiple interactions or operations, but the requirement model represents them as a single logical activity.
Actions collectively fulfill the Step, which completes the Scenario, which ultimately achieves the Outcome.

**Execution Relationship:**
Actions → complete Step
Step → realizes Scenario
Scenario → achieves Outcome

**Characteristics:**
- Actions represent logical activities
- Actions are the lowest level of requirement definition
- Actions may involve multiple interactions internally
- All Actions belonging to a Step must be completed for Step completion

**Relationship:**
Action TRIGGERED_BY Component

---

### Functional Graph Example

The following example demonstrates the functional hierarchy:

```
Buyer
  ↓
Purchase Product
  ↓
Purchase using saved address
  ↓
Purchase with coupon
  ↓
Select product
Add to cart
Confirm address
Apply coupon
Select payment
Submit order
```

**Explanation:**
- Persona: Buyer
- Outcome: Purchase Product
- Scenario: Purchase using saved address
- Step: Purchase with coupon
- Actions: Select product, Add to cart, Confirm address, Apply coupon, Select payment, Submit order

All actions together complete the Step.

---

### Visual Design to Functional Graph Mapping

When translating a visual design into the functional graph:

| Design Element | Maps To | Guidance |
|----------------|---------|----------|
| Entire page/screen purpose | **Outcome** | What complete objective does this screen serve? |
| Distinct user flows/paths | **Scenario** | Under what condition or approach is the Outcome completed? |
| Variation within a flow | **Step** | What configuration-level variation describes how the Scenario is completed? |
| User inputs, selections, confirmations | **Action** | Named logical activity the user performs to fulfill the Step |
| System processing, validation | **Action** | Named logical activity the system performs to fulfill the Step |
| Error/success states | **Scenario** or **Step** | Distinct completion variations of the Outcome |
| Navigation between screens | **Scenario** boundary | Transition between different execution context variations |

**Key principle:** Extract WHAT the design enables the user to achieve,
not HOW the design looks or WHERE elements are positioned.
