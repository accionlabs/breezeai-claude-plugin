# DataLake schema ingestion — DDL & Elasticsearch

How to populate the **schema nodes that hang beneath a DataLake**: `DDLTable → DDLColumn`,
`DDLConstraint`, `DDLIndex`, `DDLView`, `DDLProcedure`, `DDLSequence`, and the ES family
`ESIndex → ESField` / `ESAlias`.

Read this before Phase 5 whenever the source tree contains `.sql` files or ES mapping JSON.

---

## 1. The decision that matters most

There are **two write paths** and they are NOT interchangeable. Picking wrong costs hours
and produces a graph with no relationships.

| | `POST /db-ontology/stream-ingest` (bulk) | `Create_DB_Schema_*` (MCP, per object) |
|---|---|---|
| Tables / columns / indexes / views | ✅ | ✅ |
| PK / UNIQUE constraints | ✅ | ✅ |
| **FK `REFERENCES` edges** | ✅ | ❌ **impossible** — no target-table input |
| Derived `columnCount` / `hasPrimaryKey` / `isForeignKey` / `isIndexed` | ✅ correct | ⚠ wrong if the run is partial |
| **Procedures / functions / triggers** | ❌ parser returns `[]` | ✅ |
| CHECK constraints | ❌ dropped | ✅ |
| Requests for a ~5,000-object schema | **~8** | ~5,500 |
| Measured wall-clock (255 tables / 3k columns) | **17 s** | ~10 h, stalled at 10% |

**Therefore: always hybrid.**

```
tables · columns · indexes · constraints · views   →  stream-ingest   (bulk)
procedures · functions · triggers                  →  POST /db-ontology/procedure
```

> ⚠ **Never loop `Create_DB_Schema_Column`.** Each column write triggers a server-side
> `refreshTable` that re-reads the table and **re-embeds it plus every column already
> attached** — O(n²). 3,029 columns ⇒ ~32,563 embedding operations (10.8×). This is what
> makes the per-object path stall, and it can take the backend pod down.

MCP is still the right tool for **reads, the DataLake node itself, and cleanup**:
`Create_Architecture_Node`, `Get_DB_Schema_Nodes_By_Label`, `Delete_Architecture_Node`.

---

## 2. Auth — an API key IS required

Bulk ingest is REST, not MCP, so it needs `apiKey` from `.breeze.json`:

```
api-key: <apiKey>          # never echo or log it
```

If `.breeze.json` has no `apiKey`, prompt once with the standard wording (generate at
`<uiBaseUrl>/mcp/generate/key`), save it, and reply only "API key saved."

---

## 3. Preprocessing — make the DDL bare and explicitly separated

**The rule is dialect-neutral.** The parser reads *bare, `;`-separated* DDL. Real-world `.sql`
trees rarely ship that way — migration scripts wrap DDL in idempotency guards and procedural
blocks, and some dialects separate statements with something other than `;`. Untreated, the
parser silently returns `tables=0`.

**First: diagnose, don't assume.** Upload one representative file as-is. If it returns objects,
skip this section entirely. If it returns `tables=0` or `422`, apply the transforms below and
re-test on the same file before batching.

### The two failure classes

**(a) Wrapped DDL** — the `CREATE` sits inside a conditional/procedural block, so the parser
never sees it. Idioms by dialect:

| Dialect | Guard idiom |
|---|---|
| T-SQL / SQL Server | `IF NOT EXISTS (SELECT … ) BEGIN <ddl> END`, `IF OBJECT_ID(…) IS NULL BEGIN … END` |
| PostgreSQL | `DO $$ BEGIN … END $$;`, `CREATE OR REPLACE FUNCTION … $$ … $$` |
| Oracle / PL-SQL | `BEGIN EXECUTE IMMEDIATE '<ddl>'; EXCEPTION WHEN … END;` |
| MySQL / MariaDB | `DELIMITER $$ … $$ DELIMITER ;` around routines |
| Any | DDL built as a **string** and `EXEC`/`EXECUTE IMMEDIATE`-ed at runtime |

**(b) Missing separators** — statements delimited by newline, a batch marker (`GO`), or a
custom `DELIMITER` rather than `;`. The parser then reads the file as one unparseable blob.

### The transforms

Apply in order, then re-test:

1. **Strip comments** — `/* … */` and `-- …`. (This also drops DDL that is commented out at
   source — a correct exclusion, not a failure.)
