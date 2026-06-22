# Per-call inputs template — P3 flow-structuring agent

The skill renders this file (substitutes `{{...}}`) and passes the result as the `prompt`
argument when invoking `subagent_type: "breeze:metadata-flow-structuring-agent"`, ONCE per application.

The agent's full methodology — phases, mapping, field-coverage gate, schema, self-validate,
write-to-disk, dual upsert — lives in `agents/metadata-flow-structuring-agent.md`. This template only
carries per-call variable inputs. `PERSONA_HUMAN` / `PERSONA_SYSTEM` are resolved by discovery;
the agent uses them verbatim. If `PERSONA_HUMAN` is `null`, only the System half is built.

---

APP_ID:                {{app_id}}
REPO_NAME:             {{repo_name}}
REPO_PATH:             {{repo_path}}
FLAVOR:                {{flavor}}
PERSONA_HUMAN:         {{persona_human}}
PERSONA_SYSTEM:        {{persona_system}}
MAPL_PATH:             {{mapl_path}}
STEPS:                 {{steps_json}}
AJAX_ENDPOINTS:        {{ajax_endpoints_json}}
PROJECT_UUID:          {{project_uuid}}
PROJECT_NAME:          {{project_name}}
LLM_PLATFORM:          {{llm_platform}}
API_BASE:              {{api_base}}
API_KEY:               {{api_key}}
HUMAN_UPSERT_PATH:     {{human_upsert_path}}
SYSTEM_UPSERT_PATH:    {{system_upsert_path}}
OUTPUT_PATH_HUMAN:     {{output_path_human}}
OUTPUT_PATH_SYSTEM:    {{output_path_system}}
VALIDATORS_PATH:       {{validators_path}}
RULES_PATH:            {{rules_path}}

EXISTING_NEIGHBORHOOD:
{{existing_neighborhood_json}}

Begin Phase 1. Read the recipe + targets, enumerate 100% of declared fields (Phase 2), build the
two linked subtrees (Phase 3), self-validate both incl. field-coverage==1.0 (Phase 6), write to
the two OUTPUT_PATHs (Phase 7), POST both upserts with the `api-key:` header (Phase 8), and return
ONLY the `OK · …` / `FAIL_…` summary line per the agent's Return spec.
