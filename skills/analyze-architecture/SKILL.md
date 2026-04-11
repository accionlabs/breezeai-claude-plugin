---
name: analyze-architecture
description: Analyze a requirement (from Jira, document, image, diagram, or text) against the existing Architecture Graph. Maps the requirement to the 8-layer model, runs impact analysis via the Code Graph, anchors user-facing components to Functional Scenarios, detects reuse opportunities and gaps, and writes a structured analysis report back to the Jira ticket. The Architecture Graph persists only the 8 layers — all analysis output is ephemeral and lives in the write-back.
---

## Guard

Read `.breeze.json`. If missing, tell the user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`. Verify the project exists via `Call_Get_Project_Details_`.

## Invocation

```
/breeze:analyze-architecture --jira <jira-url>
/breeze:analyze-architecture "requirement text / document / diagram / image"
```

Two input modes:

| Mode | When |
|---|---|
| **Jira-linked** (`--jira`) | Requirement is tracked in a Jira ticket. Recommended. |
| **Ad-hoc** | Requirement arrived as a document, image, diagram, or free-form text. Also used for documenting an existing system into the Architecture Graph for the first time. |

Whether the input represents *current state* or a *proposed change* is inferred during classification (Step 6) from Architecture Graph state and input content — not declared at invocation.

---

## Step 1 — Load input

1. If `--jira <url>` was provided, parse the URL → instance hostname + issue key (e.g., `https://acme.atlassian.net/browse/PROJ-2245` → instance `acme.atlassian.net`, key `PROJ-2245`). Fetch the ticket via the Jira MCP and read summary, description, acceptance criteria, labels, epic link, linked issues.
2. If ad-hoc, accept the requirement text / document / image directly. Images route through multimodal extraction; diagrams are parsed as visual content.

## Step 2 — Read the three graphs (parallel)

Architecture analysis needs cross-ontology context to produce real insight. Pull three graph slices in parallel:

| Source | Tool | Purpose |
|---|---|---|
| Current Architecture Graph | `Get_All_architecture_Graph` | Reuse detection, layer boundary checks, duplicate detection, current-state inference |
| Functional Graph | `Get_all_personas` → `Get_all_outcomes_for_a_persona_id` for each, OR `Functional_Graph_Search` with keywords from the requirement | Cross-ontology anchoring (fills the `scenario` field on UserExperience / ApiGateway / Services nodes), coverage gap detection |
| Code Graph | `Code_Graph_Search` with 2–4 queries derived from the requirement | Real impact analysis — returns files, functions, classes, call graphs, `codeOntologyId`, `repositoryName` |

Also use `Get_Architecture_Nodes_By_Label` when you need a scoped read of one layer rather than the full graph.

**Flag internally:** if the Architecture Graph is empty or sparse (< 5 nodes total), the run is likely a **current-state capture**. This changes the commit policy in Step 6.

## Step 3 — Map the requirement to the 8-layer model

