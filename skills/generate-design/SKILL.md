---
name: analyze-design
description: >
  Generate design graph nodes (UserJourney, Flow, Page, Component) from
  functional graph. Maps Scenario→UserJourney, Step→Flow/Page, Action→Component.
  Use when: "create design from functional", "generate UI structure",
  "map functional to design graph".
---

## Reference

Consult `references/guide.md` for detailed mapping rules, component types, and payload structures.

## Design Graph Query Tools

Three tools are available for querying design graph nodes (see also Mutation Tools below):

### 1. Get_all_Design_By_Label

Gets all design nodes of a specific type with pagination.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`

**Use when:** You need to fetch all nodes of a specific type.

### 2. Design_Graph_Search

Semantic search across all design graph node types.

**Inputs:**

- `uuid` (required): Project UUID
- `query` (required): Search query string
- `limit` (optional): Number of results (default: 10)
- `skip` (optional): Offset for pagination (default: 0)
- `includeLabels` (optional): Filter by labels - `["UserJourney", "Flow", "Page", "Component"]`

**Use when:** You need to search for nodes by name, description, or any text content.

### 3. Get_Design_Nodes_by_Ids

Query design nodes with various filters. This is the most flexible query tool.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `queryParams` (optional): Query string for filtering

**Query Parameter Examples:**

| Use Case                         | Query Params                                     |
| -------------------------------- | ------------------------------------------------ |
| Get by specific ID               | `id=uj-123`                                      |
| Get by multiple IDs              | `id=uj-123&id=uj-456`                            |
| Get Flows by UserJourney         | `userJourneyId=uj-123`                           |
| Get Pages by Flow                | `flowId=flow-123`                                |
| Get Components by Page           | `pageId=page-123`                                |
| Get Components by parent         | `parentComponentId=comp-123`                     |
| Get Components by type           | `type=ORGANISM` or `type=MOLECULE` or `type=ATOM` |
| Get Pages by pageType            | `pageType=form` or `pageType=list`               |
| Get by modality                  | `modality=web` or `modality=mobile`              |
| Combine filters                  | `pageId=page-123&type=ORGANISM`                  |
| With pagination                  | `page=1&limit=50&sortName=name&sortOrder=asc`    |

**Use when:** You need to query nodes by specific relationships or properties.

## Design Graph Mutation Tools

### 4. Delete_Design_Node

Deletes a design node from the graph.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `apiKey` (required): API key from .breeze.json
- `nodeId` (required): The ID of the node to delete

**Use when:** You need to remove a design node from the graph.

**Confirmation Required:** Before deleting any node, ALWAYS ask the user for confirmation with:

1. **Node details:** Show the node name, type, and ID being deleted
2. **Reason:** Explain why this deletion is being performed
3. **Impact:** List any child nodes that will be orphaned

**Confirmation Format:**

```
⚠️ Delete Confirmation Required

Node to delete:
  - Name: <node name>
  - Type: <UserJourney|Flow|Page|Component>
  - ID: <nodeId>

Reason for deletion:
  <explain why this node should be deleted>

Impact:
  - <list orphaned children if any, or "No child nodes affected">

Proceed with deletion? (Yes/No)
```

**Example:**

```
⚠️ Delete Confirmation Required

Node to delete:
  - Name: PatientRegistrationForm
  - Type: Component
  - ID: comp-abc-123

Reason for deletion:
  This component is a duplicate of the existing PatientForm component
  and was created in error during the last design generation.

Impact:
  - 3 child ATOM components will be orphaned

Proceed with deletion? (Yes/No)
```

After user confirms, call Delete_Design_Node with:

```
Call Delete_Design_Node with:
  - uuid: projectUuid
  - label: "Component"
  - apiKey: apiKey
  - nodeId: "comp-abc-123"
```

**Warning:** Deleting a node may affect related nodes. Consider the following before deletion:

| Node Type   | Impact of Deletion                                      |
| ----------- | ------------------------------------------------------- |
| UserJourney | Orphans child Flows                                     |
| Flow        | Orphans child Pages                                     |
| Page        | Orphans child Components                                |
| Component   | Orphans child Components (if ORGANISM with children)    |

### Cascade Delete Option

When deleting a parent node, ask user whether to cascade delete children.

> **Important:** Components are NEVER deleted during cascade delete. Components may be reusable (GLOBAL/DOMAIN) and shared across multiple Pages/Flows. Only UserJourney, Flow, and Page nodes are cascade deleted.

**Cascade Delete Confirmation:**

```
⚠️ Cascade Delete Option

