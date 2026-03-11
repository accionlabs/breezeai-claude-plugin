---
name: init
description: >
  Initialize or validate the Breeze workspace. Sets up .breeze.json
  with API key and project UUID, checks ontology readiness, and
  optionally uploads repo or documents. Use when: first time setup,
  "init breeze", "setup breeze", or when any Breeze tool fails with
  authorization errors.
---

## Prerequisites

Read `.breeze.json` from the project root. If it exists and contains
both `apiKey` and `projectUuid`, skip to **Step 3 — Ontology Status
Check**.

## Step 1 — API Key Setup

If `apiKey` is missing from `.breeze.json`:

1. Ask the user to generate an API key at:
   https://ai.accionbreeze.com/mcp/generate/key
2. Prompt: "Paste your Breeze API key."
3. Save the key to `.breeze.json`

Example `.breeze.json` after this step:

    {
      "apiKey": "<USER_API_KEY>"
    }

**Security:** Never print API keys in output. Store only in
`.breeze.json`. Ensure `.breeze.json` is in `.gitignore`.

## Step 2 — Project Linking

If `projectUuid` is missing from `.breeze.json`:

Ask: "Would you like to:
1. Select an existing project
2. Create a new project"

**Option 1 — Select existing:**

- Call `Call_List_Project_` with the apiKey
- Display the project list (name + UUID)
- User selects one → save `projectUuid` to `.breeze.json`

**Option 2 — Create new:**

- Ask for project name and description (optional)
- Call `Call_Create_Project_` with name, description, apiKey
- Save returned `projectUuid` to `.breeze.json`

Confirm: "Project linked successfully."

## Step 3 — Ontology Status Check

Call `Call_Get_Project_Details_` with uuid and apiKey.
Inspect the response for these status fields:

**Document Ontology:**

- `functionalMetricsGenerated`: none | inprogress | done | error
- `architectureMetricsGenerated`: none | inprogress | done | error

**Repository Graph:**

- `fileGraphStatus`: started | node_creation | relationship_creation
  | metadata_addition | active | error
- Ontology generation requires `fileGraphStatus = active`

**Ontology Status:**

- `funcOntologyStatus`: none | inprogress | done | error
- `arcOntologyStatus`: none | inprogress | done | error

## Step 4 — Report Status & Recommend Next Steps

Based on the status fields, report ONE of these:

**No artifacts at all:**
"Your project has no ontology data yet.
What would you like to upload? 1. Repository  2. Documents  3. Skip"

**fileGraphStatus != active:**
"Repository indexing in progress. Ontology generation available
once complete."

**fileGraphStatus = active AND funcOntologyStatus = none:**
"Repository graph ready. Generate ontology at:
https://ai.accionbreeze.com/ontology/{projectUuid}/functional"

**Any ontology status = inprogress:**
"Ontology generation is currently in progress."

**funcOntologyStatus = done:**
"Ontology is ready for queries."

## Step 5 — Artifact Upload (if user chooses)

**Repository upload:**

    npx github:accionlabs/breeze-code-ontology-generator \
      repo-to-json-tree \
      --repo <repo-path> \
      --out breezeai \
      --upload \
      --user-api-key <apiKey> \
      --uuid <uuid> \
      --baseurl https://isometric-backend.accionbreeze.com

**Document upload:**

    npx github:accionlabs/breeze-code-ontology-generator \
      upload-docs \
      --path <docs-path> \
      --uuid <uuid> \
      --user-api-key <apiKey> \
      --baseurl https://isometric-backend.accionbreeze.com

After upload, report:
"Upload complete. Artifact indexing has started.
Next: Generate ontology at
https://ai.accionbreeze.com/ontology/{projectUuid}/functional"