2. **Unwrap guards** — replace `<guard> BEGIN <ddl> END` with `<ddl>`, matching `BEGIN`/`END`
   with a nesting-aware scan (blocks nest). **Leave guards with no block alone** — e.g.
   `IF EXISTS (…) DROP …` is a single guarded statement, not a wrapper.
3. **Drop procedural noise** left behind — `PRINT`/`RAISE NOTICE` lines, batch markers
   (`GO`, `/`, `DELIMITER …`), and orphaned `END`s.
4. **Normalise separators** — ensure a `;` terminates each statement. Where the dialect relies
   on newline or batch markers, insert `;` before each line-initial DDL/DML keyword
   (`CREATE` / `ALTER` / `DROP` / `INSERT` / `UPDATE` / `DELETE` / `EXEC` / `GRANT`).
   **This is usually the step that unlocks a stubborn file.**

> **DDL built at runtime (string-concatenated + `EXEC`) cannot be recovered statically.** Skip
> it and note it — the objects it creates exist only in a live database. See §8.

### Non-negotiable: the transforms must be no-ops on clean input

Verify this whenever you adjust them. Plain `CREATE TABLE`, Postgres
`CREATE TABLE IF NOT EXISTS foo (…)` (a DDL *clause*, not a guard — easily broken by a careless
unwrapper), and guarded `DROP` must all pass through **byte-identical**. If a transform rewrites
already-valid DDL, it is wrong.

**Measured effect on one real guarded T-SQL tree:** 0 → 11/11 files parsed, with columns *and*
indexes.

---

## 4. Batching — the 10-hour → 17-second change

`stream-ingest` accepts **one `.sql` per request** (a second file returns
`400 "Only one .sql file may be uploaded at a time."`) — but the parser handles **unlimited
statements per file**.

So concatenate. ~110 source files per upload:

```
for each file:  preprocessed text + "\n;\n"   → append to current batch
when batch has 110 files → POST it as one .sql
```

| | Requests | Time |
|---|---|---|
| One file per request | 2,193 | ~10 h |
| Batched at 110 | **8** | **17 s** |

Same content, same endpoint. The cost was per-request overhead (parse setup, S3 write,
callback, embedding pass) × 2,193 — not the work itself.

**Always add a per-batch fallback:** if a batch returns non-202, retry its files
individually so one malformed statement cannot cost 110 tables.

> ⚠ **Dialect drift.** A large concatenated blob can lose the T-SQL signal — observed
> `newid()` normalised to `(UUID())`. Structure is unaffected; **defaults are not verbatim**.
> If defaults matter, keep `GO` markers or use smaller batches.

---

## 5. The requests

### 5.1 Bulk — tables, columns, indexes, constraints, views

```
POST {apiBase}/db-ontology/stream-ingest
Header: api-key: <key>
multipart/form-data:
  file           = <one preprocessed .sql>      (required, exactly one)
  projectUuid    = <uuid>
  dataLakeId     = <id of an EXISTING DataLake node>   ← create it first
  repositoryName = <label>                      (optional)
```

Accepted MIME: `application/sql`, `application/x-sql`, `text/x-sql`, `application/json`,
`text/json`, `text/plain`, `application/octet-stream`. Max 200 MB.

Returns **202** with a parse receipt — treat the counts as your validation:

```json
{"success": true, "dialect": "transactsql",
 "tableCount": 110, "viewCount": 0, "procedureCount": 0,
 "indexCount": 204, "s3Key": "db-ontology/…ndjson.gz"}
```

**It is asynchronous.** 202 means *parsed and queued*: COG writes NDJSON to S3, calls back
`/db-ontology/stream-ingest-s3`, and the backend ingests with batched `UNWIND` Cypher.
Nodes appear **~10 s later**. Verify by reading the graph, not by the 202.

- `tableCount: 0` with 202 → parsed nothing (preprocessing failed)
- `422` → no DDL objects extracted at all

### 5.2 Per-object — procedures, functions, triggers

The parser hardcodes `procedures: []` for **every** dialect, so bulk drops all of them.
Parse them yourself and POST one at a time (concurrency 6–8 is safe — no `refreshTable`
cascade on this path):

```
POST {apiBase}/db-ontology/procedure
Header: api-key: <key>
{ "projectUuid", "dataLakeId", "name",
  "procedureType": "procedure" | "function" | "trigger",
  "schema": "dbo", "parameters": [ "@ID uniqueidentifier", … ],
  "returnType": "bit",            // functions
  "body": "<see the truncation rule below>",
  "repositoryName": "…" }
```

