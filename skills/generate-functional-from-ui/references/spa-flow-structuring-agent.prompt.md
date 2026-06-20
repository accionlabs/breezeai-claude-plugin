# Per-call inputs template

The skill renders this file (substitutes the `{{...}}` placeholders) and
passes the result as the `prompt` argument when invoking
`subagent_type: "breeze:spa-flow-structuring-agent"`.

The agent's full methodology — phases, rules, schema, self-check — lives
in `agents/spa-flow-structuring-agent.md` (installed when the plugin is
installed). This template only carries the per-call variable inputs.

---

PERSONA:               {{persona}}
ENTRY_POINT:
  route:               {{route}}
  kind:                {{kind}}
  title:               {{title}}
SEED_FILE:             {{seed_file_absolute_path}}
REPO:
  name:                {{repo_name}}
  root:                {{repo_root_absolute_path}}
PROJECT_UUID:          {{project_uuid}}
PROJECT_NAME:          {{project_name}}
LLM_PLATFORM:          {{llm_platform}}
OUTPUT_PATH:           {{output_path}}
API_BASE:              {{api_base}}
API_KEY:               {{api_key}}
CODE_ONTOLOGY_ID:      {{code_ontology_id}}
INDEXED_REPO_NAME:     {{indexed_repo_name}}

EXISTING_NEIGHBORHOOD:
{{existing_neighborhood_json}}

Begin Phase 1. Discover, enumerate, self-validate (Phase 6), write to OUTPUT_PATH (Phase 7), POST the upsert with the `api-key:` header (Phase 8), and return ONLY the `OK · …` / `FAIL_…` summary line per the agent's Phase 8 Step 4 spec.
