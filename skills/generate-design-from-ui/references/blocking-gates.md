# Blocking Gates — Generate Design from UI

## What are Blocking Gates?

**Blocking gates** are mandatory checkpoints that **MUST** be completed before proceeding. They prevent data corruption, duplicate nodes, and registry inconsistencies. Each gate is marked with ⛔ in the main skill flow.

**NEVER skip a blocking gate** — even in `auto` mode, even to "save time", even if you think you "already did it." These gates exist because AI agents consistently forget these steps after processing several scenarios.

---

## Gate 1: Non-Human Outcome Blocklist

**Location:** Step 2a-pre (before scenario selection)

**Purpose:** Prevent processing System/External System persona scenarios (they have no UI).

**Steps:**
1. Call `Get_all_personas(uuid)`
2. Identify non-human personas: `System`, `External System`
3. For each non-human persona: call `Get_all_outcomes_for_a_persona_id(uuid, personaId)`
4. Collect all outcome IDs into `blockedOutcomeIds` set
5. Log: `"Blocklist built: {N} non-human outcome(s) from {M} non-human persona(s) will be excluded"`

**Verification:**
- `blockedOutcomeIds` set must exist before ANY scenario is fetched
- If `Get_all_personas` returned zero → STOP and tell user to populate functional graph

**Usage:**
- Check every scenario's `outcomeId` against this set
- If `outcomeId IN blockedOutcomeIds` → skip with message: `"Skipping '{scenarioName}' — belongs to non-human persona (no UI)"`

**Why this can't be skipped:**
Processing system personas wastes hours of compute and creates meaningless design nodes.

---

## Gate 2: Flow Discovery Evidence Block

**Location:** Step 3e (after flow discovery, before UI file reading)

**Purpose:** Prove you actually ran the greps and didn't default to "1 flow, 1 page" without evidence.

**Required Output:**
```
┌─── FLOW DISCOVERY EVIDENCE: "{scenarioName}" ───┐
│                                                   │
│ TARGET ROUTE: /path/to/page                       │
│ TARGET FILES: src/pages/PageName/index.tsx        │
│                                                   │
│ TYPE A GREPS (entry-point flows):                 │
│   grep command: <exact command run>               │
│   hits: <N> results                               │
│   entry points found:                             │
│     1. <sourcePage> → <targetRoute> (via <Link>)  │
│     2. <sourcePage> → <targetRoute> (via navigate) │
│   classification: <N> distinct flows              │
│                                                   │
│ TYPE B GREPS (on-page branching):                 │
│   grep command: <exact command run>               │
│   hits: <N> results                               │
│   branching patterns found:                       │
│     1. <pattern> → <separate flow? yes/no + why>  │
│   classification: <N> additional flows            │
│                                                   │
│ PAGE NAV GREPS (multi-page detection):            │
│   grep command: <exact command run>               │
│   hits: <N> results                               │
│   outbound links found:                           │
│     1. <targetPage> (via navigate/Link)           │
│   classification: <N> pages per flow              │
│                                                   │
│ FINAL: <N> flows, <N> pages                       │
│ EVIDENCE: grep-confirmed / citation-confirmed     │
└───────────────────────────────────────────────────┘
```

**Rules:**
1. **Every field must be filled** — no placeholders, no "N/A", no "skipped"
2. **Grep commands must be real** — fabricating results is worse than skipping
3. **If using citations** (Step 3a Option 1), replace grep commands with citation file paths, but still show Type A/B/page-nav patterns found
4. **If flows=1 AND pages=1**, add: `SINGLE-FLOW JUSTIFICATION: <why no other entry points or branching>`

**Verification:**
- Read your own response — is the evidence block present?
- If missing → STOP, go back to Step 3b

**Why this can't be skipped:**
After processing 10+ scenarios, AI agents start inferring flow counts instead of actually searching the code. This evidence block makes skipping visible.

---

## Gate 3: Component Registry Pre-Upsert Update

**Location:** Step 6d (after building payload, before bulk upsert)

**Purpose:** Add new components to registry BEFORE creating them in the graph, enabling next scenario to deduplicate.

**Steps:**
1. **Read** `existingcomponents.json`
2. For each NEW component in current scenario's payload:
   ```json
   "ComponentName": {
     "designSystemRef": "ds-ref",
     "scope": "SCOPE",
     "id": "<generated-unique-id>",
     "supportingComponents": ["ChildA", "ChildB"]
   }
   ```