The Architecture Graph stores exactly 8 layers (per the bible's 8-tier model). For each architectural element the requirement implies, determine which layer it belongs to.

### Layer definitions

- **UserExperience** — A client-side **delivery modality**: web app, mobile app, voice interface, API client, desktop app, CLI, etc. One node per modality — NOT per page, component, or screen. Pages and components belong to the Design Ontology, not here. This layer answers: *"what delivery channels does the product support?"* A typical product has 1–4 UserExperience nodes total.

- **ApiGateway** — API gateway tier handling routing, authentication delegation, rate limiting, and request shaping. One node per gateway deployment (e.g., one Nginx, one Kong, one AWS API Gateway).

- **Services** — Backend services. Per the bible, split into two sub-types:
    - **Custom Services** — Entity, Workflow, or Integration services specific to the business domain (e.g., "Order Service", "Invoice Service", "Scheduled Post Worker")
    - **Platform Services** — Cross-cutting capabilities like **Auth, Search, Notifications** (bible: `02:260`). Note: these live in Services, not in ApiGateway or as standalone infrastructure.

- **Agents** — Intelligent orchestration components. Per the bible (`02:254-257`), four sub-types:
    - **Business Process Agents** — orchestrate multi-step business workflows
    - **Domain Agents** — specialized for a specific business domain
    - **Integration Agents** — handle system-to-system integration
    - **Assistant Agents** — user-facing AI assistants

  When a requirement proposes a new agent, ask which sub-type it is — placement and governance differ.

- **EventQueue** — Message queues, event streams, asynchronous messaging infrastructure (Kafka, RabbitMQ, SQS, Redis Streams, etc.).

- **DataLake** — Data layer including databases, data warehouses, analytics pipelines, ML model registries, feature stores, and vector DBs. The bible's name for this layer is actually **"Data Lake, Analytics, AI/ML"** (`02:262`) — it's broader than just data-at-rest. A Spark job, a dbt pipeline, or an ML training pipeline all belong here, not in Services.

- **ObservabilityMonitoring** — Logging, metrics, tracing, alerting, and telemetry. The bible calls this **"Observability & Monitoring"** (`02:252`) as two paired concepts.

- **Infrastructure** — Cloud infrastructure, deployment, scaling, networking (AWS EKS, GCP GKE, Terraform, CDN, load balancers, VPC, etc.).

### Placement rules

- If an element doesn't fit cleanly into one of the 8 layers, flag it and ask the user for placement. Do not invent new layer types — the model is fixed.
- An auth component always goes in **Services → Platform Services**, not in ApiGateway.
- An ML training pipeline goes in **DataLake**, not in Services.
- A user-facing AI chatbot goes in **Agents → Assistant Agents**, not in Services or UserExperience.
- Page/component-level concerns do NOT belong here — they belong to the Design Ontology (Journey → Flow → Page → Component). A UserExperience node is coarser than any of those.

## Step 4 — Run analysis (four sub-activities)

Run these in sequence. Their output becomes the analysis report written back in Step 7. **None of this output is persisted to the graph.**

### 4a. Impact analysis

For each area of concern in the requirement, run `Code_Graph_Search` with a targeted query (e.g., "invoice creation endpoint", "GST report generation", "user authentication"). Returned results include file paths, function signatures, line numbers, and the `calls` field — walk the call graph to find indirect impact. Cross-reference the returned `codeOntologyId` values against existing Architecture Graph nodes (each Service / UX / ApiGw node may already have a `code_ontology_id` pointing to its code cluster).

For critical files, drill in with `Get_Code_File_Details` to enumerate classes, methods, and decorators (useful for discovering API routes via Pyramid `@view_defaults`, Flask routes, Spring `@RequestMapping`, etc.).

**Output:** list of affected files + affected architecture nodes + estimated blast radius (count of files + count of components).

### 4b. Reuse detection

For each proposed new component:

1. Search the Architecture Graph for similar nodes by matching `domain`, `technologies`, `category`, `pattern` (use `Get_Architecture_Nodes_By_Label` per layer).
2. Run `Code_Graph_Search` for key concepts in the proposal — if matching functions/classes exist, the capability already lives somewhere and can probably be extended rather than duplicated.
3. Flag cross-cutting Platform Services (Auth, Search, Notifications, Logging, Audit) that should almost always be reused.

**Output:** reuse candidates with rationale + flagged duplicates that should be merged.

### 4c. Cross-ontology anchoring

For each proposed **UserExperience / ApiGateway / Services** node (the three layers whose schemas carry `scenario: []`):

1. Run `Functional_Graph_Search` against component-relevant keywords.
2. Rank candidate Scenarios (or Outcomes for cross-cutting services) by relevance.
3. Propose the top anchors to the user for confirmation.

If `--jira` was provided and the Functional Graph already has nodes citing this ticket, use those as deterministic anchors (highest precision).

**Anchoring rules:**
- Every Service / UX / ApiGateway **must** have at least one scenario anchor → **block commit** if missing.
- DataLake / EventQueue / Agents / Observability / Infrastructure do **NOT** require direct anchors. They inherit context from the Services that reference them.
- `Supports` edges land on a Scenario (primary) or Outcome (for cross-cutting services).
- `Triggers` and `Validates` edges land on Actions.
- For UserExperience nodes at modality level, the `scenario` field should hold scenarios that are unique to or primarily served by that modality (not an exhaustive list of every scenario the modality realizes — that would duplicate the Design Graph).

**Output:** proposed `scenario` field values per architecture node, unanchored blockers.

### 4d. Gap and consistency check

Run a small ruleset over the proposal + current graph state:

- Proposed Service has `emits_events: true` → is there an EventQueue?
- Proposed background worker → is there scheduler infrastructure?
- Proposed new Service → is there monitoring for it in ObservabilityMonitoring?
- Proposed DataLake table → is there a backup/retention policy?
- Proposed component uses a technology not in the existing stack → flag divergence
- Proposed component name breaks existing naming convention → suggest rename
- Layer boundary check: no UX → DataLake direct calls, no reverse data flow (Services calling UX)

**Output:** list of gaps and inconsistencies with severity.

## Step 5 — Show the analysis report and confirm

Present the structured report to the user covering:

1. **Impacted layers** — delta summary per layer
2. **Impact analysis** — direct + indirect code impact, architecture nodes touched
3. **Reuse opportunities** — what already exists
4. **Cross-ontology alignment** — proposed scenario anchors, missing coverage
5. **Gaps and consistency** — missing infrastructure, convention drift, boundary violations
6. **Proposed graph changes** — 8-layer table with full metadata for each new/modified node

Ask the user to:
- Confirm or edit the proposed scenario anchors
- Confirm or edit the metadata for each new/modified node
- Resolve blocking issues (unanchored nodes, boundary violations, duplicates)

Loop on this step until the user confirms the proposed changes.

## Step 6 — Classify and commit to the Architecture Graph

Apply the commit policy based on classification outcome:

| Classification | Action |
|---|---|
| New component, reuses existing library | Auto-commit after confirmation |
| New service with confirmed scenario anchor | Commit after user confirmation |
| New library-level component (new Service / UX / Gateway) | Commit after user confirmation — this changes the system topology |
| Modifies existing node | Commit after user confirmation |
| **Current-state capture** (empty/sparse graph + input describes existing system) | Auto-commit all after single user confirmation at the end |
| Unanchored Service / UX / ApiGateway | **Block** — clarification required before commit |
| Layer boundary violation | **Block** — redesign required |
| Duplicate of existing | **Block** — propose reuse instead |

Persist via `Create_Architecture_Node` (new) or `Update_Architecture_Node` (existing), in layer-hierarchy order:
UserExperience → ApiGateway → Services → Agents → EventQueue → DataLake → ObservabilityMonitoring → Infrastructure.

### ⚠ LABEL PARAMETER — IMPORTANT

When calling `Create_Architecture_Node` or `Update_Architecture_Node`, the `label` parameter **MUST be the bare layer name** (`UserExperience`, `ApiGateway`, `Services`, `Agents`, `EventQueue`, `DataLake`, `ObservabilityMonitoring`, `Infrastructure`), **NOT with a `Label` suffix**.

The tool's own schema description lists values like `UserExperienceLabel`, `ServicesLabel`, etc. — **this is misleading and returns a generic 400 error**. Always use the bare layer name.

```
✓ label: "UserExperience"     → success
✗ label: "UserExperienceLabel" → 400 Bad Request
```

### Required fields on every committed node

- **citation** — the Jira key + URL (Jira mode) or file path / hash (ad-hoc mode). Never commit a node without a citation.
- **scenario** — array of Functional node IDs (for UserExperience / ApiGateway / Services only). Non-empty for these three layers.
- **code_ontology_id** — the repo cluster ID from Code Graph results, when the component corresponds to existing code.

Refer to `references/guide.md` for the full data model and required fields per layer.

## Step 7 — Write back

### If `--jira` was provided

Append a comment to the Jira ticket via the Jira MCP. **The comment IS the analysis report** — the analysis itself is ephemeral and lives only here, not in the Architecture Graph. Use this format:

```
── Breeze.AI Architecture Analysis ──
Status:   Architecture Graph updated (architecture-graph@v<N>)
Case:     <classification summary>

IMPACT ANALYSIS
  Direct code impact (<count> files):
    • <file path> (<function name> L<start>-<end>)
  Indirect impact (via call graph): <count> files
  Architecture nodes touched: <count>
    <diff summary per node>

REUSE OPPORTUNITIES
  ✓ <existing component> — <reuse rationale>
  ⚠ <missing capability> — <suggestion>

CROSS-ONTOLOGY ALIGNMENT
  Functional anchors (proposed):
    ✓ "<outcome/scenario>" (id: <functional_node_id>) [cited]
  Missing action coverage:
    ⚠ <gap>

GAPS & CONSISTENCY
  ⚠ <gap or inconsistency>
  ✓ <passed check>

COMMITTED TO GRAPH
  <layer>:
    + <node name> (new)
       code_ontology_id: <id>
       scenario: [<ids>]
    ~ <node name> (modified)

Citation:    <Jira key>
URL:         <Jira URL>
Version:     architecture-graph@v<N>
```

For **blocked cases** (unanchored nodes, layer violations, duplicates), replace COMMITTED TO GRAPH with a BLOCKERS section listing the specific issues, and note that no graph changes were made.

For **current-state-capture runs** (empty/sparse graph + input describes existing system), change the heading to *"Baseline documentation — all nodes committed"* and skip REUSE OPPORTUNITIES / GAPS sections (nothing to compare against).

### If `--jira` was not provided

Return the analysis as a structured summary artifact. Optionally prompt the user for a Jira ticket URL to mirror the comment into.

---

## Principles

1. **The Architecture Graph stores only the 8-layer node structure.** Impact analysis, reuse findings, gap detection, cross-ontology alignment — all ephemeral. They live in the Jira comment or returned artifact. Never invent a "proposal" or "analysis" node type.
2. **UserExperience is modality-level, not component-level.** One node per delivery channel (web, mobile, voice, API client). Pages and components belong to the Design Ontology.
3. **Never mutate source artifacts.** Always append comments to Jira tickets, never edit descriptions.
4. **Citations are mandatory.** Every committed node must cite its source.
5. **Scenario anchoring is mandatory for UX / ApiGateway / Services.** Unanchored nodes in these three layers block commit. Supporting layers (DataLake, EventQueue, Agents, Observability, Infrastructure) do not require direct scenario anchors.
6. **Reuse is a success state, not an edge case.** The skill actively searches both the Architecture Graph and the Code Graph for existing components that satisfy the requirement.
7. **Immutable versioning.** Every graph update creates a new version. Re-analysis never silently mutates prior versions.
8. **Ambiguity blocks commit.** If the analyzer cannot classify confidently, no graph changes are made; the user is asked for clarification.