Node to delete:
  - Name: Patient Registration Journey
  - Type: UserJourney
  - ID: uj-abc-123

This node has children:
  - 3 Flows
  - 8 Pages
  - 24 Components (will be preserved, not deleted)

Delete options:
  1. Delete node only (orphan children)
  2. Cascade delete (delete node + Flows + Pages only)
  3. Cancel

Select option: (1/2/3)
```

**Cascade Delete Implementation:**

If user selects cascade delete, delete in reverse hierarchical order (children first, excluding Components):

```
1. Query child nodes (excluding Components):
   - Get Flows: queryParams="userJourneyId=<uj-id>"
   - Get Pages: queryParams="flowId=<flow-id>" (for each Flow)

2. Delete in order (bottom-up):
   a. Delete all Pages
   b. Delete all Flows
   c. Delete the parent node (UserJourney)

   Note: Components are preserved and become orphaned (pageId no longer valid)

3. Show progress:
   Cascade deleting: Patient Registration Journey
     ├── Preserving 24 Components (not deleted)
     ├── Deleting 8 Pages... Done
     ├── Deleting 3 Flows... Done
     └── Deleting UserJourney... Done

   Total deleted: 12 nodes (Components preserved)
```

**Cascade Delete by Node Type:**

| Node Type   | Cascade Deletes          | Preserved (Not Deleted)   |
| ----------- | ------------------------ | ------------------------- |
| UserJourney | Flows → Pages            | All Components            |
| Flow        | Pages                    | All Components            |
| Page        | (none)                   | All Components            |
| Component   | (not supported)          | -                         |

**Why Components Are Preserved:**

| Reason                | Explanation                                           |
| --------------------- | ----------------------------------------------------- |
| Reusability           | GLOBAL/DOMAIN components may be used by other Pages   |
| Action mappings       | Components have `actionIds[]` linking to functional graph |
| Manual cleanup        | User should explicitly delete unused components       |

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

## Step 0: Select Target Modalities

Ask user which modalities to generate design nodes for:

| Modality  | Description               |
| --------- | ------------------------- |
| `web`     | Browser-based interface   |
| `mobile`  | Native mobile application |
| `desktop` | Desktop application       |
| `api`     | Backend/Integration layer |
| `voice`   | Voice-based interface     |
| `chatbot` | Conversational interface  |

**Question:** "Which modalities do you want to create design for? (Select one or more)"

- Allow multiple selection
- Default: `web` if user doesn't specify
- Store selected modalities for use in Step 4

> **Note:** For each selected modality, separate Flow and Page nodes will be created from the same functional graph. This enables multi-platform design from a single functional specification.

## Step 1: Check Existing Design Graph

Before fetching functional data, verify if a design graph already exists for this project.

### 1a. Query for Existing Design Graph

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "UserJourney"
  - queryParams: "limit=1"
```

### 1b. Evaluate Result & Set Fetch Mode

| Result | Status | Fetch Mode for Step 2 |
|--------|--------|----------------------|
| Empty/No results | No design graph exists | Fetch ALL scenarios (no filter) |
| Returns 1+ UserJourney | Design graph exists | Fetch ONLY unprocessed scenarios (with filter) |

**Store the fetch mode** for use in Step 2:

```
IF UserJourney exists:
    fetchMode = "INCREMENTAL"
    Show: "Existing design graph found. Will only process scenarios without design."
ELSE:
    fetchMode = "FULL"
    Show: "No existing design graph. Will process all scenarios."
```

> **Note:** This approach automatically handles incremental design generation - only scenarios that haven't been converted to design nodes will be processed, preserving existing work.

## Step 2: Fetch Functional Graph Data

Fetch scenarios based on the fetch mode determined in Step 1.

### 2a. Pagination Loop with Conditional Filter

