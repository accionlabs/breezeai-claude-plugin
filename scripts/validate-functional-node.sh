#!/bin/bash
INPUT=$(cat)

# Extract the label (Persona, Outcome, Scenario, Step, Action)
LABEL=$(echo "$INPUT" | grep -o '"label"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"[[:space:]]*$/\1/')

if [ -z "$LABEL" ]; then
  echo "BLOCKED: Missing 'label' field. Must be one of: Persona, Outcome, Scenario, Step, Action." >&2
  exit 2
fi

# Validate label is one of the allowed types
case "$LABEL" in
  Persona|Outcome|Scenario|Step|Action) ;;
  *)
    echo "BLOCKED: Invalid label '$LABEL'. Must be one of: Persona, Outcome, Scenario, Step, Action." >&2
    exit 2
    ;;
esac

# --- Persona validation ---
if [ "$LABEL" = "Persona" ]; then
  # Check for forbidden persona names
  PERSONA_NAME=$(echo "$INPUT" | grep -oi '"persona"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"[[:space:]]*$/\1/')
  FORBIDDEN="Developer|Engineer|Programmer|API|Service|Component|Module|Backend|Frontend|Database|Controller|Handler|Repository"
  if echo "$PERSONA_NAME" | grep -qiE "^($FORBIDDEN)$"; then
    echo "BLOCKED: Forbidden persona name '$PERSONA_NAME'. Use a human role (Admin, User, Manager) or System/External System instead. Never use technical identifiers." >&2
    exit 2
  fi
fi

# --- Outcome validation ---
if [ "$LABEL" = "Outcome" ]; then
  # Must have personaId
  if ! echo "$INPUT" | grep -q '"personaId"'; then
    echo "BLOCKED: Outcome requires 'personaId' (parent Persona ID)." >&2
    exit 2
  fi
  # Check for technical outcome names
  OUTCOME_NAME=$(echo "$INPUT" | grep -oi '"outcome"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"[[:space:]]*$/\1/')
  if echo "$OUTCOME_NAME" | grep -qiE "(Handle API|Process Database|Render Component|Execute Query)"; then
    echo "BLOCKED: Outcome '$OUTCOME_NAME' sounds technical. Use a business capability name instead (e.g., 'Manage Fund Allocations', 'Monitor Compliance Status')." >&2
    exit 2
  fi
fi

# --- Scenario validation ---
if [ "$LABEL" = "Scenario" ]; then
  # Must have outcomeId
  if ! echo "$INPUT" | grep -q '"outcomeId"'; then
    echo "BLOCKED: Scenario requires 'outcomeId' (parent Outcome ID)." >&2
    exit 2
  fi
  # Must have description
  if ! echo "$INPUT" | grep -q '"description"'; then
    echo "BLOCKED: Scenario requires a 'description' field." >&2
    exit 2
  fi
fi

# --- Step validation ---
if [ "$LABEL" = "Step" ]; then
  # Must have scenarioId
  if ! echo "$INPUT" | grep -q '"scenarioId"'; then
    echo "BLOCKED: Step requires 'scenarioId' (parent Scenario ID)." >&2
    exit 2
  fi
  # Must have step name
  if ! echo "$INPUT" | grep -q '"step"'; then
    echo "BLOCKED: Step requires a 'step' field (short verb phrase)." >&2
    exit 2
  fi
  # Must have description
  if ! echo "$INPUT" | grep -q '"description"'; then
    echo "BLOCKED: Step requires a 'description' field." >&2
    exit 2
  fi
fi

# --- Action validation ---
if [ "$LABEL" = "Action" ]; then
  # Must have stepId
  if ! echo "$INPUT" | grep -q '"stepId"'; then
    echo "BLOCKED: Action requires 'stepId' (parent Step ID)." >&2
    exit 2
  fi
  # Must have action name
  if ! echo "$INPUT" | grep -q '"action"'; then
    echo "BLOCKED: Action requires an 'action' field (specific interaction or operation)." >&2
    exit 2
  fi
  # Must have description
  if ! echo "$INPUT" | grep -q '"description"'; then
    echo "BLOCKED: Action requires a 'description' field." >&2
    exit 2
  fi
fi

exit 0
