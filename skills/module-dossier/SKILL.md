---
name: module-dossier
description: >
  Build one architecture document per OneCMS / KinderCare domain, incrementally, module by
  module — a purely technical picture of how each module is built. A domain (e.g. "Customer
  Account Management") is one file; under it modules (Profile Management, Account Management,
  Attendance …) are sections, items (1.1 Manage Primary Sponsor, 1.2 Manage Secondary Sponsor
  …) are subsections, and workflows (Create / Update / View …) resolve to functional-graph
  scenarios. The user pastes a structured table (Domain / Module # / Module Name / Item # /
  Item Name / Workflow Name / Personas Involved / Summary); the skill resolves each workflow
  to scenarios, then documents four things for the module and nothing else — the personas
  involved, the files involved as a UI→service→facade→data→stored-proc hierarchy, the stored
  procedures involved, and the tables involved. It confirms each of those with the user
  before writing (they can correct a path, drop a file, or flag something missed). When the
  same domain name is given again it reopens that same file and adds or refreshes only the
  named module, leaving the rest intact. Use when the user wants a domain, module, or item's
  core architecture identified, documented, or written up; when scoping what a change,
  rewrite, or migration would touch; or when another task needs a module's flows, file
  inventory, or procedure list as input.
---

The hierarchy is `Domain (file) → Module (section) → Item (subsection) → Workflow (→ graph
scenario)`. The functional graph itself is `persona → outcome (task) → scenario`; module and
item are the layers above it, defined only by the table the user pastes. This skill
materialises that mapping as one document per domain at `docs/domains/<domain-slug>.md`,
**built up one module at a time** — a domain is too large to trace in a single pass.

A module section opens with the **module name and a one-line description** of what the module
does, then documents **exactly four things and nothing else** — a purely technical picture of
the module's core architecture:

1. **Personas** involved.
2. **Files** involved, as a hierarchy that flows UI → service → facade → data → stored proc.
3. **Tables** involved.
4. **Stored procedures** involved.

The description is the module's purpose in one sentence, grounded in the resolved scenarios
(and cross-checked against the table's *Summary*, which is a lead not evidence) — not a
paragraph. Everything after it is the four artifacts.

Four rules:

- **Every claim validated.** The graph that owns a fact must confirm it: a scenario-named
  service call resolves in the code graph, a code-named procedure exists in the DDL, a
  proc-named table exists in the schema. Disagreements are reported, never silently
  resolved. Lists derived from scenarios are complete for them (**traced**); name-based
  lists may miss files (**swept**) — label which.
- **Confirm each artifact with the user.** Files, then stored procedures, then tables (and
  the persona/scenario map up front) are each presented before the next is built. The user
  can correct a path, drop a file, add one you missed, or reject the framing. Fold their
  changes in before moving on — do not write the document until all four are agreed.
- **Meaningful and minimal.** The document is the four artifacts, presented cleanly. No
  section, sentence, or column that does not answer a reader's question about how the module
  is built. Plain names in prose, node ids in small code columns, shape before data. If it
  is not a persona, a file, a procedure, or a table, it does not belong.
- **Incremental — never rewrite what you weren't asked to touch.** Only the module(s) named
  in this run are traced and written. Every other module section in the domain file is left
  byte-for-byte alone.

## Constants

```
project uuid     9e9b104f-6e0d-4298-a2f0-aab538377de3   (kce.v1.0.2)
codeOntologyId   9                                       (onecms-source-cleanedup)
data_lake_id     1785396670436-miqj702                   (onecms, SQL Server)
```

Different project → `Call_List_Project_` / `Call_List_Repositories_`, and name it in the
domain-file header.

## 1 · Parse the input and open the domain file

The user pastes a table with these columns (tab- or multi-space-separated; tolerate either):

```
Domain | Module # | Module Name | Item # | Item Name | Workflow Name | Personas Involved | Summary
```

Group the rows into a tree: **Module → Item → Workflow**, carrying the row's *Personas
Involved* and *Summary* on each workflow.

`domain-slug = kebab-case(Domain)` → path `docs/domains/<domain-slug>.md`.

- **File does not exist** → this run creates it (header + the module block(s) you trace).
- **File exists** → read it and enumerate the `<!-- module:N -->` anchors already present.
  For each module in the pasted input:
  - **Module # not in the file** → new; trace it.
  - **Module # already present** → **ask the user**: refresh (re-trace and replace that
    section) or skip. Do not decide silently.