```
page = 1
allScenarios = []

LOOP:
    IF fetchMode == "INCREMENTAL":
        # Fetch only scenarios without design generated
        scenario = Get_scenarios_by_uuid(
            uuid: projectUuid,
            limit: 1,
            page: page,
            filters: "filters[isDesignGenerated][$eq]=false"
        )
    ELSE:
        # Fetch all scenarios (no filter)
        scenario = Get_scenarios_by_uuid(
            uuid: projectUuid,
            limit: 1,
            page: page
        )

    IF scenario is empty:
        BREAK (no more scenarios)

    allScenarios.append(scenario)

    Show progress: "Fetched scenario {page}: {scenario.name}"

    page++

END LOOP

IF fetchMode == "INCREMENTAL":
    Show: "Found {allScenarios.length} scenarios without design (incremental mode)"
ELSE:
    Show: "Total scenarios to process: {allScenarios.length}"

IF allScenarios.length == 0:
    Show: "All scenarios already have design generated. Nothing to process."
    Exit skill
```

### Filter Reference

| Fetch Mode | Filter | Description |
|------------|--------|-------------|
| `FULL` | None | Fetch all scenarios for initial design generation |
| `INCREMENTAL` | `filters[isDesignGenerated][$eq]=false` | Fetch only scenarios without design |

**Additional Available Filters:**
- `filters[isDesignGenerated][$eq]=true` - scenarios WITH design generated
- `filters[name][$contains]=<text>` - filter by scenario name
- `filters[status][$eq]=<status>` - filter by scenario status

### 2b. Fetch Scenario Details

For EACH scenario in allScenarios:

1. Call `Get_scenarios_by_uuid` with:
   - `uuid`: projectUuid from .breeze.json
   - `limit`: 1
   - `page`: current page number

2. Call `Get_all_steps_actions_for_a_scenario_id` with:
   - `uuid`: projectUuid from .breeze.json
   - `scenarioId`: the scenario UUID

   This returns the complete hierarchy: Scenario → Steps → Actions.

### 2c. Progress Indication

For large functional graphs, show progress:

```
Processing scenario 1 of 5: "Patient Registration"
  ├── Fetching steps and actions...
  ├── Found 4 steps, 12 actions
  └── Done

Processing scenario 2 of 5: "Appointment Booking"
  ...
```

## Step 3: Check Existing Design Coverage & Reusable Components

### 3a. Check Direct Mappings

Query existing design nodes to find what's already mapped from functional graph.

**Step 3a.1: Fetch all existing design nodes**

```
Call Get_all_Design_By_Label for each type:
  - uuid: projectUuid
  - label: "UserJourney"  → Get all user journeys
  - label: "Flow"         → Get all flows
  - label: "Page"         → Get all pages
  - label: "Component"    → Get all components
```

**Step 3a.2: Check for existing mappings**

For each functional node, check if a design node already maps to it:

| Functional Node | Design Node   | Check Field    | Query Example                                    |
| --------------- | ------------- | -------------- | ------------------------------------------------ |
| Scenario        | UserJourney   | `scenarioId`   | Search results for matching scenarioId           |
| Step            | Flow          | `stepIds[]`    | `Get_Design_Nodes_by_Ids` with `label=Flow`      |
| Step            | Page          | `stepIds[]`    | `Get_Design_Nodes_by_Ids` with `label=Page`      |
| Action          | Component     | `actionIds[]`  | `Get_Design_Nodes_by_Ids` with `label=Component` |

**Step 3a.3: Use semantic search for fuzzy matching**

```
Call Design_Graph_Search with:
  - uuid: projectUuid
  - query: "<scenario/step/action name>"
  - includeLabels: ["UserJourney", "Flow", "Page", "Component"]
```

This helps find design nodes that may be related but not directly mapped.

### 3b. Build Reusable Component Registry

Analyze ALL actions and identify reusable patterns:

```
Action Analysis → Identify Pattern → Check Registry → Reuse or Create

Example:
- Action: "Enter patient name"    → TextInput pattern
- Action: "Enter doctor name"     → TextInput pattern (SAME!)
- Action: "Enter emergency name"  → TextInput pattern (SAME!)

Result: Create ONE TextInputField component, reuse for all three.
```

**Reusability Levels:**

| Level    | Scope              | When to Use                                  |
| -------- | ------------------ | -------------------------------------------- |
| `GLOBAL` | Entire application | TextInput, Button, Select - used everywhere  |
| `DOMAIN` | Business domain    | PatientCard, VitalsDisplay - domain-specific |
| `PAGE`   | Single page        | Specific layout component                    |

**Build Registry:**

1. Group actions by `designSystemRef` pattern (see Step 3b table)

