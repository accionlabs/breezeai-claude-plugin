## UI Pass Rules Reference

---

## Functional Graph Definitions

### Outcome

A high-level goal or capability a persona needs to accomplish.
Outcomes are **business capabilities**, not technical functions or
API endpoints.

- Evaluate existing Outcomes FIRST
- Prefer broader Outcomes over narrower ones
- Capture variation as new Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent

**Good:** "Manage Fund Allocations", "Monitor Compliance Status"
**Bad:** "Handle API Requests", "Process Database Queries", "Render Components"

**Quality checks:** understandable by non-technical stakeholders,
stable across implementation changes, broad enough to absorb future
Scenarios. If more than 3-4 new Outcomes appear necessary,
re-evaluate for over-segmentation.

### Scenario

A **specific user or system flow** under an Outcome. Testable — you
can write acceptance criteria. Clear start and end.

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging
- Each Scenario must include a brief description

**Good:** "Filter Dashboard by Date Range", "Submit Compliance Report"
**Bad:** "Use the System", "Do Things with Data"

For System Persona scenarios, the description MUST describe the
internal processing behavior, NOT the UI that triggers it.

### Step

**Sequential stages** within a Scenario — the major phases to
complete the flow.

- Each Step is a distinct stage, ORDERED in sequence
- Step name = short verb phrase
- Steps do NOT require descriptions (the name is sufficient)
- A Scenario typically has 3-8 Steps (max 10)

### Action

**Atomic operations or user inputs** within a Step. Rules differ
by persona type:

**HUMAN PERSONA actions** (User, Admin, or any named role):
- Describe what the user PROVIDES, DECIDES, or OBSERVES
- MUST be platform-agnostic (web, mobile, CLI, voice)
- FORBIDDEN words: click, tap, swipe, hover, scroll, drag, drop,
  toggle, button, dropdown, modal, dialog, popup, panel, checkbox,
  radio, slider, tooltip, menu, sidebar, navbar, tab, icon
- USE instead: Provide, Choose, Confirm, Review, Dismiss, Open,
  Close, Submit, Cancel, Specify, Indicate, Acknowledge, Request
- description = null, unless a real user-facing constraint exists

**SYSTEM PERSONA actions:**
- Single atomic internal operations
- description REQUIRED: formula, threshold, field names, condition,
  error message, data format, or input/output contract
- null only for trivial glue (e.g. "Log completion")

**EXTERNAL SYSTEM PERSONA actions:**
- Single atomic API/integration operations
- description = endpoint, payload shape, or auth mechanism when known

**Quantity:** 1-5 Actions per Step. If more than 5, split the Step.

---

## UI Pass Specific Rules

---

### Source-of-truth hierarchy

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the UI folder | **Primary** — pages, widgets, services, queries, stores | Filesystem has literal JSX, decorator strings, store fields, hook names |
| `Code_Graph_Search` on the UI repo | **Optional accelerator** — locate entry-point pages or trace cross-file flows | Faster than blind globbing, but always confirm by `Read`ing the actual file |
| `Functional_Graph_Search` | **Dedup check only** — never as a source of code knowledge | See Step 1 |
| `Get_Code_File_Details` | **Avoid** for frontend reading | Use raw `Read` on JSX/TSX files |

---

### Frontend repo detection

A valid frontend repo has `package.json` AND at least one of:
`src/router/`, `src/routes/`, `app/routes`, `pages/`, `src/pages/`,
`app/`, or React/Vue/Angular Router imports under `src/`.

If no frontend router file found, stop and suggest
`/breeze:generate-functional-from-backend`.

---

### Persona rules (UI pass specific)

- The UI pass writes **only human personas** — never `System`
- Read the auth model (route guards, JWT claims, role decorators)
  and use named human roles when present
- Fall back to `User` only when the repo's domain has no role
  distinctions
- Never invent roles — extract literal names from code only
- Subscription tiers are NOT personas — propose them in a separate
  "feature flags — not personas" list
- The confirmed persona set from sub-step 0.2 is a **closed set** —
  if the per-EP loop needs a persona not in the set, STOP and ask
  the user

---

### `apis[]` type reference

The `type` field supports: **REST / GraphQL / gRPC / WebSocket / Event**

| UI pattern | `type` | When |
|---|---|---|
| fetch/axios/useQuery/useMutation | `"REST"` | Most common |
| GraphQL query/mutation subscription | `"GraphQL"` | When UI subscribes to GQL |
| Socket.IO / plain ws | `"WebSocket"` | Real-time connections |
| Server-Sent Events | `"Event"` | SSE streams |
| gRPC-Web | `"gRPC"` | gRPC from browser |

---

### Dedup decision matrix

| Score | Match type | Action |
|---|---|---|
| > 0.6 | Same interaction model (single vs bulk, header vs row, modal vs inline) | **Reuse** — link new content to existing via same name |
| > 0.6 | Different interaction model | **Differentiate** — sibling scenario with disambiguated name |
| < 0.6 | No match | **Proceed fresh** |

Use `parameters3_Value` for project UUID — wrong slot fails silently.

---

### Panel classification rules

- **Viewer** (markdown render, read-only popup) — fold into
  triggering page's scenarios as actions.
  `"classification": "viewer"`
