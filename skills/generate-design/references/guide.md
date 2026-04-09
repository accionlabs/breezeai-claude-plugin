# Design Ontology Graph Generation Rules

This document defines the rules for generating Design Ontology Graph nodes from the Functional Graph.

---

## API Tools Reference

### Functional Graph Query Tools

#### Get_scenarios_by_uuid

Fetches scenarios from the functional graph with pagination and filtering.

**Inputs:**

- `uuid` (required): Project UUID
- `limit` (optional): Number of results per page
- `page` (optional): Page number for pagination
- `filters` (optional): Filter string for conditional queries

**Filter Examples:**

| Filter | Description |
|--------|-------------|
| `filters[isDesignGenerated][$eq]=false` | Scenarios without design |
| `filters[isDesignGenerated][$eq]=true` | Scenarios with design |
| `filters[name][$contains]=<text>` | Filter by scenario name |
| `filters[status][$eq]=<status>` | Filter by status |

#### Get_all_steps_actions_for_a_scenario_id

Fetches complete hierarchy for a scenario including all steps and actions.

**Inputs:**

- `uuid` (required): Project UUID
- `parameters0_Value` (required): The scenario ID (e.g. `1771932502952-zxdi7x4`).
  This maps to `filters[id][$eq]` on the backend. Do NOT pass it as `scenarioId` —
  the tool schema requires the exact name `parameters0_Value` and will fail with
  `Required → at parameters0_Value` otherwise.

**Returns:** Complete hierarchy: Scenario → Steps → Actions

#### Update_Functional_Node

Updates a functional graph node (used to mark scenarios as processed).

**Inputs:**

- `uuid` (required): Project UUID
- `apiKey` (required): API key from .breeze.json
- `label` (required): Node type - `Scenario`
- `id` (required): Node ID to update
- `data` (required): Object with fields to update

**Example:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Scenario",
  "id": "<scenario UUID>",
  "data": {
    "isDesignGenerated": true
  }
}
```

---

### Design Graph Query Tools

#### 1. Get_all_Design_By_Label

Gets all design nodes of a specific type with pagination.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`

**Use when:** You need to fetch all nodes of a specific type.

#### 2. Design_Graph_Search

Semantic search across all design graph node types.

**Inputs:**

- `uuid` (required): Project UUID
- `query` (required): Search query string
- `limit` (optional): Number of results (default: 10)
- `skip` (optional): Offset for pagination (default: 0)
- `includeLabels` (optional): Filter by labels - `["UserJourney", "Flow", "Page", "Component"]`

**Use when:** You need to search for nodes by name, description, or any text content.

#### 3. Get_Design_Nodes_by_Ids

Query design nodes with various filters. This is the most flexible query tool.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `queryParams` (optional): Query string for filtering

**Query Parameter Examples:**

| Use Case | Query Params |
|----------|--------------|
| Get by specific ID | `id=uj-123` |
| Get by multiple IDs | `id=uj-123&id=uj-456` |
| Get Flows by UserJourney | `userJourneyId=uj-123` |
| Get Pages by Flow | `flowId=flow-123` |
| Get Components by Page | `pageId=page-123` |
| Get Components by parent | `parentComponentId=comp-123` |
| Get Components by type | `type=ORGANISM` or `type=MOLECULE` or `type=ATOM` |
| Get Pages by pageType | `pageType=form` or `pageType=list` |
| Get by modality | `modality=web` or `modality=mobile` |
| Combine filters | `pageId=page-123&type=ORGANISM` |
| With pagination | `page=1&limit=50&sortName=name&sortOrder=asc` |

**Use when:** You need to query nodes by specific relationships or properties.

---

### Design Graph Mutation Tools

#### Create_Design_Node

Creates a new design node in the graph.

**Inputs:**

- `uuid` (required): Project UUID
- `apiKey` (required): API key from .breeze.json
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `data` (required): Node data object (see payload structures below)

**Payload Structures:**

See sections below for UserJourney, Flow, Page, and Component payload structures.

#### Update_Design_Node

Updates an existing design node.

**Inputs:**

- `uuid` (required): Project UUID
- `apiKey` (required): API key from .breeze.json
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `nodeId` (required): The ID of the node to update
- `data` (required): Object with fields to update

**Example — link action to existing component:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "nodeId": "<component UUID>",
  "data": {
    "actionIds": ["<existing actionIds>", "<new action UUID>"],
    "usedIn": ["<existing usedIn>", "<new parent name>"]
  }
}
```

**Example — link step to existing flow (flow deduplication):**

When a flow with the same `(name, modality)` already exists from a prior
scenario, append the new step's UUID to the existing flow's `stepIds[]`.
This reuses the entire flow including all its pages and components.

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Flow",
  "nodeId": "<existing flow UUID>",
  "data": {
    "stepIds": ["<existing step-uuid-1>", "<new step-uuid-from-current-scenario>"]
  }
}
```

**Example — link step to existing page (page deduplication):**

