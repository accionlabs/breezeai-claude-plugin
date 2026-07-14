{{!--
  Per-call input renderer for breeze:app-ui-module-agent.
  The skill substitutes the {{...}} placeholders and passes the rendered text as the `prompt`
  argument of the Agent tool. Keep it short — the agent's system prompt carries the methodology.
--}}
Build ONE frontend feature module of the app at `{{APP_DIR}}`.

FIRST read `{{APP_DIR}}/AGENT_GUIDE.md` in full, then skim the shared design-system barrel, icon set,
data layer, and the `AppRoute` route-registry type so you use the REAL exported signatures.

PROJECT_UUID (for MCP graph reads): `{{PROJECT_UUID}}`
YOUR FOLDER (create files ONLY here): `{{MODULE_FOLDER}}`
YOUR ROUTES FILE: `{{MODULE_FOLDER}}/routes.tsx` exporting `export const routes: AppRoute[]`.

ROUTES YOU OWN (no other agent uses these):
{{ROUTES_OWNED}}

SIDEBAR NAV (add `nav` ONLY to these routes, exactly as given):
{{NAV_SPEC}}

CROSS-LINKS (owned by other modules — `<Link>`/navigate to them, do NOT build them):
{{CROSS_LINKS}}

YOUR OUTCOMES (read EACH to the action level via Get_all_scenarios_for_a_outcome_id then
Get_all_steps_actions_for_a_scenario_id; every Action = a UI behaviour you must build):
{{OUTCOMES}}   {{!-- one per line: "<outcome_id> — <name>  → route hint" --}}

MODULE INTENT (what this area is + the key pages/flows to deliver):
{{MODULE_BRIEF}}

When done: `cd {{APP_DIR}} && npx tsc -b --noEmit 2>&1 | grep -i "{{MODULE_FOLDER}}" | head -40` and
fix YOUR errors only (ignore sibling-folder errors from other in-flight agents). Return a concise
manifest: routes created (path + nav) and how each outcome (and its actions) is covered.