2. Fetch all existing reusable components:

   ```
   Call Get_Design_Nodes_by_Ids with:
     - uuid: projectUuid
     - label: "Component"
     - queryParams: "type=ATOM&page=1&limit=100"

   Call Get_Design_Nodes_by_Ids with:
     - uuid: projectUuid
     - label: "Component"
     - queryParams: "type=MOLECULE&page=1&limit=100"
   ```

3. For each unique `designSystemRef` pattern, search for existing component:

   ```
   Call Design_Graph_Search with:
     - uuid: projectUuid
     - query: "<designSystemRef value>" (e.g., "TextInput", "Button")
     - includeLabels: ["Component"]
   ```

4. Build a map: `{ designSystemRef → existingComponentId or "CREATE_NEW" }`

**Example Registry Result:**

| designSystemRef | Existing Component ID | Action         |
| --------------- | --------------------- | -------------- |
| TextInput       | comp-abc-123          | REUSE          |
| Button          | comp-def-456          | REUSE          |
| DatePicker      | null                  | CREATE_NEW     |
| Select          | comp-ghi-789          | REUSE          |

### 3c. For existing mappings, ask user:

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

Present unmapped functional nodes as gaps to be filled.

## Step 4: Generate Design Graph Nodes

For each functional node without design coverage (identified in Step 3), prepare design nodes:

### 4a. Scenario → UserJourney

Call `Create_Design_Node` with:

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "UserJourney",
  "data": {
    "name": "<scenario name>",
    "description": "<scenario description>",
    "scenarioId": "<scenario UUID>"
  }
}
```

### 4b. Step → Flow OR Page (EXCLUSIVE - choose one)

> **Important:** A Step maps to Flow OR Page, never both.
>
> **Multi-modality:** Create separate Flow/Page for EACH modality selected in Step 0.

**Decision Criteria:**

| Choose Flow When                               | Choose Page When                    |
| ---------------------------------------------- | ----------------------------------- |
| Multi-page navigation sequence                 | Single screen interaction           |
| Reusable sub-journey pattern                   | Data entry/display on one screen    |
| Process spanning multiple screens              | Form, list, detail, or dashboard    |
| Step contains sub-steps needing separate pages | Step is one discrete UI interaction |

**For each selected modality**, create Flow or Page with that modality:

**For Flow**, call `Create_Design_Node` (once per selected modality):

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Flow",
  "data": {
    "name": "<step name> (<modality>)",
    "description": "<step description>",
    "modality": "<selected modality from Step 0>",
    "entryPoint": "<entry point page/screen>",
    "exitPoint": "<exit point page/screen>",
    "userJourneyId": "<parent UserJourney UUID>",
    "stepIds": ["<step UUID>"]
  }
}
```

Example for 2 modalities (web + mobile):

- Flow: "Patient Registration Flow (web)" with `modality: "web"`
- Flow: "Patient Registration Flow (mobile)" with `modality: "mobile"`