When a page with the same `(name, pageType, modality)` already exists from a
prior scenario, append the new step's UUID to the existing page's `stepIds[]`
instead of creating a duplicate page.

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Page",
  "nodeId": "<existing page UUID>",
  "data": {
    "stepIds": ["<existing step-uuid-1>", "<new step-uuid-from-current-scenario>"]
  }
}
```

> **Note:** Always append to existing arrays, don't replace them. First fetch the current node to get current values.

#### Bulk_Update_Design_Nodes

Creates the entire UserJourney tree for a scenario in one call using a nested
payload. The backend handles hierarchy creation, ID linking, and component
deduplication (upsert by `designSystemRef`) automatically.

**Inputs:**

- `uuid` (required): Project UUID
- `apiKey` (required): API key from .breeze.json
- `data` (required): Nested tree object (see payload structure below)

**Payload Structure:**

```json
{
  "userJourneys": [
    {
      "name": "User Registration Journey",
      "description": "End-to-end registration flow",
      "scenarioId": "scenario-uuid-from-functional-graph",
      "flows": [
        {
          "name": "Sign Up Flow",
          "description": "New user sign up process",
          "modality": "WEB",
          "entryPoint": "page-id-1",
          "exitPoint": "page-id-3",
          "stepIds": ["step-uuid-1", "step-uuid-2"],
          "pages": [
            {
              "name": "Registration Page",
              "description": "User fills in registration details",
              "pageType": "form",
              "requiresAuth": false,
              "allowedRoles": [],
              "stepIds": ["step-uuid-1"],
              "components": [
                {
                  "name": "RegistrationForm",
                  "type": "ORGANISM",
                  "description": "Main registration form with validation",
                  "designSystemRef": "ds-form-ref",
                  "props": "{\"variant\": \"primary\"}",
                  "states": ["idle", "loading", "error", "success"],
                  "layoutType": "vertical",
                  "slots": ["header", "body", "footer"],
                  "actionIds": ["action-uuid-1"],
                  "children": [
                    {
                      "name": "EmailInput",
                      "type": "ATOM",
                      "description": "Email input field",
                      "designSystemRef": "ds://inputs/TextInput@1.0",
                      "actionIds": ["action-uuid-2"]
                    },
                    {
                      "name": "PasswordInput",
                      "type": "ATOM",
                      "description": "Password input with strength meter",
                      "designSystemRef": "ds://inputs/PasswordInput@1.0"
                    },
                    {
                      "name": "SubmitButton",
                      "type": "ATOM",
                      "description": "Submit registration button",
                      "designSystemRef": "ds://buttons/Button@1.0",
                      "actionIds": ["action-uuid-3"]
                    }
                  ]
                }
              ]
            },
            {
              "name": "Confirmation Page",
              "description": "Email verification confirmation",
              "pageType": "info",
              "requiresAuth": false,
              "stepIds": ["step-uuid-2"],
              "components": [
                {
                  "name": "ConfirmationMessage",
                  "type": "MOLECULE",
                  "description": "Displays confirmation message",
                  "designSystemRef": "ds://feedback/Alert@1.0"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Payload Rules:**

- **One UserJourney per call** — each call handles one scenario. Do NOT batch
  multiple scenarios.
- **Nesting = hierarchy** — Flows nest under UserJourney, Pages under Flows,
  Components under Pages, child Components under parent Components via
  `children`.
- **Component children** — ORGANISM lists MOLECULE/ATOM children, MOLECULE
  lists ATOM children, ATOM has no children (omit or `[]`).
- **Upsert for reuse** — include reusable components with their
  `designSystemRef`. If a component with the same ref exists, the backend
  appends new `actionIds` instead of duplicating.
- **Multi-modality** — include separate Flow entries per modality under the
  same UserJourney, each with its own `modality` field.

**Children Array (Component Composition):**

Every non-ATOM component MUST include a `children` array listing its direct
child components:

| Component Type | `children` value                             |
|----------------|----------------------------------------------|
| TEMPLATE       | Names of ORGANISMs it contains               |
| ORGANISM       | Names of MOLECULEs and/or ATOMs it contains  |
| MOLECULE       | Names of ATOMs it contains                   |
| ATOM           | `[]` (leaf node — no children)               |

**Example composition:**

```
TEMPLATE "RegistrationPageLayout"
  children: ["HeaderBar", "PatientRegistrationForm", "FooterActions"]

ORGANISM "PatientRegistrationForm"
  children: ["FullNameField", "EmailField", "PhoneField", "DatePickerField", "GenderSelect", "SubmitButton"]

MOLECULE "FullNameField"
  children: ["TextLabel", "TextInput", "ValidationMessage"]

ATOM "TextInput"
  children: []
```

Order within `children` reflects visual/logical order on the page.

#### Delete_Design_Node

Deletes a design node from the graph.

**Inputs:**

- `uuid` (required): Project UUID
- `label` (required): Node type - `UserJourney` | `Flow` | `Page` | `Component`
- `apiKey` (required): API key from .breeze.json
- `nodeId` (required): The ID of the node to delete

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

**Deletion Impact:**

| Node Type | Impact of Deletion |
|-----------|-------------------|
| UserJourney | Orphans child Flows |
| Flow | Orphans child Pages |
| Page | Orphans child Components |
| Component | Orphans child Components (if ORGANISM with children) |

### Cascade Delete Option

When deleting a parent node, ask user whether to cascade delete children.

> **Important:** Components are NEVER deleted during cascade delete. Components may be reusable (GLOBAL/DOMAIN) and shared across multiple Pages/Flows. Only UserJourney, Flow, and Page nodes are cascade deleted.

**Cascade Delete Confirmation:**

```
⚠️ Cascade Delete Option

Node to delete:
  - Name: <node name>
  - Type: UserJourney
  - ID: <nodeId>

This node has children:
  - N Flows
  - N Pages
  - N Components (will be preserved, not deleted)

Delete options:
  1. Delete node only (orphan children)
  2. Cascade delete (delete node + Flows + Pages only)
  3. Cancel

Select option: (1/2/3)
```

**Cascade Delete by Node Type:**

| Node Type | Cascade Deletes | Preserved (Not Deleted) |
|-----------|-----------------|------------------------|
| UserJourney | Flows → Pages | All Components |
| Flow | Pages | All Components |
| Page | (none) | All Components |
| Component | (not supported) | - |

---

## Mapping Overview

| Functional Node | Design Node           | Relationship                                                       |
| --------------- | --------------------- | ------------------------------------------------------------------ |
| Scenario        | UserJourney           | 1:1 mapping via `scenarioId`                                       |
| Step            | Flow **OR** Page      | Step maps to either Flow or Page (not both) via `stepIds`          |
| Action          | Page **OR** Component | Action maps to either Page or Component (not both) via `actionIds` |
| -               | Template              | Part of Component (no functional mapping)                          |

### Exclusive Mapping Rules

> **Important:** These are mutually exclusive mappings:
>
> - A **Step** can be mapped to a **Flow** OR a **Page**, but NOT both simultaneously
> - An **Action** can be mapped to a **Page** OR a **Component**, but NOT both simultaneously

---

## 1. UserJourney Generation Rules

**Source:** Functional `Scenario` node

### Rules

1. **One Scenario = One UserJourney** - Each scenario in the functional graph creates exactly one UserJourney
2. **Name derivation**: Use scenario name directly or add "Journey" suffix if needed
3. **Description**: Copy scenario description or enhance with journey context
4. **Cross-ontology link**: Always set `scenarioId` to create `MAPS_TO` relationship

### Payload Structure

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "UserJourney",
  "data": {
    "name": "{Scenario.scenario}",
    "description": "{Scenario.description}",
    "scenarioId": "{Scenario.id}"
  }
}
```

### Example

```
Functional: Scenario "Conduct and Document Medical Tests"
     ↓
Design: UserJourney "Conduct and Document Medical Tests"
        scenarioId: "1774964938271-f4sd9fm"
```

---

## 2. Flow Generation Rules

**Source:** Functional `Step` node

### Rules

1. **Step → Flow (Exclusive)** - A Step can map to a Flow OR a Page, not both
2. **When to use Flow**: When the step represents a multi-page navigation sequence or reusable sub-journey
3. **Name derivation**: `{Step.step} Flow` or keep step name
4. **Modality required**: Always specify `modality` (web | mobile | desktop | api)
5. **Entry/Exit points**: Define navigation context
6. **Cross-ontology link**: Set `stepIds` array to create `MAPS_TO` relationships
7. **Grouping**: Multiple related steps can be grouped into one flow if they represent a single user interaction sequence

> **Note:** If a Step is mapped to a Flow, do NOT also map it to a Page. Choose one based on the step's nature.

### Modality Types

| Modality   | Description               | Use Case                                | Example                               |
| ---------- | ------------------------- | --------------------------------------- | ------------------------------------- |
| `web`      | Browser-based interface   | Web applications, SPA, responsive sites | "Patient Portal Web App"              |
| `mobile`   | Native mobile application | iOS/Android apps with native UI         | "Doctor Mobile App"                   |
| `desktop`  | Desktop application       | Electron, native desktop software       | "Hospital Management Desktop"         |
| `api`      | Backend/Integration layer | REST APIs, microservices, webhooks      | "Lab Results Integration API"         |
| `voice`    | Voice-based interface     | Alexa skills, Google Assistant, IVR     | "Appointment Booking Voice Assistant" |
| `kiosk`    | Self-service terminal     | Check-in kiosks, information terminals  | "Patient Check-in Kiosk"              |
| `wearable` | Wearable device interface | Smartwatch, fitness trackers            | "Vitals Monitoring Watch App"         |
| `chatbot`  | Conversational interface  | Chat widgets, messaging bots            | "Patient Support Chatbot"             |

### Modality Selection Rules

| Context                 | Modality                           | When to Choose                                  |
| ----------------------- | ---------------------------------- | ----------------------------------------------- |
| Browser-based interface | `web`                              | Primary user interaction via browser            |
| Native mobile app       | `mobile`                           | Touch-first, offline-capable mobile experience  |
| Desktop application     | `desktop`                          | Heavy data processing, local file access needed |
| Backend/Integration     | `api`                              | System-to-system communication, no direct UI    |
| Multi-platform          | Create separate flows per modality | Same journey across different platforms         |

### Modality Examples

```
Scenario: "Patient Appointment Booking"

Web Flow:
  - modality: "web"
  - Pages: Calendar View → Time Slot Selection → Confirmation

Mobile Flow:
  - modality: "mobile"
  - Pages: Date Picker → Available Slots → Booking Summary

API Flow:
  - modality: "api"
  - Endpoints: GET /slots → POST /appointments → GET /confirmation

Voice Flow:
  - modality: "voice"
  - Interactions: "What day?" → "What time?" → "Confirmed for..."
```

### Payload Structure

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Flow",
  "data": {
    "name": "{Step.step} Flow",
    "description": "Flow for {Step.step}",
    "modality": "web | mobile | desktop | api",
    "entryPoint": "Previous page/flow or entry context",
    "exitPoint": "Next page/flow or completion context",
    "userJourneyId": "{parent UserJourney.id}",
    "stepIds": ["{Step.id}"]
  }
}
```

### Example

```
Functional: Step "Order Medical Tests" (order: 1)
     ↓
Design: Flow "Order Medical Tests Flow"
        modality: "web"
        stepIds: ["1774964938277-vfem9cu"]
        userJourneyId: "{UserJourney.id}"
```

---

## 3. Page Generation Rules

**Source:** Functional `Step` node (alternative to Flow)

### Rules

1. **Step → Page (Exclusive)** - A Step can map to a Flow OR a Page, not both
2. **When to use Page**: When the step represents a single screen/interface interaction
3. **Page per interaction context**: Create separate pages for distinct interaction states
4. **Name derivation**: `{Step.step} Page` or contextual name
5. **PageType selection**: Based on step's primary function
6. **Auth requirements**: Derive from persona/outcome context
7. **Cross-ontology link**: Set `stepIds` for `MAPS_TO` relationship

> **Note:** If a Step is mapped to a Page directly, do NOT also map it to a Flow. Choose based on complexity:
>
> - **Use Page**: Single screen interaction
> - **Use Flow**: Multi-page sequence or reusable navigation pattern

### Page Types

| PageType    | Description               | Use Case                       | Example                          |
| ----------- | ------------------------- | ------------------------------ | -------------------------------- |
| `form`      | Data entry/input page     | Creating or editing records    | Patient Registration Form        |
| `detail`    | Single record display     | Viewing complete information   | Patient Profile Detail           |
| `list`      | Multiple items display    | Browsing collections           | Patient List, Appointment Queue  |
| `dashboard` | Analytics/overview        | Summarized data views          | Doctor Dashboard, Admin Overview |
| `modal`     | Overlay/popup interaction | Quick actions, confirmations   | Delete Confirmation, Quick Edit  |
| `menu`      | Navigation/selection      | Choosing options or navigation | Main Menu, Settings Menu         |
| `search`    | Search results display    | Finding specific items         | Patient Search Results           |
| `settings`  | Configuration page        | User/system preferences        | Account Settings, Notifications  |
| `wizard`    | Multi-step guided flow    | Complex sequential input       | Onboarding Wizard, Checkout Flow |
| `report`    | Data report display       | Formatted data presentation    | Lab Report, Discharge Summary    |
| `calendar`  | Date-based view           | Scheduling, events             | Appointment Calendar             |
| `kanban`    | Status-based board        | Workflow tracking              | Patient Status Board             |

### PageType Selection Rules

| Step Function          | PageType    | Example Step                       |
| ---------------------- | ----------- | ---------------------------------- |
| Data entry/input       | `form`      | "Enter Patient Information"        |
| Single record display  | `detail`    | "View Patient Profile"             |
| Multiple items view    | `list`      | "Browse All Patients"              |
| Analytics/overview     | `dashboard` | "View Department Statistics"       |
| Quick action overlay   | `modal`     | "Confirm Appointment Cancellation" |
| Navigation/selection   | `menu`      | "Select Department"                |
| Search results         | `search`    | "Find Patient Records"             |
| Settings configuration | `settings`  | "Configure Notifications"          |
| Multi-step process     | `wizard`    | "Complete Registration Process"    |
| Report generation      | `report`    | "Generate Discharge Summary"       |
| Schedule management    | `calendar`  | "Manage Appointments"              |
| Workflow tracking      | `kanban`    | "Track Patient Status"             |

### PageType Examples

```
Step: "Enter Patient Information"
  → PageType: "form"
  → Components: PatientRegistrationForm (ORGANISM)

Step: "View Patient Profile"
  → PageType: "detail"
  → Components: PatientHeader, MedicalHistory, Appointments (ORGANISMs)

Step: "Browse All Patients"
  → PageType: "list"
  → Components: SearchFilters, PatientTable, Pagination (ORGANISMs)

Step: "View Department Statistics"
  → PageType: "dashboard"
  → Components: MetricCards, Charts, RecentActivity (ORGANISMs)
```

### Action → Page Mapping (Alternative to Component)

When an Action represents a page-level interaction rather than a specific UI element, map it directly to a Page using `actionIds`:

| Action Pattern                              | Map To    | Example                             |
| ------------------------------------------- | --------- | ----------------------------------- |
| Page-level action (navigate, view)          | Page      | "View Dashboard" → Dashboard Page   |
| Element-level action (click, enter, select) | Component | "Enter Name" → Name Input Component |

> **Implementation Note:** To support Action → Page mapping, add `actionIds?: string[]` to the `PageGraph` entity and `PageDto` validation.

### Payload Structure

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Page",
  "data": {
    "name": "{Step.step} Page",
    "description": "Page for {Step.description}",
    "pageType": "form | list | detail | dashboard | modal | menu | search | settings",
    "requiresAuth": true | false,
    "allowedRoles": ["{Persona.persona}"],
    "flowId": "{parent Flow.id}",
    "stepIds": ["{Step.id}"],
    "actionIds": ["{Action.id}"]
  }
}
```

> **Note:**
>
> - Use `stepIds` OR leave empty based on exclusive mapping rule
> - Use `actionIds` only for page-level actions (requires entity update - see Implementation Note above)

### Example 1: Step maps to Page

```
Functional: Step "Order Medical Tests"
     ↓
Design: Page "Order Medical Tests Page"
        pageType: "form"
        requiresAuth: true
        allowedRoles: ["Doctor"]
        flowId: "{Flow.id}"
        stepIds: ["1774964938277-vfem9cu"]
        actionIds: [] (actions map to components instead)
```

### Example 2: Action maps to Page

```
Functional: Action "View Patient Dashboard"
     ↓
Design: Page "Patient Dashboard"
        pageType: "dashboard"
        stepIds: [] (step maps to flow instead)
        actionIds: ["action-123"]
```

---

## 4. Component Generation Rules

**Source:** Functional `Action` node

### Rules

1. **Action → Component (Exclusive)** - An Action can map to a Page OR a Component, not both
2. **When to use Component**: When the action represents a specific UI interaction element
3. **Atomic Design hierarchy**: Use ORGANISM → MOLECULE → ATOM pattern
4. **Grouping actions**: Related actions become child components of an ORGANISM
5. **Cross-ontology link**: Set `actionIds` for `IMPLEMENTED_BY` relationship
6. **Template as Component**: Templates are TEMPLATE type components applied to pages

> **Note:** If an Action is mapped to a Component, do NOT also map it to a Page. Choose based on granularity:
>
> - **Use Page**: When the action represents an entire page-level interaction
> - **Use Component**: When the action represents a specific UI element interaction

### Component Types (Atomic Design Hierarchy)

| Type       | Definition                                 | When to Use                                             |
| ---------- | ------------------------------------------ | ------------------------------------------------------- |
| `TEMPLATE` | Reusable layout pattern for page structure | Page-level layout (header, sidebar, content areas)      |
| `ORGANISM` | Complex component with multiple molecules  | Forms, cards, tables, panels containing multiple inputs |
| `MOLECULE` | Group of atoms functioning as a unit       | Input with label, search box with button, card item     |
| `ATOM`     | Single UI element                          | Button, input field, label, icon, checkbox              |

---

### Component Categories by Function

Components can also be categorized by their functional purpose. Use these as `designSystemRef` values:

#### Input Components

| Component       | Type     | Description              | Example Action         |
| --------------- | -------- | ------------------------ | ---------------------- |
| `TextInput`     | ATOM     | Single-line text entry   | "Enter patient name"   |
| `TextArea`      | ATOM     | Multi-line text entry    | "Enter medical notes"  |
| `NumberInput`   | ATOM     | Numeric value entry      | "Enter age"            |
| `PasswordInput` | ATOM     | Masked text entry        | "Enter password"       |
| `EmailInput`    | ATOM     | Email format entry       | "Enter email address"  |
| `PhoneInput`    | MOLECULE | Phone number with format | "Enter contact number" |
| `SearchInput`   | MOLECULE | Search with suggestions  | "Search patients"      |
| `AutoComplete`  | MOLECULE | Input with auto-complete | "Select medication"    |

#### Selection Components

| Component          | Type     | Description                 | Example Action         |
| ------------------ | -------- | --------------------------- | ---------------------- |
| `Checkbox`         | ATOM     | Binary selection            | "Accept terms"         |
| `RadioGroup`       | MOLECULE | Single selection from group | "Select gender"        |
| `Select`           | ATOM     | Dropdown selection          | "Select department"    |
| `MultiSelect`      | MOLECULE | Multiple selection dropdown | "Select symptoms"      |
| `Toggle`           | ATOM     | On/off switch               | "Enable notifications" |
| `SegmentedControl` | MOLECULE | Button group selection      | "Select view mode"     |
| `Slider`           | ATOM     | Range value selection       | "Set pain level"       |
| `Rating`           | MOLECULE | Star/score rating           | "Rate experience"      |

#### Date/Time Components

| Component         | Type     | Description            | Example Action            |
| ----------------- | -------- | ---------------------- | ------------------------- |
| `DatePicker`      | ATOM     | Single date selection  | "Select birth date"       |
| `TimePicker`      | ATOM     | Time selection         | "Select appointment time" |
| `DateTimePicker`  | MOLECULE | Combined date and time | "Schedule appointment"    |
| `DateRangePicker` | MOLECULE | Start and end dates    | "Select date range"       |
| `Calendar`        | ORGANISM | Full calendar view     | "View monthly schedule"   |

#### Button Components

| Component              | Type     | Description            | Example Action   |
| ---------------------- | -------- | ---------------------- | ---------------- |
| `Button`               | ATOM     | Primary action trigger | "Submit form"    |
| `IconButton`           | ATOM     | Icon-only button       | "Delete item"    |
| `ButtonGroup`          | MOLECULE | Grouped buttons        | "Save / Cancel"  |
| `SplitButton`          | MOLECULE | Button with dropdown   | "Export as..."   |
| `FloatingActionButton` | ATOM     | FAB for primary action | "Add new record" |
| `LinkButton`           | ATOM     | Text link style button | "View details"   |

#### Display Components

| Component | Type | Description          | Example Action           |
| --------- | ---- | -------------------- | ------------------------ |
| `Label`   | ATOM | Text label           | Display field name       |
| `Text`    | ATOM | Body text            | Display information      |
| `Heading` | ATOM | Title/heading text   | Section title            |
| `Badge`   | ATOM | Status indicator     | "Show status"            |
| `Tag`     | ATOM | Categorization label | "Show category"          |
| `Avatar`  | ATOM | User/entity image    | Display user photo       |
| `Icon`    | ATOM | Visual indicator     | Display status icon      |
| `Image`   | ATOM | Image display        | Display medical image    |
| `Video`   | ATOM | Video player         | Play instructional video |

#### Feedback Components

| Component     | Type     | Description            | Example Action           |
| ------------- | -------- | ---------------------- | ------------------------ |
| `Alert`       | MOLECULE | Inline message         | Show validation error    |
| `Toast`       | MOLECULE | Temporary notification | Show success message     |
| `Snackbar`    | MOLECULE | Action notification    | Show undo option         |
| `ProgressBar` | ATOM     | Linear progress        | Show upload progress     |
| `Spinner`     | ATOM     | Loading indicator      | Show loading state       |
| `Skeleton`    | ATOM     | Content placeholder    | Show loading placeholder |
| `Tooltip`     | ATOM     | Contextual help        | Show field hint          |

#### Navigation Components

| Component    | Type     | Description         | Example Action        |
| ------------ | -------- | ------------------- | --------------------- |
| `Navbar`     | ORGANISM | Main navigation bar | Navigate application  |
| `Sidebar`    | ORGANISM | Side navigation     | Navigate sections     |
| `Breadcrumb` | MOLECULE | Location trail      | Show current location |
| `Tabs`       | MOLECULE | Tab navigation      | Switch between views  |
| `Stepper`    | MOLECULE | Step indicator      | Show wizard progress  |
| `Pagination` | MOLECULE | Page navigation     | Navigate list pages   |
| `Menu`       | MOLECULE | Dropdown menu       | Show action options   |
| `Link`       | ATOM     | Navigation link     | Navigate to page      |

#### Layout Components

| Component   | Type     | Description          | Example Action            |
| ----------- | -------- | -------------------- | ------------------------- |
| `Card`      | ORGANISM | Content container    | Group related info        |
| `Panel`     | ORGANISM | Section container    | Group form section        |
| `Accordion` | ORGANISM | Collapsible sections | Expand/collapse sections  |
| `Modal`     | ORGANISM | Overlay dialog       | Show confirmation         |
| `Drawer`    | ORGANISM | Slide-in panel       | Show filters              |
| `Divider`   | ATOM     | Visual separator     | Separate sections         |
| `Spacer`    | ATOM     | Layout spacing       | Add whitespace            |
| `Grid`      | TEMPLATE | Grid layout          | Arrange components        |
| `Stack`     | TEMPLATE | Stack layout         | Vertical/horizontal stack |

#### Data Display Components

| Component  | Type     | Description           | Example Action              |
| ---------- | -------- | --------------------- | --------------------------- |
| `Table`    | ORGANISM | Data table            | Display patient list        |
| `DataGrid` | ORGANISM | Advanced data grid    | Display with sorting/filter |
| `List`     | ORGANISM | Vertical list         | Display items               |
| `Tree`     | ORGANISM | Hierarchical view     | Display org structure       |
| `Timeline` | ORGANISM | Chronological display | Show patient history        |
| `Chart`    | ORGANISM | Data visualization    | Show statistics             |
| `StatCard` | MOLECULE | Metric display        | Show KPI value              |

#### Form Components

| Component      | Type     | Description           | Example Action      |
| -------------- | -------- | --------------------- | ------------------- |
| `Form`         | ORGANISM | Form container        | Group form fields   |
| `FormField`    | MOLECULE | Label + input + error | Single form field   |
| `FormSection`  | ORGANISM | Grouped form fields   | Section of form     |
| `FormActions`  | MOLECULE | Form action buttons   | Submit/Reset/Cancel |
| `FileUpload`   | MOLECULE | File upload control   | Upload document     |
| `ImageUpload`  | MOLECULE | Image upload control  | Upload photo        |
| `SignaturePad` | MOLECULE | Signature capture     | Capture signature   |

#### Medical-Specific Components

| Component         | Type     | Description           | Example Action      |
| ----------------- | -------- | --------------------- | ------------------- |
| `VitalsCard`      | ORGANISM | Vital signs display   | Show patient vitals |
| `MedicationList`  | ORGANISM | Medication display    | Show prescriptions  |
| `LabResultsTable` | ORGANISM | Lab results display   | Show test results   |
| `DiagnosisCard`   | ORGANISM | Diagnosis information | Show diagnosis      |
| `AppointmentCard` | MOLECULE | Appointment details   | Show appointment    |
| `PatientHeader`   | ORGANISM | Patient summary       | Show patient info   |
| `BodyDiagram`     | ORGANISM | Anatomical diagram    | Select body part    |

---

### TEMPLATE Type

**Definition:** Reusable layout pattern that defines the structural arrangement of a page.

| Template Example     | Layout Structure                           | Use Case                  |
| -------------------- | ------------------------------------------ | ------------------------- |
| `FormPageTemplate`   | Header + Form Body + Actions Footer        | Data entry pages          |
| `ListPageTemplate`   | Header + Filters + Data Table + Pagination | List/search result pages  |
| `DetailPageTemplate` | Header + Content Sections + Action Bar     | Single record detail view |
| `DashboardTemplate`  | Header + Widget Grid + Sidebar             | Analytics/overview pages  |
| `SplitPaneTemplate`  | Navigation Sidebar + Main Content          | Master-detail layouts     |
| `ModalTemplate`      | Title Bar + Body + Action Buttons          | Dialog/overlay screens    |
| `WizardTemplate`     | Progress Bar + Step Content + Navigation   | Multi-step forms          |

**Example:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "FormPageTemplate",
    "type": "TEMPLATE",
    "description": "Standard form page with header, scrollable form body, and sticky action footer",
    "layoutType": "flex",
    "slots": ["page-header", "form-body", "action-footer"],
    "pageId": "patient-registration-page"
  }
}
```

---

### ORGANISM Type

**Definition:** Complex, self-contained component composed of molecules and/or atoms that forms a distinct section of the UI.

| Organism Example          | Contains                                      | Use Case                   |
| ------------------------- | --------------------------------------------- | -------------------------- |
| `PatientRegistrationForm` | Name, DOB, Gender, Contact fields             | Complete registration form |
| `MedicalHistoryCard`      | Condition list, Date, Severity                | Display medical history    |
| `AppointmentScheduler`    | Calendar, Time slots, Doctor selection        | Book appointments          |
| `SearchResultsTable`      | Headers, Rows, Pagination, Actions            | Display search results     |
| `NavigationHeader`        | Logo, Menu items, User profile, Notifications | Page header navigation     |
| `DiagnosisPanel`          | Test results, Findings, Recommendations       | Diagnosis summary          |
| `PaymentForm`             | Card details, Billing address, Submit         | Payment processing         |

**Example:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "PatientRegistrationForm",
    "type": "ORGANISM",
    "description": "Complete patient registration form with all required fields",
    "designSystemRef": "FormContainer",
    "layoutType": "flex",
    "states": ["default", "loading", "error", "success"],
    "pageId": "registration-page",
    "actionIds": []
  }
}
```

---

### MOLECULE Type

**Definition:** Group of atoms that function together as a unit to perform a specific task.

| Molecule Example    | Contains                                     | Use Case                          |
| ------------------- | -------------------------------------------- | --------------------------------- |
| `TextInputField`    | Label + Input + Error message                | Single text input with validation |
| `SearchBox`         | Input + Search button + Clear button         | Search functionality              |
| `DateRangePicker`   | Start date + End date + Presets              | Date range selection              |
| `FileUploader`      | Drop zone + File list + Progress bar         | File upload interface             |
| `PaginationControl` | Page numbers + Prev/Next + Page size         | Table pagination                  |
| `UserAvatar`        | Image + Name + Status indicator              | User identity display             |
| `NotificationItem`  | Icon + Message + Timestamp + Actions         | Single notification               |
| `AddressInput`      | Street + City + State + Zip fields           | Address entry group               |
| `TestResultRow`     | Test name + Value + Reference range + Status | Lab result display                |

**Example:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "PatientNameInput",
    "type": "MOLECULE",
    "description": "Patient name input field with label and validation",
    "designSystemRef": "TextInputField",
    "props": "{\"label\": \"Patient Name\", \"required\": true, \"maxLength\": 100}",
    "states": ["default", "focused", "error", "disabled"],
    "parentComponentId": "patient-registration-form",
    "actionIds": ["1774964938304-l2glj6n"]
  }
}
```

---

### ATOM Type

**Definition:** Basic UI building block that cannot be broken down further while maintaining functionality.

| Atom Example  | Description                 | Use Case                      |
| ------------- | --------------------------- | ----------------------------- |
| `Button`      | Clickable action trigger    | Submit, Cancel, Save actions  |
| `TextInput`   | Single-line text entry      | Name, email, search input     |
| `TextArea`    | Multi-line text entry       | Notes, descriptions, comments |
| `Checkbox`    | Binary selection            | Agreement, feature toggles    |
| `RadioButton` | Single selection from group | Gender, payment method        |
| `Select`      | Dropdown selection          | Country, category selection   |
| `DatePicker`  | Date selection              | Birth date, appointment date  |
| `TimePicker`  | Time selection              | Appointment time              |
| `Label`       | Text display                | Field labels, section titles  |
| `Icon`        | Visual indicator            | Status icons, action icons    |
| `Badge`       | Status/count indicator      | Notification count, status    |
| `Spinner`     | Loading indicator           | Async operation feedback      |
| `Avatar`      | User/entity image           | Profile pictures              |
| `Divider`     | Visual separator            | Section separation            |
| `Tooltip`     | Contextual help             | Field hints, explanations     |

**Example:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "SubmitButton",
    "type": "ATOM",
    "description": "Submit button for form submission",
    "designSystemRef": "Button",
    "props": "{\"variant\": \"primary\", \"size\": \"large\", \"label\": \"Submit\"}",
    "states": ["default", "hover", "active", "disabled", "loading"],
    "parentComponentId": "patient-registration-form",
    "actionIds": ["submit-action-id"]
  }
}
```

---

### Component Type Selection Rules

| Action Pattern              | Component Type | Example                                          |
| --------------------------- | -------------- | ------------------------------------------------ |
| Complete functional section | `ORGANISM`     | "Patient Registration" → PatientRegistrationForm |
| Grouped input with label    | `MOLECULE`     | "Enter patient name" → PatientNameInput          |
| Single input action         | `ATOM`         | "Enter age" → NumberInput                        |
| Selection from options      | `ATOM`         | "Select gender" → GenderSelect                   |
| Submit/trigger action       | `ATOM`         | "Submit form" → SubmitButton                     |
| Display data group          | `MOLECULE`     | "Show test result" → TestResultRow               |
| Complex data display        | `ORGANISM`     | "View all results" → TestResultsTable            |
| Date/time entry             | `MOLECULE`     | "Select appointment" → DateTimePicker            |
| Page layout structure       | `TEMPLATE`     | Layout definition → FormPageTemplate             |

### Hierarchical Composition Rules

```
Page
├── TEMPLATE (optional - page layout structure)
└── ORGANISM (main functional container)
    ├── MOLECULE (grouped inputs/controls)
    │   └── ATOM (individual elements)
    └── ATOM (standalone elements)
```

---

## Component Reusability Rules

Components should be designed for maximum reusability across pages, flows, and user journeys. Follow these principles when creating component hierarchies.

### Reusability Principles

| Principle                        | Description                                  | Example                                       |
| -------------------------------- | -------------------------------------------- | --------------------------------------------- | ------------ |
| **Single Responsibility**        | Each component does one thing well           | `DatePicker` only handles date selection      |
| **Composition over Inheritance** | Build complex components from simple ones    | `FormField` = Label + Input + ErrorMessage    |
| **Context Independence**         | Components work without knowing their parent | `Button` works in any form or card            |
| **Configurable via Props**       | Behavior changes through props, not code     | `Button` with `variant: "primary"             | "secondary"` |
| **Stateless when Possible**      | Prefer stateless components for reusability  | `DisplayCard` receives data, doesn't fetch it |

### Reusability Levels

| Level        | Scope                  | Description                     | Example                       |
| ------------ | ---------------------- | ------------------------------- | ----------------------------- |
| **Global**   | Entire application     | Used across all pages and flows | Button, TextInput, Icon       |
| **Domain**   | Specific domain/module | Used within a business domain   | PatientCard, AppointmentSlot  |
| **Page**     | Single page            | Specific to one page's layout   | DashboardHeader, ReportFooter |
| **Instance** | One-time use           | Unique, non-reusable component  | SpecialPromoBanner            |

### Identifying Reusable Components

When analyzing Actions, identify reusability by checking:

```
Is this action pattern repeated?
    │
    ├── YES across multiple Scenarios → Create GLOBAL component
    │       Example: "Enter name" appears in Patient, Doctor, Staff forms
    │       → Create reusable TextInputField (MOLECULE)
    │
    ├── YES within same Outcome → Create DOMAIN component
    │       Example: "Show patient vitals" in multiple diagnosis scenarios
    │       → Create reusable VitalsCard (ORGANISM)
    │
    └── NO, unique to this Step → Create PAGE-SPECIFIC component
            Example: "Display special certification badge"
            → Create CertificationBadge (ATOM) - page specific
```

### Reusable Component Hierarchy Patterns

#### Pattern 1: Form Field Pattern (MOLECULE)

Reuse the same field structure across all forms:

```
TextInputField (MOLECULE) - GLOBAL REUSABLE
├── Label (ATOM)
├── TextInput (ATOM)
├── HelperText (ATOM)
└── ErrorMessage (ATOM)

Usage:
- Patient Registration Form → PatientNameField (uses TextInputField)
- Doctor Profile Form → DoctorNameField (uses TextInputField)
- Staff Onboarding Form → StaffNameField (uses TextInputField)
```

**Payload:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "TextInputField",
    "type": "MOLECULE",
    "description": "Reusable text input with label, helper, and error - GLOBAL",
    "designSystemRef": "TextInputField",
    "props": "{\"label\": \"string\", \"placeholder\": \"string\", \"required\": \"boolean\", \"helperText\": \"string\"}",
    "states": ["default", "focused", "error", "disabled", "readonly"],
    "children": [
      { "name": "Label", "type": "ATOM" },
      { "name": "TextInput", "type": "ATOM" },
      { "name": "HelperText", "type": "ATOM" },
      { "name": "ErrorMessage", "type": "ATOM" }
    ]
  }
}
```

#### Pattern 2: Card Pattern (ORGANISM)

Reuse card structure with different content:

```
BaseCard (ORGANISM) - GLOBAL REUSABLE
├── CardHeader (MOLECULE)
│   ├── Title (ATOM)
│   ├── Subtitle (ATOM)
│   └── ActionMenu (MOLECULE)
├── CardBody (MOLECULE) - SLOT for content
└── CardFooter (MOLECULE)
    └── ActionButtons (MOLECULE)

Domain Extensions:
- PatientCard extends BaseCard (adds patient-specific fields)
- AppointmentCard extends BaseCard (adds appointment-specific fields)
- TestResultCard extends BaseCard (adds result-specific fields)
```

**Payload:**

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "BaseCard",
    "type": "ORGANISM",
    "description": "Reusable card container with header, body slot, and footer - GLOBAL",
    "designSystemRef": "Card",
    "layoutType": "flex",
    "slots": ["card-header", "card-body", "card-footer"],
    "states": ["default", "hover", "selected", "expanded"],
    "children": [
      {
        "name": "CardHeader",
        "type": "MOLECULE",
        "children": [
          { "name": "Title", "type": "ATOM" },
          { "name": "Subtitle", "type": "ATOM" },
          { "name": "ActionMenu", "type": "MOLECULE" }
        ]
      },
      {
        "name": "CardFooter",
        "type": "MOLECULE",
        "children": [{ "name": "ActionButtons", "type": "MOLECULE" }]
      }
    ]
  }
}
```

#### Pattern 3: Table Pattern (ORGANISM)

Reuse table structure with configurable columns:

```
DataTable (ORGANISM) - GLOBAL REUSABLE
├── TableToolbar (MOLECULE)
│   ├── SearchInput (MOLECULE)
│   ├── FilterDropdown (MOLECULE)
│   └── ActionButtons (MOLECULE)
├── TableHeader (MOLECULE)
│   └── ColumnHeader[] (ATOM) - configurable
├── TableBody (MOLECULE)
│   └── TableRow[] (MOLECULE) - configurable
└── TableFooter (MOLECULE)
    └── Pagination (MOLECULE)

Domain Extensions:
- PatientTable → columns: [Name, Age, Gender, Status, Actions]
- AppointmentTable → columns: [Date, Time, Doctor, Patient, Status]
- LabResultsTable → columns: [Test, Value, Reference, Status]
```

#### Pattern 4: Form Section Pattern (ORGANISM)

Reuse form sections across different forms:

```
FormSection (ORGANISM) - GLOBAL REUSABLE
├── SectionHeader (MOLECULE)
│   ├── Title (ATOM)
│   └── Description (ATOM)
├── SectionBody (MOLECULE) - SLOT for fields
└── SectionDivider (ATOM)

Reusable Sections:
- PersonalInfoSection (used in Patient, Doctor, Staff forms)
- AddressSection (used in Patient, Billing, Shipping forms)
- ContactSection (used in Patient, Emergency Contact, Referral forms)
- InsuranceSection (used in Patient Registration, Claims forms)
```

### Reusability Matrix

Map Actions to reusable components based on patterns:

| Action Pattern              | Reusable Component | Reusability Level | Type     |
| --------------------------- | ------------------ | ----------------- | -------- |
| "Enter {field} name"        | TextInputField     | GLOBAL            | MOLECULE |
| "Enter {field} email"       | EmailInputField    | GLOBAL            | MOLECULE |
| "Enter {field} phone"       | PhoneInputField    | GLOBAL            | MOLECULE |
| "Select {field} date"       | DatePickerField    | GLOBAL            | MOLECULE |
| "Select {option} from list" | SelectField        | GLOBAL            | MOLECULE |
| "Upload {type} file"        | FileUploadField    | GLOBAL            | MOLECULE |
| "View {entity} list"        | DataTable          | GLOBAL            | ORGANISM |
| "View {entity} details"     | DetailCard         | GLOBAL            | ORGANISM |
| "Fill {domain} form"        | BaseForm           | GLOBAL            | ORGANISM |
| "Show patient info"         | PatientCard        | DOMAIN            | ORGANISM |
| "Show appointment"          | AppointmentCard    | DOMAIN            | ORGANISM |
| "Show test results"         | LabResultCard      | DOMAIN            | ORGANISM |
| "Show vitals"               | VitalsCard         | DOMAIN            | ORGANISM |

### Component Inheritance Example

```
Action: "Enter patient name"
Action: "Enter doctor name"
Action: "Enter staff name"

Instead of creating 3 separate components:
✗ PatientNameInput
✗ DoctorNameInput
✗ StaffNameInput

Create ONE reusable component with props:
✓ TextInputField (MOLECULE) - GLOBAL
  props: { label: "Patient Name" | "Doctor Name" | "Staff Name" }

Instances:
- PatientNameField: TextInputField with label="Patient Name"
- DoctorNameField: TextInputField with label="Doctor Name"
- StaffNameField: TextInputField with label="Staff Name"
```

### Reusability in Payload Structure

When creating components, indicate reusability:

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "TextInputField",
    "type": "MOLECULE",
    "description": "Reusable text input field with label and validation",
    "designSystemRef": "TextInputField",
    "props": "{\"label\": \"string\", \"required\": \"boolean\", \"maxLength\": \"number\"}",
    "reusability": "GLOBAL",
    "usedIn": [
      "PatientRegistrationForm",
      "DoctorProfileForm",
      "StaffOnboardingForm"
    ],
    "pageId": null,
    "actionIds": []
  }
}
```

### Component Creation Decision Tree

```
When creating a component from an Action:

1. Does a similar component already exist?
   │
   ├── YES → Reuse existing component with different props
   │         Example: Use TextInputField for all text inputs
   │
   └── NO → Continue to step 2

2. Will this pattern repeat in other contexts?
   │
   ├── YES, across application → Create GLOBAL component
   │   └── Place in shared component library
   │
   ├── YES, within domain → Create DOMAIN component
   │   └── Place in domain-specific library
   │
   └── NO → Create PAGE-SPECIFIC component
       └── Attach directly to page

3. What is the appropriate granularity?
   │
   ├── Single UI element → ATOM
   ├── Group of atoms with behavior → MOLECULE
   ├── Self-contained section → ORGANISM
   └── Page layout structure → TEMPLATE
```

### Example: Building Reusable Hierarchy

**Scenario:** Multiple forms need patient demographics

```
Functional Actions:
- "Enter patient name" (Patient Registration)
- "Enter patient age" (Patient Registration)
- "Enter patient name" (Appointment Booking)
- "Enter emergency contact name" (Emergency Form)

Reusable Component Hierarchy:

GLOBAL ATOMS:
├── TextInput
├── NumberInput
├── Label
└── ErrorMessage

GLOBAL MOLECULES (built from atoms):
├── TextInputField (Label + TextInput + ErrorMessage)
├── NumberInputField (Label + NumberInput + ErrorMessage)
└── SelectField (Label + Select + ErrorMessage)

DOMAIN ORGANISMS (built from molecules):
├── PersonalInfoSection
│   ├── NameField (TextInputField with label="Name")
│   ├── AgeField (NumberInputField with label="Age")
│   └── GenderField (SelectField with label="Gender")
│
└── ContactInfoSection
    ├── PhoneField (PhoneInputField)
    ├── EmailField (EmailInputField)
    └── AddressFields (AddressInput)

PAGE ORGANISMS (built from domain organisms):
├── PatientRegistrationForm
│   ├── PersonalInfoSection (reused)
│   ├── ContactInfoSection (reused)
│   └── InsuranceSection
│
├── AppointmentBookingForm
│   ├── PersonalInfoSection (reused)
│   └── AppointmentDetailsSection
│
└── EmergencyContactForm
    └── ContactInfoSection (reused)
```

**Benefits:**

- `TextInputField` created once, used everywhere
- `PersonalInfoSection` reused across 3 different forms
- Changes to `TextInputField` automatically apply to all forms
- Consistent UX across the application

### Action → Component Type Mapping

| Action Pattern          | Component Type                  | Example                                                |
| ----------------------- | ------------------------------- | ------------------------------------------------------ |
| Multiple related inputs | ORGANISM with MOLECULE children | "Record Patient Information" → Patient Form (ORGANISM) |
| Single input action     | MOLECULE or ATOM                | "Enter patient name" → Name Input (ATOM)               |
| Selection action        | ATOM (select/dropdown)          | "Select gender" → Gender Select (ATOM)                 |
| Submit/trigger action   | ATOM (button)                   | "Submit form" → Submit Button (ATOM)                   |
| Display action          | MOLECULE or ORGANISM            | "View results" → Results Panel (ORGANISM)              |
| Date/time entry         | MOLECULE                        | "Enter admission date" → DateTime Picker (MOLECULE)    |

### Payload Structure

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Component",
  "data": {
    "name": "{derived from Action.action}",
    "type": "TEMPLATE | ORGANISM | MOLECULE | ATOM",
    "description": "{Action.description or derived}",
    "designSystemRef": "Reference to design system component",
    "props": "JSON string of component properties",
    "states": [
      "default",
      "hover",
      "active",
      "disabled",
      "loading",
      "error",
      "success"
    ],
    "layoutType": "flex | grid | stack | absolute",
    "slots": ["header", "content", "footer", "actions"],
    "pageId": "{parent Page.id}",
    "parentComponentId": "{parent Component.id for nested}",
    "actionIds": ["{Action.id}"]
  }
}
```

### Example

```
Functional: Step "Order Medical Tests"
           Actions:
             - "Request USG Abdomen and Pelvis" (order: 1)
             - "Request CECT Abdomen" (order: 2)
             - "Request S.CEA test" (order: 3)
     ↓