3. Add under appropriate type key: `ATOM`, `MOLECULE`, `ORGANISM`, `TEMPLATE`
4. **Write** file back
5. **Verify** write succeeded (read file, check size increased)

**Verification Before Proceeding:**
- File updated? YES → proceed to Step 6g
- File updated? NO → STOP and fix

**Why before bulk upsert:**
If bulk call fails, the next retry/scenario still sees these components. If you update AFTER bulk upsert, a failure leaves registry stale.

**Why this can't be skipped:**
This is the **most commonly forgotten step**. Symptoms:
- Duplicate components in design graph
- Components marked "new" that should be "reused"
- `existingcomponents.json` stuck at early state with few entries

**Self-check prompt (run mentally before EVERY scenario):**
> "Have I updated existingcomponents.json since the last Bulk_Update_Design_Nodes call? If NO → do it NOW."

---

## Gate 4: Flow Count Validation

**Location:** Step 6f (after building payload, before preview/upsert)

**Purpose:** Catch "lazy flow discovery" where you defaulted to 1 flow / 1 page without evidence.

**Validation Rules:**

| Condition          | Action                                                                 |
|--------------------|------------------------------------------------------------------------|
| flows=1, pages=1   | ⛔ REQUIRES `SINGLE-FLOW JUSTIFICATION` in Step 3e evidence block     |
|                    | If justification missing → STOP, go back to Step 3b, run the greps    |
| flows=1, pages>1   | ✅ OK — single flow can span multiple pages                            |
| flows>1            | ✅ OK — multiple flows discovered from grep evidence                   |
| flows=0            | ⛔ ERROR — every scenario must have at least 1 flow                    |

**In `auto` mode:**
If validation fails, log warning and **re-run Step 3b greps** for this scenario rather than skipping. The goal is accuracy, not speed.

**Self-check question:**
> "Am I reporting 1 flow / 1 page because I actually grepped and found no branching, or because I skipped the greps? If I skipped → go back NOW."

---

## Gate 5: Registry Disk Persistence Post-Upsert

**Location:** Step 6h (after bulk upsert succeeds)

**Purpose:** Persist Flow and Page IDs to disk so future sessions can reuse them.

**Steps for Flow Registry:**
1. **Read** `existingflows.json` from disk
2. For each new flow in the payload, fetch its real ID from bulk upsert response (or query `Design_Graph_Search`)
3. Add/update entry keyed by `"{name}|{modality}"`:
   ```json
   "Login|WEB": {
     "id": "<real-uuid>",
     "stepIds": ["step-1", "step-2"],
     "modality": "WEB"
   }
   ```
4. **Write** `existingflows.json` back to disk
5. **Verify** write succeeded

**Steps for Page Registry:**
1. **Read** `existingpages.json` from disk
2. For each new page in the payload, fetch its real ID
3. Add/update entry keyed by `"{name}|{pageType}|{modality}"`:
   ```json
   "Dashboard|dashboard|WEB": {
     "id": "<real-uuid>",
     "stepIds": ["step-3"],
     "pageType": "dashboard"
   }
   ```
4. **Write** `existingpages.json` back to disk
5. **Verify** write succeeded

**Why IDs matter:**
- **Flows/Pages**: When reused, call `Update_Design_Node(nodeId, data: { stepIds: [...] })` to append new stepIds — requires real UUID
- **Components**: Reuse via `designSystemRef` in bulk payload — backend deduplicates automatically, no ID needed

**Why this can't be skipped:**
These files survive across Claude Code sessions. If you skip disk persistence, the next batched session loses all reuse data.

---

## Gate 6: Component Registry MCP Sync Post-Upsert

**Location:** Step 6h-post (after bulk upsert and Flow/Page registry updates)

**Purpose:** Update component registry with real MCP IDs and confirmed metadata.

**Steps:**
1. Fetch newly created components:
   ```
   Get_all_Design_By_Label(uuid, label: "Component", page: "1", limit: "50")
   ```
   (paginate if needed)
2. For each component in response, update corresponding entry in `existingcomponents.json`:
   - Real MCP UUID (`id`)
   - Confirmed `designSystemRef`
   - Confirmed `scope`
   - Confirmed `supportingComponents`
3. **Write** file back
4. **Read** file back and verify it contains expected component count

**Verification Before Next Scenario:**
Mentally confirm:
1. ✅ existingcomponents.json updated in Step 6d
2. ✅ existingcomponents.json synced from MCP in Step 6h-post
3. ✅ File contains all components from this scenario

