# Per-call inputs template

The skill renders this file (substitutes the `{{...}}` placeholders) and
passes the result as the `prompt` argument when invoking
`subagent_type: "breeze:design-from-ui-structuring-agent"`.

The agent's full methodology — phases, rules, self-check — lives in
`agents/design-from-ui-structuring-agent.md` (installed when the plugin
is installed). This template only carries the per-call variable inputs.

Each agent call processes ONE outcome (one page of its scenarios).
Scenarios within an outcome share target pages, so the agent reads UI
files once and processes all scenarios against that shared context.

---

OUTCOME:
  id:                  {{outcome_id}}
  name:                {{outcome_name}}
  personaName:         {{persona_name}}
  personaId:           {{persona_id}}
  platform:            {{platform}}
MODALITIES:            [{{modalities}}]
FRAMEWORK:             {{framework}}
UI_REPO:               {{repo_root_absolute_path}}
PROJECT_UUID:          {{project_uuid}}
API_BASE:              {{api_base}}
API_KEY:               {{api_key}}
SCRIPTS_PATH:          {{scripts_path}}
OUTPUT_DIR:            {{output_dir}}
REFERENCES_PATH:       {{skill_references_path}}
COMPONENT_REGISTRY:    {{component_registry_path}}
PAGE_REGISTRY:         {{page_registry_path}}
APP_SUFFIX:            {{app_suffix}}
PLATFORM_ID:           {{platform_id}}
PAGE:                  {{page}}
MODE:                  {{mode}}

Begin Phase 0. Load component registry cache (if available), then
Phase 0b: fetch scenarios and steps/actions by running
`python3 SCRIPTS_PATH/fetch_steps_actions.py API_BASE API_KEY PROJECT_UUID OUTCOME_ID --page PAGE --limit 50`
via Bash (CRITICAL — this fetches your page of unprocessed scenarios
with their stepIds and actionIds. Without this, the entire run is
useless),
Phase 1: run grep discovery (use step/action names to drive keyword
matching), Phase 2: read UI code once, Phase 3: loop through each
scenario (classify, build payload with stepIds/actionIds, validate,
upsert), Phase 4: write outcome file and return summary line.
