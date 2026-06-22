## UI Pass Rules Reference — adapter

> **Read the single source of truth FIRST** (ADR 0001): the node model, reuse/dedup,
> citations, `rule-a`, write protocol, and validation are in
> [`../../shared/functional/core.md`](../../shared/functional/core.md); the human-persona
> rules (platform-agnostic action language, **forbidden UI words**, persona derivation,
> per-field atomicity) are in
> [`../../shared/functional/human-overlay.md`](../../shared/functional/human-overlay.md).
> This file no longer restates those — it carries ONLY the UI source-extraction adapter
> below. The hard gates are enforced by the shared `validate.py` (a shim in this skill's
> `validators/`) regardless. The UI pass writes **only human personas**.

---

## UI Pass Specific Rules

---

### Source-of-truth hierarchy

| Tool | When to use | Why |
|---|---|---|
| `Glob` / `Read` / `Grep` on the UI folder | **Primary** — pages, widgets, services, queries, stores | Filesystem has literal JSX, decorator strings, store fields, hook names |
| `Code_Graph_Search` on the UI repo | **Optional accelerator** — locate entry-point pages or trace cross-file flows | Faster than blind globbing, but always confirm by `Read`ing the actual file |
| `Functional_Graph_Search` | **Dedup check only** — never as a source of code knowledge | See Step 1 |
| `Get_Code_Nodes_By_Label` | **Avoid** for frontend reading | Use raw `Read` on JSX/TSX files |

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
- **Prefer `/breeze:detect-personas` output** over manual grep — it
  performs individual-variable usage counting and eliminates
  dead-code roles automatically
- Fall back to `User` only when the repo's domain has no role
  distinctions
- Never invent roles — extract literal names from code only
- **Verify actual usage:** a role constant that is defined but has
  0 usages outside its definition and import lines is dead code and
  MUST NOT become a persona. Grep each role variable individually
  (never combined via `|`) to get accurate counts
- Subscription tiers are NOT personas — propose them in a separate
  "feature flags — not personas" list
- The confirmed persona set from sub-step 0.2 is a **closed set** —
  if the per-EP loop needs a persona not in the set, STOP and ask
  the user

---

### `apis[]` type reference

The `type` field is **free text** (the backend stores it as a plain string — no enum is enforced). Recommended values: **REST / GraphQL / gRPC / WebSocket / Event / SOAP** — use `SOAP` for ASP.NET Web Forms / WCF / ASMX web-service calls.

| UI pattern | `type` | When |
|---|---|---|
| fetch/axios/useQuery/useMutation | `"REST"` | Most common |
| GraphQL query/mutation subscription | `"GraphQL"` | When UI subscribes to GQL |
| Socket.IO / plain ws | `"WebSocket"` | Real-time connections |
| Server-Sent Events | `"Event"` | SSE streams |
| gRPC-Web | `"gRPC"` | gRPC from browser |
| SOAP web service (WCF / ASMX) | `"SOAP"` | ASP.NET Web Forms façade / service-proxy call |

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
- `actions[].apis[]` `type` is free text (recommended: **REST /
  GraphQL / gRPC / WebSocket / Event / SOAP**)
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