State the plan back before tracing: which modules are new, which already exist, which the
user chose to refresh. Trace one module at a time and merge it (§10) before starting the
next, so a failure mid-run never leaves a half-written section.

## 2 · Map workflows to scenarios — table is scope, graph is truth  ·  CONFIRM

The pasted table defines **what** to cover. The graph + code + DB remain the **only**
evidence for architecture claims. Per workflow row:

```
Functional_Graph_Search(uuid, query="<workflow name words>", limit=25)
```

`embedText` on each hit carries its `Persona / Outcome / Scenario` lineage. A workflow may
**equal** a graph scenario, be a **slice** of one, or **span** several.

Then resolve the personas — the roster written into the module section:

```
Get_all_personas(uuid, limit=30)
Get_all_outcomes_for_a_persona_id(uuid, persona_id, limit=60)   # check every persona
```

Keep the personas holding this module's mapped scenarios; sort by scenario count. Permission
facts are already in outcome descriptions (`"read-only; Save gated on MODULE_X UPDATE at
Foo.ascx.cs:1240"`) — lift verbatim. List `System` / `External System` separately. Cross-check
the table's *Personas Involved* against the graph and **report disagreements, resolve nothing
silently**; the *Summary* is a lead, never evidence.

**⇢ Gate 1.** Show the resolved map — item → workflow → scenario ids → personas — and the
persona roster. A workflow that resolves to nothing is asked about, never guessed. Get the
user's buy-in (or corrections) before tracing code.

## 3 · Flows and seeds

