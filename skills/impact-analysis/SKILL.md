---
name: impact-analysis
description: >
  Searches Breeze functional, design, code, and architecture graphs to perform
  impact analysis of a proposed change. Shows an analysis summary and optionally
  generates a detailed document with diagrams. Use for: "impact analysis", "what
  if we change X", "what breaks if Y fails", "blast radius of Z" — cross-layer
  change assessment from functional → design → code → architecture (deployed-
  system blast radius). Supports optional `--project <uuid|name>` to target a
  Breeze project other than the one in `.breeze.json`, and `--detailed` to skip
  the summary and emit the full diagrammed document directly.
---

# Breeze Impact Analysis

Perform impact analysis of a proposed change across the Breeze functional, design, code, and architecture graphs to understand full context — from user intent down to deployed services, data stores, and operational blast radius — before acting.

## Your Task

Given a user prompt that implies a change (new feature, modification, removal, failure scenario), search all four Breeze graphs, perform an impact analysis, present a summary, and — if the user wants — generate a comprehensive document with diagrams.

## Step 1 — Project & Output Mode

### 1a. Project resolution

Follow CLAUDE.md's project-resolution rules (per-invocation override via `--project` flag or natural-language hint → `.breeze.json` fallback → announce active project). This skill prints `Breeze Impact Analysis` on the line above the `Project: <name> (<uuid>)` header so the report title appears first. Auth handling on Breeze MCP failures is also covered in CLAUDE.md.

### 1b. Detailed-mode flag

The user may pass `--detailed` (or `--full` / `--report`, or natural phrasing like "give me the full report", "detailed report", "skip the summary") anywhere in `$ARGUMENTS`. Treat this as a one-shot output mode override:

- **SUMMARY mode (default, no flag)** → run all steps as written. Step 4 emits the summary template **inline in the conversation**, then asks the user whether to generate the detailed document.
- **DETAILED mode (flag present)** → run all steps as written, but in Step 4 **skip the summary template entirely** and **save the detailed document to a Markdown file** in the current working directory, following the Detailed-mode output template defined in Step 4. After writing, print a short confirmation block inline (file path + verdict + risk level + 3–5 headline findings) so the user / calling skill sees the takeaways without opening the file. Filename convention: `impact-analysis-<short-kebab-slug-derived-from-prompt>.md` (e.g. `impact-analysis-saved-search-email-frequency.md`); fall back to `impact-analysis-<YYYY-MM-DD>.md` if no usable slug can be derived. Use the Write tool. Strip `--detailed` (and any synonyms) from `$ARGUMENTS` before processing the prompt.

Do not produce both a summary and a detailed document in the same invocation.

**Example invocations:**
- `/impact-analysis expand keyword search to status text and description` → SUMMARY mode (default).
- `/impact-analysis --detailed expand keyword search to status text and description` → DETAILED mode — emit the diagrammed document directly, no summary, no yes/no prompt.
- `/impact-analysis --project "Lead Manager V2" --detailed what breaks if Redis is offline` → DETAILED mode against an explicit project override.

## Step 2 — Read All Four Graphs (in parallel)

First, call `Call_List_Repositories_` to enumerate the project's repositories. Cache the inventory (name + id + metadata). You'll use it for two things: (a) scoping `Code_Graph_Search` per-repo when the prompt clearly maps to one or two subsystems, and (b) anchoring code hits back to their parent repo when reasoning about cross-repo coordination in Step 2.3, Step 3.1, and the final output.

Then run these four calls simultaneously using queries derived from the user's prompt:

1. **Functional Graph Search** (`Functional_Graph_Search`)
   Search for related personas, outcomes, scenarios, steps, and actions.

2. **Design Graph Search** (`Design_Graph_Search`)
   Search for related user journeys, flows, pages, and components.