**For Page**, call `Create_Design_Node` (once per selected modality):

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Page",
  "data": {
    "name": "<step name> (<modality>)",
    "description": "<step description>",
    "pageType": "<form|list|detail|dashboard|modal|search|wizard|report>",
    "modality": "<selected modality from Step 0>",
    "requiresAuth": true,
    "flowId": "<parent Flow UUID for this modality>",
    "stepIds": ["<step UUID>"]
  }
}
```

Example for 2 modalities (web + mobile):

- Page: "Patient Form (web)" with `modality: "web"`, linked to web Flow
- Page: "Patient Form (mobile)" with `modality: "mobile"`, linked to mobile Flow

**PageType Selection:**

| Step Function         | PageType    | Example Step                 |
| --------------------- | ----------- | ---------------------------- |
| Data entry/input      | `form`      | "Enter Patient Information"  |
| Single record display | `detail`    | "View Patient Profile"       |
| Multiple items view   | `list`      | "Browse All Patients"        |
| Analytics/overview    | `dashboard` | "View Department Statistics" |
| Quick action overlay  | `modal`     | "Confirm Cancellation"       |
| Search results        | `search`    | "Find Patient Records"       |
| Multi-step process    | `wizard`    | "Complete Registration"      |
| Report generation     | `report`    | "Generate Discharge Summary" |

### 4c. Action → Page OR Component (EXCLUSIVE - choose one)

> **Important:** An Action maps to Page OR Component, never both.

**Decision Criteria:**

| Choose Page When                   | Choose Component When                 |
| ---------------------------------- | ------------------------------------- |
| Page-level action (navigate, view) | Element-level action (click, enter)   |
| "View Dashboard", "Open Settings"  | "Enter Name", "Submit Form"           |
| Action represents entire screen    | Action represents specific UI element |

**For Action → Page**, add `actionIds` to the Page payload (see 4b).

**For Action → Component**, follow the REUSE-FIRST approach:

### Component Reuse Decision Flow

```
For each Action:
    │
    ├─► 1. Determine designSystemRef from action content
    │
    ├─► 2. Check Registry (from Step 3b): Does component exist?
    │       │
    │       ├─► YES (existing component found)
    │       │       │
    │       │       └─► REUSE: Link action to existing component
    │       │           - Add actionId to existing component's actionIds[]
    │       │           - DO NOT create new component
    │       │
    │       └─► NO (no existing component)
    │               │
    │               └─► CREATE NEW: Create component and add to registry
    │                   - Create with reusability level
    │                   - Add to registry for future reuse
    │
    └─► 3. For PAGE-SPECIFIC components (ORGANISM containers):
            - Always create new (they're page-specific)
            - But their children (MOLECULE/ATOM) can be reused
```

### Reuse Examples

**Scenario: Multiple "Enter name" actions across different steps**

```
Actions:
- "Enter patient name"     (Step: Patient Registration)
- "Enter doctor name"      (Step: Doctor Assignment)
- "Enter guardian name"    (Step: Emergency Contact)

WITHOUT Reuse (❌ Bad):
- Component: PatientNameInput    (TextInput) ← action 1
- Component: DoctorNameInput     (TextInput) ← action 2
- Component: GuardianNameInput   (TextInput) ← action 3

WITH Reuse (✓ Good):
- Component: TextInputField (GLOBAL, reusable)
    └── actionIds: [action1, action2, action3]
    └── props: configurable via label prop
```

**What gets REUSED vs CREATED NEW:**

| Component Type                     | Reuse?  | Reason                            |
| ---------------------------------- | ------- | --------------------------------- |
| ATOM (TextInput, Button, Select)   | ✓ REUSE | Same UI element, different labels |
| MOLECULE (FormField, SearchBox)    | ✓ REUSE | Same pattern, different config    |
| ORGANISM (PatientForm, DoctorForm) | ✗ NEW   | Page-specific containers          |
| TEMPLATE                           | ✓ REUSE | Layout patterns are reusable      |

### designSystemRef Lookup Table

| Action Content         | designSystemRef  | Type     | Reusable? |
| ---------------------- | ---------------- | -------- | --------- |
| "Enter name/text"      | `TextInput`      | ATOM     | ✓ GLOBAL  |
| "Enter email"          | `EmailInput`     | ATOM     | ✓ GLOBAL  |
| "Enter password"       | `PasswordInput`  | ATOM     | ✓ GLOBAL  |
| "Enter number/age"     | `NumberInput`    | ATOM     | ✓ GLOBAL  |
| "Select from options"  | `Select`         | ATOM     | ✓ GLOBAL  |
| "Select multiple"      | `MultiSelect`    | MOLECULE | ✓ GLOBAL  |
| "Select date"          | `DatePicker`     | ATOM     | ✓ GLOBAL  |
| "Select date and time" | `DateTimePicker` | MOLECULE | ✓ GLOBAL  |
| "Toggle/switch on-off" | `Toggle`         | ATOM     | ✓ GLOBAL  |
| "Check/accept"         | `Checkbox`       | ATOM     | ✓ GLOBAL  |
| "Submit/save/confirm"  | `Button`         | ATOM     | ✓ GLOBAL  |
| "Upload file"          | `FileUpload`     | MOLECULE | ✓ GLOBAL  |
| "Search"               | `SearchInput`    | MOLECULE | ✓ GLOBAL  |
| "View list/table"      | `Table`          | ORGANISM | ✓ DOMAIN  |
| "Fill form"            | `Form`           | ORGANISM | ✗ PAGE    |
| "Display info card"    | `Card`           | ORGANISM | ✓ DOMAIN  |

### Component Hierarchy (with Reuse)

```
Page
└── ORGANISM (NEW - page-specific, e.g., PatientRegistrationForm)
    ├── MOLECULE (REUSE - FormField pattern)
    │   └── ATOM (REUSE - TextInput)
    ├── MOLECULE (REUSE - FormField pattern)
    │   └── ATOM (REUSE - Select)
    └── ATOM (REUSE - Button)
```

### Creating Components (Reuse-Aware)

**Check if reusable component exists**

Option A - Use semantic search:

```
Call Design_Graph_Search with:
  - uuid: projectUuid
  - query: "<designSystemRef value>" (e.g., "TextInput", "Button")
  - includeLabels: ["Component"]
```

Option B - Query by component type (more precise):

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "Component"
  - queryParams: "type=ATOM" or "type=MOLECULE"
```

Then filter results locally by `designSystemRef` and `reusability: "GLOBAL"` or `"DOMAIN"`.

Option C - Get components used in a specific page:

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "Component"
  - queryParams: "pageId=<page-uuid>"
```

**If EXISTS → Update existing component**

Call `Update_Design_Node` to add actionId and update usedIn:

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Component",
  "nodeId": "<existing component UUID>",
  "data": {
    "actionIds": ["<existing actionIds>", "<new action UUID>"],
    "usedIn": ["<existing usedIn>", "<new parent page/component name>"]
  }
}
```

> **Note:** Always append to existing arrays, don't replace them. First fetch the current component using `Get_Design_Nodes_by_Ids` with `id=<component-uuid>` to get current values.

**If NOT EXISTS → Create new reusable component**

Call `Create_Design_Node`:

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Component",
  "data": {
    "name": "<generic name, e.g., TextInputField>",
    "type": "<ATOM|MOLECULE|ORGANISM>",
    "description": "<reusable component description>",
    "designSystemRef": "<from table above>",
    "reusability": "<GLOBAL|DOMAIN|PAGE>",
    "props": "{\"label\": \"string\", \"required\": \"boolean\", \"placeholder\": \"string\"}",
    "states": ["default", "focused", "error", "disabled", "loading"],
    "layoutType": "flex",
    "slots": [],
    "usedIn": ["<parent component/page names that use this>"],
    "pageId": "<null for GLOBAL, Page UUID for PAGE-level>",
    "parentComponentId": "<parent ORGANISM UUID if nested>",
    "actionIds": ["<action UUID>"]
  }
}
```

**Key differences for reusable components:**

| Field         | GLOBAL/DOMAIN (Reusable)                           | PAGE (Instance)                     |
| ------------- | -------------------------------------------------- | ----------------------------------- |
| `name`        | Generic: "TextInputField"                          | Specific: "PatientNameInput"        |
| `pageId`      | `null` (not tied to page)                          | Page UUID                           |
| `reusability` | "GLOBAL" or "DOMAIN"                               | "PAGE"                              |
| `props`       | Schema: `{"label": "string"}`                      | Values: `{"label": "Patient Name"}` |
| `usedIn`      | Array of all component/page names using this       | Usually empty or single parent      |

**Reusability and Modality:**

| Reusability | Create per Modality? | Reason                                 |
| ----------- | -------------------- | -------------------------------------- |
| GLOBAL      | NO - create once     | Same component works across modalities |
| DOMAIN      | NO - create once     | Domain logic same across modalities    |
| PAGE        | YES - per modality   | Each Page has its own instance         |

**Grouping Actions into Components:**

When multiple related actions exist under a Step:

1. Create one ORGANISM for the group (e.g., "PatientForm")
2. Create MOLECULE/ATOM children for each action
3. Set `parentComponentId` to link children to ORGANISM
4. Repeat for each selected modality

### 4d. Template Generation (Optional)

Create TEMPLATE components for consistent page layouts.

**When to Create Templates:**

| PageType    | Template           | Layout Structure                      |
| ----------- | ------------------ | ------------------------------------- |
| `form`      | FormPageTemplate   | Header + Form Body + Actions Footer   |
| `list`      | ListPageTemplate   | Header + Filters + Table + Pagination |
| `detail`    | DetailPageTemplate | Header + Content Sections + Actions   |
| `dashboard` | DashboardTemplate  | Header + Widget Grid + Sidebar        |
| `wizard`    | WizardTemplate     | Progress Bar + Step Content + Nav     |
| `modal`     | ModalTemplate      | Title Bar + Body + Action Buttons     |

**Template Payload:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "<pageType>PageTemplate",
    "type": "TEMPLATE",
    "description": "Reusable layout pattern for <pageType> pages",
    "reusability": "GLOBAL",
    "layoutType": "flex",
    "slots": ["header", "content", "footer", "actions"],
    "usedIn": ["<page names using this template>"],
    "pageId": "<Page UUID where applied>"
  }
}
```

