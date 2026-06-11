---
name: project
description: >
  Full Breeze project management: show, list, switch (use), create,
  auth, status, and full bootstrap (setup). Use for: "which project
  am I on", "list projects", "switch project", "set project", "create
  project", mid-session project changes, MCP re-authentication, and
  first-time workspace bootstrap. This is the canonical home for all
  project-management operations.
---

## Guard

Most modes here require an authenticated Breeze MCP session. The `auth` and
`setup` modes handle the auth handshake themselves; all other modes (`show`,
`list`, `use`, `create`, `status`) assume an active session and surface a clear
error pointing at `/breeze:project auth` if they hit a 401. Project resolution
and auth rules are defined centrally in `CLAUDE.md` at the plugin root.

---

## Mode dispatch

Parse `$ARGUMENTS` and dispatch:

| `$ARGUMENTS` shape | Mode |
|---|---|
| empty / whitespace | **show** — print active project + summary |
| `list` (case-insensitive) | **list** — print all accessible projects |
| `use <value>` | **switch** — resolve `<value>` and update `.breeze.json` |
| `auth` (case-insensitive) | **auth** — MCP authentication handshake |
| `create <name> [--description "..."]` | **create** — create a new project and link |
| `status` (case-insensitive) | **status** — full metadata report (alias of `show`) |
| `setup` (case-insensitive) | **setup** — full bootstrap (auth + link/create + ontology check + status) |
| anything else | print the usage hint and stop |

Usage hint (for unknown args):

    Usage:
      /breeze:project                              show currently active project
      /breeze:project list                         list all accessible projects
      /breeze:project use <name|uuid>              switch and persist
      /breeze:project create <name> [--desc "..."] create a new project and link
      /breeze:project auth                         re-authenticate the MCP session
      /breeze:project status                       full metadata report on active project
      /breeze:project setup                        full bootstrap (auth + link + ontology check)

---

## Cross-project queries within an invocation

If a request requires data from a project *other than* the one currently linked
in `.breeze.json` — e.g., comparing V1 and V2 in one analysis, or
cross-referencing a sister project — pass the target `uuid` directly to each MCP
tool call. Do NOT silently mutate `.breeze.json` to switch projects
mid-invocation. Only the `use`, `create`, and `setup` modes of this skill (when
the user explicitly invokes them) may modify `.breeze.json`.

---

## Mode: show (no args)

1. Read `.breeze.json`. If missing or `projectUuid` absent, respond:

       No project currently linked. Options:
       - /breeze:project setup    — initial link + MCP auth
       - /breeze:project list     — see what's available
       - /breeze:project use <X>  — link to an existing project

   Then stop.

2. Call `Call_Get_Project_Details_` with the existing `projectUuid`.

3. Render:

       Active project: <name>  (<uuid>)
       Status:         <status>
       Version:        <version>
       Author:         <author.firstName> <author.lastName> <author.email>
       Description:    <metadata.description or "—">

4. Short hint at the bottom:

       Switch with:    /breeze:project use <name-or-uuid>
       See all:        /breeze:project list

If `Call_Get_Project_Details_` returns empty / 404, treat the previously linked
project as gone: tell the user the link is stale and offer `/breeze:project
list` + `/breeze:project use <name>` (or `/breeze:project setup` to start
fresh).

---

## Mode: list

1. Call `Call_List_Project_` (limit high enough to capture all — start with 50,
   paginate if `total` exceeds).

2. Read `.breeze.json` to get the current `projectUuid` (if any).

3. Render as a monospace table:

       UUID                                     Name                Status    Active
       ─────────────────────────────────────    ───────────────     ──────    ──────
       4f803786-60d9-4f66-b719-c51a84a7df40     Lead Manager V1     active    ←
       69944bfe-366d-4bc7-8586-4e0b04901e24     Lead Manager V2     active
       bf6cfa91-9495-41ce-93d7-36d45ddeaae1     ETL & Harvestor     active

   Mark the row whose UUID matches `.breeze.json`'s `projectUuid` with an `←`
   arrow in the Active column. If `.breeze.json` is missing or empty, omit the
   Active column entirely and add a note: "No project currently linked."

