{{!--
  Per-call input renderer for breeze:app-backend-module-agent.
  The skill substitutes the {{...}} placeholders and passes the rendered text as the `prompt`
  argument of the Agent tool. Keep it short — the agent's system prompt carries the methodology.
--}}
Build ONE backend feature module of the service at `{{APP_DIR}}`.

FIRST read `{{APP_DIR}}/AGENT_GUIDE.md` in full, then skim the shared middleware, data store / models,
validation + error helpers, config, and the router-registry pattern so you use the REAL exports.

PROJECT_UUID (for MCP graph reads): `{{PROJECT_UUID}}`
YOUR FOLDER (create files ONLY here): `{{MODULE_FOLDER}}`
URL PREFIX YOU OWN (no other agent uses it): `{{ROUTE_PREFIX}}`

API CONTRACTS the matching UI module expects (implement these endpoints byte-for-byte):
{{CONTRACTS}}   {{!-- METHOD url — request DTO — response shape; from HAS_API. "(none captured — derive from actions)" if empty --}}

YOUR OUTCOMES (read EACH to the action level via Get_all_scenarios_for_a_outcome_id then
Get_all_steps_actions_for_a_scenario_id; every Action implies an endpoint / validation / persistence /
external call / branch / error path you must implement):
{{OUTCOMES}}   {{!-- one per line: "<outcome_id> — <name>" --}}

MODULE INTENT (the resource(s) + the operations to deliver, with role gating):
{{MODULE_BRIEF}}

Build route/controller + service + validation + data access (against the shared store) + DTO/types +
a test file (Scenario→describe, Step→it, Action→assertion). Self-register routes under the prefix via
the guide's router pattern — do NOT edit shared bootstrap files.

When done: `cd {{APP_DIR}} && npx tsc -b --noEmit 2>&1 | grep -i "{{MODULE_FOLDER}}" | head -40` and
fix YOUR errors only. Return a concise manifest: endpoints created (`METHOD {{ROUTE_PREFIX}}/...`) and
how each outcome (and its actions / side effects) is covered.