**Template Reuse:** Check if template exists before creating. Templates are GLOBAL reusable.

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "Component"
  - queryParams: "type=TEMPLATE"
```

Then check if a template with the same `name` or `pageType` pattern already exists.

### 4e. Order Preservation

Preserve the `order` field from functional graph:

| Functional Node | Design Node | Order Field     |
| --------------- | ----------- | --------------- |
| Step.order      | Flow/Page   | `order` in data |
| Action.order    | Component   | `order` in data |

```json
{
  "data": {
    "name": "...",
    "order": 1,
    ...
  }
}
```

This ensures design nodes maintain the same sequence as functional nodes.

## Step 5: User Confirmation

Present the design nodes in two tables:

### New Components to Create

| Functional Node | →   | Design Node | Modality | Type     | Reuse  | Name              |
| --------------- | --- | ----------- | -------- | -------- | ------ | ----------------- |
| Scenario: X     | →   | UserJourney | -        | -        | -      | X                 |
| Step: Y         | →   | Page        | web      | form     | -      | Y (web)           |
| Step: Y         | →   | Page        | mobile   | form     | -      | Y (mobile)        |
| Action: A       | →   | Component   | -        | ATOM     | GLOBAL | TextInputField    |
| Action: B       | →   | Component   | web      | ORGANISM | PAGE   | PatientForm (web) |

### Reusing Existing Components

| Functional Node | →   | Existing Component | Action       |
| --------------- | --- | ------------------ | ------------ |
| Action: C       | →   | TextInputField     | Add actionId |
| Action: D       | →   | Button             | Add actionId |
| Action: E       | →   | Select             | Add actionId |

Ask: "Proceed with creating/linking these design nodes? (Yes/No/Select specific)"

Allow user to:

- Confirm all
- Reject all
- Select specific nodes to create
- Override reuse decision (create new instead of reusing)
- Filter by modality

## Step 6: Create Design Nodes

### 6a. Create NEW nodes

For each confirmed NEW node, call `Create_Design_Node` with:

- `uuid`: projectUuid from .breeze.json
- Node data as prepared in Step 4

**Creation order** (to establish relationships):

1. GLOBAL/DOMAIN reusable components first (no pageId dependency)
2. UserJourney nodes (references Scenario)
3. Flow/Page nodes (references Steps, get UUIDs for components)
4. PAGE-level components last (need pageId from step above)

### 6b. Link actions to EXISTING reusable components

For each action reusing an existing component, call `Update_Design_Node`:

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Component",
  "nodeId": "<existing component UUID>",
  "data": {
    "actionIds": ["<existing actionIds...>", "<new action UUID>"]
  }
}
```