4. Footer:

       Switch with:  /breeze:project use <name-or-uuid>

---

## Mode: switch (`use <value>`)

1. Extract `<value>` from `$ARGUMENTS` (everything after `use`).

2. Call `Call_List_Project_` and resolve `<value>`:

   - **Exact UUID match** → one match, proceed.
   - **Exact name match (case-insensitive)** → one match, proceed.
   - **Unambiguous substring of name (case-insensitive)** → one match, proceed.
   - **Zero matches** → stop. List available projects (name + UUID). Do NOT
     mutate `.breeze.json`.
   - **Multiple matches** → stop. Show all matches and ask the user to
     disambiguate by UUID. Do NOT mutate.

3. Read `.breeze.json` (may not exist).

   - If it exists: preserve every other key; update only `projectUuid`.
   - If it does not exist: create it with `{"projectUuid": "<uuid>"}`.

4. Render confirmation:

       Switched to: <name>  (<uuid>)
       Previously:  <previous name or "(none)">
       .breeze.json updated.

5. Footer:

       Next: any /breeze:* skill will now use this project.
       For a one-shot override that does NOT touch .breeze.json, use
       --project <name> on any individual skill invocation.

---

## Mode: auth

The Breeze MCP server handles authentication via a browser handshake; no API key
is stored locally for MCP access.

1. Attempt a lightweight MCP call (e.g. `Call_List_Project_` with `limit: 1`) to
   test the current session.

2. If it succeeds → respond:

       MCP session is already authenticated.

   Then stop.

3. If it fails with an auth error, run the handshake:

   a. Trigger the Breeze MCP authentication flow. If the Breeze MCP server
      exposes an `authenticate` tool, call it to obtain the authorization URL;
      otherwise Claude Code surfaces the login URL automatically when the server
      reports it needs auth.

   b. Share the URL with the user and ask them to complete sign-in in their
      browser.

   c. Once they confirm completion, finalize the session (call the MCP server's
      `complete_authentication` tool if it exposes one).

   d. Retry the lightweight call to verify the session is now live.

   e. Render:

          MCP session re-authenticated.

      Then stop.

   If verification still fails after this flow, ask the user to retry
   `/breeze:project auth` or check their network / SSO.

---

## Mode: create (`create <name> [--description "..."]`)

1. Parse `<name>` and optional `--description "..."` from `$ARGUMENTS`
   (everything after `create`).

2. Require `<name>` to be non-empty. If absent, stop with the usage hint.

3. Confirm with the user before creating:

       Create new project '<name>' with description '<desc-or-(none)>'?
       (yes/no)

   On `no`, stop without creating.

4. Call `Call_Create_Project_` with the name and description. Capture the
   returned `projectUuid`.

5. Read `.breeze.json` (may not exist).

   - If it exists: preserve every other key; update only `projectUuid` to the
     new project's UUID.
   - If it does not exist: create it with `{"projectUuid": "<uuid>"}`.

6. Render confirmation:

       Created project: <name>  (<uuid>)
       .breeze.json updated.

7. Footer:

       Next: any /breeze:* skill will now use this project.

---

## Mode: status

Alias of `show` (no args). Same metadata report. Call this when you want to be
explicit about asking for project status rather than relying on the no-args
default.

---

## Mode: setup

Full workspace bootstrap. Performs auth → link/create → ontology check → status
in one flow. This is the canonical home for first-time workspace bootstrap. It
links the project and reports readiness — it does **not** upload repos
or documents (use `/breeze:onboard-repository` for code, and
`/breeze:analyze-functional` / `/breeze:visual-to-text` for documents and
designs).

1. **Auth check.** Run the steps in Mode: auth. If auth fails permanently, stop.

2. **Read `.breeze.json`** and remember whether `projectUuid` was already
   present.

3. **No existing `projectUuid` (first-time link)** — ask:

       Would you like to:
       1. Select an existing project
       2. Create a new project

   - On 1 → run "select existing" sub-flow below.
   - On 2 → run "create new" sub-flow below.

