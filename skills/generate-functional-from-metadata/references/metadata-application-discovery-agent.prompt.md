# Per-call inputs template — P3 discovery agent

The skill renders this file (substitutes `{{...}}`) and passes the result as the `prompt`
argument when invoking `subagent_type: "breeze:metadata-application-discovery-agent"`, ONCE per run.

The agent's full methodology — phases, module classification, applications.json schema,
summary-line spec — lives in `agents/metadata-application-discovery-agent.md`. This template only
carries per-call variable inputs.

---

ROOT:                  {{root_absolute_path}}
PROJECT_UUID:          {{project_uuid}}
PROJECT_NAME:          {{project_name}}
OUTPUT_PATH:           {{output_path}}
RULES_PATH:            {{rules_path}}
EXISTING_PERSONAS:     {{existing_personas_json}}

Read the P3 mapping rules at RULES_PATH first.

Inventory every P3 application (parse every `MAPL(*)`; also `MAAP`/`MASC` for batch) under
ROOT, classify each module, resolve candidate personas, and write the full inventory +
checkpoint to OUTPUT_PATH. If OUTPUT_PATH already exists, do NOT overwrite — return the
`OK_RESUME · …` line. Otherwise return ONLY the `OK · …` / `FAIL_…` summary line per the
agent's Phase 5 spec.
