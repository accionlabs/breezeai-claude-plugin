# Per-call inputs template — discovery agent

The skill renders this file (substitutes the `{{...}}` placeholders) and passes
the result as the `prompt` argument when invoking
`subagent_type: "breeze:backend-entrypoint-discovery-agent"`, ONCE per run.

The agent's full methodology — discovery phases, persona mechanical mapping,
entrypoints.json schema, summary-line spec — lives in
`agents/backend-entrypoint-discovery-agent.md`. This template only carries the
per-call variable inputs.

---

REPO:
  name:                {{repo_name}}
  root:                {{repo_root_absolute_path}}
FRAMEWORK_HINT:        {{framework_hint}}
PROJECT_UUID:          {{project_uuid}}
PROJECT_NAME:          {{project_name}}
CODE_ONTOLOGY_ID:      {{code_ontology_id}}
INDEXED_REPO_NAME:     {{indexed_repo_name}}
OUTPUT_PATH:           {{output_path}}
EXISTING_PERSONAS:     {{existing_personas_json}}

Inventory every REST route, GraphQL operation, and queue/event/cron handler (plus orphans) under REPO.root. Flag GraphQL operations as `needs_confirmation` (do NOT wait for input). Write the full inventory to OUTPUT_PATH and return ONLY the `OK · …` / `FAIL_…` summary line per the agent's Phase 7 spec.
