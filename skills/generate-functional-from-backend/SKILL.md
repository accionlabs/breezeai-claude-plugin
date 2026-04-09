---
name: generate-functional-from-backend
description: >
  Generate System-persona functional graph from a backend repo.
  Entry points are REST routes and GraphQL resolvers.
  Use when: generate functional from backend, backend to functional,
  backend functional pass.
argument-hint: "[repo-path]"
---

## What this skill does

Transforms a backend repo into the **System / External System**
half of the functional graph (Persona > Outcome > Scenario > Step >
Action), with API calls captured structurally in `action.apis[]`.

```
generate-functional-from-ui      -> User-persona scenarios
generate-functional-from-backend -> System-persona scenarios   (this skill)
```

The two passes are fully independent — they share the functional
graph as the only common surface (idempotent merge by outcome name).

## Resources

- For all rules (functional graph definitions, backend-pass-specific rules, validation, pitfalls), read [references/rules.md](references/rules.md)

## Inputs

- **Backend repo path** — if provided as argument (`$ARGUMENTS`), use
  it directly; otherwise resolved in Phase -1
- **`.breeze.json`** — for `apiKey`, `apiBase`, `projectUuid`
- **Existing functional graph** — queried for dedup AND cross-pass
  merge reference
- **Optional: `entrypoints.json`** if resuming from a prior session
  (looked up inside the backend repo directory)

## Outputs

- **Functional graph** updated with System-persona scenarios + actions
- **`entrypoints.json`** — inventory + running checkpoint (written
  inside the user-provided backend repo directory, e.g.
  `<backendRepo>/entrypoints.json`)

---

# PHASES

---

## Guard

1. Read `.breeze.json` from the plugin working directory
2. If missing or incomplete, tell the user to run `/breeze:setup-project`
3. Extract `apiKey`, `projectUuid`, `apiBase`
4. Confirm the project has at least one code ontology indexed

---

## Phase -1 — Resolve the target backend repo

1. Check if user passed a path via `$ARGUMENTS` — validate it exists
   and looks like a backend repo
2. Check `.breeze.json` field `targetRepos.backend`
3. Check if cwd looks like a backend repo
4. Ask the user — single prompt: "Which backend repo do you want me
   to read? Provide an absolute path."
5. Persist the chosen path to `.breeze.json`:
   ```json
   { "targetRepos": { "backend": "/abs/path/to/backend-repo" } }
   ```
6. If path looks like a frontend repo, stop and suggest
   `/breeze:generate-functional-from-ui`

> **Rules:** see [rules.md](references/rules.md) → "Backend repo detection"

---

## Phase 0 — Discover entry points

If `entrypoints.json` already exists, read it and skip to the
per-EP loop (resuming). Do not overwrite.

---

### Sub-step 0.1 — Detect framework

1. Read `package.json` / `pom.xml` / `pyproject.toml` / `go.mod` etc.
2. Identify the backend framework from detection signals
3. Record the detected framework and controller/resolver glob pattern

> **Rules:** see [rules.md](references/rules.md) → "Framework detection table"

---

### Sub-step 0.2 — Confirm persona scope (no gate — mechanical)

1. Record in `entrypoints.json.personas[]`:
   ```json
   "personas": [
     { "name": "System", "source": "mechanical mapping", "isExisting": false },
     { "name": "External System", "source": "mechanical mapping", "isExisting": false }
   ]
   ```
2. Load existing personas: `Get_all_personas(projectUuid)` and flip
   `isExisting` where they already exist

> **Rules:** see [rules.md](references/rules.md) → "Persona rules (backend
> pass specific)". Assignment is mechanical — no user gate needed.

---

### Sub-step 0.3 — Discover REST routes

1. Optionally `Code_Graph_Search` to locate controller definitions
2. `Read` the controller/router files locally
3. Apply the per-framework discovery recipe

> **Rules:** see [rules.md](references/rules.md) → "Route discovery recipes"

---

### Sub-step 0.4 — Extract route details

For each REST route capture: `httpMethod`, `absoluteUrl` (resolved),
`controllerClass` / `handlerFunction`, `methodName`, `file`, `line`,
`parameters`, `requestType`, `responseType`, `authGuards` (recorded
but NOT used for persona assignment).

---

### Sub-step 0.5 — Categorize

Group routes by domain category (e.g. Search, Pipeline,
Notifications, Account, Export, Import, Sync, Webhooks, Admin).

---

### Sub-step 0.6 — Discover orphan handlers

1. Compare every handler file under `src/controllers/**`,
   `src/routes/**` etc. against routes from 0.3
2. For unmatched files, check imports, decorators, test-only usage
3. Classify each orphan

> **Rules:** see [rules.md](references/rules.md) → "Orphan handler classification"

---

### Sub-step 0.7 — Discover GraphQL entry points ⛔ HARD GATE

If the repo has NO GraphQL surface, skip and record
`"graphqlGranularity": null`.

1. Enumerate schema + resolver files — grep for SDL files, resolver
   decorators, resolver maps, GraphQL modules
