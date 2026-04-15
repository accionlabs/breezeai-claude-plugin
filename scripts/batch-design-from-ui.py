#!/usr/bin/env python3
"""
Batch orchestration script for /breeze:generate-design-from-ui

Processes scenarios in batches via Claude Code CLI (`claude -p`),
avoiding the "shall I continue?" problem on large scenario sets.

State is persisted to disk between batches via:
  - existingcomponents.json  (component registry)
  - existingflows.json       (flow registry)
  - existingpages.json       (page registry)

Usage:
  python scripts/batch-design-from-ui.py [options]

Options:
  --batch-size N     Scenarios per batch (default: 20)
  --max-turns N      Max Claude Code turns per batch (default: 200)
  --ui-repo PATH     Path to frontend repo (overrides .breeze.json)
  --start-from N     Resume from batch N (0-indexed, default: 0)
  --dry-run          Print batches without executing
  --modality M       Modality to use (default: auto-detect)
"""

import subprocess
import json
import sys
import os
import argparse
import time
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
BREEZE_CONFIG = PLUGIN_DIR / ".breeze.json"
COMPONENTS_FILE = PLUGIN_DIR / "skills" / "generate-design-from-ui" / "existingcomponents.json"
FLOWS_FILE = PLUGIN_DIR / "skills" / "generate-design-from-ui" / "existingflows.json"
PAGES_FILE = PLUGIN_DIR / "skills" / "generate-design-from-ui" / "existingpages.json"
LOG_FILE = PLUGIN_DIR / "scripts" / "batch-design-from-ui.log"


def load_json(path: Path, default=None):
    """Load JSON file, return default if missing or invalid."""
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def registry_summary():
    """Get current registry counts for logging."""
    components = load_json(COMPONENTS_FILE, {"ATOM": {}, "MOLECULE": {}, "ORGANISM": {}, "TEMPLATE": {}})
    flows = load_json(FLOWS_FILE)
    pages = load_json(PAGES_FILE)

    comp_count = sum(len(v) for v in components.values())
    return {
        "components": comp_count,
        "flows": len(flows),
        "pages": len(pages),
    }


def log(msg: str):
    """Log to both stdout and log file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def build_prompt(batch_scenarios: list[dict], batch_num: int, total_batches: int, args) -> str:
    """Build the Claude Code prompt for a single batch."""

    scenario_list = "\n".join(
        f"  {i+1}. {s['name']} (ID: {s['id']})"
        for i, s in enumerate(batch_scenarios)
    )

    ui_repo_line = f'--ui-repo "{args.ui_repo}"' if args.ui_repo else ""
    modality_line = f"\nModality: {args.modality}" if args.modality else ""

    return f"""You are running batch {batch_num + 1} of {total_batches} for design graph generation.

Run /breeze:generate-design-from-ui {ui_repo_line}

IMPORTANT BATCH CONTEXT:
- Processing mode: auto (NO confirmation prompts, NO "shall I continue" — process all scenarios below without stopping)
- This is an automated batch run. Do NOT ask any questions. Do NOT pause between scenarios.
- The following registry files already exist on disk from prior batches — load them in Step 1:
  - existingcomponents.json (component registry)
  - existingflows.json (flow registry)
  - existingpages.json (page registry)
- After EVERY scenario, persist ALL three registries to disk (this is critical for cross-batch continuity)
{modality_line}

SCENARIOS TO PROCESS (this batch only):
{scenario_list}

Use scenario selection mode: Option 2 (Search & Generate) — search for each scenario by name from the list above, process them in order.

EXECUTION RULES:
- Process ALL {len(batch_scenarios)} scenarios above sequentially without stopping
- Do NOT ask for confirmation — auto mode is selected
- Do NOT skip flow discovery greps (Type A + Type B + page nav) for ANY scenario
- Produce the Flow Discovery Evidence Block for EVERY scenario
- Update and persist all registry files after EVERY scenario
- If a scenario fails, log the error and continue to the next one
- When all {len(batch_scenarios)} scenarios are done, output a JSON summary:
  {{"completed": [...scenario IDs...], "failed": [...], "registryCounts": {{"components": N, "flows": N, "pages": N}}}}
"""


def fetch_unprocessed_scenarios(args) -> list[dict]:
    """Fetch all unprocessed scenarios via a quick Claude Code call."""
    log("Fetching unprocessed scenarios from functional graph...")

    prompt = f"""Read .breeze.json and get the apiKey and projectUuid.
Then call Get_scenarios_by_uuid with uuid=<projectUuid>, isDesignGenerated="false", page="1", limit="200".
Also call Get_all_personas to identify non-human personas (System, External System).
For each non-human persona, call Get_all_outcomes_for_a_persona_id to get blocked outcome IDs.

