---
name: setup-project
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

Also set the `apiBase` field (defaults to `https://isometric-backend.accionbreeze.com`):

    {
      "apiKey": "<USER_API_KEY>",
      "apiBase": "https://isometric-backend.accionbreeze.com"
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

## Step 2b — AWS Credentials (Optional)

If `awsAccessKey` and `awsSecretKey` are missing from `.breeze.json`:

Ask: "Do you have AWS credentials for Bedrock? (needed for code-to-functional graph generation)"

If yes:
1. Prompt for AWS Access Key ID and AWS Secret Access Key
2. Save to `.breeze.json`:

```json
{
  "awsAccessKey": "<ACCESS_KEY>",
  "awsSecretKey": "<SECRET_KEY>"
}
```

**Security:** Never print AWS credentials in output. Store only in
`.breeze.json`.

If no, skip — these can be added later when running
`/breeze:generate-functional-from-code`.