This links the functional action to the existing design component via `IMPLEMENTED_BY` relationship.

### 6c. CONTAINS Relationships (Design Graph Hierarchy)

The design graph has internal CONTAINS relationships for hierarchy:

```
UserJourney
    └── CONTAINS → Flow
                      └── CONTAINS → Page
                                        └── CONTAINS → Component (ORGANISM)
                                                          └── CONTAINS → Component (MOLECULE)
                                                                            └── CONTAINS → Component (ATOM)
```

**How CONTAINS relationships are created:**

| Parent Node | Child Node | Created Via                      |
| ----------- | ---------- | -------------------------------- |
| UserJourney | Flow       | `userJourneyId` in Flow payload  |
| Flow        | Page       | `flowId` in Page payload         |
| Page        | Component  | `pageId` in Component payload    |
| Component   | Component  | `parentComponentId` in Component |

> **Note:** The backend automatically creates CONTAINS relationships when these ID fields are provided.

**Querying Hierarchical Relationships:**

To get child nodes of a parent, use `Get_Design_Nodes_by_Ids`:

| Parent       | Child      | Query                                                 |
| ------------ | ---------- | ----------------------------------------------------- |
| UserJourney  | Flows      | `label=Flow`, `queryParams=userJourneyId=<uj-id>`     |
| Flow         | Pages      | `label=Page`, `queryParams=flowId=<flow-id>`          |
| Page         | Components | `label=Component`, `queryParams=pageId=<page-id>`     |
| Component    | Children   | `label=Component`, `queryParams=parentComponentId=<comp-id>` |