2. Pick the EP granularity (per-operation, per-resolver-class, or
   per-type-field)
3. Enumerate every operation — record: operation name, resolver file +
   line, return type, arguments, directives
4. Read the resolver bodies for each operation
5. Present discovery list to user with chosen granularity
6. Wait for user confirmation
7. Record in `entrypoints.json` under `graphqlOperations[]`

> **Rules:** see [rules.md](references/rules.md) → "GraphQL EP granularity
> rules". This is a **HARD GATE** — do not proceed until user confirms.

---

### Sub-step 0.8 — Cross-reference frontend API callers (optional)

1. If frontend repo is indexed in code graph, list every endpoint the
   frontend calls
2. Flag backend routes with no frontend caller
3. Do NOT modify the graph — just record for review

---

### Sub-step 0.9 — Write `entrypoints.json`

1. Write the full inventory to disk with this schema:

```json
{
  "project": "<repo name>",
  "projectUuid": "<from .breeze.json>",
  "framework": "nestjs",
  "backendRepo": "<resolved target repo path>",
  "generatedAt": "<ISO timestamp>",
  "personas": [
    { "name": "System", "source": "mechanical mapping", "isExisting": true },
    { "name": "External System", "source": "mechanical mapping", "isExisting": false }
  ],
  "graphqlGranularity": "per-operation",
  "graphqlOperations": [
    {
      "operation": "projectById",
      "kind": "Query",
      "file": "src/projects/projects.resolver.ts",
      "line": 42,
      "returnType": "Project",
      "args": "id: ID!",
      "category": "Projects"
    }
  ],
  "totalEntryPoints": 47,
  "entryPoints": [
    {
      "id": 1,
      "type": "REST",
      "httpMethod": "POST",
      "absoluteUrl": "/v2/search/projects/export-email/xls",
      "controllerClass": "ProjectsController",
      "methodName": "projectExportEmailToExcel",
      "file": "src/controllers/projects.controller.ts",
      "line": 262,
      "parameters": ["filter: ProjectParams (query)"],
      "requestType": "ParamExportProjects",
      "responseType": "ResponseApi<{queued:boolean}>",
      "authGuards": ["JwtAuthGuard"],
      "category": "Export",
      "subType": null,
      "status": "pending"
    },
    {
      "id": 2,
      "type": "GraphQL",
      "kind": "Query",
      "operation": "projectById",
      "resolverClass": "ProjectsResolver",
      "methodName": "projectById",
      "file": "src/projects/projects.resolver.ts",
      "line": 42,
      "args": "id: ID!",
      "returnType": "Project",
      "category": "Projects",
      "status": "pending"
    },
    {
      "id": 3,
      "type": "REST",
      "httpMethod": "POST",
      "absoluteUrl": "/v2/webhook/partner/project-update",
      "controllerClass": "PartnerWebhookController",
      "methodName": "receiveProjectUpdate",
      "file": "src/webhooks/partner.controller.ts",
      "line": 31,
      "authGuards": ["HmacSignatureGuard"],
      "category": "Webhooks",
      "subType": "webhook",
      "status": "pending"
    }
  ],
  "completed": [],
  "remaining": [1, 2, 3, "...", 47],
  "orphans": {
    "deadCode": [],
    "orphanHandlersFolded": [],
    "routesWithNoFrontendCaller": []
  }
}
```

2. Present the EP list to the user and ask if any should be excluded

---

# PER-EP LOOP (repeat for each entry point)

---

## Step 1 — Dedup check

1. `Functional_Graph_Search` for the EP's likely outcome name + 2-3
   likely scenario names
2. Apply dedup decision matrix to decide: reuse, differentiate,
   attach, or proceed fresh

> **Rules:** see [rules.md](references/rules.md) → "Dedup decision matrix"

---

## Step 2 — Read the handler file fully

1. `Read` the entire controller / resolver file — imports, class
   definition, constructor (service injections), full handler body
2. For GraphQL resolvers, also `Read` the SDL file, any `@Directive`
   implementations, and DataLoader/batching wrappers
3. Skip leaf utilities unless the handler imports something non-trivial
4. For every injected service/repository/client, read the file before
   drafting scenarios

> **Rules:** see [rules.md](references/rules.md) → "Component-import drill-down
> rule"

---

## Step 3 — Resolve template literals, prefixes, and decorators

1. For REST: resolve route prefix template literals by `Read`ing the
   imported config file. Combine `@Controller('prefix')` +
   `@Post('subpath')` into a single `absoluteUrl`.
2. For GraphQL: confirm the operation name, argument types, and return
   type against both SDL and resolver method signature. If they
   disagree, SDL is authoritative — note the drift.

---

## Step 4 — Trace call chain and enumerate side effects

1. Walk one or two hops deep through constructor-injected services,
   repository injections, and external clients
2. For each handler, enumerate all side effects:
   - DB writes/reads — repository class, table, fields
   - ES index writes/reads — index, document shape
   - S3 uploads — bucket, key pattern
   - HTTP outbound — URL
   - Queue/event publishes — queue/topic, message shape
   - Email sends