**Extracting routines:** match `CREATE (PROCEDURE|PROC|FUNCTION|TRIGGER)` with an optional
bracketed schema (`[dbo].[spX]`), then:

- **Skip matches inside string literals.** `set @Command = @Command + 'Create Trigger dbo.' + @NAME`
  is a *generator*, not DDL. Check for an odd number of `'` between line-start and the match.
- **`body` is capped at 1000 chars server-side.** A naive `text[:1000]` on a proc with a long
  signature stores **100% parameters and 0% logic** (a 41-param proc's signature runs to
  char 2,016 of 11,433). **Slice from the `AS` keyword onward** and prepend a one-line
  signature summary, so the stored window carries behaviour and the `exec`/function calls that
  give proc→proc lineage.

### 5.3 Elasticsearch

Same `stream-ingest` endpoint — upload the **mapping JSON** instead of `.sql`; the backend
classifies it and routes to the ES analyzer. Produces `ESIndex → ESField` (self-nesting via
`HAS_SUB_FIELD` for nested/multi-fields) and `ESAlias`.

---

## 6. Parser coverage — what silently vanishes

| Object | Bulk parser | Note |
|---|---|---|
| TABLE, COLUMN, INDEX, VIEW | ✅ | |
| PRIMARY KEY / FOREIGN KEY / UNIQUE | ✅ | FK edge only on this path |
| `ALTER TABLE … ADD COLUMN` | ✅ | |
| **CHECK constraint** | ❌ | table parses, constraint dropped, no error |
| **PROCEDURE / FUNCTION / TRIGGER** | ❌ | hardcoded `[]` — use §5.2 |
| **SEQUENCE** | ❌ | use `Create_DB_Schema_Sequence` if present |

**Known parser bug:** `nullable` may come back `false` for **every** column (the analyzer
treats an explicit `NULL` as `NOT NULL`). If the deployed parser still has it, either fix it
upstream or backfill `nullable` from source DDL afterwards. Check one known-nullable column
before trusting the field.

---

## 7. Attribute rules that bite

- **`dataType` is decomposed, not raw.** `nvarchar(150)` → `dataType=NVARCHAR` + `length=150`;
  `decimal(18,4)` → `precision=18`, `scale=4`. Sending the raw string leaves length null.
- **`indexType` enum is `BTREE|BITMAP|FUNCTION_BASED|DOMAIN`** — SQL Server
  clustered/nonclustered has nowhere to go; flatten to `BTREE` and note the loss.
- **`parameters` is asymmetric** — POST an array, the node stores a JSON *string*.
- **Index `columns[]` order is semantic** (covering-index prefixes) — preserve it.
- **Derived fields** (`columnCount`, `hasPrimaryKey`, `isForeignKey`, `isIndexed`) — never
  send; they are recomputed per child write.
- **`DataLake.type`** (`Relational` | `Elastic` | `Non-Relational`) is **required at create
  and immutable after** — changing it would orphan every attached schema node.

---

## 8. One DataLake per PHYSICAL database

Not per schema, not per logical grouping. Detect multiple databases from the code:

- a second connection string (e.g. `ArchiveConnectionString`) → a second DataLake
- read/write splits of the *same* database → still **one** DataLake

Some objects exist only at runtime and **cannot** be captured statically — audit/custom-field
companion tables whose columns are generated by a stored procedure, and views built by a
`spBuildAll*` routine. Ingest them as stubs and record a `comment` explaining that the live
database is wider. Do not treat the thin row count as a parsing failure.

---

## 9. Verify — never trust the 202

```
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="table"      )  → total
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="column"     )  → total
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="constraint",
    filters={"constraintType": {"$eq": "FOREIGN_KEY"}})          → FK edges exist?
Get_DB_Schema_Nodes_By_Label(data_lake_id, label="procedure"  )  → total
```

Sanity checks before declaring success:

- a known wide table reports the **right `columnCount`** and `hasPrimaryKey: true`
- **FK count > 0** (if the schema declares any) — proves the bulk path ran
- procedure count matches what you extracted
- a known-nullable column actually reads `nullable: true`

If a re-ingest is needed, prefer a **fresh DataLake** over reconciling a partial one:
derived fields on partially-written tables stay wrong until a complete pass, and the old
node can be deleted once the new one verifies.