Collapse this module's mapped scenarios into flows — personas word the same flow
differently. Then per scenario (all personas' variants):

```
Get_all_steps_actions_for_a_scenario_id(uuid, scenario_id)
```

Seeds — the service calls anchoring each flow — come from **Api nodes** and **action
description prose** together (measured: only 28/160 actions carry an Api node; neither source
suffices alone). Normalise `Service.Method`, `/KUCare.Services/X.asmx/Method`, and
`IService.Method` to one endpoint. A seedless flow often has a fully-named twin under another
persona.

## 4 · Trace each seed into the file hierarchy

```
Get_Code_Nodes_By_Label(project_uuid, label="Function",
  filters={"codeOntologyId": 9, "name": "<Method>"}, children=true)
```

Same-named functions across layers (interface, service, facade, data) *are* the chain — this
is the UI→service→facade→data→proc hierarchy the document renders. Verified wrinkles:

- **Two data-access patterns**: `Framework/KUCare.Data/*Data.cs` uses `GetSQLCommand("PROC")`;
  `Framework/KUCare.Repositories/*Repository.cs` (+ `CacheRepositories/` twin) uses
  `CreateCommand("PROC", CommandType.StoredProcedure)`. Grep **both**.
- **Proc names are not always literals.** The same repositories also pass the name as a
  constant: `_dbProvider.CreateCommand(DBConstants.ENRL_GetReservations, CommandType.StoredProcedure)`.
  Both forms coexist *within one file*, so the literal-only grep does not degrade
  gracefully — it returns a plausible-looking short list. On BUCC Reservation it found 44 of
  77 and dropped the entire `ENRL_*`/`NBC_*` core, including the primary search and insert
  procs. Always run both patterns below and union them.
- **Chains vary**: UI may call the service directly (no `.svc` hop); same-named parallel
  chains exist (`AssignSponsor` in StudentService *and* EnrollmentService); `ServiceStubs/`
  are test doubles — keep off the chain.
- **Collect callers too** (grep `.Method(`): that is how batch jobs attach to a flow with
  evidence.

Procedure names, from statement text — **both** name forms, unioned (verified in §6, listed
in §7):

```bash
jq -r '.result' <dump> | jq -r '.data[].text' > /tmp/stmts.txt
{ grep -oE '(GetSQLCommand|CreateCommand)\("[A-Za-z0-9_]+"'            /tmp/stmts.txt | sed 's/.*("//;s/"$//'
  grep -oE '(GetSQLCommand|CreateCommand)\(\s*DBConstants\.[A-Za-z0-9_]+' /tmp/stmts.txt | sed 's/.*DBConstants\.//'
} | sort -u
```

Sanity-check the union: a module with UI write flows but no `Ins`/`Upd` procedures means the
extraction failed, not that the module is read-only.

For each domain data class, page Statements until retrieved = `total` (`SponsorData.cs` is
891 across three pages; `ReservationRepository.cs` is 757 across two — stopping early loses
procedures).

## 5 · Periphery sweep (label **swept**)  ·  CONFIRM files

Scenarios miss mail builders, batch jobs, reports. Name-sweep per module/item token:

```
Get_Code_Nodes_By_Label(label="File",
  filters={"codeOntologyId": 9, "path": {"$containsi": "<token>"}}, children=false, limit=200)
```

Layer = path prefix: `CMS/Controls/`, `Presenters/`, `Framework/KUCare.Enterprise*Services/`,
`*/Service.Interface/`, `Framework/KUCare.Services|Facade|Domain|Repositories|Data/`,
`Shared/KUCare.DTO|Common/`, `KUCare.Rest/`, `KUCare.Reports/`, `KUCare.WindowServices/`.
Fold `.designer.cs` into its `.ascx.cs` owner.

**⇢ Gate 2.** Present the full file hierarchy — the flow-by-flow chains plus the swept
periphery, labelled which is which. This is the module's file inventory. Let the user drop a
file, correct a path, or name one that was missed; fold it in before touching procedures.

## 6 · Stored procedures — verify each  ·  CONFIRM procedures

The `DBConstants` identifier has so far equalled the real procedure name, but it is still a
code name. Verify every name from §4 against a `DDLProcedure` node before it goes in the
list. Read the body from the `procedure` node's `definition` field (not
`Architecture_Graph_Search`); page all of them once and reuse the dump:

```bash
jq -r '.result' <proc-dump> | jq -c '.data[] | {name, def:.definition}' >> /tmp/bodies.json
```

**⇢ Gate 3.** Present the procedure list, each tied to the flow that calls it. The user can
drop one, flag one as wrong, or add a known proc. Confirm before tables.

## 7 · Tables — corroborate against procedure bodies  ·  CONFIRM tables

```
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="table", limit=600)
```

Owned schemas follow this module's mapped outcomes (`spon`, `std`, `fin`, `enrl`, …);
cross-schema tables get tagged with the reaching flow. Migration scratch (`datafix.*`,
`dbo.ZZ_*`, `*_log`, `Backup_*`, `dbo.TEMP_*`, `*Tracking1`) is one line.

Corroborate every table against the procedure bodies from §6 — where lists disagree, bodies
win:

```bash
jq -r --arg p "<PROC>" 'select(.name==$p)|.def' /tmp/bodies.json \
  | grep -oiE '(FROM|JOIN|UPDATE|INSERT[[:space:]]+INTO|DELETE[[:space:]]+FROM)[[:space:]]+\[?[A-Za-z0-9_]+\]?\.\[?[A-Za-z0-9_]+\]?'
```

Strip `EXEC` targets and `dbo.tbl_*` helpers — the regex catches them as though they were tables.

