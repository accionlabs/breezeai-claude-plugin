#!/bin/bash
INPUT=$(cat)

echo "[breeze-hook] pre-init-check triggered" >&2

# Extract skill name without jq
SKILL=$(echo "$INPUT" | grep -o '"skill"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

echo "[breeze-hook] SKILL: $SKILL" >&2

# Skip if not a breeze skill (no skill name or not from this plugin)
[ -z "$SKILL" ] && exit 0

# Skip init — it doesn't need .breeze.json
case "$SKILL" in
  init|breeze:init) exit 0 ;;
esac

# Strip "breeze:" prefix if present
SKILL_NAME="${SKILL#breeze:}"

# Check if this skill exists in our plugin's skills/ directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -d "$SCRIPT_DIR/skills/$SKILL_NAME" ]; then
  # Not our plugin's skill, ignore
  exit 0
fi

# It's a breeze skill — check .breeze.json
if [ ! -f ".breeze.json" ]; then
  echo "BLOCKED: .breeze.json not found. Run /breeze:init first to set up your Breeze workspace." >&2
  exit 2
fi

if ! grep -q '"apiKey"' .breeze.json; then
  echo "BLOCKED: .breeze.json is missing 'apiKey'. Run /breeze:init to complete setup." >&2
  exit 2
fi

if ! grep -q '"projectUuid"' .breeze.json; then
  echo "BLOCKED: .breeze.json is missing 'projectUuid'. Run /breeze:init to link a project." >&2
  exit 2
fi

exit 0