Design:
  ORGANISM: "Medical Test Order Form"
    ├── MOLECULE: "USG Request Field" (actionIds: ["1774964938303-yq7hiwo"])
    ├── MOLECULE: "CECT Request Field" (actionIds: ["1774964938303-6hacwy4"])
    ├── MOLECULE: "S.CEA Request Field" (actionIds: ["1774964938303-etfshbq"])
    └── ATOM: "Submit Order Button"
```

---

## 5. Template Generation Rules (as Component)

**Source:** No direct functional mapping (design decision)

### Rules

1. **Template = Component with type "TEMPLATE"**
2. **Purpose**: Define reusable page layouts
3. **No actionIds**: Templates don't map to functional actions
4. **Applied to Pages**: Referenced by pages for layout consistency

### Common Template Patterns

| Template Name      | Layout Structure                     | Use Case             |
| ------------------ | ------------------------------------ | -------------------- |
| Form Template      | Header + Form Body + Actions         | Data entry pages     |
| List Template      | Header + Filters + List + Pagination | List/search pages    |
| Detail Template    | Header + Content Sections + Actions  | Detail view pages    |
| Dashboard Template | Header + Grid of Cards/Widgets       | Overview pages       |
| Split Template     | Sidebar + Main Content               | Navigation + content |
| Modal Template     | Header + Body + Footer Actions       | Overlay dialogs      |

### Payload Structure

```json
{
  "uuid": "<projectUuid from .breeze.json>",
  "apiKey": "<apiKey from .breeze.json>",
  "label": "Component",
  "data": {
    "name": "{Template Name}",
    "type": "TEMPLATE",
    "description": "Reusable layout pattern for {purpose}",
    "designSystemRef": "Layout reference",
    "layoutType": "flex | grid",
    "slots": ["header", "sidebar", "content", "footer", "actions"],
    "pageId": "{Page.id where applied}"
  }
}
```

### Example

```json
{
  "uuid": "<projectUuid>",
  "apiKey": "<apiKey>",
  "label": "Component",
  "data": {
    "name": "Form Page Template",
    "type": "TEMPLATE",
    "description": "Standard form page layout with header, form area, and action buttons",
    "layoutType": "flex",
    "slots": ["header", "form-body", "actions"],
    "pageId": "page-123"
  }
}
```

---

## Complete Generation Algorithm

```
FOR each Scenario in Functional Graph:
    1. CREATE UserJourney
       - name = Scenario.scenario
       - scenarioId = Scenario.id

    FOR each Step in Scenario (ordered by step.order):

        2. DECIDE: Is this Step a multi-page sequence or single screen?

        IF Step is multi-page sequence:
            3a. CREATE Flow (Step maps to Flow)
                - name = Step.step + " Flow"
                - modality = determine from context
                - stepIds = [Step.id]
                - userJourneyId = UserJourney.id

            4a. CREATE Page(s) within Flow
                - flowId = Flow.id
                - stepIds = [] (empty - Step already mapped to Flow)

        ELSE (Step is single screen):
            3b. CREATE Page directly (Step maps to Page)
                - name = Step.step + " Page"
                - pageType = determine from Step function
                - flowId = parent Flow.id (if exists)
                - stepIds = [Step.id]

        5. CREATE Template Component (if needed)
           - type = "TEMPLATE"
           - pageId = Page.id

        FOR each Action in Step:

            6. DECIDE: Is this Action page-level or element-level?

            IF Action is page-level:
                7a. MAP Action to Page
                    - Page.actionIds = [Action.id]

            ELSE (Action is element-level):
                7b. GROUP Actions by logical function

                FOR each Action Group:
                    8. CREATE ORGANISM Component
                       - pageId = Page.id
                       - actionIds = [] (empty - actions map to children)

                    FOR each Action in Group:
                        9. CREATE MOLECULE/ATOM Component
                           - parentComponentId = ORGANISM.id
                           - actionIds = [Action.id]
