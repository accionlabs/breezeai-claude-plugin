# Breeze plugin — Claude Code preamble

Auto-loaded by Claude Code at the start of every session in a repo where this
plugin is installed. Central precondition for all skills under `skills/`. Skills
should NOT duplicate this — they defer to this file for project resolution and
auth handling.

## When a skill needs a project

Every Breeze skill that makes an MCP call is **project-bound**: it needs a
`projectUuid`. Resolve it using the flow below.

### Step 1: Derive from the prompt

Look for a project reference in the current invocation. Three forms are
accepted, in this order of preference:

- **`--project <value>` (or `--project=<value>`)** anywhere in `$ARGUMENTS`.
- **Bare UUID** matching `[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`
  anywhere in the prompt — use directly, no lookup needed.
- **Project name or substring** appearing in the prompt (e.g., *"for Lead
  Manager V2: ..."*, *"on OneBid: ..."*, *"... in the ETL & Harvestor
  project"*). Call `Call_List_Project_` and match against accessible project
  names (case-insensitive substring).

Then resolve:

- **Exactly one match** → use that UUID for this invocation only. Do NOT mutate
  `.breeze.json`. Strip the override tokens (`--project <value>` or the
  natural-language project phrase) from `$ARGUMENTS` before processing the rest
  of the prompt.
- **Multiple matches** → list them numbered, with names + UUIDs, and ask the
  user to pick one. Wait for the choice before continuing.
- **Zero matches / no project mentioned** → fall through to Step 2. Do **not**
  error — many prompts simply don't include a project hint.

This is the mechanism for cross-project parallel skill runs (different terminals
/ Claude sessions targeting different projects without re-linking
`.breeze.json`).

### Step 2: `.breeze.json` fallback

If Step 1 didn't resolve a project, read `.breeze.json` from the repo root:

- **Has `projectUuid`** → use it.
- **File missing OR `projectUuid` absent** → call `Call_List_Project_`, present
  the accessible projects numbered with names + UUIDs, and ask the user to pick
  one. Use that UUID for this invocation only — do NOT mutate `.breeze.json`. To
  persist the choice, the user should follow up with
  `/breeze:project use <name|uuid>` (or run `/breeze:project setup`).

### Step 3: Announce the active project

Begin the response with one line so the user can verify scope at a glance:

    Project: <name> (<uuid>)

## Persistent project mapping

`.breeze.json` is mutated ONLY by these skill modes:

- `/breeze:project setup` — initial link (or full bootstrap).
- `/breeze:project use <name|uuid>` — switch the persistent default.
- `/breeze:project create <name>` — create a new project and link it.

A successful `--project` override, bare UUID, or natural-language hint applies to
that invocation only; it does not change `.breeze.json`. For cross-project
queries *within* a single invocation, pass the resolved `uuid` directly to each
MCP tool call rather than rewriting `.breeze.json`.

## Auth (Breeze MCP)

MCP tool calls authenticate via Keycloak SSO, handled by Claude Code at sign-in.
Tokens last roughly 7 days from the last successful handshake.

If a Breeze MCP tool call fails with a 401 / unauthenticated error (including
the very first call when the session has never been authenticated), stop and
tell the user:

> *"Breeze MCP server requires authentication. Please open this URL in your
> browser to authorize..."*

Claude Code typically surfaces the actual login URL automatically when an MCP
server needs auth. If it doesn't appear in the user's terminal, escalate via
`/breeze:project auth` to trigger the handshake explicitly.

The `apiKey` in `.breeze.json` is **not** used for MCP tool calls. It is only
for non-MCP consumers:

- the `breeze-code-ontology-generator` CLI run by `/breeze:onboard-repository`
  in **automatic upload** mode,
- the REST `/functional-graph/v2/upsert` path used by
  `/breeze:generate-functional-from-ui` (its flow-structuring sub-agent POSTs
  with an `api-key:` header),
- the retired `/breeze:deprecated-cluster-pipeline` (resume of historical runs).

(Other functional-graph writers — `generate-functional-from-backend` and
`update-functional-graph` — write via MCP tools and need no key.)

These skills prompt for the key on-demand and point the user at
`<uiBaseUrl>/mcp/generate/key`. MCP-only and manual-upload workflows never need
a key.

## Service URLs

All Breeze service URLs resolve in this order:

1. Per-project override in `.breeze.json` (`uiBaseUrl`, `apiBase`).
2. Plugin-wide defaults in `breeze.config.json` at the plugin root
   (`uiBaseUrl: https://ai.accionbreeze.com`,
   `apiBase: https://isometric-backend.accionbreeze.com`).
3. Hardcoded fallback in the individual SKILL.md (last resort).

To repoint every skill at a different Breeze deployment, edit
`breeze.config.json` once.

## Skills that don't need a project

These skills are exempt from the resolution flow above — run them as requested:

| Skill / mode | Why exempt |
|---|---|
| `/breeze:project setup` | Creates `.breeze.json`. |
| `/breeze:project auth` | OAuth handshake only. |
| `/breeze:project list` | Lists accessible projects. |
| `/breeze:project create <name>` | Creates a new project and links it. |
| `/breeze:visual-to-text` | Reads a design (Figma / PDF / image) and writes local user stories — makes no Breeze MCP calls. |

All other skills are project-bound and follow Steps 1–3 above.
`/breeze:onboard-repository` needs a resolvable `projectUuid` but never probes
the graph — it follows the same flow.

## Notes

- Never print API keys or AWS credentials in output.
- When adding a new skill to `skills/`: if it makes any Breeze MCP call, it is
  project-bound by default — add a short `## Project` section that defers to this
  file rather than re-deriving the guard. If it genuinely doesn't need a project,
  add it to the exempt table above in the same commit.
