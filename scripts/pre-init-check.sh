#!/bin/bash
INPUT=$(cat)

# Extract skill name without jq
SKILL=$(echo "$INPUT" | grep -o '"skill"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

# Skip init skill — it doesn't need .breeze.json
case "$SKILL" in
  init|breeze:init) exit 0 ;;
esac

# Only act on breeze skills
case "$SKILL" in
  search|breeze:search|update-graph|breeze:update-graph|requirements|breeze:requirements|design|breeze:design|architecture|breeze:architecture|codegen|breeze:codegen) ;;
  *) exit 0 ;;
esac

# Check .breeze.json exists
if [ ! -f ".breeze.json" ]; then
  echo "BLOCKED: .breeze.json not found. Run /breeze:init first to set up your Breeze workspace." >&2
  exit 2
fi

# Check apiKey exists
if ! grep -q '"apiKey"' .breeze.json; then
  echo "BLOCKED: .breeze.json is missing 'apiKey'. Run /breeze:init to complete setup." >&2
  exit 2
fi

# Check projectUuid exists
if ! grep -q '"projectUuid"' .breeze.json; then
  echo "BLOCKED: .breeze.json is missing 'projectUuid'. Run /breeze:init to link a project." >&2
  exit 2
fi

exit 0