3. Capture every API operation in `action.apis[]`

> **Rules:** see [rules.md](references/rules.md) → "`apis[]` type reference"

---

## Step 5 — Field enumeration for validation and response actions

1. For validation actions: enumerate DTO fields + rules from
   class-validator / zod / joi
2. For response-building actions: enumerate response DTO fields or
   GraphQL selection set
3. For enum-gated branches: follow the type definition and record
   the full enum set
4. Put long field lists in the **Scenario description**

---

## Step 6 — Build payload

1. Map EP to an outcome (one outcome per related EP cluster or shared
   with closely-related EPs)
2. Build persona -> outcome -> scenario -> step -> action tree
3. Populate `apis[]` on every action that performs an API operation

**Payload schema:**

```json
{
  "project": {
    "uuid": "<projectUuid from .breeze.json>",
    "name": "<repo or project name>"
  },
  "payload": {
    "personas": [
      {
        "persona": "System",
        "description": "...optional...",
        "citations": [
          { "type": "code", "name": "<handler file>", "reference": "<file path>" }
        ],
        "outcomes": [
          {
            "outcome": "Track Construction Project Pipeline",
            "description": "...business capability...",
            "citations": [
              { "type": "code", "name": "<file>", "reference": "<file path>" }
            ],
            "scenarios": [
              {
                "scenario": "Validate and enqueue project export",
                "description": "ProjectsController.projectExportEmailToExcel validates...",
                "steps": [
                  {
                    "step": "Receive export request",
                    "actions": [
                      {
                        "action": "Receive POST /v2/search/projects/export-email/xls",
                        "description": "Body: ParamExportProjects...",
                        "apis": [
                          {
                            "type": "REST",
                            "method": "POST",
                            "url": "/v2/search/projects/export-email/xls",
                            "request": "ParamExportProjects + ProjectParams",
                            "response": "ResponseApi<{queued:boolean}>"
                          }
                        ]
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  },
  "skipStepAndAction": false
}
```

> **Rules:** see [rules.md](references/rules.md) → "Persona rules", "Outcome
> rules", "Action rules", "Quantity targets", "`apis[]` type
> reference", and `../shared/functional-graph-rules.md` for canonical
> rules.

---

## Step 6.5 — Pre-upsert side-effect coverage validator

1. Take the Step 4 side-effect inventory
2. For each side effect, match to at least one action by repository/
   table in description, outbound URL in `apis[]`, or
   `trivialSideEffects[]` exclusion
3. Calculate coverage percentage
4. If >=90% -> proceed. If <90% -> fix payload or re-read missed files

> **Rules:** see [rules.md](references/rules.md) → "Side-effect coverage
> validator rules"

---

## Step 7 — Upsert ONE EP at a time

1. Write payload to `<backendRepo>/be_ep{NN}_{name}.json`
2. POST it:
   ```bash
   curl -X POST "${API_BASE}/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK" \
     -H "api-key: ${API_KEY}" \
     -H "Content-Type: application/json" \
     -d @<backendRepo>/be_ep01_export_email.json
   ```
3. If Rule A or Rule B fails, refuse to POST — fix and re-validate

> **Rules:** see [rules.md](references/rules.md) → "Pre-upsert validation
> rules" and "Write protocol"

---

## Step 8 — Verify

1. `Functional_Graph_Search` for a unique phrase from each new
   scenario's description
2. Confirm: scenario appears, score > 0.4, `scenarioId` returned
3. If merged into an outcome with existing User scenarios, confirm
   both persona types now appear

---

## Step 9 — Update checkpoint

1. Mark EP's `status` from `in_progress` -> `done`
2. Pop the EP id from `remaining[]`
3. Append a `completed[]` record:

```json
{
  "epId": 12,
  "title": "POST /v2/projects/export-email/xls",
  "outcomeName": "Track Construction Project Pipeline",
  "outcomeUuid": "73f29538-...",
  "scenariosCreated": 3,
  "actionsCreated": 11,
  "apiCallsLogged": 2,
  "sideEffectsLogged": 5,
  "verificationScores": { "validate and enqueue": 0.71 },
  "payload": "<backendRepo>/be_ep12_project_export.json",
  "completedAt": "<ISO>"
}
```

4. Edit (do not rewrite) `entrypoints.json` — only `status`,
   `completed[]`, `remaining[]` mutate

---

# REFERENCE

## Cost per EP

~**9-13 tool calls per EP**. For 50 EPs: 450-650 calls. Plan for
multiple sessions.

## Multi-session resume

When context budget hits ~75%: flush current EP's checkpoint, stop
and report. To resume: **"continue backend pass from entrypoints.json"**.

## When NOT to use

- **Frontend-only repos** — use `/breeze:generate-functional-from-ui`
- **Quick first-time exploration** — deprecated `generate-functional-from-code`

## See also

- `/breeze:generate-functional-from-ui` — the frontend half
- `/breeze:generate-functional-from-code` — deprecated legacy pipeline
- `/breeze:validate-functional-graph` — quality checks after generation
- `/breeze:generate-spec` — export the graph as a spec doc
