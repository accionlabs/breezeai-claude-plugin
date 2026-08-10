---
name: code-ontology-audit-check
description: Run a full Breeze code ontology audit for one or all repos. Checks file coverage, function/class/LOC counts, intentional exclusions, and ghost files. Use when validating a repo's code graph completeness.
---

# Breeze Audit Checks

Run a full Breeze code ontology audit for one or all repos in the **hubexo / Nimbus** workspace.

## Usage

`/code-ontology-audit-check [repo-name]`  
If no repo is specified, audit all repos in sequence.

## Prerequisites

- The **breeze-mcp** server must be connected (tools like `Get_Code_Nodes_By_Label` available). Without it, only the disk-side checks (file counts, exclusions) can run.
- The repo must already be **generated and uploaded** to BreezeAI (run `breeze-code-ontology-generator` with `--repo`/`--out` and `--upload`, which produces `<repo>-project-analysis.ndjson.gz`). The `.ndjson` snapshot is the cross-reference for checks 2 & 7.

---

## Conventions

- **Language coverage** — Breeze (tree-sitter) parses **TypeScript, JavaScript, C#, Python, Java, Go, PHP, VB.NET, Vue, Perl, Salesforce Apex** and extracts SQL/DDL statements. It does **NOT parse Groovy or Terraform/HCL** — those files are only picked up (if at all) as config. Account for this per repo below.
- **Frontend (Angular) code** (`nimbus-api`'s `nimbus-app`, `hubspot-tools`'s `ui`): HTML and CSS/SCSS are **not indexed** by Breeze — intentional. Only TS/JS, JSON, MD, YAML, and similar code-bearing files count.
- **Config files** — `.json`, `.yml/.yaml`, `Dockerfile`, `.xml`, `.gradle`, `Makefile`, `.toml`, `.ini` are indexed as config nodes, not parsed for functions/classes.
- **The generator emits `.ndjson` for every supported language** (including C#/Python), so checks 2 & 7 should have an ndjson snapshot for any TS/C#/Python repo.
- **Each audit must end with the Final Ontology Completeness Check** (step 7 below).
- After completing an audit, **create a verdict file** named after the repo (e.g. `nimbus-api.md`) in the `mds/` folder, and **update `mds/audit-checks.md`** with the results.

---

## Checks to Perform (for each repo)

### 1. Code Ontology Coverage

Compare Breeze-indexed file count against actual files on disk.

- Paginate `Get_Code_Nodes_By_Label` (label=`File`) to get total indexed file count
- Run `find <repo>/ -type f` on disk, filtered to indexable types (TS, JS, MJS, CS, PY, JSON, YAML, MD, Dockerfile, and — as config only — XML/gradle/toml)
- Explain any delta (HTML/SCSS excluded for Angular; test dirs excluded; **Groovy/Terraform not parseable** — see per-repo notes)

### 2. Function, Class & LOC Count Verification

Cross-check Breeze totals against the ndjson static analysis file (`<repo>-project-analysis.ndjson`, from the `projectMetaData` record).

| Metric    | Breeze | ndjson |
| --------- | ------ | ------ |
| Files     |        |        |
| Functions |        |        |
| Classes   |        |        |
| LOC       |        |        |

If no ndjson is available, note that and confirm counts are plausible for the repo size.

### 3. LOC Delta Investigation

Investigate any gap between Breeze LOC and raw `wc -l`.

- Identify major drivers (auto-generated/vendored files, generated `ts-force` entities, blank lines, parser methodology)
- Confirm delta is expected and not a data quality issue

### 4. Intentional Exclusions

Confirm and document files/directories that Breeze intentionally skips:

- Angular UI: HTML, SCSS/CSS templates
- Tests & fixtures: `test/` dirs, `.spec.ts`/`.feature` (Cucumber/SpecFlow), `test-data/`, mocks
- Vendored/generated: `node_modules`, vendored JS (e.g. `ltxml.js`/`openxml.js`), `OpenXmlPowerTools`, generated migration snapshots, `.njk` Nunjucks templates
- **Unsupported languages:** Groovy (`classic-spec-reader`), Terraform/HCL (`nimbus-scripts`)
- Data/asset artifacts: `.docx`, `.xlsx`, `.csv`, `.jsonl`, `.db`, `.mdf`, `.bdb`, fonts (`.TTF`/`.FON`), `.zip`, `.lic`

### 5. Ghost File Detection

Identify file nodes in the Breeze graph that no longer exist on disk.

- Paginate all Breeze file paths via `Get_Code_Nodes_By_Label`
- Check each path against the current repo on disk
- If ghosts found: determine whether a clean re-index is needed (merge vs. replace)
- After re-index: re-query each ghost path and confirm `total: 0`

### 6. Ghost File Root Cause Analysis (if ghosts found)

- Determine whether prior re-index was a **merge** (adds without pruning) or a **replace** (fresh)
- Confirm a clean re-index resolves all stale nodes

### 7. Final Ontology Completeness Check *(mandatory)*

Verify all files, classes, functions, and statements required for the code ontology are indexed.

- Query Breeze for File, Class, Function, and Statement node counts
- Cross-reference against ndjson snapshot (if available)
- Confirm intentional exclusions are documented
- Note any gaps beyond what Breeze's parser intentionally skips

**On completion:** create or update the verdict file `mds/<repo-name>.md` and record the outcome in `mds/audit-checks.md`.

---

## Summary Table (fill in per repo)

| Check                         | Status | Finding |
| ----------------------------- | ------ | ------- |
| File count coverage           |        |         |
| Function count                |        |         |
| Class count                   |        |         |
| LOC delta                     |        |         |
| Intentional exclusions        |        |         |
| Ghost files                   |        |         |
| Ontology completeness         |        |         |

---

## Repo Quick Reference (hubexo / Nimbus workspace)

| Repo | Path | Languages (indexed) | Key exclusions / notes |
| ---- | ---- | ------------------- | ---------------------- |
| `nimbus-api` | `nimbus-api/` (Nx under `nx/`) | TS (Angular, NestJS, Express) | HTML, SCSS (Angular templates/styles); `.feature`, `e2e`; `nimbus-spec-import` uses **XSLT (not parsed)**. **Huge — audit per Nx app/lib.** |
| `nimbus-document-import` | `nimbus-document-import/` | TS (spec-parser, json-importer), C# (xml-parser) | **Groovy `classic-spec-reader` NOT indexed**; test dirs, `test-data/`, XSD/XML fixtures |
| `nimbus-publishing-engine` | `nimbus-publishing-engine/` | C# / .NET | Vendored `OpenXmlPowerTools`; SpecFlow `.feature`; fonts (`.TTF`/`.FON`), `.lic`, `.zip` bundles |
| `nbs-docx-helper` | `nbs-docx-helper/` | TS | Vendored JS (`ltxml.js`, `ltxml-extensions.js`, `openxml.js`); `.docx` fixtures |
| `nimbus-salesforce-sync` | `nimbus-salesforce-sync/` | TS | `ts-force`-generated `entities/` (tag as generated); `tests/`, `.db`/`.txt` data, `.njk` templates |
| `hubspot-tools` | `hubspot-tools/` | TS (CLI + Next.js) | Next.js HTML/CSS; `output/` data (`.db`/`.jsonl`/`.csv`/`.xlsx`); generated `ts-force` entities |
| `nimbus-tools` | `nimbus-tools/` | TS (majority), C#, Python, SQL | **Per-tool monorepo — audit each subfolder.** `archive/` (retired); data artifacts (`.docx`/`.xlsx`/`.mdf`/`.bdb`) |
| `nimbus-glenigan-project-match-prototype` | `nimbus-glenigan-project-match-prototype/` | TS (NestJS/Nx) | `packages/` (empty); CSV/`output.*` data; prototype (low volume) |
| `import-glenigan-ids` | `import-glenigan-ids/` | Python | Single script; `poetry.lock`. Tiny — expect ~1 file |
| `nimbus-scripts` | `nimbus-scripts/` | YAML, Python, Docker (config only) | **Terraform/HCL NOT parsed** — expect near-zero code nodes; infra repo, low audit value |