If ANY checkbox is unchecked → STOP and fix.

**Why this can't be skipped:**
Pending/placeholder IDs are unreliable for cross-scenario deduplication. Next scenario's reuse resolution depends on accurate, MCP-sourced data.

---

## Gate 7: Scenario Processed Marker

**Location:** Step 6i (after all registries updated)

**Purpose:** Mark scenario as complete so it won't be reprocessed.

**Steps:**
```
Update_Functional_Node(
  uuid: <projectUuid>,
  label: "Scenario",
  id: <scenario UUID>,
  data: { "isDesignGenerated": true },
  citationId: [0],
  citations: [{ "type": "document", "name": "skip", "inputText": "skip" }]
)
```

**Why this must be last:**
Only mark complete after ALL registries are updated. If you mark complete but registries are stale, the scenario appears "done" but produced incomplete/corrupt data.

---

## Per-Scenario Checklist

Before moving to next scenario, verify ALL boxes checked:

```
⛔ PER-SCENARIO CHECKLIST (verify ALL before next scenario):
  □ Flow & page discovery greps executed (Type A + Type B + page nav)
  □ existingcomponents.json updated with new components (Step 6d)
  □ Bulk_Update_Design_Nodes called (Step 6g)
  □ existingcomponents.json synced from MCP with real IDs (Step 6h-post)
  □ Flow & Page registries updated AND written to disk (Step 6h)
  □ Scenario marked as processed (Step 6i)
  
If ANY box unchecked → DO NOT proceed to next scenario.
```

---

## Auto Mode Clarification

**❌ "Auto mode" does NOT mean "skip blocking gates"**

It means:
- ✅ Skip per-scenario user confirmation (Step 6f-post)
- ✅ Log progress instead of asking "shall I continue?"
- ✅ On error: log and skip scenario (don't stop entire batch)

It does NOT mean:
- ❌ Skip flow discovery
- ❌ Skip evidence blocks
- ❌ Skip registry updates
- ❌ Skip verification steps

**Auto mode is "autonomous execution with all safety checks intact"**, not "fast and loose mode."

---

## What Happens When You Skip a Gate

| Gate Skipped | Immediate Effect | Downstream Effect |
|--------------|------------------|-------------------|
| Gate 1 (blocklist) | Process system personas | Wasted compute, meaningless design nodes |
| Gate 2 (evidence) | Default to 1 flow/1 page | Shallow, inaccurate design graph |
| Gate 3 (pre-upsert) | Registry not updated | Next scenario creates duplicates |
| Gate 4 (validation) | Accept invalid flow counts | Incomplete flow/page discovery |
| Gate 5 (disk persist) | IDs not saved | Next session loses reuse data |
| Gate 6 (MCP sync) | Stale IDs in registry | Cross-scenario deduplication breaks |
| Gate 7 (mark complete) | Scenario reprocessed | Duplicate design nodes on retry |

**Cumulative effect:** After skipping gates on 5-10 scenarios, the design graph becomes a mess of duplicates, shallow flows, and broken linkages. Cleanup requires manual intervention or re-running from scratch.

---

## Recovery Procedures

### If you realize you skipped a gate mid-batch:

1. **STOP processing new scenarios**
2. **Identify which scenarios were affected** (check logs)
3. **For each affected scenario:**
   - If Gate 3/6 skipped: manually update registries from MCP
   - If Gate 2/4 skipped: re-run flow discovery
   - If Gate 5 skipped: query MCP for real IDs and update disk files
4. **Verify registries are now correct**
5. **Resume processing**

### If you discover corruption after batch completes:

1. **Query the design graph** for duplicates (same `designSystemRef` with different IDs)
2. **Check registry files** for missing/stale entries
3. **Either:**
   - Merge duplicates manually via MCP tools
   - Mark affected scenarios as `isDesignGenerated=false` and reprocess
   - Start fresh with corrected registry files

---

## Gates Are Not Negotiable

These gates represent **hard-learned lessons** from production usage. Every gate exists because skipping it caused data corruption in real projects.

**If a gate feels unnecessary:** It's not. You're about to make the same mistake that led to adding the gate in the first place.

**If you're tempted to skip "just this once":** The registry files and design graph don't care about your intentions. Corruption accumulates silently until the graph is unusable.

**If execution feels slow because of gates:** Good. Slow and correct beats fast and broken. If speed is critical, use `generate-design` instead (no UI reading, faster execution, less accurate output).