Output ONLY a JSON object (no markdown, no explanation):
{{
  "scenarios": [
    {{"id": "uuid", "name": "scenario name", "outcomeId": "uuid"}},
    ...
  ],
  "blockedOutcomeIds": ["uuid", ...],
  "total": N
}}
"""
    result = subprocess.run(
        ["claude", "-p", prompt, "--max-turns", "20"],
        capture_output=True,
        text=True,
        cwd=str(PLUGIN_DIR),
    )

    if result.returncode != 0:
        log(f"ERROR fetching scenarios: {result.stderr}")
        sys.exit(1)

    # Extract JSON from output (may have surrounding text)
    output = result.stdout.strip()
    try:
        # Try to find JSON in the output
        start = output.index("{")
        end = output.rindex("}") + 1
        data = json.loads(output[start:end])
    except (ValueError, json.JSONDecodeError) as e:
        log(f"ERROR parsing scenario list: {e}")
        log(f"Raw output:\n{output}")
        sys.exit(1)

    blocked = set(data.get("blockedOutcomeIds", []))
    all_scenarios = data.get("scenarios", [])

    # Filter out non-human persona scenarios
    human_scenarios = [
        s for s in all_scenarios
        if s.get("outcomeId") not in blocked
    ]

    log(f"Found {len(all_scenarios)} total scenarios, {len(human_scenarios)} human-persona (filtered {len(all_scenarios) - len(human_scenarios)} system/external)")
    return human_scenarios


def run_batch(batch_scenarios: list[dict], batch_num: int, total_batches: int, args) -> dict:
    """Run a single batch via Claude Code CLI."""
    prompt = build_prompt(batch_scenarios, batch_num, total_batches, args)

    pre_stats = registry_summary()
    log(f"--- BATCH {batch_num + 1}/{total_batches} ---")
    log(f"Scenarios: {len(batch_scenarios)}")
    log(f"Pre-batch registries: {pre_stats}")

    if args.dry_run:
        log("[DRY RUN] Would execute Claude Code with prompt:")
        log(prompt[:500] + "...")
        return {"completed": [], "failed": [s["id"] for s in batch_scenarios], "skipped": True}

    start_time = time.time()

    result = subprocess.run(
        ["claude", "-p", prompt, "--max-turns", str(args.max_turns)],
        capture_output=True,
        text=True,
        cwd=str(PLUGIN_DIR),
    )

    elapsed = time.time() - start_time
    log(f"Batch {batch_num + 1} finished in {elapsed:.0f}s (exit code: {result.returncode})")

    post_stats = registry_summary()
    log(f"Post-batch registries: {post_stats}")
    log(f"Delta: +{post_stats['components'] - pre_stats['components']} components, "
        f"+{post_stats['flows'] - pre_stats['flows']} flows, "
        f"+{post_stats['pages'] - pre_stats['pages']} pages")

    # Try to parse batch summary from output
    batch_result = {
        "completed": [],
        "failed": [],
        "exit_code": result.returncode,
        "elapsed_seconds": elapsed,
        "registry_delta": {
            k: post_stats[k] - pre_stats[k] for k in post_stats
        },
    }

    if result.returncode != 0:
        log(f"WARNING: Batch exited with code {result.returncode}")
        log(f"stderr: {result.stderr[:500]}")

    # Try to extract the JSON summary from output
    try:
        output = result.stdout.strip()
        start = output.rindex('{"completed"')
        data = json.loads(output[start:])
        batch_result["completed"] = data.get("completed", [])
        batch_result["failed"] = data.get("failed", [])
    except (ValueError, json.JSONDecodeError):
        # If no parseable summary, infer from registry delta
        if post_stats["flows"] > pre_stats["flows"]:
            log("Could not parse batch summary, but registry grew — assuming partial success")
        else:
            log("Could not parse batch summary and no registry growth — batch may have failed")

    return batch_result


def main():
    parser = argparse.ArgumentParser(description="Batch orchestration for generate-design-from-ui")
    parser.add_argument("--batch-size", type=int, default=20, help="Scenarios per batch (default: 20)")
    parser.add_argument("--max-turns", type=int, default=200, help="Max Claude Code turns per batch (default: 200)")
    parser.add_argument("--ui-repo", type=str, default=None, help="Path to frontend repo")
    parser.add_argument("--start-from", type=int, default=0, help="Resume from batch N (0-indexed)")
    parser.add_argument("--dry-run", action="store_true", help="Print batches without executing")
    parser.add_argument("--modality", type=str, default=None, help="Modality (web/mobile/desktop)")
    args = parser.parse_args()

    log("=" * 60)
    log("BATCH DESIGN-FROM-UI ORCHESTRATION")
    log(f"Config: batch_size={args.batch_size}, max_turns={args.max_turns}")
    log(f"Plugin dir: {PLUGIN_DIR}")
    log("=" * 60)

    # Verify .breeze.json exists
    if not BREEZE_CONFIG.exists():
        log("ERROR: .breeze.json not found. Run /breeze:setup-project first.")
        sys.exit(1)

    # Fetch unprocessed scenarios
    scenarios = fetch_unprocessed_scenarios(args)
    if not scenarios:
        log("No unprocessed scenarios found. Nothing to do.")
        return

    # Create batches
    batches = [
        scenarios[i:i + args.batch_size]
        for i in range(0, len(scenarios), args.batch_size)
    ]
    log(f"Created {len(batches)} batches of up to {args.batch_size} scenarios each")

    # Process batches
    all_completed = []
    all_failed = []

    for i, batch in enumerate(batches):
        if i < args.start_from:
            log(f"Skipping batch {i + 1} (--start-from {args.start_from})")
            continue

        result = run_batch(batch, i, len(batches), args)
        all_completed.extend(result.get("completed", []))
        all_failed.extend(result.get("failed", []))

        log(f"Running total: {len(all_completed)} completed, {len(all_failed)} failed")

        # Brief pause between batches to avoid rate limits
        if i < len(batches) - 1:
            log("Waiting 5s before next batch...")
            time.sleep(5)

    # Final summary
    log("=" * 60)
    log("FINAL SUMMARY")
    log(f"Total scenarios: {len(scenarios)}")
    log(f"Completed: {len(all_completed)}")
    log(f"Failed: {len(all_failed)}")
    final_stats = registry_summary()
    log(f"Final registries: {final_stats}")
    log("=" * 60)

    if all_failed:
        log(f"Failed scenario IDs: {all_failed}")
        log("Re-run with --start-from to retry failed batches, or run the skill manually for individual scenarios.")


if __name__ == "__main__":
    main()