```

### Decision Flowchart

```
                    ┌─────────────┐
                    │    Step     │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │  Multi-page sequence?   │
              └────────────┬────────────┘
                    ┌──────┴──────┐
                   YES            NO
                    │              │
                    ▼              ▼
               ┌────────┐    ┌────────┐
               │  Flow  │    │  Page  │
               └────────┘    └────────┘


                    ┌─────────────┐
                    │   Action    │
                    └──────┬──────┘
                           │
              ┌────────────┴────────────┐
              │   Page-level action?    │
              └────────────┬────────────┘
                    ┌──────┴──────┐
                   YES            NO
                    │              │
                    ▼              ▼
               ┌────────┐    ┌───────────┐
               │  Page  │    │ Component │
               └────────┘    └───────────┘
```

---

## Quick Reference Card

| From (Functional) | To (Design)           | Key Fields                   | Exclusive?           |
| ----------------- | --------------------- | ---------------------------- | -------------------- |
| Scenario          | UserJourney           | `scenarioId`                 | No                   |
| Step              | Flow **OR** Page      | `stepIds`                    | **Yes** (choose one) |
| Action            | Page **OR** Component | `actionIds`                  | **Yes** (choose one) |
| -                 | Template (Component)  | `type: "TEMPLATE"`, `pageId` | N/A                  |

### Decision Matrix for Exclusive Mappings

| Functional Node | Choose This Design Node | When                                                                |
| --------------- | ----------------------- | ------------------------------------------------------------------- |
| Step            | **Flow**                | Multi-page sequence, reusable navigation pattern                    |
| Step            | **Page**                | Single screen interaction                                           |
| Action          | **Page**                | Page-level interaction (navigate, view entire screen)               |
| Action          | **Component**           | Element-level interaction (click button, enter text, select option) |

---

## Cross-Ontology Relationships

### MAPS_TO Relationship

- **Scenario → UserJourney**: Created when `scenarioId` is provided
- **Step → Flow**: Created when `stepIds` is provided on Flow (**exclusive with Step → Page**)
- **Step → Page**: Created when `stepIds` is provided on Page (**exclusive with Step → Flow**)

### IMPLEMENTED_BY Relationship

- **Action → Page**: Created when `actionIds` is provided on Page (**exclusive with Action → Component**)
- **Action → Component**: Created when `actionIds` is provided on Component (**exclusive with Action → Page**)

### Exclusive Mapping Constraint

```
Step ──┬──► Flow     (if multi-page sequence)
       │
       └──► Page     (if single screen)

       ⚠️ Cannot map to BOTH

