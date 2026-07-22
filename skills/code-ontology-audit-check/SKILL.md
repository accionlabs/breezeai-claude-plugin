---
name: code-ontology-audit-check
description: Run a full Breeze code ontology audit for one or all repos. Checks file coverage, function/class/LOC counts, intentional exclusions, and ghost files. Use when validating a repo's code graph completeness.
---

# Breeze Audit Checks

Run a full Breeze code ontology audit for one or all repos.

## Usage

`/code-ontology-audit-check [repo-name]`  
If no repo is specified, audit all repos in sequence.

---

## Conventions

- **Frontend repos** (`source-platform`, `source-web`): HTML and CSS/SCSS files are **not indexed** by Breeze — intentional. Only TS, JS, JSON, MD, YAML, and similar code-bearing files count.
- **Each audit must end with the Final Ontology Completeness Check** (step 7 below).
- After completing an audit, **create a verdict file** named after the repo (e.g. `source-platform.md`) in the `mds/` folder, and **update `mds/audit-checks.md`** with the results.

---

## Checks to Perform (for each repo)

### 1. Code Ontology Coverage

Compare Breeze-indexed file count against actual files on disk.

- Paginate `Get_Code_Nodes_By_Label` (label=`File`) to get total indexed file count
- Run `find <repo>/ -type f` on disk, filtered to indexable types (TS, JS, MJS, JSON, YAML, MD, Docker)
- Explain any delta (HTML/SCSS excluded for frontend; test dirs excluded for backend)

### 2. Function, Class & LOC Count Verification

Cross-check Breeze totals against the ndjson static analysis file (if available).

| Metric    | Breeze | ndjson |
| --------- | ------ | ------ |
| Files     |        |        |
| Functions |        |        |
| Classes   |        |        |
| LOC       |        |        |

If no ndjson is available (e.g. C# repos), note that and confirm counts are plausible for the repo size.

### 3. LOC Delta Investigation

Investigate any gap between Breeze LOC and raw `wc -l`.

- Identify major drivers (auto-generated files, blank lines, parser methodology)
- Confirm delta is expected and not a data quality issue

### 4. Intentional Exclusions

Confirm and document files/directories that Breeze intentionally skips:

- Frontend repos: HTML, SCSS/CSS templates
- Backend repos: `test/` directory, `.njk` Nunjucks templates (notifications), auto-generated migration snapshots

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

## Repo Quick Reference

| Repo               | Path                  | Key exclusions                            |
| ------------------ | --------------------- | ----------------------------------------- |
| `source-platform`  | `source-platform/`    | HTML, SCSS (Angular templates/styles)     |
| `source-web`       | `source-web/`         | HTML, SCSS (Angular templates/styles)     |
| `source-catalogue` | `source-catalogue/`   | `test/` directory                         |
| `notifications`    | `notifications/`      | `.njk` Nunjucks templates, `test/`        |
