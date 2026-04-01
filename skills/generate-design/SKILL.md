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

Three tools are available for querying design graph nodes:

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
- Store selected modalities for use in Step 3

> **Note:** For each selected modality, separate Flow and Page nodes will be created from the same functional graph. This enables multi-platform design from a single functional specification.

## Step 1: Fetch Functional Graph Data

Fetch all scenarios, steps, and actions for the project using pagination:

### 1a. Pagination Loop

```
page = 1
allScenarios = []

LOOP:
    scenario = Get_scenarios_by_uuid(uuid, limit=1, page)

    IF scenario is empty:
        BREAK (no more scenarios)

    allScenarios.append(scenario)

    Show progress: "Fetched scenario {page}: {scenario.name}"

    page++

END LOOP

Show: "Total scenarios to process: {allScenarios.length}"
```

### 1b. Fetch Scenario Details

For EACH scenario in allScenarios:

1. Call `Get_scenarios_by_uuid` with:
   - `uuid`: projectUuid from .breeze.json
   - `limit`: 1
   - `page`: current page number

2. Call `Get_all_steps_actions_for_a_scenario_id` with:
   - `uuid`: projectUuid from .breeze.json
   - `scenarioId`: the scenario UUID

   This returns the complete hierarchy: Scenario → Steps → Actions.

3. Extract `allowedRoles` from the Persona associated with this scenario's Outcome.

### 1c. Progress Indication

For large functional graphs, show progress:

```
Processing scenario 1 of 5: "Patient Registration"
  ├── Fetching steps and actions...
  ├── Found 4 steps, 12 actions
  └── Done

Processing scenario 2 of 5: "Appointment Booking"
  ...
```

## Step 2: Check Existing Design Coverage & Reusable Components

### 2a. Check Direct Mappings

Query existing design nodes to find what's already mapped from functional graph.

**Step 2a.1: Fetch all existing design nodes**

```
Call Get_all_Design_By_Label for each type:
  - uuid: projectUuid
  - label: "UserJourney"  → Get all user journeys
  - label: "Flow"         → Get all flows
  - label: "Page"         → Get all pages
  - label: "Component"    → Get all components
```

**Step 2a.2: Check for existing mappings**

For each functional node, check if a design node already maps to it:

| Functional Node | Design Node   | Check Field    | Query Example                                    |
| --------------- | ------------- | -------------- | ------------------------------------------------ |
| Scenario        | UserJourney   | `scenarioId`   | Search results for matching scenarioId           |
| Step            | Flow          | `stepIds[]`    | `Get_Design_Nodes_by_Ids` with `label=Flow`      |
| Step            | Page          | `stepIds[]`    | `Get_Design_Nodes_by_Ids` with `label=Page`      |
| Action          | Component     | `actionIds[]`  | `Get_Design_Nodes_by_Ids` with `label=Component` |

**Step 2a.3: Use semantic search for fuzzy matching**

```
Call Design_Graph_Search with:
  - uuid: projectUuid
  - query: "<scenario/step/action name>"
  - includeLabels: ["UserJourney", "Flow", "Page", "Component"]
```

This helps find design nodes that may be related but not directly mapped.

### 2b. Extract Personas/Roles

The functional graph has: Persona → Outcome → Scenario → Step → Action

Extract `allowedRoles` for Pages from the Persona associated with each Scenario:

```
For each Scenario:
    1. Get parent Outcome (Scenario belongs to Outcome)
    2. Get parent Persona (Outcome belongs to Persona)
    3. Store: scenarioId → Persona.name

Use Persona.name as allowedRoles[] when creating Pages.
```

**API Call:** Use `Get_all_personas` or traverse from Scenario to get Persona info.

### 2c. Build Reusable Component Registry

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

1. Group actions by `designSystemRef` pattern (see Step 3c table)

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

### 2d. For existing mappings, ask user:

| Option      | Action                                         |
| ----------- | ---------------------------------------------- |
| **Skip**    | Keep existing design node unchanged            |
| **Update**  | Update design node with latest functional data |
| **Replace** | Delete existing and create new design node     |

Present unmapped functional nodes as gaps to be filled.

## Step 3: Generate Design Graph Nodes

For each functional node without design coverage, prepare design nodes:

### 3a. Scenario → UserJourney

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

### 3b. Step → Flow OR Page (EXCLUSIVE - choose one)

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
    "allowedRoles": ["<persona from functional graph>"],
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

### 3c. Action → Page OR Component (EXCLUSIVE - choose one)

> **Important:** An Action maps to Page OR Component, never both.

**Decision Criteria:**

| Choose Page When                   | Choose Component When                 |
| ---------------------------------- | ------------------------------------- |
| Page-level action (navigate, view) | Element-level action (click, enter)   |
| "View Dashboard", "Open Settings"  | "Enter Name", "Submit Form"           |
| Action represents entire screen    | Action represents specific UI element |

**For Action → Page**, add `actionIds` to the Page payload (see 3b).

**For Action → Component**, follow the REUSE-FIRST approach:

### Component Reuse Decision Flow

```
For each Action:
    │
    ├─► 1. Determine designSystemRef from action content
    │
    ├─► 2. Check Registry (from Step 2b): Does component exist?
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

**Step 1: Check if reusable component exists**

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

**Step 2a: If EXISTS → Update existing component**

Call `Update_Design_Node` to add actionId and update usedIn:

```json
{
  "uuid": "<projectUuid>",
  "nodeId": "<existing component UUID>",
  "data": {
    "actionIds": ["<existing actionIds>", "<new action UUID>"],
    "usedIn": ["<existing usedIn>", "<new parent page/component name>"]
  }
}
```

> **Note:** Always append to existing arrays, don't replace them. First fetch the current component using `Get_Design_Nodes_by_Ids` with `id=<component-uuid>` to get current values.

**Step 2b: If NOT EXISTS → Create new reusable component**

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

### 3d. Template Generation (Optional)

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

### 3e. Order Preservation

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

## Step 4: User Confirmation

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

## Step 5: Create Design Nodes

### 5a. Create NEW nodes

For each confirmed NEW node, call `Create_Design_Node` with:

- `uuid`: projectUuid from .breeze.json
- Node data as prepared in Step 3

**Creation order** (to establish relationships):

1. GLOBAL/DOMAIN reusable components first (no pageId dependency)
2. UserJourney nodes (references Scenario)
3. Flow/Page nodes (references Steps, get UUIDs for components)
4. PAGE-level components last (need pageId from step 3)

### 5b. Link actions to EXISTING reusable components

For each action reusing an existing component, call `Update_Design_Node`:

```json
{
  "uuid": "<projectUuid>",
  "nodeId": "<existing component UUID>",
  "data": {
    "actionIds": ["<existing actionIds...>", "<new action UUID>"]
  }
}
```

This links the functional action to the existing design component via `IMPLEMENTED_BY` relationship.

### 5c. CONTAINS Relationships (Design Graph Hierarchy)

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

### 5d. Error Handling

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

## Step 6: Output Summary

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