4. **Existing `projectUuid` (confirm / switch)** —

   a. Call `Call_Get_Project_Details_` with the existing UUID to identify the
      current project.

   b. Ask:

          You're currently linked to **{currentProject.name}**
          (`{currentProject.uuid}`). Would you like to:
          1. Keep this project (just show its status)
          2. Switch to a different existing project
          3. Create a new project

   c. Route on the answer:

      - **Keep** → continue to Step 6 (ontology check).
      - **Switch** → run "select existing" sub-flow below, then overwrite
        `projectUuid` in `.breeze.json`.
      - **Create new** → run "create new" sub-flow below, then overwrite
        `projectUuid` in `.breeze.json`.

   If `Call_Get_Project_Details_` returns empty / 404 for the existing UUID,
   treat the link as gone and fall through to the first-time prompt in step 3.

5. **Sub-flows:**

   - **Select existing:** Call `Call_List_Project_`, display the project list
     (name + UUID), user selects one, save its UUID to `.breeze.json`
     (preserving other keys).

   - **Create new:** Ask for project name and optional description. Call
     `Call_Create_Project_`. Save the returned `projectUuid` to `.breeze.json`
     (preserving other keys).

6. **Ontology readiness check.** Report plainly what the linked project already
   contains, so the user knows which pipeline step is next. Do NOT upload
   anything here.

   - **Code graph** — call `Call_List_Repositories_`. Report how many
     repositories are indexed (or "none indexed yet").
   - **Functional graph** — call `Get_all_personas` (and optionally
     `Call_Get_Project_Details_`). Report persona/outcome counts at a glance, or
     "empty".
   - **Design graph** — note present/absent if cheaply observable; otherwise
     skip.

7. **Status report** (same as Mode: show / Mode: status). Render the metadata
   report for the now-linked project.

8. **Next-step guidance** — tailor to what the ontology check found:

       Your project is linked. Next:

       Brownfield (existing code):
       - /breeze:onboard-repository <repo>          index each repo into the code graph (once per repo)
       - /breeze:generate-functional-from-ui  <fe>  User-persona functional graph
       - /breeze:generate-functional-from-backend <be>  System-persona functional graph
       - /breeze:validate-functional-graph          quality check
       - /breeze:generate-spec                       export a functional specification

       Greenfield (designs / docs, no code yet):
       - /breeze:visual-to-text                      Figma / PDF / images → user stories
       - /breeze:analyze-functional                  ingest requirement documents

       Already populated:
       - /breeze:search <question>                   explore the graph
       - /breeze:impact-analysis                     cross-layer blast radius

       Each analysis skill also accepts --project <name|uuid> for a
       one-shot, non-persistent override.

---

## Rules

- **Modes that write `.breeze.json`**: `use`, `create`, `setup` (when it ends up
  linking or creating). All other modes are pure reads.
- **Modes that touch auth**: `auth`, `setup`. All other modes assume an active
  session and surface a clear error pointing at `/breeze:project auth` if they
  hit 401.
- **No API key is collected here.** MCP access uses Keycloak OAuth. Skills that
  hit the non-MCP REST/CLI surface (`/breeze:onboard-repository` automatic mode,
  the v2 REST upsert path) prompt for the key on-demand. See `CLAUDE.md`.
- **This skill never probes individual graphs beyond the lightweight ontology
  readiness check in setup.** For graph exploration, use `/breeze:search`.
- **Per-invocation `--project` overrides on analysis skills are outside this
  skill's scope.** This skill manages the persisted active project via
  `.breeze.json`. Per-invocation overrides belong to `search`,
  `impact-analysis`, `generate-spec`, and the rest.
- **Never mutate `.breeze.json` outside `use` / `create` / `setup`.** For
  cross-project queries within an invocation, pass `uuid` directly to MCP tool
  calls instead of switching the active project.
- **When in doubt** between `setup` and `use`: use `setup` for first-time link
  or when you suspect auth might be broken; use `use` for a fast mid-session
  switch on an already-authenticated session.