**Example: Get all components under a page**

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "Component"
  - queryParams: "pageId=page-123&page=1&limit=100"
```

**Example: Get all ORGANISM components under a page**

```
Call Get_Design_Nodes_by_Ids with:
  - uuid: projectUuid
  - label: "Component"
  - queryParams: "pageId=page-123&type=ORGANISM"
```

### 6d. Error Handling

Handle failures gracefully during creation:

```
TRY:
    Create node
    Store returned UUID for dependent nodes
CATCH error:
    Log: "Failed to create {nodeType}: {error}"
    Ask user: "Continue with remaining nodes? (Yes/No/Retry)"

    IF Retry:
        Retry creation
    ELSE IF No:
        Rollback created nodes (optional)
        Exit
    ELSE:
        Skip failed node, continue
```

**Partial Failure Recovery:**

| Failure Point        | Recovery Action                        |
| -------------------- | -------------------------------------- |
| UserJourney creation | Cannot proceed - critical failure      |
| Flow/Page creation   | Skip dependent components, log warning |
| Component creation   | Continue with other components         |
| Reuse update fails   | Create new component instead           |

The backend automatically creates:

- `MAPS_TO` relationships: Scenario→UserJourney, Step→Flow/Page
- `IMPLEMENTED_BY` relationships: Action→Component
- `CONTAINS` relationships: Via parent ID fields (userJourneyId, flowId, pageId, parentComponentId)

### 6e. Mark Scenarios as Processed

After successfully creating all design nodes for a scenario, mark it as processed to enable incremental mode for future runs.

**For EACH successfully processed scenario**, call `Update_Functional_Node`:

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Scenario",
  "id": "<scenario UUID>",
  "data": {
    "isDesignGenerated": true
  }
}
```

**When to mark as processed:**

| Condition | Action |
|-----------|--------|
| All design nodes created successfully | Mark `isDesignGenerated: true` |
| Partial failure (some nodes failed) | Do NOT mark - allows retry |
| UserJourney creation failed | Do NOT mark - critical failure |

**Progress indication:**

```
Marking scenario as processed: "Patient Registration"
  └── Updated isDesignGenerated = true

Marking scenario as processed: "Appointment Booking"
  └── Updated isDesignGenerated = true
```

> **Note:** This step is critical for incremental mode (Step 1b). Without it, scenarios will be re-processed on every run.

## Step 7: Output Summary

Present results:

**Design Graph Generated (by Modality)**

| Modality  | UserJourneys | Flows | Pages | Components (New) |
| --------- | ------------ | ----- | ----- | ---------------- |
| web       | N            | N     | N     | N                |
| mobile    | N            | N     | N     | N                |
| **Total** | N            | N     | N     | N                |

**Component Reuse Statistics**

| Metric                        | Count |
| ----------------------------- | ----- |
| New GLOBAL components created | N     |
| New DOMAIN components created | N     |
| New PAGE components created   | N     |
| Existing components reused    | N     |
| Actions linked via reuse      | N     |

**Reuse Efficiency:** `(Reused / Total Actions) × 100`%

**Relationships Established**

| Relationship Type | Relationship                      | Count |
| ----------------- | --------------------------------- | ----- |
| Cross-Ontology    | MAPS_TO (Scenario→UserJourney)    | N     |
| Cross-Ontology    | MAPS_TO (Step→Flow/Page)          | N     |
| Cross-Ontology    | IMPLEMENTED_BY (Action→Component) | N     |
| Design Hierarchy  | CONTAINS (UserJourney→Flow)       | N     |
| Design Hierarchy  | CONTAINS (Flow→Page)              | N     |
| Design Hierarchy  | CONTAINS (Page→Component)         | N     |
| Design Hierarchy  | CONTAINS (Component→Component)    | N     |

**Errors/Warnings (if any)**

| Issue                 | Count | Action Taken     |
| --------------------- | ----- | ---------------- |
| Failed creations      | N     | Skipped/Retried  |
| Reuse update failures | N     | Created new      |
| Missing parent nodes  | N     | Skipped children |

**Next Steps**

- Refine design nodes with additional properties
- Run `/breeze:create-page` to generate UI code
- Export to Figma for visual design
