# Per-call inputs template — metadata flow-structuring agent

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
UNDECLARED_ENTRY_POINTS: {{undeclared_entry_points_json}}
SHARED_FRAMEWORK_BRIEF:
{{shared_framework_brief}}
PROJECT_UUID:          {{project_uuid}}
PROJECT_NAME:          {{project_name}}
LLM_PLATFORM:          {{llm_platform}}
API_BASE:              {{api_base}}
API_KEY_FILE:          {{api_key_file}}   # path to JSON holding `apiKey` — read it at POST time; never inline the literal
HUMAN_UPSERT_PATH:     {{human_upsert_path}}
SYSTEM_UPSERT_PATH:    {{system_upsert_path}}
OUTPUT_PATH_HUMAN:     {{output_path_human}}
OUTPUT_PATH_SYSTEM:    {{output_path_system}}
VALIDATORS_PATH:       {{validators_path}}
SHARED_FUNCTIONAL_PATH: {{shared_functional_path}}
RULES_PATH:            {{rules_path}}

# (no EXISTING_NEIGHBORHOOD — the agent builds its own persona-scoped dedup read-back from the live graph)

Begin Phase 1. Read the recipe + targets, enumerate 100% of declared fields (Phase 2), build the
two linked subtrees (Phase 3), self-validate both incl. field-coverage==1.0 (Phase 6), write to
the two OUTPUT_PATHs (Phase 7), POST both upserts with the `api-key:` header (Phase 8), and return
ONLY the `OK · …` / `FAIL_…` summary line per the agent's Return spec.
