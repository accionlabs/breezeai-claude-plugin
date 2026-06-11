---
name: setup-project
description: >
  Backward-compatible alias for `/breeze:project setup`. Performs the
  full Breeze workspace bootstrap: MCP auth + project link/create +
  ontology readiness check + status report. Prefer `/breeze:project setup`
  going forward — this skill remains as a stable entry point for muscle
  memory and existing documentation. Use when: first time setup, "init
  breeze", "setup breeze", or when any Breeze tool fails with
  authorization errors.
---

## Scope

This skill is a backward-compatible alias. When invoked, execute the same
bootstrap flow that `/breeze:project setup` documents. The behavior is
intentionally identical.

The canonical home for this flow (and all other project-management operations —
`show`, `list`, `use`, `create`, `auth`, `status`) is `/breeze:project`. New
documentation and prompts should point users at `/breeze:project setup`; this
skill remains so the older command keeps working.

It links the project and reports readiness only. It does **NOT** upload repos or
documents:

| You want to… | Use this skill instead |
|---|---|
| Upload a source repo into the code graph | `/breeze:onboard-repository` |
| Ingest a PDF / markdown / text document | `/breeze:analyze-functional` |
| Convert a UI design visual into user stories | `/breeze:visual-to-text` |

**No API key is collected here.** MCP access is authenticated via Keycloak OAuth
— Claude Code handles sign-in automatically. Skills that hit the non-MCP REST/CLI
surface prompt for the key on-demand. See `CLAUDE.md`.

## Behavior — full bootstrap

Run these phases in order. (For the canonical / future-proof version, see Mode:
setup in `/breeze:project`'s SKILL.md — execute it identically.)

### Phase 1 — MCP Authentication

1. Attempt a lightweight MCP call (`Call_List_Project_` with `limit: 1`) to test
   the current session.
2. If it succeeds → continue to Phase 2.
3. If it fails with an auth error: trigger the Breeze MCP authentication flow
   (call the server's `authenticate` tool if exposed, else Claude Code surfaces
   the login URL). Share the URL, ask the user to complete sign-in, then finalize
   (`complete_authentication` if exposed) and retry the lightweight call. If
   verification still fails, ask the user to retry or check network/SSO and stop.

### Phase 2 — Project Linking

Read `.breeze.json`. Remember whether `projectUuid` was already present.

**No existing `projectUuid` (first-time link)** — ask:

    Would you like to:
    1. Select an existing project
    2. Create a new project

- **Select existing**: Call `Call_List_Project_`, display the list (name +
  UUID), let the user pick. Save the chosen UUID to `.breeze.json` (preserving
  any other keys).
- **Create new**: Ask for project name and optional description. Call
  `Call_Create_Project_`. Save the returned `projectUuid` to `.breeze.json`
  (preserving any other keys).

**Existing `projectUuid` (confirm / switch)** —

1. Call `Call_Get_Project_Details_` with the existing UUID to identify the
   current project.
2. Ask whether to keep / switch / create new.
3. Route: **Keep** → Phase 3. **Switch** → "select existing" sub-flow, overwrite
   `projectUuid`. **Create new** → "create new" sub-flow, overwrite
   `projectUuid`.

If the existing UUID returns empty / 404 from `Call_Get_Project_Details_`, treat
the link as gone and fall through to the first-time link prompt above.

### Phase 3 — Ontology Check + Status + Next Steps

1. **Ontology readiness check** (report only, no uploads): `Call_List_Repositories_`
   for code-graph repo count; `Get_all_personas` for functional-graph counts.
2. Call `Call_Get_Project_Details_` with the active UUID and render the metadata
   report (name, uuid, status, version, author, description).
3. End with the next-step guidance from `/breeze:project` Mode: setup (brownfield
   → onboard-repository / generate-functional-from-*; greenfield → visual-to-text
   / analyze-functional; populated → search / impact-analysis / generate-spec).
   Remind the user that analysis skills also accept `--project <name|uuid>` for a
   one-shot override.

## See also

- `/breeze:project setup` — canonical home for this exact flow
- `/breeze:project use <name|uuid>` — fast mid-session switch
- `/breeze:project auth` — re-authenticate without changing the link
- `/breeze:project list` — view all accessible projects
