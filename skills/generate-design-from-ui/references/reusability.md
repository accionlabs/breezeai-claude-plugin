# Reusability — Registries, Dedup & Multi-Parent Linking

## Principle

**Never create a duplicate — always link to existing if semantically
the same.** The backend handles multi-parent linking automatically
via name-based dedup.

---

## Three Registries

| Registry               | Indexed by         | Storage                           | Purpose                       |
| ---------------------- | ------------------ | --------------------------------- | ----------------------------- |
| **Flow Registry**      | `(name, modality)` | `existingflows.json` on disk      | Reuse flows across scenarios  |
| **Page Registry**      | `(name, pageType)` | `existingpages.json` on disk      | Reuse pages across flows      |
| **Component Registry** | `(type, name)`     | `existingcomponents.json` on disk | Reuse components across pages |

---

## Backend Dedup Mechanism

**The backend deduplicates Flows, Pages and Components by `projectUuid + name + platform` (case-insensitive).**
**UserJourneys are the exception:** they are keyed by `projectUuid + scenarioId + platform`.
Re-upserting a scenario updates (and renames, if the name changed) its own UJ; two personas'
same-named scenarios each get their own UJ; a UJ is never moved to another scenario. A UJ
sent without `scenarioId` falls back to matching by name.

When a node with the same name already exists in the bulk upsert:

1. A new parent relationship edge is created (e.g. `INCLUDES_FLOW`)
2. The new parent ID is appended to the parent ID array
   (`userJourneyIds[]`, `flowIds[]`, `pageIds[]`)
3. New `stepIds`/`actionIds` are appended to existing arrays
4. NO duplicate node is created

**This means: just include the node by name in the payload.** No `id`
field needed. No `Update_Design_Node` calls needed for linking. The
bulk upsert handles everything.

---

## Reuse Decision per Level

### Flows — INCLUDE by name

1. Check Flow Registry for match by `(name, modality)`
2. **Match found → reuse payload** — include the flow by name with
   `pages: []`. The backend creates the `INCLUDES_FLOW` edge and
   appends the new UJ ID to `userJourneyIds[]`.
   **DO NOT omit reused flows** — the backend needs the name present
   in the payload to create the parent edge.
3. No match → create in bulk payload with full stepIds → add to registry after upsert

```json
// Reuse — parent edge only:
{ "name": "Email Login Flow", "modality": "WEB", "pages": [] }

// Create — first time, full stepIds:
{ "name": "Email Login Flow", "modality": "WEB", "stepIds": ["step-1","step-2"], "pages": [...] }
```

### Pages — INCLUDE by name

1. Check Page Registry for match by `(name, pageType)`
2. **Match found → reuse payload** — include the page by name with
   `components: []`. The backend creates the `CONTAINS_PAGE` edge
   and appends the new Flow ID to `flowIds[]`.
   **DO NOT omit reused pages** — the backend needs the name present
   in the payload to create the parent edge.
3. No match → create in bulk payload with full stepIds → add to registry after upsert

```json
// Reuse — parent edge only:
{ "name": "LoginPage", "pageType": "FORM", "components": [] }

// Create — first time, full stepIds:
{ "name": "LoginPage", "pageType": "FORM", "stepIds": ["step-3"], "components": [...] }
```

### Components — INCLUDE by name

1. Check by exact name match → backend deduplicates automatically
2. `designSystemRef` for design system traceability (NOT the dedup key)
3. No match → create new → add to registry before upsert (BLOCKING)

---

## Reuse by Component Type

| Type     | Reuse behavior                    | Scope           |
| -------- | --------------------------------- | --------------- |
| ATOM     | Always reuse globally             | GLOBAL          |
| MOLECULE | Reuse globally or by domain       | GLOBAL / DOMAIN |
| ORGANISM | Always create new, reuse children | PAGE            |
| TEMPLATE | Reuse globally by layout pattern  | GLOBAL          |

---

## What Gets Linked vs Created

| Design Node               | Same scenario                  | Across scenarios                      |
| ------------------------- | ------------------------------ | ------------------------------------- |
| UserJourney               | Always new (1:1 with scenario) | Never reused                          |
| Flow                      | Unique within journey          | **Reused** if same `(name, modality)` |
| Page                      | Unique within flow             | **Reused** if same `(name, pageType)` |
| Component (ATOM/MOLECULE) | Reused within page             | **Reused** globally                   |
| Component (ORGANISM)      | New per page                   | New per page (children reused)        |
| Component (TEMPLATE)      | Reused within page             | **Reused** globally                   |

---

## Registry Update Timing

```
Before bulk upsert:
  ⛔ Update existingcomponents.json with names + designSystemRefs
     (BLOCKING GATE — needed for component reuse in next scenario)

After bulk upsert:
  → Add new Flows to Flow Registry with names (for dedup check)
  → Add new Pages to Page Registry with names (for dedup check)

No MCP sync needed for components — existingcomponents.json is
already accurate from the pre-upsert update (Step 6d). Backend
dedup is by name, not UUID, so MCP UUIDs are never consumed.
```
