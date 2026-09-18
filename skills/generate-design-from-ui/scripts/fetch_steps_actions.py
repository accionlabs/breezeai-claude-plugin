#!/usr/bin/env python3
"""Fetch scenarios (with steps and actions) for an outcome via the Breeze REST API.

Usage:
  python3 fetch_steps_actions.py <api_base> <api_key> <project_uuid> <outcome_id> [--page N] [--limit N]

Options:
  --page N    Page number (default: 1). Used for splitting large outcomes
              across multiple sub-agents — each agent gets one page.
  --limit N   Scenarios per page (default: 50).

Output (stdout): JSON object:
  {
    "scenarios": [
      {
        "id": "scenario-uuid",
        "name": "Scenario Name",
        "isDesignGenerated": false,
        "stepsActions": [
          {
            "stepId": "step-uuid",
            "stepName": "Step Name",
            "order": 1,
            "actions": [
              { "actionId": "action-uuid", "actionName": "Action Name" }
            ]
          }
        ]
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 50,
      "total": 120,
      "hasMore": true
    }
  }

Called by the design-from-ui sub-agent via Bash. Uses api-key auth,
no MCP or JWT required.

Flow:
  1. Fetch one page of scenarios for the outcome
  2. Filter out scenarios with isDesignGenerated=true
  3. For each remaining scenario, fetch the full step/action tree
  4. Output merged result with pagination info
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error


def api_get(api_base: str, api_key: str, url_path: str, params: dict) -> dict:
    """Make an authenticated GET request to the Breeze API."""
    query = urllib.parse.urlencode(params)
    url = f"{api_base}{url_path}?{query}"

    req = urllib.request.Request(url, method="GET")
    req.add_header("api-key", api_key)
    req.add_header("Accept", "application/json")

    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_scenarios_page(api_base: str, api_key: str, project_uuid: str,
                         outcome_id: str, page: int, limit: int) -> tuple:
    """Fetch one page of scenarios for an outcome. Returns (scenarios, total)."""
    body = api_get(api_base, api_key, f"/functional-graph/{project_uuid}/Scenario", {
        "filters[outcomeId][$eq]": outcome_id,
        "limit": str(limit),
        "page": str(page),
    })

    return body.get("data", []), body.get("total", 0)


def fetch_scenario_tree(api_base: str, api_key: str, project_uuid: str, scenario_id: str) -> dict:
    """Fetch the full Scenario -> Steps -> Actions tree."""
    try:
        body = api_get(api_base, api_key, f"/functional-graph/{project_uuid}/Scenario", {
            "filters[id][$eq]": scenario_id,
            "withChildren": "true",
        })
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": f"HTTP {e.code}: {e.reason}", "scenarioId": scenario_id}), file=sys.stderr)
        return None
    except Exception as e:
        print(json.dumps({"error": str(e), "scenarioId": scenario_id}), file=sys.stderr)
        return None

    data = body.get("data", [])
    if not data:
        print(json.dumps({"error": "Scenario not found or empty", "scenarioId": scenario_id}), file=sys.stderr)
        return None

    return data[0]


def parse_scenario_tree(raw: dict) -> list:
    """Parse the raw scenario tree into the stepsActions format."""
    steps_actions = []

    for order, step_node in enumerate(raw.get("children", []), start=1):
        step_id = step_node.get("id", "")
        step_name = step_node.get("step", step_node.get("name", ""))

        actions = []
        for action_node in step_node.get("children", []):
            action_id = action_node.get("id", "")
            action_name = action_node.get("action", action_node.get("name", ""))
            actions.append({
                "actionId": action_id,
                "actionName": action_name,
            })

        steps_actions.append({
            "stepId": step_id,
            "stepName": step_name,
            "order": order,
            "actions": actions,
        })

    return steps_actions


def parse_args(args: list) -> tuple:
    """Parse command-line args. Returns (api_base, api_key, project_uuid, outcome_id, page, limit)."""
    if len(args) < 5:
        print("Usage: fetch_steps_actions.py <api_base> <api_key> <project_uuid> <outcome_id> [--page N] [--limit N]",
              file=sys.stderr)
        sys.exit(1)

    api_base = args[1].rstrip("/")
    api_key = args[2]
    project_uuid = args[3]
    outcome_id = args[4]
    page = 1
    limit = 50

    i = 5
    while i < len(args):
        if args[i] == "--page" and i + 1 < len(args):
            page = int(args[i + 1])
            i += 2
        elif args[i] == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
            i += 2
        else:
            i += 1

    return api_base, api_key, project_uuid, outcome_id, page, limit


def main():
    api_base, api_key, project_uuid, outcome_id, page, limit = parse_args(sys.argv)

    # Step 1: Fetch one page of scenarios for this outcome
    scenarios, total = fetch_scenarios_page(api_base, api_key, project_uuid, outcome_id, page, limit)

    # Step 2: Filter out already-processed scenarios
    pending = [s for s in scenarios if not s.get("isDesignGenerated", False)]

    # Step 3: For each pending scenario, fetch steps/actions
    results = []
    for scenario in pending:
        sid = scenario.get("id", "")
        sname = scenario.get("scenario", scenario.get("name", ""))

        tree = fetch_scenario_tree(api_base, api_key, project_uuid, sid)
        if tree:
            steps_actions = parse_scenario_tree(tree)
        else:
            steps_actions = []

        results.append({
            "id": sid,
            "name": sname,
            "isDesignGenerated": False,
            "stepsActions": steps_actions,
        })

    # Step 4: Output with pagination info
    has_more = (page * limit) < total
    output = {
        "scenarios": results,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "hasMore": has_more,
        },
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
