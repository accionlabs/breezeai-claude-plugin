---
name: design-analysis
description: >
  Analyze UI/UX design requirements and map them to the design graph
  (Atom, Molecule, Organism, Template, DesignPage). Accepts text
  requirements, Jira links, Figma URLs, or frontend repo scanning as input.
  Searches existing design nodes, identifies create vs update actions,
  and syncs to Jira. Use when: "analyze design", "update design graph",
  "add components from Figma", "scan frontend for design nodes".
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

## Instructions

### Step 1: Gather Design Input

Ask the user how they want to provide the design requirement. Present these options:

1. **Text requirement** — describe the UI components, pages, or layouts needed
2. **Jira link** — provide a Jira issue URL or key to extract requirements
3. **Figma URL** — provide a Figma frame URL to extract design components
4. **Scan frontend repo** — scan the current working directory for existing frontend components

**If text requirement:**
- Collect the requirement text from the user
- Clarify any ambiguity — ask follow-up questions if component types, layout, or page structure are unclear
- Refine until user confirms the requirement is complete

**If Jira link:**
- Extract the issue key from the URL (e.g., `PROJECT-123` from `https://...atlassian.net/browse/PROJECT-123`)
- Call `getJiraIssue` to fetch the issue details (summary, description, acceptance criteria, attachments)
- Parse the requirement from the issue description and any linked child issues or subtasks
- Extract: UI expectations, page descriptions, user flows, component requirements, and acceptance criteria
- Clarify any ambiguity with the user if the Jira issue lacks sufficient UI detail

**If Figma URL:**
- Extract `fileKey` and `nodeId` from URL format: `figma.com/design/:fileKey/:fileName?node-id=:nodeId`
- Convert `-` to `:` in nodeId
- Call Figma MCP tool (`get_design_context`) with fileKey and nodeId to fetch the frame
- Review the screenshot and generated code
- Extract: page purpose, navigation structure, data displays, user actions, interactive elements, layout zones

**If scan frontend repo:**
- Use Glob to find component files (e.g., `**/*.tsx`, `**/*.jsx`, `**/*.vue`, `**/*.svelte`)
- Read key component files to understand the existing component library
- Identify pages, layouts, organisms, molecules, and atoms from the file structure and code
- Present a summary of discovered components for user confirmation

### Step 2: Identify Design Nodes

From the gathered input, decompose the requirement into design graph nodes following atomic design methodology. Refer to `references/guide.md` for the full data model and identification rules.

Classify each component into one of 5 labels (bottom-up order):

| Label | What it is | Examples |
|-------|-----------|----------|
| **Atom** | Smallest UI primitive, no children | Button, Input, Icon, Badge, Avatar, Checkbox |
| **Molecule** | Group of atoms working together | Search bar, Form field, Card, Menu item, Stat card |
| **Organism** | Complex group of molecules/atoms | Header, Sidebar, Data table, Modal, Form section |
| **Template** | Page layout skeleton with zones | Dashboard layout, Detail layout, Form layout |
| **DesignPage** | Full page with route & data sources | Analytics page, Settings page, User profile page |

For each identified node, populate the metadata fields defined in the guide:
- `name` — unique, descriptive component name
- `category` — from the allowed values for that label
- `description` — human-readable summary
- All other label-specific fields (props, events, slots, zones, route, etc.)

Present the identified nodes in a table grouped by label (DesignPage → Template → Organism → Molecule → Atom) for user review.

### Step 3: Search Existing Design Nodes

For each identified node, search the existing design graph to check if it already exists.

Use `Design_Graph_Search` with `uuid` = projectUuid and `parameters0_Value` = a relevant search query based on the identified node names and descriptions. This returns matching nodes across all labels at once.

If more granular lookup is needed, use `Get_all_Design_By_Label` with `uuid` = projectUuid and `label` = the specific label (Atom, Molecule, Organism, Template, DesignPage) to fetch all existing nodes of that type.

Compare each identified node against existing nodes:
- **Match by name** (exact or semantically equivalent)
- If a match is found → mark as **UPDATE** (note the existing node `id`)
- If no match → mark as **CREATE**

### Step 4: Present Action Plan

Show the user a clear action plan in tabular format:

**Nodes to CREATE:**

| # | Label | Name | Category | Description |
|---|-------|------|----------|-------------|
| 1 | Atom | ... | ... | ... |

**Nodes to UPDATE:**

| # | Label | Name (existing ID) | Fields to Update | Reason |
|---|-------|---------------------|-----------------|--------|
| 1 | Organism | ... (id: xxx) | props, slots | New props added from requirement |

**Parent-Child Relationships:**
Show which atoms compose into molecules, molecules into organisms, etc.

Ask user: **"Do you confirm creating X nodes and updating Y nodes? Any changes?"**

Incorporate user feedback. Repeat until user confirms.

### Step 5: Create/Update Design Nodes

After user confirmation, execute mutations in bottom-up order (children before parents so IDs are available for linking):

1. **Create/Update Atoms** — use `Create_Design_Node` (label: `Atom`) or `Update_Design_Node`
2. **Create/Update Molecules** — link `atomIds` to created/existing atom IDs
3. **Create/Update Organisms** — link `moleculeIds` and `atomIds`
4. **Create/Update Templates** — link `organismIds`, `moleculeIds`, `atomIds`
5. **Create/Update DesignPages** — link `templateIds`, `organismIds`, etc.

For each create call, use:
- `uuid` = projectUuid from `.breeze.json`
- `apiKey` = apiKey from `.breeze.json`
- `label` = the node type (Atom, Molecule, Organism, Template, DesignPage)
- `data` = the metadata object with all populated fields

For each update call, additionally pass:
- `id` = the existing node ID

Report success/failure for each node created or updated.

### Step 6: Jira Sync

After design graph updates are complete, ask the user:

**"Would you like to update Jira with the design changes?"**

If user confirms:

**If new components were created:**
- Ask user for the Jira project key if not already known
- Create a new Jira ticket for each significant new component (or one ticket grouping related components)
- Set summary: "Design Component: [component name]"
- Set description with: component type, category, props, parent/child relationships, and any Figma URL
- Suggest appropriate issue type (Task or Story)

**If existing components were updated:**
- Ask if there is an existing Jira ticket to update
- If yes, add a comment summarizing what fields were changed and why
- If no, create a new ticket documenting the update

If user declines, skip Jira sync.

## Output Format

Present analysis results using this structure:

**Design Analysis: [Requirement/Frame Name]**

**1. Input Summary**
Source (text/Jira/Figma/repo scan) and key findings.

**2. Component Inventory**

| Label | Name | Category | Status (New/Existing) |
|-------|------|----------|-----------------------|
| DesignPage | ... | ... | New |
| Template | ... | ... | Existing (update) |
| Organism | ... | ... | New |
| Molecule | ... | ... | Existing (no change) |
| Atom | ... | ... | New |

**3. Parent-Child Composition**
```
DesignPage: [page name]
  └─ Template: [template name]
       └─ Organism: [organism name]
            ├─ Molecule: [molecule name]
            │    └─ Atom: [atom name]
            └─ Atom: [atom name]
```

**4. Action Summary**
Nodes created, updated, and skipped. Jira tickets created/updated.