- **Feature-rich** (own tabs, forms, CRUD, API calls, internal
  state machines) — separate EP with `"type": "panel"` and full
  per-EP processing. `"classification": "feature-rich"`

Sub-tab workspaces inside pages are NOT panels — discover them by
grepping for `TabsContent`, `activeTab`, `<Tabs` and process each
tab as part of the parent page's batch (same EP, multiple scenarios).

Conditional layouts on parameterized routes (e.g. `/chat/:agent/:id`)
— read EVERY conditional branch; significant branches become variant
EPs with `"type": "route-variant"`.

---

### Follow-the-trigger rule

For every `setPanelType("X")` / equivalent found in a page:
1. Look up the panel type string in `panels[]`
2. Feature-rich -> do NOT capture internals here; DO capture "open
   panel X" action linking to the panel EP's id
3. Viewer -> READ the renderer now; capture every interactive element
   as actions under this EP
4. Unknown panel type -> STOP, ask user

---

### Component-import drill-down rule

For every imported component matching
`/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/` AND
that has its own `useState`/`useReducer`/`useStore` hook, you MUST
read the file before drafting scenarios. Record in citation list.
If skipped, justify in `completed[]` under `skippedComponents[]`.

---

### JSX coverage validator rules (Step 6.5)

- >=90% of the JSX widget inventory must be matched to an action
- Common chrome (close buttons, breadcrumbs) CAN be added to
  `viewOnlyChrome[]` but must be justified in one line each
- **Widgets with action verbs (Save, Submit, Generate, Delete,
  Upload, Download, Send, Confirm, Apply, Run, Create, Update) can
  NEVER be excluded** — if unmatched, validator MUST fail
- **Network-verb actions (Submit, Generate, Upload, Delete, Send,
  Save, Fetch, Retrieve, Sync) MUST have `apis[]`** — if missing,
  validator MUST fail

---

### Pre-upsert validation rules (Step 7)

**Rule A — network-verb actions must have `apis[]`.** If
`action.action` contains any of: Submit, Generate, Upload, Download,
Delete, Save, Send, Fetch, Retrieve, Publish, Persist, Sync, Import,
Export, Share, Subscribe, Unsubscribe, Authenticate, Authorize,
Refresh, Poll — the action MUST have a non-empty `apis[]` block.
If not:
1. Open the service/query file, find the URL, add `apis[]`, OR
2. Rename the action to remove the verb if local-only, OR
3. Document why no `apis[]` in description (e.g. "persists to
   localStorage")

**Rule B — every `useMutation` / `useQuery` / `mutateAsync`
discovered in Step 4 must resolve to a `Read` of the service file.**
If you have a hook reference you never followed, go back, Read the
service, add the URL.

If either rule fails -> refuse to POST. Fix and re-validate.

---

### Orphan classification

| Classification | Action |
|---|---|
| sub-component | Fold into parent page EP, do NOT create new EP |
| dead code | Flag for user, exclude |
| truly unused | Exclude |

---

### Write protocol

**The UI pass writes to the functional graph EXCLUSIVELY via the
curl upsert endpoint** — one POST per EP. Never batch multiple EPs.

**Forbidden write paths:**
- `Update_Functional_Node` MCP tool
- `Call_Create_Functional_Node_` MCP tool
- Any per-node MCP write that requires a parent UUID lookup first

**Payload schema rules:**
- `project.uuid` from `.breeze.json` — required
- `personas[]` must be an array even with one persona
- Only human personas from the confirmed set — never `System`
- Each level matched by **name** at upsert time — idempotent
- `actions[].apis[]` supports **REST / GraphQL / gRPC / WebSocket /
  Event**
- `citations[]` supported at persona and outcome level

---

### Boundary with the backend pass

The frontend pass **never**:
- Reads backend repos
- Creates System persona scenarios
- Makes claims about controller files, routes, or handlers
- Cites backend file paths
- Writes any handoff file for the backend pass

The two passes share the functional graph as the only common surface.
No file-based handoff.

---

### Common pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Reading only `index.tsx` | < 5 scenarios per EP | Glob the page dir, read 4-10 files |
| Skipping the JSX audit | Steppers/toggles/tabs missing | Step 3 is mandatory |
| Opaque Display actions | No field enumeration | Step 5 is mandatory |
| Trusting code graph for literal strings | URL mismatches | Always `Read` the service file |
| Batching multiple EPs in one upsert | Per-EP count low | One upsert per EP |
| Wrong `Functional_Graph_Search` slot | Schema error | Use `parameters3_Value` for project UUID |
| Writing a handoff file for backend | Skill drift | No handoff needed |
| Skipping `apis[]` for non-REST calls | GraphQL/WS/gRPC flows missing | Use matching enum value |
| Network-verb action with no `apis[]` | "Submit X" has no URL | Rule A refuses to POST |
| Treating panels as "just a viewer" | Panel interactions dropped | Sub-step 0.7 + follow-the-trigger rule |
| Skipping component imports | Wrapper components hide sub-flows | Step 2 drill-down rule |
| Using `System` persona | Wrong ownership | Always human persona |
| Forbidden words in action names | "Click stage tile" | Use intent verbs |
| Code-level prose in human action desc | "TNLMPaper card click invokes onStageClick" | `description` = null unless user-facing constraint |
| Naming outcomes after pages | "Open Dashboard" | Business capabilities |
