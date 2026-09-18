# MCP Tools & Write Protocol

## Functional Graph Query Tools

| Tool | Purpose |
|---|---|
| `Get_scenarios_by_uuid` | Fetch scenarios with pagination and filtering |
| `Functional_Graph_Search` | Search for matching scenarios |

> **Steps/actions** are fetched via `fetch_steps_actions.py` (REST API
> with api-key), not via MCP. See Phase 0b in the sub-agent.

## Design Graph Query Tools

| Tool | Purpose |
|---|---|
| `Get_all_Design_By_Label` | Paginate existing design nodes by type |
| `Design_Graph_Search` | Semantic search for dedup |
| `Get_Design_Nodes_by_Ids` | Query nodes by relationships |

## Mutation Tools

| Tool | Purpose |
|---|---|
| `Bulk_Update_Design_Nodes` | **PRIMARY** — create entire UserJourney tree per scenario |
| `Create_Design_Node` | Create a single node with per-node citations (not idempotent — 400 on duplicate name) |
| `Update_Design_Node` | Update metadata fields on existing nodes |
| `Update_Functional_Node` | Mark scenario as processed (`isDesignGenerated=true`) |
| `Delete_Design_Node` | Remove nodes when replacing |

---

## Parameter Naming (CRITICAL)

| Tool | Parameter | Correct Name | Wrong Names |
|---|---|---|---|
| All Breeze MCP tools | Project ID | `uuid` | `projectId`, `projectUuid` |
| `Get_all_Design_By_Label` | Node label | `label` | `parameters0_Value` |

---

## Pagination Rule

All paginated MCP calls MUST use a `total`-based exit condition,
**not** a `count < limit` heuristic:

```
results = []
page = 1

LOOP:
  1. Call the paginated tool (page, limit)
  2. Read `total` from the response metadata
  3. Append returned items to results
  4. IF results.length >= total → EXIT
  5. page += 1
  6. REPEAT
END LOOP
```

> **Why not `count < limit`?** If the last page has exactly `limit`
> items, `count < limit` is false → triggers one extra empty request.
> Checking against `total` (returned by all Breeze paginated endpoints)
> exits cleanly regardless of page size alignment.
>
> If the response does not include a `total` field, fall back to:
> `IF count == 0 → EXIT` (zero items = no more pages).

---

## Write Protocol

**This skill writes to the design graph EXCLUSIVELY via
`Bulk_Update_Design_Nodes`** — one call per scenario. Never batch
multiple scenarios in one call.

**Backend dedup:** Nodes are matched by `projectUuid + name + platform`
(case-insensitive). If existing, new parent edges are created and
parent ID arrays (`userJourneyIds[]`, `flowIds[]`, `pageIds[]`) are
appended to. No `Update_Design_Node` calls needed for linking.

**`existingcomponents.json` update is a BLOCKING GATE** — must
complete before every `Bulk_Update_Design_Nodes` call.

**Post-upsert:** update Flow & Page registries with names (for local
dedup checking). No MCP sync needed for components — the pre-upsert
registry update (Step 6d) is sufficient since dedup is by name.

**Mark processed:** `Update_Functional_Node` with
`isDesignGenerated: true` after successful upsert.

---

## Citation Placement (Design Graph)

Per-node `citations` arrays are supported on **UserJourney**, **Page**,
and **Component** nodes. Each node's citations are resolved individually
and merged with the top-level `citations` (which apply as a shared
default to every node). **Flow does not support per-node citations**
(derived structure — no distinct source artifact).

| Level | Per-node `citations`? | Typical source |
|---|---|---|
| **Component** | yes — primary | the component file / Figma component |
| **Page** | yes | the route definition file |
| **UserJourney** | optional | a design doc or Figma board |
| Flow | no | derived structure, no distinct artifact |

Citation format: `{"type": "code", "reference": "<code-ontology-node-id>"}`.
Other types: `document`, `exDoc`, `figma`, `jira`, `confluence`, `prompt`.
