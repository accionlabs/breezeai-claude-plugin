# Per-call inputs template

The skill renders this file (substitutes the `{{...}}` placeholders) and
passes the result as the `prompt` argument when invoking
`subagent_type: "breeze:design-from-ui-structuring-agent"`.

The agent's full methodology — phases, rules, self-check — lives in
`agents/design-from-ui-structuring-agent.md` (installed when the plugin
is installed). This template only carries the per-call variable inputs.

Each agent call processes ONE outcome (all its scenarios). Scenarios
within an outcome share target pages, so the agent reads UI files once
and processes all scenarios against that shared context.

---

OUTCOME:
  id:                  {{outcome_id}}
  name:                {{outcome_name}}
  personaName:         {{persona_name}}
SCENARIOS:             {{scenarios_json}}
MODALITIES:            [{{modalities}}]
FRAMEWORK:             {{framework}}
UI_REPO:               {{repo_root_absolute_path}}
PROJECT_UUID:          {{project_uuid}}
OUTPUT_DIR:            {{output_dir}}
REFERENCES_PATH:       {{skill_references_path}}
COMPONENT_REGISTRY:    {{component_registry_path}}
MODE:                  {{mode}}

Begin Phase 0. Load component registry cache (if available), then
Phase 1: run grep discovery for all scenarios, Phase 2: read UI code
once, Phase 3: loop through each scenario (classify, build, validate,
upsert), Phase 4: write results manifest and return summary line.