**A body-named table missing from the DDL inventory is a finding, not a typo to normalise.**
Measured: 29 procedures write `enrl.Reservation`, which exists as neither table, view, nor
synonym — only `resrv.Reservation` does. Confirm the inventory is complete first (retrieved =
`total` for both `table` and `view`), then report the disagreement and attribute the table
list to the objects that verifiably exist. Never quietly rewrite one schema prefix to another.

**⇢ Gate 4.** Present the table list, each tied to its flow, with scratch excluded in one
line. Get the user's buy-in or corrections.

## 8 · Verify before writing

A separate pass over the agreed module draft: every file → File node at that exact path;
every procedure → `DDLProcedure` with that exact name; every table → DDL node *and*
referenced by a verified procedure body; every flow → its scenario ids. **Functional-graph
prose is a lead, never evidence, for code names** (graph said `STD_AssignSponsor`; code runs
`STD_AssignSponsorToStudent`). A failed claim is corrected or marked *unresolved* inline.

## 9 · Merge into the domain file

Each module section is wrapped in anchor comments so it can be located, replaced, or appended
deterministically:

```
<!-- module:N -->
## N · <Module Name>
…
<!-- /module:N -->
```

- **File absent** → create it with the domain header (§Template) and this run's module block.
- **New module** → insert its `<!-- module:N -->…<!-- /module:N -->` block in **Module-#
  order** among the existing sections.
- **Refreshed module** → replace only the text between that module's anchors. Touch nothing
  outside them.
- **Header index** → add or refresh this module's entry (number, name, date) in the
  **Modules covered** line. Leave other modules' entries alone.

After merging, report the file path and which module sections it now contains.

## Tool quirks

- `include_labels`, `fields`, and the DB tool's `filters` are rejected (string
  serialisation) — the error asks for a list/dict, but passing one fails the same way, so
  there is no working form. Code-graph `filters` works; for DB pull full pages and `jq`.
- `semanticType` is `null` on most statements — grep statement `text`, never filter on it.
  (It *is* populated on synthetic `route` nodes, where it usefully confirms a WCF
  `[OperationContract]` and its endpoint.)
- Bulk results spill to `{"result": "<json string>"}` files → `jq -r '.result' | jq …`.
  Assume this for anything bulk: one `Function` name with `children=true` can exceed the
  limit on its own. Use `children=false` when you only need the layer chain, and reach for
  `children=true` on the single facade method whose statements you actually want to read.
- `Get_Code_File_Details` takes a File node `id`, not a path.

## Template

Per-domain file. The header sits once at the top; each module is a self-contained block
between anchors, holding only the four artifacts.

````markdown
# <Domain Name>

**Project:** <name> — `<uuid>` · code ontology `<id>` · data lake `<name>`
**Modules covered:** N <Module Name> (<YYYY-MM-DD>) · M <Module Name> (<YYYY-MM-DD>)

<!-- module:N -->
## N · <Module Name>

<one-line description of what the module does>

*Generated <YYYY-MM-DD> · items <first>–<last>*

<out of scope: unresolved or excluded workflows for this module — one line, only when present>

### Personas

| Persona | Access | Notes |
|---|---|---|
| <name> | <read-only / create / edit> | <one line, from permission gates> |

### Files

Per item, the flow from UI down to the stored proc:

#### <Item #> <Item Name>  *(<personas>)*  → scenarios `<id>` `<id>`
```
CMS/Controls/<Entry>.ascx
  → Framework/KUCare.Services/<X>Service.cs
  → Framework/KUCare.Facade/<X>Facade.cs
  → Framework/KUCare.Data/<X>Data.cs        (or KUCare.Repositories/<X>Repository.cs)
      → <PROC_NAME>
```

<repeat #### per item; shared periphery (mail, batch, reports) once at the end, labelled swept>

### Tables

| Table | Used by (item / flow) |
|---|---|
| `<schema>.<name>` | <item / flow> |

<one line: migration scratch excluded>

### Stored procedures

| Procedure | Item / flow |
|---|---|
| `<PROC_NAME>` | <item / flow> |
<!-- /module:N -->
````