3. **Code Graph Search** (`Code_Graph_Search`)
   Search for related code files, classes, methods, and modules. If the prompt strongly implies one or two repos from the inventory above (e.g., a frontend-only change → the `frontendweb_*` repo, a search-feature change → `backend_*_search_*`), issue parallel `code_ontology_id=`-scoped searches per repo (the repo's integer `_id` from `Call_List_Repositories_`) instead of one broad call. Otherwise do one broad call.

4. **Architecture Graph read — per label, in parallel** (`Get_Architecture_Nodes_By_Label`)
   Issue 8 parallel `Get_Architecture_Nodes_By_Label` calls, one per layer: `UserExperience`, `ApiGateway`, `ObservabilityMonitoring`, `Agents`, `Services`, `EventQueue`, `DataLake`, `Infrastructure`. **This tool is an enumeration, not a search** — it takes only `uuid` and `label` (no `query` parameter) and returns every node in that label. Step 2.2's intersection logic filters them down by relevance. Splitting per-label avoids the token-overflow that `Get_All_architecture_Graph` hits on populated projects (per-layer payloads can still be sizeable — e.g., DataLake with many DB schemas). Do NOT use `Architecture_Graph_Search` — that's similarity-filtered search and will silently drop anchors whose embedding doesn't match the prompt.

If a search returns no results, note "No matches found" for that graph. If the Architecture Graph is empty (all 8 layer counts are 0), note "Architecture Graph not populated" and skip Step 2.2.

## Step 2.1 — Functional Drill-Down

Based on the Functional_Graph_Search results, drill deeper into the functional graph:

1. ALWAYS call `Get_all_personas` first to get the full persona list with their IDs. Cache the response — you will need each persona's `name` AND `type` (if present) when rendering the Functional Layer section of the detailed report, which groups by persona with type-aware glyphs (`👤` human / `🤖` system / `☁️` external).
2. For outcomes/scenarios returned by the search, match the `personaId` / `outcomeId` fields on each hit back to the persona list to identify the affected personas and the touched outcome(s). A Scenario or Outcome hit from `Functional_Graph_Search` already carries the `outcomeId` you need for step 3 — you do NOT have to enumerate a persona's full outcome set to reach it. (If a query returns only Step/Action hits, recover the `outcomeId` from the scenario root in the step 4 response.)
3. Call `Get_all_scenarios_for_a_outcome_id` for each touched outcome to enumerate ALL of its scenarios — this catches sibling scenarios that search did not rank (e.g. an alternate fan-out path on the same outcome), which matters for blast-radius completeness.
4. For each relevant scenario, call `Get_all_steps_actions_for_a_scenario_id` to get the complete steps and actions.
5. **Escalation only — `Get_all_outcomes_for_a_persona_id`.** This call enumerates a persona's *entire* outcome set and seeds an expensive fan-out (per persona → all outcomes → per outcome → all scenarios → steps/actions), most of it irrelevant to a surgical change. Skip it by default for narrow, search-anchored changes. Fire it only when (a) `Functional_Graph_Search` recall is weak/ambiguous and no outcome anchor surfaced, or (b) the change is broad enough that you need cross-outcome closure under a persona (a sibling *outcome* search never surfaced).

This gives you the full functional chain: Persona → Outcome → Scenario → Step → Action. Steps are first-class members of the chain — do not collapse them into their parent scenario at render time.

`Get_all_steps_actions_for_a_scenario_id` also returns any `Api` node nested under its parent Action via the `HAS_API` relation, carrying the endpoint contract (`method`, `url`, `type`, `request` DTO name, `response` shape). Only entry-point actions have one — most actions return `children: []`. Use this Api node to populate the Code Context / Code Layer `Endpoint / Page` column and the ApiGateway request-path reasoning **without** a separate code-graph lookup. Field-level request/response detail is NOT on the Api node — reconstruct it from the sibling `Validate <field>` actions' descriptions.

## Step 2.2 — Architecture Impact

Skip this step if every architecture layer returned zero nodes. If only some layers are empty, silently skip those layers and proceed with the populated ones — do not surface "layer X is empty" anywhere in the output (see HARD RULE).

This step is about **how the user's prompt impacts the deployed system** — not about auditing the architecture graph for metadata completeness. The goal is to answer: *"given what the user is proposing to change, which deployed nodes are on the hook, and what does that mean for them operationally?"*

Intersect the functional + code results with the Architecture Graph to identify touched nodes, then reason about what the prompt means for those nodes.

1. **Anchor by name / description / technology / domain.** Cross-reference keywords from the functional scenarios, design journeys/pages/components, and the user's prompt itself against every architecture node's `name`, `description`, `domain`, and `technologies` fields. This is the primary anchoring path. (Note: architecture nodes no longer carry a `scenario` array — scenario-based anchoring is not used.)

2. **Anchor by code.** For each Code Graph hit, read its `codeOntologyId` (or `clusterId` on File nodes). Match against the `code_ontology_id` on every architecture node. Any match is a **code-anchored** touchpoint.

3. **One-hop supporting-layer expansion.** For each touched Service, include the supporting-layer nodes it depends on — DataLake (databases, indexes, caches, object stores), EventQueue (queues, CDC streams, event buses), ObservabilityMonitoring (logs, metrics, alerts), and Infrastructure (compute, networking, IaC). Use name patterns, shared technologies, and cross-reference with Code Graph imports (e.g., `loopback-connector-oracle` → Oracle DataLake node; `ElastiCache` imports → Redis node) when explicit relationship edges are not available.

4. **Request-path ordering.** If the prompt touches user-facing flows, order the ApiGateway nodes into a request path (typically edge → DNS → CDN/WAF → gateway → load balancer → ingress) so the summary can show the full hop chain.

5. **Impact assessment on touched nodes.** For the set of nodes surfaced in steps 1–4, reason about what the user's prompt means for them. Useful lenses:
   - **Failure domains touched by this prompt** — which of the touched nodes are single points of failure *for this specific flow* (e.g., a lone ES gateway that all search traffic funnels through).
   - **Data roles for this prompt** — which touched data store is the source of truth, which is the indexed / cached / replicated copy; what reads vs. writes the prompt implies.
   - **Regional reach** — does the prompt cross regional shards, and if so, how does region routing happen (env var, header, tenant lookup).
   - **Async tail implications** — how writes from this prompt propagate through CDC / queues / notifications, and what the lag consequences are for the user-facing surface.
   - **Deployment coordination** — how many services must be redeployed together for a change implied by the prompt; whether shared code (e.g., duplicated query builders) forces multi-repo synchronization.
   - **Capacity / scaling pressure** — if the prompt implies a traffic-shape change (new filter, heavier query, fanout), which nodes absorb that pressure first.
   - **Reuse opportunities** — if a proposed change implies new cross-cutting capability (auth, notifications, search) but an existing Platform Service already provides it, call that out so the user doesn't build a duplicate.

   This step's output is a set of operational consequences for nodes that exist in the graph. Keep the focus on the impact picture.

## Step 2.3 — Code Graph Deep-Dive

For the top 3–5 `Code_Graph_Search` hits, call `Get_Code_Nodes_By_Label(label="File", filters={"path": <hit.path>, "codeOntologyId": <hit.codeOntologyId>} OR {"id": <fileId>}, children=true)` when any of the following holds:

- The hit is a `File` node and you need its method/class structure to pinpoint the actual touchpoint inside the file.
- The prompt implies modifying or extending a specific function or route that the search returned only at file granularity.
- You need explicit repo + clusterId + module info to anchor a Code Context entry confidently.

For each enriched hit, retain the parent repo (from the inventory in Step 2). When the touched code spans multiple repos, render Code Context entries with their parent repo prefix (e.g. `frontendweb_react_tnlm: src/utils/posthog.ts`) so cross-repo coordination is visible at a glance — never bare paths when more than one repo is involved.

### Statement-level verification (optional escalation — verify the claim, don't restate the ticket)

When the change hinges on a **specific literal, query, guard, or statement inside a function** (e.g. a value swap like `3072 → 1024`, a particular Cypher/SQL string, a `size()`/null guard, a branch), escalate from file granularity to the function/class body:

```
Get_Code_Nodes_By_Label(label="Function" | "Class", filters={"name": "<symbol>"}, children=true)
```

This returns the symbol's `statements[]` (each with verbatim `text` + line range) and its resolved `calls[]` — letting you confirm the touchpoint against the indexed graph instead of paraphrasing the ticket. Use it for the 1–3 **primary** touchpoints only.

Guardrails (all learned the hard way — follow them):

- **Scope by `codeOntologyId`, not `repositoryName`.** Use `filters={"name": "<symbol>", "codeOntologyId": <repo._id>}`, where `<repo._id>` is the `_id` from `Call_List_Repositories_` (it equals the `codeOntologyId` stamped on every node). This is a stable, immutable key. Do NOT filter by `repositoryName`: the value `Call_List_Repositories_` returns there is the **slug** (`"breezeai-backend"`), but nodes store the repo's **display name** (`"BreezeAI Backend"`), so filtering by the slug returns zero rows with no error — and `repositoryName` is mutable (a rename leaves stale names on nodes) so it is unreliable to filter on regardless. (Tracked as a generator bug; `codeOntologyId` is the canonical scoping key.) If you only have a symbol name and no repo id, filter by `name` alone (optionally `+ path`).
- **Do NOT restrict `fields` if you need statement text.** The `fields` parameter silently drops the nested statement `text`, leaving only line ranges. Omit it (accept the larger payload) when you need to read the code.
- **Follow `calls[]` to the true touchpoint.** A search hit is often a thin router/wrapper that delegates the real logic to another function (resolved via `calls[].path`). Pull that callee before concluding — e.g. a `vectorSearchWithFilters` that just routes into an `executeSingleVectorSearch` where the actual query lives.
- **Treat an empty `statements: []` as a PARSER BLIND SPOT, not "no logic".** The generator captures only a narrow allow-list (declarations/returns) at the function-body root and skips bare expression-statements and anything nested inside `try`/`catch`/`if`/`for` blocks; for several non-JS/TS languages (Java, C#, Python, PHP, Go, Apex, Perl) statement capture is currently a silent no-op entirely (see the *Code Ontology Capture Matrix* tracker). When statements are absent, fall back to the node's `embedText`/`calls`, or read the source file directly — never report "no logic found" from an empty array.
- **Cap at 1–3 functions.** Statement payloads are large and can exceed the tool's token limit (spilling to a file); over-fetching whole files with `children=true` will blow the budget.

Feed the verified result into the Code Context / Code Layer `Current → Adds` columns and the `Cross-checks vs the prompt` block: a literal confirmed (or contradicted — e.g. the value is already changed in the indexed commit) at statement level is a graph-grounded finding, materially stronger than restating the ticket.

If `Code_Graph_Search` returned zero hits, skip this step. Steps 2.1 and 2.3 are independent and can run in parallel.

## Step 2.4 — Data Layer (Schema-Side) Impact

This step surfaces DDL-level impact — columns, procedures, triggers, materialized views, indexes, constraints — that the architecture-layer search alone misses. It runs in three stages with bounded call cost. Stage 1 is the trigger; Stages 2 and 3 are conditional.

### Stage 1 — Broad DDL Discovery (always when triggered)

**Trigger:** Step 2.2 surfaced ≥1 touched DataLake. Run Stage 1 against ALL touched DataLakes — non-relational lakes (ES, Redis, Kafka) naturally produce zero DDL hits and drop out. Do NOT pre-filter by `category` field — the field is AI-generated and may vary across projects.

**Action:** 5 parallel `Architecture_Graph_Search` calls, one per DDL label.

```
parallel:
  Architecture_Graph_Search(uuid, query=<prompt>, include_labels=["DDLColumn"],     threshold=0.4)
  Architecture_Graph_Search(uuid, query=<prompt>, include_labels=["DDLProcedure"],  threshold=0.4)
  Architecture_Graph_Search(uuid, query=<prompt>, include_labels=["DDLView"],       threshold=0.4)
  Architecture_Graph_Search(uuid, query=<prompt>, include_labels=["DDLConstraint"], threshold=0.4)
  Architecture_Graph_Search(uuid, query=<prompt>, include_labels=["DDLIndex"],      threshold=0.4)
```

**Filter & gate:**
- Drop hits whose `dbOntologyId ∉ touched_datalakes` (filter to the subset surfaced in Step 2.2)
- If total surviving hits < 3 → **suppress the Data Context block** in the summary AND **the Data Layer table** in the detailed doc (change isn't schema-touching)
- Otherwise proceed

### Stage 2 — Focus-Table Detail (selective, default cost = 0)

**Identify focus tables:** cluster Stage 1 hits by `tableId`. A focus table has ≥2 hits across any DDL labels. **Cap at 5 focus tables.** If more than 5, surface this in the output as a scope-too-broad signal — do not fan out.

**For each focus table, in order, stop when you have enough:**

1. **Parse `ddlText` from the Stage 1 table hit (default, 0 extra calls).** Every `DDLTable` returned by Stage 1 includes the full `CREATE TABLE` statement. Parse for columns + types + lengths + nullability + defaults + inline PK + inline constraints. Covers ~80% of impact-analysis questions.

2. **Targeted semantic column search (1 call, only if needed).** When the prompt implies cross-table column comparison (e.g. "find all `STATUS_TEXT` columns"):
   ```
   Architecture_Graph_Search(uuid, query="<TABLE_NAME> columns",
                             include_labels=["DDLColumn"], threshold=0.3)
   ```
   Approximate but cheap. May miss generic columns (CREATED_AT, IS_DELETED).

3. **DataLake-wide bulk fetch (last resort, amortized per DataLake).** Only when ≥2 focus tables share a parent DataLake AND structured column nodes are essential:
   ```
   Get_DB_Schema_Nodes_By_Label(data_lake_id, label="column")  ← one call per DataLake
   → cache result, client-side filter by tableId for each focus table
   ```
   One expensive call (~thousands of nodes) reused across all focus tables in that DataLake.

### Stage 3 — Cross-Reference Search (selective, only for drops / renames / type-changes / FK additions)

**Trigger:** prompt implies a structural change that needs downstream-dependency scan. Skip for purely additive changes.

**Action per affected DataLake (parallel, cached per DataLake):**
```
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="constraint")  → filter incoming FKs by referenced table
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="view")        → grep definition for table name (word-boundary)
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="procedure")   → grep body for table name (word-boundary)
```

### Classify each touched DataLake into one of three tiers

For the output, classify each touched DataLake by combining its writability with the nature of its findings:

| Tier | Trigger | Render |
|---|---|---|
| **🚨 Blocking (RO)** | DataLake is read-only (pattern matches `rmsowned-readonly` or similar) AND Stage 1 surfaced new columns/constraints/views being proposed | Full detail + "cross-team coordination needed" callout — appears FIRST in the Data Context / Data Layer section |
| **● V2-writable** | DataLake's pattern indicates V2 can mutate it (`full-crud`, `v2-modifies-via-migration`) AND DDL changes are needed | Full detail — application/migration work |
| **✓ Confirmed (RO)** | DataLake is read-only AND Stage 1 only surfaced EXISTING columns the prompt references — no DDL needed | One-line summary: "RO ✓ — columns X, Y already present, no DDL required" |
| **— Tangential** | DataLake had < 3 hits all with score 0.40-0.45 (weak match) | **Skip entirely from output** |

Detect writability via the DataLake's `pattern` array (e.g., `"rmsowned-readonly"` → read-only; `"full-crud-v1-and-v2"`, `"v2-modifies-via-migration"` → writable). Pattern strings are project-specific but consistently descriptive.

### Verdict

After tier classification, emit a single-line **Verdict** that takes one of these states:

- **🔴 BLOCKING** — at least one DataLake is in 🚨 tier (cross-team coordination required before V2 work can begin)
- **🟡 V2 WORK** — at least one ● V2-writable DataLake needs DDL, no blocking dependencies
- **🟢 NO DDL** — all findings are in ✓ Confirmed tier; application-layer change only

The Verdict is the most actionable single piece of output from this step. It belongs as the **last line** of the Data Context block (summary) and as a **callout box** at the bottom of the Data Layer section (detailed doc).

### Call-budget summary

| Scenario | Calls |
|---|---|
| UI-only ticket (Stage 1 < 3 hits) | 5 (Stage 1 only, then skip) |
| Schema-touching, additive, 3 focus tables | 5 (Stage 1) + 0 (ddlText parse) = **5** |
| Cross-table column comparison needed | 5 + 3 = **8** |
| Drop/rename, 1 DataLake, full dependency scan | 5 + 0 + 3 = **8** |
| Heavy: drop/rename across 2 DataLakes | 5 + 0 + 6 = **11** |

Bounded in every realistic case. Compare to a naive "always bulk fetch every DataLake" approach which could hit 50+ calls per analysis.

## Step 3 — Deep Analysis

Synthesize results from all four graphs into a deep analysis. Think across layers:

- **What does this prompt mean functionally?** — Which personas are involved, what outcomes/scenarios are touched, what business logic is relevant.
- **What does this mean from a design perspective?** — Which UI flows, pages, components are related, what user journeys are affected.
- **What does this mean at the code level?** — Which files, modules, classes, methods implement the relevant functionality.
- **What does this mean at the deployed-system level?** — Which UserExperience / ApiGateway / Services / Agents / EventQueue / DataLake / ObservabilityMonitoring / Infrastructure nodes are touched *by this prompt*. What's the request path. What's the async tail (CDC, queues, alert chains). What data stores hold the source-of-truth vs. the indexed / cached copy. Which of the touched nodes are single points of failure for this flow. The frame is **"what does the user input mean for the architecture?"**, not "what is wrong with the architecture graph?".
- **How are these connected?** — Trace the thread from functional requirement → design element → code implementation → deployed architecture node. Focus on the impact path, not ontology gaps.
- **What are the dependencies and risks?** — Upstream/downstream effects, shared components, breaking change potential. At the architecture layer, quantify **blast radius in deployed nodes** (how many services redeploy, how many data stores migrate, how many regions affected) — not just code files.

## Step 4 — Return Analysis Summary

**If DETAILED mode was set in Step 1b, skip this summary template entirely** and produce the detailed document instead, following the **Detailed-mode output template** defined immediately after this summary template. In DETAILED mode the document is written to a Markdown file in the current working directory (per Step 1b's filename convention) — the conversation response is a short confirmation block, NOT the full report. Do not also produce the summary. If the user explicitly specifies a file path (e.g. "save it to docs/impact.md"), honour that path instead of the default convention.

Otherwise emit the summary using the single template below.

```
Breeze Impact Analysis
Project: <name> (<uuid>)

Functional Context:
  - Personas: <list of relevant personas>
  - Scenarios: <list of relevant scenario names>
  - Key Actions: <most relevant actions/steps>

Design Context:
  - User Journeys: <related journeys>
  - Flows/Pages: <related flows and pages>
  - Components: <related UI components>

Code Context:
  - Files: <related source files, prefixed with parent repo when more than one repo is involved>
  - Modules/Classes: <related modules>
  - Key Methods: <relevant methods/functions>

  ** When 3+ files share a pattern that's being changed (multiple DSL builders, parallel
     controllers, similar React components), REPLACE the bullets above with a markdown
     table — significantly more scannable than bullets when the change is "same edit
     across N similar sites": **

  | Repo | File | Endpoint / Page | Current | Adds |
  |---|---|---|---|---|

  Column meanings:
  - **Repo** — which repo to clone/edit (`backend_nodejs_global_tnlm`, `frontendweb_react_tnlm`, etc.).
  - **File** — path with line number (e.g. `src/.../search-result-project.dsl.ts:18`). No symbol name in this column.
  - **Endpoint / Page** — the user-facing thing this file backs: a route (`POST /v1/search/project`), a page (`Dashboard search bar`), or a component slot. One concept per cell, not both.
  - **Current** — what the code does today (fields searched, behavior, fields rendered).
  - **Adds** — what the change introduces (new fields, new behavior, copy diff).

  If multiple symbols inside the same file change, list multiple rows — don't try to cram symbols into the `File` cell.

Architecture Context:
  - UserExperience: <delivery modalities on this flow>
  - ApiGateway path: <ordered request hop chain>
  - Services: <service nodes exercised, with tech stack>
  - Agents: <agent / LLM-workflow nodes exercised on this flow>
  - DataLake: <stores read/written on this flow, noting source-of-truth vs index/cache>
  - EventQueue: <queues / CDC / event buses that carry this flow's async tail>
  - Observability: <log / metric surfaces for this flow>
  - Infrastructure: <compute / networking substrate>

Data Context (conditional — only emit when Step 2.4 Stage 1 returned ≥3 hits):
  - 🚨 Cross-team (RO): <list RO DataLakes where DDL is needed but V2 can't ship it — name DataLake + 1-line "what needs to change + who owns it">
  - ● V2 work: <list V2-writable DataLakes where DDL changes are needed — name DataLake + 1-line summary>
  - ✓ Confirmed (RO): <list RO DataLakes where existing columns/structures suffice — single-line "RO ✓ — columns X, Y already present">
  - Verdict: <🔴 BLOCKING / 🟡 V2 WORK / 🟢 NO DDL> — <one-line justification>

  Omit any of the three lines (Cross-team / V2 work / Confirmed) that have no entries.
  Omit the whole Data Context block if Step 2.4 was suppressed (< 3 Stage 1 hits).

Impact on touched nodes:
  <2–4 bullets: SPOFs for this flow, source-of-truth vs. cache data roles,
   async-tail cost, which nodes absorb new load, multi-service coordination needs>

Feature Traceability:
  <how functional → design → code → architecture are linked for this prompt>

Architecture Blast Radius: <LOW / MEDIUM / HIGH / CRITICAL> — <one-line quantification>

Risk Level: <Low/Medium/High> — <one-line justification accounting for code-level risk
  AND deployed-system blast radius>

Cross-checks vs the prompt (include this block ONLY when the user's prompt itself
includes a stated analysis, count, or assertion the skill can validate or dispute):
  - ✅ <items the analysis confirmed — one bullet per confirmed claim>
  - ⚠️ <items the prompt understated, missed, or got wrong — one bullet each
        with a one-line explanation of the delta>
```

Notes on the template:
- Include a layer line in the Architecture Context block only when at least one node in that layer is touched by the prompt. The block is a roster of what the prompt exercises — silently omit empty layers (do NOT print "(none)" or "Agents: empty").
- If every architecture layer is empty, replace the whole Architecture Context block with a single line: `Architecture Context: Not available — architecture graph is not populated for this project.`
- Mark each architecture node with `✓` (exists, touched), `✗` (removed / failing in this scenario), `~` (modified), or `+` (new, proposed).
- Each `Impact on touched nodes` bullet names a specific touched node and describes an operational consequence — failure behavior, load characteristic, coordination requirement, or data-flow role.
- **Emit `Impact on touched nodes`, `Architecture Blast Radius`, and `Risk Level` lines only when the prompt clearly implies a change to the system** (new feature, modification, removal, failure scenario). If the prompt turns out to be purely exploratory ("how does X work?"), omit these three blocks and add a one-line note suggesting `/breeze:search` for explanatory questions — this skill is impact-analysis only.

IMPORTANT: After presenting this summary, explicitly ask the user:

"Would you like me to generate a detailed analysis document with diagrams for this? (yes/no)"

---

### Detailed-mode output template

Use this skeleton verbatim for headings, table column names, section ordering, and Mermaid `classDef` declarations. Substitute every `<placeholder>` slot with content derived from the analysis. Section ordering is FIXED — do not reorder. Conditional sections (marked) are included only when their trigger applies.

In DETAILED mode this entire document is written to a Markdown file (per Step 1b's filename convention) using the Write tool. After writing, print a short confirmation to the conversation containing: the absolute file path, the Verdict (from the Data Layer section if present, otherwise the Risk Level), and 3–5 headline findings as bullets — NOT the full document.

````
# Breeze Impact Analysis
**Project:** <name> (`<uuid>`)

**Legend:** `+ new` · `~ modified` · `✓ existing/touched` · `✗ removed`

---

## Executive Summary

<paragraph 1: what the change is + total surface area in one sentence>
<paragraph 2: most material discovery or constraint surfaced during analysis>
<paragraph 3: headline operational risk OR cross-cutting consideration>
<paragraph 4 (optional): blast-radius quantification + verdict>

---

## Functional Layer (touched nodes)

#### <glyph> <Persona Name> *(<persona-type label>)*

| Marker | Type | Name | Notes |
|---|---|---|---|
| <marker> | Outcome | <Outcome name> (`<id>`) | <one-line notes> |
| <marker> | Scenario | <Scenario name> (`<id>`) | <one-line notes> |
| <marker> | Step | <Step name> (`<id>`) | <one-line notes> |
| <marker> | Action | <Action name> (`<id>`) | <one-line notes> |

#### <glyph> <next persona> *(<type>)*

| Marker | Type | Name | Notes |
|---|---|---|---|
...

*(One `####` subsection per touched persona. Persona type, glyph, ordering, and Step-row rules per the Per-layer tables spec above. No row duplication across personas.)*

---

## Design Layer (touched nodes)

| Marker | Type | Name | Notes |
|---|---|---|---|
| <marker> | UserJourney | <name> (`<id>`) | <notes> |
| <marker> | Flow | <name> (`<id>`) | <notes> |
| <marker> | Page | <name> (`<id>`) | <notes> |
| <marker> | Component | <name> (`<id>`) | <notes> |

---

## Code Layer (touched files)

| Marker | Repo | File | Endpoint / Page | Current | Adds |
|---|---|---|---|---|---|
| <marker> | <repo> | <path:line> | <route or page> | <current behavior> | <new behavior> |

---

## Architecture Layer (touched nodes)

| Marker | Layer | Node | Touched because… |
|---|---|---|---|
| <marker> | UserExperience | <node name> (`<id>`) | <one-line reason> |
| <marker> | ApiGateway | <node name> (`<id>`) | <one-line reason> |
| <marker> | Services | <node name> (`<id>`) | <one-line reason> |
| <marker> | Agents | <node name> (`<id>`) | <one-line reason> |
| <marker> | EventQueue | <node name> (`<id>`) | <one-line reason> |
| <marker> | DataLake | <node name> (`<id>`) | <one-line reason> |
| <marker> | ObservabilityMonitoring | <node name> (`<id>`) | <one-line reason> |
| <marker> | Infrastructure | <node name> (`<id>`) | <one-line reason> |

*(Silently omit layer rows with no touched nodes — never print "Agents: empty" or similar. HARD RULE.)*

---

## Data Layer (Schema-Side)

*(Conditional — include only when Step 2.4 Stage 1 returned ≥3 hits. One block per touched DataLake. Ordering: 🚨 Blocking → ● V2-writable → ✓ Confirmed → skip Tangential entirely.)*

### <tier-marker> `<DataLake name>` — <tier label> *(patterns: `<pattern1>`, `<pattern2>`)*

**Tables touched:** <list>

**DDL operations:**

| # | Op | Object | Statement | Migration file | Reversible | Ship in |
|---|---|---|---|---|---|---|
| <n> | <ADD/DROP/ALTER/...> | <schema.table.col> | <SQL statement or summary> | <migration path or "—"> | ✓/✗ | <release/window> |

**Dependents (from Stage 3 cross-reference scan):**

| Type | Name | Schema | Risk to operation # | Action |
|---|---|---|---|---|
| <FK/View/MV/Trigger/Procedure> | <object name or "—"> | <schema> | #<n> or "—" | <action or "None found"> |

*(Repeat block per touched DataLake.)*

**Verdict callout:**

> <🔴 BLOCKING / 🟡 V2 WORK / 🟢 NO DDL> — <one-to-two sentence justification>

---

## Request-Path Diagram

```mermaid
flowchart LR
    <nodes and edges showing user → edge → gateway → service → storage>

    classDef changed fill:#fff4b8,stroke:#b8860b,color:#000
    classDef unchanged fill:#e8f4ff,stroke:#3a78a8,color:#000
    classDef storage fill:#e8ffe8,stroke:#2e8b57,color:#000
    class <changed-nodes> changed
    class <unchanged-nodes> unchanged
    class <storage-nodes> storage
```

## Async-Tail Diagram

```mermaid
flowchart TD
    <nodes and edges showing upstream → queue/CDC/worker → destination, including external sinks>

    classDef new fill:#fff4b8,stroke:#b8860b,color:#000
    classDef unchanged fill:#e8f4ff,stroke:#3a78a8,color:#000
    classDef storage fill:#e8ffe8,stroke:#2e8b57,color:#000
    class <new-nodes> new
    class <unchanged-nodes> unchanged
    class <storage-nodes> storage
```

*(Omit the Async-Tail diagram when the change has no async tail — purely synchronous request/response feature.)*

---

## Cross-Layer Traceability Matrix

| Scenario | Functional | Design | Code | Architecture |
|---|---|---|---|---|
| <scenario name> | <outcome/scenario ref> | <UJ/Flow/Page/Component ref> | <repo:path> | <touched arch nodes> |

*(One row per scenario covered by the change. Reuse scenario list from the Functional Layer section.)*

---

## Single Points of Failure for this Flow

1. **<node name>** — failure mode → user-visible effect → mitigation in this design. <one paragraph>
2. ...

*(Only nodes whose failure breaks THIS flow. Not generic platform SPOFs.)*

---

## Risk Taxonomy

### <n>. <Risk title> — <LOW/MEDIUM/HIGH> likelihood × <LOW/MEDIUM/HIGH> consequence
**Why:** <one paragraph explaining the mechanism>
**Worst case:** <one sentence>
**Mitigation:**
1. <concrete action>
2. <concrete action>
3. <concrete action>

*(3–7 risks total. Each MUST use the Why / Worst case / Mitigation triple — no flat risk paragraphs.)*

---

## QA Test Plan

| # | Test | Expected |
|---|---|---|
| 1 | <concrete test with concrete inputs> | <concrete expected output> |
| 2 | ... | ... |

*(6–12 cases. Include regression-guard cases and edge cases (special characters, pagination boundaries, large payloads).)*

---

## Operational Considerations

- **New log groups / dashboards:** <names>
- **New alarms:** <names + thresholds where known>
- **Capacity test plan:** <what to measure + on what env>
- **Rollback path (clean):** <ordered steps>
- **Rollback path (dirty):** <what's lost, what's recoverable>
- **Alarm channel:** <existing SNS / Slack / etc.>

---

## Out of Scope

- <bullet 1>
- <bullet 2>
- ...

*(Explicit pre-emption of scope creep. Often as valuable as the in-scope analysis.)*

---

## Open Questions

1. **<topic>** — <specific question with implementation impact>
2. ...

*(3–6 questions. Must have concrete implementation consequence — not generic "have you considered" prompts.)*

---

## Implementation Options

*(Conditional — include only when 2+ viable paths exist. Omit when there's only one sensible approach.)*

### Option A: <name> (recommended)
<one-paragraph description>
- **Pros:** <bullets>
- **Cons:** <bullets>
- **Cost:** <time estimate + infra cost>
- **Risk:** <Low/Medium/High>

### Option B: <name>
<as above>

**Recommendation: Option <X>.** <one-paragraph reasoning>

---

## Multi-Service Deploy Coordination

*(Conditional — include whenever >1 service or repo must redeploy.)*

Required deploy order:

1. **`<repo>`** — <what to ship> → <how to verify before next step>
2. **`<repo>`** — <what to ship> → <how to verify>
...

<Note on backwards-compatibility windows; per-step rollback path.>

---

## Staged-rollout Plumbing

*(Conditional — include only when the prompt implies a feature flag or cohort rollout.)*

- **Flag storage:** <env var / GrowthBook / LaunchDarkly / DB row>
- **Gate location in code:** <repo:path>
- **Kill-switch behavior:** <fail-safe direction>
- **Rollout stages:** Stage 0 (internal) → Stage 1 (design partners) → Stage 2 (X% public) → ...

---

## Suggested Ticket Slicing

*(Conditional — include for non-trivial changes.)*

- **<ID>** — <scope>. <deps or "no deps">
- **<ID> → <dep>** — <scope>.
...

*(Use IDs with explicit dependencies. One line per ticket.)*

---

## Cross-checks vs the prompt

*(Conditional — include ONLY when the user's prompt contains a stated analysis, count, or assertion the skill can validate or dispute.)*

- ✅ <claim from prompt the analysis confirmed> — <one line>
- ⚠️ <claim from prompt the analysis disputes / extends> — <one line explaining the delta>
````

After writing the file, the inline confirmation block printed to the conversation should look like:

```
Detailed impact-analysis written to: <absolute path>

Verdict: <🔴 BLOCKING / 🟡 V2 WORK / 🟢 NO DDL or Risk: <Low/Medium/High>>

Headline findings:
- <finding 1>
- <finding 2>
- <finding 3>
- <finding 4 (optional)>
- <finding 5 (optional)>
```

## Rules

- Always read all four graphs, even if the prompt seems to only affect one area. Functional / Design / Code are semantic searches; Architecture is per-label enumeration via 8 parallel `Get_Architecture_Nodes_By_Label` calls (one per architecture label).
- The summary should be informative but concise — the detailed doc comes later if requested (or directly in DETAILED mode).
- **DETAILED mode (Step 1b):** when the user passes `--detailed` (or a synonym), Step 4 skips the summary template and emits the detailed document directly. Never produce both a summary and a detailed document in the same invocation.
- **Output target — mode-dependent:**
   - **SUMMARY mode** → emit inline in the conversation. Never write to a file in SUMMARY mode.
   - **DETAILED mode** → write the full report to a Markdown file in the current working directory using the Write tool, following Step 1b's filename convention (`impact-analysis-<short-kebab-slug>.md` or `impact-analysis-<YYYY-MM-DD>.md` fallback). The inline conversation response is a short confirmation block (path + verdict + 3–5 headline findings), NOT the full document. If the user gives an explicit file path in the prompt (e.g. *"save it to `docs/impact-2026-05-18.md`"*), honour that path verbatim instead of the default convention.
   - This mode-dependent split is deliberate: parent skills calling `/breeze:impact-analysis --detailed ...` must Read the produced file to consume the full report. The inline confirmation tells the caller where to look.
- **Project targeting (Step 1a + CLAUDE.md):** project resolution follows CLAUDE.md's rules (`--project <uuid|name>` override → `.breeze.json` fallback). Step 1a adds a skill-specific natural-language hint form. Do not mutate `.breeze.json`.
- If functional, design, AND code searches all return no results, report "No relevant context found in any graph" and skip the doc offer — even if the architecture graph is populated, there's nothing to anchor it to.
- Do not modify or interfere with the user's original prompt — your job is analysis only.
- Architecture analysis is read-only. This skill never mutates the Architecture Graph.
- Architecture analysis is **impact-on-deployed-system**, not ontology audit. Frame every architecture observation as "what does the user's prompt mean for this node?" — not "what is missing from the graph?".
- **HARD RULE — never surface graph-hygiene gaps to the user.** This is output shown to non-Breeze readers who may misread coverage shortfalls as product defects. Do NOT include (in the summary, the detailed doc, or any user-visible line):
  - "empty scenario arrays", "unanchored", "orphan scenario", "graph-hygiene gap", "fully unanchored"
  - "Agents layer is empty / count=0" or any "layer X has 0 nodes" observation
  - "missing code_ontology_id", "missing regional counterpart", "region mismatch"
  - a `Gaps:` line inside the Architecture Context block, ever
  - any itemization of what the graph is missing

  If `scenario[]` arrays or `code_ontology_id` fields are empty, silently fall back to name/technology matching and proceed with the impact analysis — do not mention the fallback. If the architecture graph is entirely empty, use the single baseline line from the "Notes on the Architecture Context block" section and stop there.
- **The detailed document (if requested, or auto-emitted in DETAILED mode)** is a structured artifact, not a long-form essay. Emit the sections below in this order. Mandatory sections appear in every detailed doc; conditional sections appear only when applicable.

  **MANDATORY HEADER — print verbatim, immediately under the title/metadata block:**

  > `Legend: + new · ~ modified · ✓ existing/touched · ✗ removed`

  This legend covers markers across all four ontologies (Functional, Design, Code, Architecture). It MUST appear in every detailed doc — readers from outside the team rely on it to interpret the per-layer tables.

  **MANDATORY SECTIONS (in this order):**

  1. **Executive Summary** — 2–4 paragraphs naming the change, the surface area, and the headline risk.

  2. **Per-layer touched-nodes tables — one per ontology, markers on every row.** All five ontologies get the same marker treatment in the detailed doc (this differs from the SUMMARY template above, which marks only Architecture nodes):
     - *Functional Layer — one section per persona, NOT a single flat table.* The functional graph hierarchy is **Persona → Outcome → Scenario → Step → Action** — render the persona axis as the top-level grouping so the reader can scan by who-is-affected. Rules:
        * **One markdown subsection (`####` heading) per persona that has ≥1 touched node.** Heading format: `<glyph> <Persona Name> <em>(<persona-type label>)</em>`.
        * **Persona-type lookup is graph-driven, NOT text-heuristic.** Every persona returned by `Get_all_personas` (cached in Step 2.1) carries the information you need. Resolve the type in this order:
           1. **Persona `type` field** if present on the persona record — use it verbatim.
           2. Otherwise the persona's **`name` field** — Breeze functional graphs include dedicated, canonically-named personas for non-human actors. The two canonical names to recognise are:
              - `System` (case-insensitive exact match) — internal background actor
              - `External System` (case-insensitive exact match) — third-party / external service
           3. Anything else → treat as a human persona.
        * **Glyph by type:** 👤 human · 🤖 System · ☁️ External System. Never invent a persona name; never guess from outcome wording. If the affected node's parent Outcome's `personaId` maps to a persona record named `System`, the heading is literally `🤖 System (system persona)` — not `🤖 Alert Dispatcher` or any other invented label.
        * **Section ordering:** human personas first (PMs / UX readers care most), then system personas, then external-system personas. Within each type bucket, order by number of touched rows descending (most-impacted persona first).
        * **Inside each persona section, render a table with columns:** `Marker | Type (Outcome/Scenario/Step/Action) | Name | Notes`. **Step rows are mandatory** — do NOT skip the Step layer. Order rows by hierarchy: each Outcome immediately followed by its Scenarios, each Scenario by its Steps, each Step by its Actions. This makes the chain visually scannable inside one table without nested tables.
        * **HARD RULE — the rendered parent chain must be complete and marker-consistent (no orphan rows).** Every row's parent must appear as a row above it, and a row's marker constrains what its parent may be:
           - A `+ new` node's **entire ancestry up to the first pre-existing node must also be shown.** If you add an Action, ask: does its Step already exist in the graph? Does its Scenario? Each ancestor that does NOT already exist is itself a `+ new` row and MUST be rendered. You stop climbing only when you reach a real, already-existing node the new subtree genuinely attaches to — that attachment node is `✓` (or `~` if that node's own content changes to host the child). A new Action almost always implies a new Step **and** a new Scenario, because you cannot hang a new leaf under a different feature's existing Scenario.
           - **Never parent a `+ new` node under an unrelated existing node and mark that parent `~` to "make it fit".** `~` means *this node's own content/behavior changes*, not *this node is nearby* or *this node is where I attached something new*.
           - **Distinguish a modified node from a cloned template.** If an existing node is only being used as the **pattern you copy** and is not itself altered, mark it `✓` and label it "reference / pattern" in Notes — do NOT mark it `~`. Reserve `~` for nodes whose description, fields, validation, routing, or behavior actually change (e.g. an existing chooser Scenario that genuinely gains a new option is `~`; the sibling Scenario you merely cloned is `✓`).
           - **Additive-feature default:** for a "new feature" prompt that reuses an existing pattern, represent it as a **new `+` Scenario → `+` Step → `+` Action subtree under an existing `✓` Outcome** (plus a separate `✓ reference` row for the pattern being cloned), rather than smearing `~` across the pattern's chain. Before finalizing, re-read each persona table top-to-bottom and confirm every `+`/`~` leaf has a visible, correctly-marked parent path to a Persona.
        * **A single node appears under exactly one persona section** — its parent Outcome's persona. Do not duplicate rows across personas even if a Scenario is conceptually relevant to multiple personas; pick the owning Outcome's persona.
        * **Persona-name resolution:** the `Get_all_personas` call in Step 2.1 returns the ID→name map. Walk every non-Outcome row (Scenario/Step/Action) up to its parent Outcome to find its persona. If the chain breaks (e.g., orphan Action with no resolvable Outcome), put the row under a final `❓ Unattributed` section — do NOT silently drop it.
     - *Design Layer table* — columns: `Marker | Type (Page/Component/UserJourney/Flow) | Name | Notes`
     - *Code Layer table* — columns: `Marker | Repo | File | Endpoint / Page | Current | Adds` (same shape as the summary's Code Context table, plus the marker column up front — see Step 4 for column meanings)
     - *Architecture Layer table* — columns: `Marker | Layer | Node | Touched because…`
     - *Data Layer (Schema-Side) section* — **conditional on Step 2.4 Stage 1 returning ≥3 hits.** Render as one block per touched DataLake (not a flat table — the per-DataLake grouping is the point). Each block uses the tier classification from Step 2.4:
       * 🚨 Blocking (RO) blocks appear FIRST. Include: DataLake name + access pattern; tables touched with current `ddlText`-parsed column summary; what DDL is being requested; dependent procedures / materialized views / triggers / incoming FKs; the "RMS-or-equivalent coordination ticket needed" callout.
       * ● V2-writable blocks appear second. Same content shape; framed as work V2 can ship via its migration repo.
       * ✓ Confirmed (RO) blocks appear last as one-liners: "<DataLake> (RO): <columns> already present, no DDL required".
       * Skip — Tangential entirely.
       * Close the section with the **Verdict callout box**: 🔴 BLOCKING / 🟡 V2 WORK / 🟢 NO DDL with a 1-2 sentence justification. Same Verdict line that appeared in the summary's Data Context — repeated here so the detailed doc is self-contained.

  3. **Request-path Mermaid diagram** — MUST use `classDef` color-coding (e.g., `changed` / `unchanged` / `storage`) so every node visually carries its status. Do not emit an uncolored diagram. Example:

     ```
     classDef changed fill:#fff4b8,stroke:#b8860b,color:#000
     classDef unchanged fill:#e8f4ff,stroke:#3a78a8,color:#000
     classDef storage fill:#e8ffe8,stroke:#2e8b57,color:#000
     class GT,IDX1,IDX2 changed
     class R,CF,AG,NG unchanged
     class ES,DB storage
     ```

  4. **Async-tail Mermaid diagram** — full pipeline from upstream source through queue/CDC/worker/destination, including external sinks (SES, third-party APIs, Kafka topics, downstream DBs) when relevant.

  5. **Cross-layer traceability matrix** — table with one row per scenario; columns `Functional | Design | Code | Architecture`.

  6. **Single Points of Failure for this flow** — list nodes whose failure breaks *this flow specifically* (not generic platform SPOFs). One paragraph per SPOF: failure mode → user-visible effect → mitigation in this design.

  7. **Risk taxonomy — structured.** List 3–7 risks. Each risk uses this sub-structure:
     - **Heading** with a `<Likelihood> × <Consequence>` rating (e.g., "Latency on the ES hot path — LOW likelihood × HIGH consequence")
     - **Why** — one paragraph
     - **Worst case** — one sentence
     - **Mitigation** — numbered list of concrete actions

     Do NOT emit a generic risk paragraph or a flat risk table — the Why/Worst case/Mitigation breakdown is what makes this section actionable for triage.

  8. **QA test plan — concrete table.** Markdown table with columns `# | Test | Expected`. 6–12 specific test cases with concrete inputs and concrete expected outputs. Include regression-guard cases (empty input, behavior unchanged on existing paths) and edge cases (special characters, pagination boundaries, large payloads).

  9. **Operational considerations** — alarms to add or tune, capacity test plan, rollback path. Bulleted; concrete; name specific dashboards/services where possible.

  10. **Out of Scope** — explicit bulleted list of what the change does NOT affect. Pre-empts scope creep and is often as valuable as the in-scope analysis.

  11. **Open Questions for the change author** — numbered list of 3–6 specific questions that surfaced during analysis and need answering before merging. Questions must have concrete implementation impact (field placement, indexer behavior, UX behavior, pagination, auth) — not generic "have you considered…" prompts.

  **CONDITIONAL SECTIONS (include when applicable):**

  - **Implementation Options** — include when 2+ viable paths exist for shipping the change (msearch fanout vs unified index, sync vs async, in-place migration vs blue-green, shared base class vs duplicated edits). Each option: pros / cons / cost-to-ship / risk + a recommendation with reasoning. Omit when there's only one sensible path.

  - **Multi-Service Deploy Coordination** — include whenever more than one service or repo must redeploy. Cover ordering, what makes each step backwards-compatible (or not), which deploys can lag behind the others, and rollback path per service.

  - **Staged-rollout plumbing** — include if the prompt implies a feature flag or cohort rollout: flag storage location, where the gate lives in code, kill-switch behavior, rollout stage definition (Stage 0 internal → Stage 1 design partners → …).

  - **Suggested ticket slicing** — include for non-trivial changes. Use IDs with explicit dependencies (e.g., `DB-01 → B-01 → T-01`). One line per ticket: scope + dependency.

  The architecture section describes impact on touched nodes — never enumerates graph-completeness gaps.