Action ──┬──► Page       (if page-level action)
         │
         └──► Component  (if element-level action)

         ⚠️ Cannot map to BOTH
```

---

## Appendix: All Types Reference

### Modality Types

| Value      | Description               |
| ---------- | ------------------------- |
| `web`      | Browser-based interface   |
| `mobile`   | Native mobile application |
| `desktop`  | Desktop application       |
| `api`      | Backend/Integration layer |
| `voice`    | Voice-based interface     |
| `kiosk`    | Self-service terminal     |
| `wearable` | Wearable device interface |
| `chatbot`  | Conversational interface  |

### Page Types

| Value       | Description               |
| ----------- | ------------------------- |
| `form`      | Data entry/input page     |
| `detail`    | Single record display     |
| `list`      | Multiple items display    |
| `dashboard` | Analytics/overview        |
| `modal`     | Overlay/popup interaction |
| `menu`      | Navigation/selection      |
| `search`    | Search results display    |
| `settings`  | Configuration page        |
| `wizard`    | Multi-step guided flow    |
| `report`    | Data report display       |
| `calendar`  | Date-based view           |
| `kanban`    | Status-based board        |

### Component Types (Atomic Design)

| Value      | Description                        | Level         |
| ---------- | ---------------------------------- | ------------- |
| `TEMPLATE` | Reusable page layout pattern       | Page-level    |
| `ORGANISM` | Complex self-contained component   | Section-level |
| `MOLECULE` | Group of atoms functioning as unit | Field-level   |
| `ATOM`     | Basic UI building block            | Element-level |

### Component Categories (by Function)

| Category     | Examples                                                   | Typical Type           |
| ------------ | ---------------------------------------------------------- | ---------------------- |
| Input        | TextInput, NumberInput, PasswordInput, EmailInput          | ATOM                   |
| Selection    | Checkbox, RadioGroup, Select, MultiSelect, Toggle          | ATOM/MOLECULE          |
| Date/Time    | DatePicker, TimePicker, DateRangePicker, Calendar          | ATOM/MOLECULE/ORGANISM |
| Button       | Button, IconButton, ButtonGroup, SplitButton, FAB          | ATOM/MOLECULE          |
| Display      | Label, Text, Badge, Tag, Avatar, Icon, Image               | ATOM                   |
| Feedback     | Alert, Toast, Snackbar, ProgressBar, Spinner, Tooltip      | ATOM/MOLECULE          |
| Navigation   | Navbar, Sidebar, Breadcrumb, Tabs, Stepper, Pagination     | MOLECULE/ORGANISM      |
| Layout       | Card, Panel, Accordion, Modal, Drawer, Divider, Grid       | ATOM/ORGANISM/TEMPLATE |
| Data Display | Table, DataGrid, List, Tree, Timeline, Chart, StatCard     | MOLECULE/ORGANISM      |
| Form         | Form, FormField, FormSection, FormActions, FileUpload      | MOLECULE/ORGANISM      |
| Medical      | VitalsCard, MedicationList, LabResultsTable, DiagnosisCard | MOLECULE/ORGANISM      |

### Layout Types (for Components)

| Value      | Description               |
| ---------- | ------------------------- |
| `flex`     | Flexbox layout            |
| `grid`     | CSS Grid layout           |
| `stack`    | Vertical/horizontal stack |
| `absolute` | Absolute positioning      |

### Component States

| Value       | Description              |
| ----------- | ------------------------ |
| `default`   | Normal state             |
| `hover`     | Mouse hover state        |
| `active`    | Active/pressed state     |
| `focused`   | Keyboard focus state     |
| `disabled`  | Disabled state           |
| `loading`   | Loading/processing state |
| `error`     | Error/invalid state      |
| `success`   | Success/valid state      |
| `selected`  | Selected state           |
| `expanded`  | Expanded state           |
| `collapsed` | Collapsed state          |

### Reusability Levels

| Level      | Scope              | When to Use                                    |
| ---------- | ------------------ | ---------------------------------------------- |
| `GLOBAL`   | Entire application | Button, TextInput, Card - used everywhere      |
| `DOMAIN`   | Business domain    | PatientCard, AppointmentSlot - domain-specific |
| `PAGE`     | Single page        | DashboardHeader - page-specific layout         |
| `INSTANCE` | One-time use       | SpecialPromoBanner - unique, non-reusable      |

### Reusable Component Patterns

| Pattern              | Type     | Description                          | Example                     |
| -------------------- | -------- | ------------------------------------ | --------------------------- |
| Field Pattern        | MOLECULE | Label + Input + Error                | TextInputField, SelectField |
| Card Pattern         | ORGANISM | Header + Body + Footer               | BaseCard, InfoCard          |
| Table Pattern        | ORGANISM | Toolbar + Header + Body + Pagination | DataTable                   |
| Form Section Pattern | ORGANISM | Header + Fields + Divider            | PersonalInfoSection         |
| List Pattern         | ORGANISM | Header + Items + Empty State         | BaseList                    |
| Modal Pattern        | ORGANISM | Header + Content + Actions           | ConfirmationModal           |