---

## 10 · Generate the Excel capability matrix

After all gates are confirmed and all modules for the run are merged into the domain
markdown file, also produce an Excel spreadsheet. Run this step once, **after** the last
module's Gate 4 has been approved.

### File layer classification

Classify every file path collected in §4–§5 into one of four columns. Match is a
**case-insensitive substring** on the normalised path (backslashes → forward slashes).
The first matching rule wins.

| Excel column | Path substrings that match |
|---|---|
| **Client** | `onecms/cms` · `onecms/presenters/kucare.presenters` · `onecms/subsidy` |
| **Service Layer** | `onecms/easydraftservice` · `onecms/framework/kucare.services` · `onecms/framework/kucare.enterpriseservices` · `onecms/framework/kucare.enterpriseextservices` · `onecms/framework/kucare.enrollmentrefactor/domain` |
| **Façade Layer** | `onecms/framework/kucare.facade` · `onecms/framework/kucare.enrollmentrefactor/facade` |
| **Data Access Layer** | `onecms/framework/kucare.repositories` · `onecms/framework/kucare.data` · `onecms/framework/kucare.enrollmentrefactor/repositories` · `onecms/dataaccessmanagement` |
| **Jobs** | `onecms/kucare.windowservices` |

Files that match none of the above are silently dropped (build artifacts, test doubles,
shared DTO projects, etc. do not belong in the matrix).

### Accumulate data

For each row the user pasted, build a JSON object and append it to a list. Aggregate by
**Item** (one Excel row per unique Item #, not per Workflow): union all files, procedures,
and tables from every workflow under that item.

```json
{
  "rows": [
    {
      "domain": "Customer Account Management",
      "module_num": "1",
      "module_name": "Profile Management",
      "item_num": "1.1",
      "capability": "Manage Primary Sponsor",
      "personas": ["Case Manager", "Enrollment Specialist"],
      "files": [
        "onecms/CMS/Controls/Sponsor/ManageSponsor.ascx",
        "onecms/Framework/KUCare.Services/SponsorService.cs",
        "onecms/Framework/KUCare.Facade/SponsorFacade.cs",
        "onecms/Framework/KUCare.Repositories/SponsorRepository.cs"
      ],
      "procs": ["STD_GetSponsor", "STD_SaveSponsor"],
      "tables": ["std.Sponsor", "std.SponsorAddress"]
    }
  ]
}
```

Save this as `excel-data.json`.

### Run the script

Install `openpyxl` if not present:

```bash
python3 -c "import openpyxl" 2>/dev/null || pip install openpyxl --quiet
```

Generate the spreadsheet:

```bash
python3 {SKILL_BASE_DIR}/scripts/generate-excel.py excel-data.json \
  "docs/domains/<domain-slug>-capability-matrix.xlsx"
```

`{SKILL_BASE_DIR}` is the directory containing this SKILL.md file.

The script prints a one-line summary and exits 0. On error it prints to stderr and exits
non-zero — relay the message to the user.

### Excel output specification

The spreadsheet has one sheet named **Capability Matrix** with these 13 columns in order:

| # | Column header |
|---|---|
| A | Domain |
| B | Module # |
| C | Module Name |
| D | Item # |
| E | Capability |
| F | Personas |
| G | List of Source Code Files (Client) |
| H | List of Source Code Files (Service Layer) |
| I | List of Source Code Files (Façade Layer) |
| J | List of Source Code Files (Data Access Layer) |
| K | List of Stored Procedures |
| L | List of Tables |
| M | Jobs |

- One data row per Item (after aggregating all its workflows).
- File names within a cell are newline-separated (wrap text on).
- Header row: white text on dark-blue fill, bold, frozen.
- Alternating row shading (light blue on even rows).
- Column widths: A 22, B 10, C 24, D 8, E 36, F 24, G–J 48 each, K 36, L 30, M 40.
