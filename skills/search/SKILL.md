---
name: search
description: >
  Search the functional, design, code, and architecture graphs to answer
  questions about the system. Smart-routes to one graph, a subset, or all of
  them based on query intent. Use for: feature discovery, "how does X work",
  "who handles Y", finding code or UI implementations, schema lookups, and
  cross-layer questions. Default entry point for any question about the project.
---

## Project

This skill needs a `projectUuid` — follow CLAUDE.md's project-resolution rules (`--project` override → `.breeze.json` fallback → announce active project header). Auth handling on Breeze MCP failures is also covered in CLAUDE.md.

---

## Tools Available

All tools below are read-only. Pass `projectUuid` (or `project_uuid` / `uuid`, per each tool's schema) on every call.

### Functional graph
- `Functional_Graph_Search` — semantic search across Persona / Outcome / Scenario / Step / Action.
- `Get_all_personas` — list every Persona with its ID.
- `Get_all_outcomes_for_a_persona_id` — outcomes under a Persona.
- `Get_all_scenarios_for_a_outcome_id` — scenarios under an Outcome.
- `Get_all_steps_actions_for_a_scenario_id` — full Step → Action tree under a Scenario.

### Code graph
- `Call_List_Repositories_` — list every indexed repository in the project (name, id, file/class/function counts, language, repo URL, commit, branch). Use first for "which codebases are indexed" questions, and to enable per-repo scoping on subsequent `Code_Graph_Search` calls.
- `Code_Graph_Search` — semantic search across File / Function / Class. Supports `code_ontology_id=` (the repo's immutable `_id` as an **integer**, from `Call_List_Repositories_`) to scope a search to one repo when the question clearly maps to a single subsystem (e.g., a frontend-only change → the `frontendweb_*` repo). When the touched code spans multiple repos, anchor each hit back to its parent repo from the inventory. (There is no `repository_name` filter — the mutable display name was removed; scope by `code_ontology_id`.)
- `Get_Code_Nodes_By_Label` — fetch code nodes by label (`File` / `Function` / `Class`), filtered on any field (`path`, `name`, `id`, `codeOntologyId`, `type`, …) with `children=true` to attach the full subtree. For a single file's full hierarchical structure (classes → methods → statements, functions → statements, file-level statements) call `Get_Code_Nodes_By_Label(label="File", filters={"id": <fileId>} OR {"path": <path>, "codeOntologyId": <id>}, children=true)`. Always filter on a unique key (`id`, or `path` + `codeOntologyId`) — `data` is an array and a bare `path` can match the same file across repos. (`repositoryName` is **rejected** as a filter — the mutable display name fails loud; scope by `codeOntologyId`, the repo's integer `_id`.) `children=false` (or a `fields` projection) returns a lean node list when you don't need the drill-down.

### Design graph
- `Design_Graph_Search` — semantic search across design nodes (journeys, flows, pages, components).
- `Get_all_Design_By_Label` — list design nodes filtered by label type.
- `Get_Design_Nodes_by_Ids` — fetch specific design nodes by ID.

### Architecture + DB-schema graph
- `Architecture_Graph_Search` — semantic search across architecture-layer nodes (UserExperience, ApiGateway, ObservabilityMonitoring, Agents, Services, EventQueue, DataLake, Infrastructure) **AND** DDL nodes attached to each DataLake (DDLTable, DDLColumn, DDLConstraint, DDLIndex, DDLView, DDLSequence, DDLProcedure). Filter via `include_labels=[...]` and tune `threshold` (default ~0.4). **Embedding-filtered — silently drops nodes whose name/description doesn't match the query.** For *enumeration* questions ("list every service", "every table in DataLake X"), fall back to the by-label tools below — those don't filter.
- `Get_Architecture_Nodes_By_Label` — enumerate every architecture node in one layer (no semantic filter, no silent drops). Use for "list all services / queues / data stores".
- `Get_DB_Schema_Nodes_By_Label` — list DDL entities under one DataLake by label (`table`, `column`, `constraint`, `index`, `view`, `sequence`, `procedure`). Supports pagination, sort, equality/regex filters (e.g. `{"tableId": {"$eq": "<uuid>"}}`), parent/child tree walks. Use for "all tables in DataLake X", "FKs referencing table Y", "columns of table Z".

### Label routing for `Architecture_Graph_Search`

Pick `include_labels` by query intent — narrow when you can, omit when truly ambiguous:

| Query shape | `include_labels` |
|---|---|
| "which service handles X" | `["Services"]` |
| "what queue/topic carries X" | `["EventQueue"]` |
| "what data stores hold X" (store-level) | `["DataLake"]` |
| "what alerts on X" / "where do X logs go" | `["ObservabilityMonitoring"]` |
| "what compute / VPC / region runs X" | `["Infrastructure"]` |
| "which frontend / app exposes X" | `["UserExperience"]` |
| "which API / route / gateway handles X" | `["ApiGateway"]` |
| "which agent / LLM workflow runs X" | `["Agents"]` |
| "find tables for X" / "which tables store Y" | `["DDLTable"]` |
| "find columns named X" | `["DDLColumn"]` |
| "FKs referencing X" / "unique constraint on Y" | `["DDLConstraint"]` |
| "indexes on X" | `["DDLIndex"]` |
| "views / materialized views including X" | `["DDLView"]` |
| "stored procs / triggers doing X" | `["DDLProcedure"]` |
| "sequences for X" | `["DDLSequence"]` |
| "everything related to the auth schema" | `["DDLTable","DDLColumn","DDLConstraint","DDLView","DDLProcedure"]` |
| "what stores AND schema back X" | `["DataLake","DDLTable","DDLView"]` |
| Truly ambiguous one-word queries | omit `include_labels` |

When a question demands completeness ("are these ALL the services / tables?"), don't rely on this tool — use `Get_Architecture_Nodes_By_Label` or `Get_DB_Schema_Nodes_By_Label`.

---

## Phase 1 — Classify Query Scope

Inspect `$ARGUMENTS`. Decide **which graphs to search**. You can pick one, a subset, or all. The goal is to cover the layers the user's question actually touches — no more, no less.

### 1a. Single-graph fast-paths

Stop at the first match:

| Query shape | Route to |
|---|---|
| Pure code lookup — "where is X implemented", "find function/class/file Y", "show me the route handler for Z" | `Code_Graph_Search` → then `Get_Code_Nodes_By_Label(label="File", filters={path + codeOntologyId \| id}, children=true)` on top hits. If the query names or implies a single repo, list repos via `Call_List_Repositories_` first and scope the search via `code_ontology_id=` (the repo's integer `_id`). |
| Repo inventory — "which codebases", "list the repos", "what languages does this project use", "what's the repo for X" | `Call_List_Repositories_` |
| Pure UI — "what page shows X", "which component", "what does the settings screen look like" | `Design_Graph_Search` → optionally `Get_Design_Nodes_by_Ids` for detail |
| Personas / roles only — "who manages X", "what roles exist" | `Get_all_personas` → drill down (see Phase 3) |
| Targeted deployment question — "which service handles X", "what queue carries Y", "what data store holds Z" | `Architecture_Graph_Search` with matching `include_labels` (see routing table above) |
| Enumerate one architecture layer — "list every service / queue / data store / topic" | `Get_Architecture_Nodes_By_Label` |
| Targeted DDL question — "find tables for X", "columns named Y", "FKs to Z", "views including W" | `Architecture_Graph_Search` with DDL `include_labels` |
| Enumerate schema under one DataLake — "all tables in DataLake X", "every view in Y" | `Get_DB_Schema_Nodes_By_Label` (find the DataLake's id first via `Architecture_Graph_Search` or `Get_Architecture_Nodes_By_Label`) |

### 1b. Multi-graph triggers

If the query doesn't fit a single-graph fast-path, pick the layers it implies and run them in parallel.

**Trigger words that add a layer:**
- *screen, page, component, UI, UX, flow, wireframe, design* → add **Design**
- *file, function, class, method, module, import* → add **Code**
- *repo, repository, codebase, language* → add **Code** (start with `Call_List_Repositories_`)
- *service, deploy, deployment, region, SPOF, queue, topic, bucket, cache, tech stack, infra* → add **Architecture**
- *table, column, schema, DDL, foreign key, FK, materialized view, procedure, trigger, constraint, sequence, index* → add **Architecture (DDL labels)**
- *persona, role, outcome, scenario, workflow, business logic* → add **Functional**

**Shape-based routing:**
- "how does X work" / "explain Y" / "what happens when…" / "walk me through Z" → **Functional + Code** minimum (add Design if UI-facing, add Architecture if deployment-facing, add DDL labels if data-flow involves specific tables)
- "what is the impact of…" / "what breaks if…" / "what does X depend on" → **Functional + Code + Architecture** (add Design if UI-facing) — but for full impact analysis prefer `/breeze:impact-analysis`
- "compare X and Y" (where X, Y are features) → **Functional + Code**

**Default when truly ambiguous** → **Functional + Code**.

> Running all graphs is fine when the question is genuinely cross-cutting. Don't over-narrow out of caution, but don't fan out for a question that's obviously single-layer.

### 1c. Output structure — per-ontology (always)

There is one output shape: the **per-ontology view** (Phase 4). Every synthesized answer is an exhaustive summary, then one native-hierarchy tree per graph. There is no separate "woven narrative" mode, and no trailing comparison section.

- Search **all five layers by default** — Functional, Design, Code, Architecture, and **Data (DDL)** — unless the query is explicitly scoped to a subset. Covering every layer the question actually touches is the point, so favor breadth. Always include the DDL fetch (`Architecture_Graph_Search` with DDL `include_labels` and/or `Get_DB_Schema_Nodes_By_Label` on the touched DataLake) so the Data layer renders when the schema is onboarded.
- The output shape does **not** change *which* graphs you search — Phase 1a/1b scoping and Phase 3 drill-down still apply; this only fixes how Phase 4 renders.
- For an obviously single-layer lookup (e.g. "where is function X"), still use the per-ontology shape — just render the one relevant block; never pad with empty trees.

---

## Phase 2 — Execute in Parallel

Run every chosen semantic search / enumeration call simultaneously. Do not sequentialize.

Typical parallel batch:
- `Functional_Graph_Search`
- `Design_Graph_Search`
- `Code_Graph_Search` (optionally per-repo splits if the query maps to ≤2 repos from the `Call_List_Repositories_` inventory)
- `Architecture_Graph_Search` (with `include_labels` per the routing table — for cross-cutting queries you may issue 2 parallel calls, e.g. one architecture-layer set and one DDL-label set)

If a graph returns no results, note "No matches in {graph}" internally and continue — don't fail the whole search.

---

## Phase 3 — Drill Down

After the parallel reads, drill into top hits to build a complete picture. No magic relevance thresholds — just shape-based rules.

### Functional drill-down — top-down hierarchy

The functional graph is **Persona → Outcome → Scenario → Step → Action**. Drill along this chain as far as the question requires:

1. **Search hit is (or references) a Persona** → call `Get_all_outcomes_for_a_persona_id` to list its outcomes.
2. **Search hit is (or drills into) an Outcome** → call `Get_all_scenarios_for_a_outcome_id` to list its scenarios.
3. **Search hit is (or drills into) a Scenario** → call `Get_all_steps_actions_for_a_scenario_id` to get the full Step → Action tree.
4. **Search hit is an Action or Step** → identify the parent Scenario (via `scenarioId` in the result) and run `Get_all_steps_actions_for_a_scenario_id` on it to get the full flow.

For "how does X work" questions, drill all the way to Steps/Actions. For "who does X" or "what outcomes exist", stopping at Outcomes or Scenarios is usually enough.

### Code drill-down
- **Always anchor hits to their parent repo** from the `Call_List_Repositories_` inventory. When the touched code spans multiple repos, prefix file paths with the repo name (e.g., `frontendweb_react_tnlm: src/utils/posthog.ts`) so cross-repo coordination is visible at a glance.
- **Top hits are Files** → call `Get_Code_Nodes_By_Label(label="File", filters={"path": <path>, "codeOntologyId": <id>} OR {"id": <fileId>}, children=true)` on each to see classes, methods, decorators, statements.
- **Top hits are Functions or Classes** → their source and call chain are already in the search payload. To see the whole surrounding file, call `Get_Code_Nodes_By_Label(label="File", filters={"path": <hit.path>, "codeOntologyId": <hit.codeOntologyId>}, children=true)` — you can fetch the full file straight from the hit's `path` + `codeOntologyId`, no need to resolve the File id first.

### Design drill-down
- **Top hits are design nodes** → if the search payload is thin, call `Get_Design_Nodes_by_Ids` on the top IDs for full detail, or `Get_all_Design_By_Label` to widen within a label type.

### Architecture + DDL drill-down
- **Top hits are architecture nodes** → already self-contained (name, description, technologies, pattern, regions); use directly in synthesis.
- **Top hits are DDL nodes (DDLTable / DDLColumn / DDLView / DDLProcedure …)** → the `ddlText` (for tables) or `definition` (for views/procs) is typically in the search payload. For a complete schema picture under one DataLake — every column of a table, every FK pointing at it, every view that references it — call `Get_DB_Schema_Nodes_By_Label` with the matching `data_lake_id` and the appropriate label + `filters`.
- **Enumeration follow-up** — if the semantic search returned an incomplete set and the question demands completeness ("are these ALL the tables?"), fall back to `Get_Architecture_Nodes_By_Label` (one architecture layer) or `Get_DB_Schema_Nodes_By_Label` (schema-side, one DataLake).

### Cross-Persona Drill-Down

When drilling into a functional Outcome, check if the **same Outcome name exists under other Personas** (common for features that span UI and backend). After finding an Outcome under a User persona, also fetch it under the System persona (and vice versa) via `Get_all_outcomes_for_a_persona_id`, then `Get_all_scenarios_for_a_outcome_id` on the matching outcome. Render both under their respective persona blocks in the Functional tree.

---

## Phase 4 — Synthesize (Per-Ontology Output)

Present every answer as the **per-ontology view**. Do NOT weave the layers into a single running narrative, and do NOT emit a flat per-graph ranked list — structure the answer in three fixed parts:

**1. Answer summary.** Four elements, in this order.

**1a — `Direct Answer`.** ONE paragraph, first, before any structure. It must answer the question completely on its own: who triggers it, what the system does, where it ends up. A reader who stops after this paragraph should be able to repeat the answer back correctly. No preamble, no "this flow consists of…", just the answer.

**1b — a structured walkthrough.** Pick the skeleton from the question's shape and use numbered headings — never undifferentiated prose:

| question shape | skeleton |
|---|---|
| "what happens when…", "end to end", "walk me through" — a **pipeline** | **Phase 1…N**, one heading per stage, in execution order. Each phase names its trigger, what happens, and the concrete artefacts (endpoint, table, code entry point). |
| "what is the process for…", "how does X work" — a **capability** | **numbered layers**: 1 Behaviour (Functional) · 2 Design · 3 Implementation (Code) · 4 Deployed System + Data. Omit a layer that returned nothing. |
| a lookup or comparison | no skeleton — a short brief is fine. |

Cover, as they apply: who can trigger it and any role gates; every distinct entry path or variant; the request path with key endpoints as `method` + `route`; backend processing and any external system it delegates to; sync vs async and how completion/polling works; data read vs written and where; preconditions and guards; and the notable failure paths. Name concrete entities inline — scenario names, file:line, endpoints, node names, stored procedures.

**1c — tabulate anything with 3+ parallel items.** Status/route codes and their meanings, field groups and their validation rules, stored procedures in call order, business rules with their code locations, repos touched with their `codeOntologyId`. A table beats a paragraph and beats a bullet list for anything that shares a shape. When **two or more tables are written**, add a consolidated **data-touch map**: `table · READ/WRITE · phase · what is stored`.

**1d — one flow-at-a-glance.** A single fenced ASCII diagram of the whole path, with branches drawn (blocked paths, validation failures, sync vs async forks) — not one diagram per layer. Place it after the walkthrough.

End the summary with a one-line **Coverage:** list naming only the layers that returned findings, e.g. `Coverage: Functional ✓ · Code ✓ · Architecture ✓`. Never list a layer that returned nothing (don't-surface-gaps rule).

**2. Per-ontology hierarchy blocks.** One block per layer that returned findings, each rendered in that graph's **native hierarchy** as a fenced monospace tree. Omit any empty layer silently. Fixed order: Functional → Design → Code → Architecture → Data.

- **🧠 Functional** — `Persona → Outcome → Scenario → Step → Action`. Group by Persona with type glyphs (👤 human · 🤖 System · ☁️ External System). Indent the tree; for "how does X work" drill all the way to Action. **Attach the endpoint contract from the graph itself:** entry-point Actions carry an `Api` child via the `HAS_API` relation (returned by `Get_all_steps_actions_for_a_scenario_id`). Render it as an `Api:` leaf under its Action showing `method` + `url` (+ request DTO / response shape when present). Source the endpoint from this `Api` node — do NOT reach into the code graph for a route the functional graph already carries. Most Actions have no `Api` child (only entry points do); render the leaf only where it exists.
- **🎨 Design** — `UserJourney → Flow → Page → Component`.
- **💻 Code** — `Repo → File → Class/Function → key statement`, every leaf tagged `repo: path:line`. Show the real call chain / route decorator / DTO / enum literal, not just symbol names.
- **🏗️ Architecture** — the deployed path across layers (`UserExperience → ApiGateway → Services → Agents → DataLake`), naming concrete nodes and the read/write direction on stores.
- **🗄️ Data (DDL)** — `DataLake → Table → (Columns / Constraints / Indexes / Views / Procedures)`. Source columns from the table's `ddlText`; use `Get_DB_Schema_Nodes_By_Label(data_lake_id, label=…)` for a complete column/FK/view set. Omit silently if the schema layer isn't onboarded for the project.

Keep each tree compact but **preserve depth** — never flatten a 5-level functional chain into a single arrow line. Use real node names/IDs for existing nodes.

**3. Anchor appendix.** A single fenced block listing every distinct integration point the answer touched — REST routes, EventBus addresses, `DoFilter`/`WriteData` names, stored procedures, data-api table writes. One per line, no commentary. This is the fastest thing for a reader to scan for "what would I have to change", and it makes the answer usable as input to a follow-up task. Omit only when the answer touched none.

**The answer ends with the anchor appendix.** Do not append a reconciliation, comparison, agreements/divergences, or gap-analysis section. If two layers genuinely conflict on a fact, say so inline where that fact appears, in one clause; do not promote it into a section of its own.

**Verified vs inferred.** Everything inside a tree, table or code block is a claim you verified. If you are extrapolating — a file path that follows the repo's naming convention but which you did not open, a step you assume by symmetry with a sibling app — say so in the line itself (`(inferred — not opened)`) or leave it out. Never place an unverified item in an authoritative-looking block with the caveat in a footnote below.

---

## End-to-End Flow Questions

For any question shaped like *"what happens when…"*, *"explain the flow of…"*, *"how does X process work"*:

1. **Always** search **Functional + Code** at minimum.
2. Add **Design** if the flow starts at a UI action.
3. Add **Architecture** if the flow crosses services / queues / data stores (which is usually true). Add DDL labels too if the prompt names specific tables or asks about persistence shape.
4. In the functional graph, query **twice** — once with user-centric terms (UI actions, clicks, forms) and once with system-centric terms ("System processes…", "backend handles…", "External System…"). This captures both the trigger side and the processing side of the dual-persona model.
5. Drill the top functional hits all the way to Steps/Actions via the Phase 3 hierarchy chain.
5a. **Expand EVERY scenario under both halves of the outcome — not just the happy path.** List them with `Get_all_scenarios_for_a_outcome_id` on the human AND the System outcome, then call `Get_all_steps_actions_for_a_scenario_id` on each. The eligibility gate, the blocked-path variants and the "serve the form" scenario are where the routing codes, the reference-data filters and the guard conditions live — and they are the easiest to skip, because their names sound like plumbing next to the obvious "Apply for X" scenario. An answer that expands only the happy path will silently omit the status codes and the tables the gate reads.
6. Render as the per-ontology view — exhaustive Answer summary + per-graph trees (Phase 4).

A single search returns an incomplete picture for process questions — always fan out.

---

## Don'ts

- **Don't narrate the search.** No "Excellent!", no "I now have enough data", no "Let me compose the output", no "All 6 searches are complete". The answer opens with the `Direct Answer` paragraph and nothing before it.
- **Don't present raw search results as the final answer.** Always drill down and synthesize.
- **Don't claim a feature doesn't exist** from one failed search — try a rephrase or widen to another graph first.
- **Don't trust an empty `Architecture_Graph_Search` result for an enumeration question.** Embedding-filtered search silently drops nodes — if the user asked to enumerate (all services, all tables), use `Get_Architecture_Nodes_By_Label` / `Get_DB_Schema_Nodes_By_Label` instead.
- **Don't mention empty layers or graph-completeness gaps** in user-visible output (e.g., "the architecture graph has 0 Agents"). Silently fall back; present what you do have.
- **Don't append a cross-ontology / reconciliation section.** No "agreements vs divergences", no layer-by-layer comparison, no gap analysis. The answer is the summary, the trees and the anchor appendix — nothing after it. A genuine conflict between two layers belongs inline, in a clause, next to the fact it concerns.
- **Don't duplicate `/breeze:impact-analysis`.** `search` reads and synthesizes across layers. It does **not** do scenario-ID → architecture-node anchoring, blast-radius scoring, risk levels, tier classification, or templated Context blocks. If the user asks for impact assessment, blast radius, or a detailed analysis doc, point them at `/breeze:impact-analysis`.
- **Don't run all graphs for an obviously single-layer question** — it wastes tokens and blurs the answer.

---

## Output

- **Every answer uses the per-ontology view** (Phase 4): `Direct Answer` paragraph → numbered Phase/Layer walkthrough with tables → flow-at-a-glance → `Coverage:` line → one native-hierarchy tree per layer (Functional / Design / Code / Architecture / Data-DDL, empty layers omitted) → anchor appendix. Preserve each graph's hierarchy depth; never flatten into a single running narrative or a flat ranked list. No reconciliation, comparison or gap-analysis section.
- For a discovery-style query, the per-graph trees carry the ranked entities (entity type, name, parent repo/DataLake) and the summary states what was found; for a single-layer lookup, render just the one relevant block.
- **Always** name concrete entities (e.g., *Scenario "Run hourly ANZ ETL"*, *file `backend_nodejs_global_tnlm: src/project/.../search-result-project.dsl.ts`*, *Service node "global_tnlm"*, *DDLTable `RESEARCH_PROJECT_VERSION`*) rather than vague references.
- **Link the layers**: when functional + code + architecture + DDL all fire, show how they connect on this specific flow.
