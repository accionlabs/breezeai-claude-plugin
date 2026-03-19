### Design Graph

The design graph follows **Atomic Design** methodology, decomposing UI into 5 hierarchical levels:

**Atom → Molecule → Organism → Template → DesignPage**

1. **Atom** — Smallest indivisible UI element (no children)
2. **Molecule** — Functional group of atoms working together
3. **Organism** — Complex UI section composed of molecules and atoms
4. **Template** — Page layout skeleton defining zones and grid structure
5. **DesignPage** — Complete page with route, data sources, and auth requirements

---

### How to Identify Each Node Type

#### Atom Identification

An element is an **Atom** if ALL of these are true:
- It cannot be broken down further into meaningful sub-components
- It has a single responsibility (one thing it does)
- It is reusable across many different contexts
- It does not contain other named components

**Decision questions:**
- "Can I split this into smaller meaningful UI parts?" → NO → Atom
- "Does it compose other named components inside it?" → NO → Atom

**Common Atoms:**

| Category | Examples |
|----------|----------|
| `interactive` | Button, IconButton, Toggle, Switch, Checkbox, Radio, Link |
| `display` | Text, Heading, Icon, Badge, Avatar, Tooltip, Divider, Spinner, Tag |
| `form` | Input, TextArea, Select, DatePicker, TimePicker, Slider, FileInput |

**Required fields:** `name`, `category`, `description`
**Key optional fields:** `props`, `events`, `hasInternalState`, `responsive`, `ariaRole`, `status`

**Atom naming convention:**
- Use PascalCase: `PrimaryButton`, `SearchInput`, `UserAvatar`
- Be specific: `SubmitButton` not just `Button` (if it has distinct behavior)
- Avoid generic names: `Element`, `Thing`, `Widget`

---

#### Molecule Identification

An element is a **Molecule** if ALL of these are true:
- It composes 2+ atoms into a functional unit
- The atoms work together to accomplish one task
- It is still relatively simple and single-purpose
- Removing any atom would break its core functionality

**Decision questions:**
- "Is this a group of atoms that form one functional unit?" → YES → Molecule
- "Does it have a single focused purpose?" → YES → Molecule
- "Does it contain complex layout zones or multiple independent sections?" → YES → probably Organism

**Common Molecules:**

| Category | Examples |
|----------|----------|
| `search` | Search bar (Input + Button + Icon) |
| `form-field` | Form field (Label + Input + Error message) |
| `card` | Stat card (Icon + Value + Label), Info card (Image + Title + Text) |
| `menu-item` | Nav item (Icon + Label + Badge) |
| `stat` | KPI display (Value + Trend + Label) |
| `breadcrumb` | Breadcrumb trail (Links + Separators) |
| `pagination` | Page controls (Buttons + Page numbers + Text) |
| `file-upload` | Upload zone (DropArea + Button + Progress) |

**Required fields:** `name`, `category`, `description`, `atomIds`
**Key optional fields:** `props`, `events`, `layoutDirection`, `responsive`, `status`

**Molecule naming convention:**
- Describe the function: `SearchBar`, `LoginFormField`, `StatCard`
- Include context when needed: `DashboardStatCard` vs `ProfileStatCard`

---

#### Organism Identification

An element is an **Organism** if ANY of these are true:
- It is a distinct section of a page that can function independently
- It composes multiple molecules and/or atoms into a complex unit
- It has its own layout structure (grid, flex sections)
- It consumes context (auth, theme, data) beyond simple props
- It has named content slots

**Decision questions:**
- "Is this a major section of the page?" → YES → Organism
- "Does it compose multiple molecules?" → YES → Organism
- "Could a designer or PM point to this as a 'section' of the page?" → YES → Organism
- "Does it just group a few atoms for one task?" → YES → probably Molecule

**Common Organisms:**

| Category | Examples |
|----------|----------|
| `header` | Page header, App bar (Logo + Nav + Search + UserMenu) |
| `sidebar` | Sidebar navigation (NavItems + CollapseToggle + Logo) |
| `footer` | Page footer (Links + Copyright + Social icons) |
| `toolbar` | Action toolbar (Buttons + Filters + Sort) |
| `data-table` | Data table (Headers + Rows + Pagination + Filters) |
| `form-section` | Form group (Title + FormFields + Validation + Submit) |
| `card-grid` | Card collection (Cards + Layout + Empty state) |
| `modal` | Modal dialog (Overlay + Header + Content + Actions) |
| `notification-center` | Notification list (Alerts + Badges + Actions) |

**Required fields:** `name`, `category`, `description`, `moleculeIds` or `atomIds`
**Key optional fields:** `slots`, `events`, `contextConsumed`, `mobileBehavior`, `responsive`, `status`

**Organism naming convention:**
- Name by section role: `AppHeader`, `DataTableSection`, `UserFormSection`
- Include page context if page-specific: `DashboardHeader` vs generic `AppHeader`

---

#### Template Identification

An element is a **Template** if ALL of these are true:
- It defines the spatial layout of a page (zones, grid, structure)
- It does NOT contain real data — it defines WHERE things go
- It can be reused across multiple pages with different content
- It specifies grid columns, max width, and named zones

**Decision questions:**
- "Does this define WHERE content goes without specifying WHAT content?" → YES → Template
- "Could multiple pages share this exact layout?" → YES → Template
- "Does it have named zones (header, sidebar, content, footer)?" → YES → Template
- "Is it a specific page with real data and routes?" → YES → DesignPage, not Template

**Common Templates:**

| Category | Examples |
|----------|----------|
| `dashboard-layout` | Main grid with sidebar + header + content area |
| `detail-layout` | Title + tabs + content + sidebar details |
| `list-layout` | Filters + data table + pagination |
| `form-layout` | Stepper/sections + form content + actions |
| `split-layout` | Left panel + right panel (e.g., email client) |
| `fullscreen-layout` | Full viewport with minimal chrome (e.g., editor) |
| `wizard-layout` | Multi-step with progress indicator |
| `auth-layout` | Centered card with branding (login, register) |

**Required fields:** `name`, `category`, `description`, `zones`
**Key optional fields:** `gridColumns`, `maxWidth`, `isRouteLayout`, `routePattern`, `contextProvided`, `responsive`, `status`

**Template naming convention:**
- Suffix with "Layout": `DashboardLayout`, `AuthLayout`, `WizardLayout`
- Be generic (templates are reusable): `ListLayout` not `UserListLayout`

---

#### DesignPage Identification

An element is a **DesignPage** if ALL of these are true:
- It represents a complete, routable page in the application
- It has a URL route (e.g., `/dashboard/analytics`)
- It fetches real data from specific API endpoints
- It composes templates and/or organisms with actual content

**Decision questions:**
- "Does this have its own URL route?" → YES → DesignPage
- "Does it fetch data from APIs?" → YES → DesignPage
- "Is this what the user sees as a complete 'screen'?" → YES → DesignPage
- "Is it just a layout shell without real data?" → YES → Template, not DesignPage

**Common DesignPages:**

| Category | Examples |
|----------|----------|
| `analytics` | Dashboard, Reports, Charts |
| `listing` | User list, Product catalog, Order history |
| `detail` | User profile view, Order details, Product page |
| `editor` | Rich text editor, Form builder, Code editor |
| `settings` | Account settings, App preferences, Integrations |
| `auth` | Login, Register, Forgot password, MFA |
| `onboarding` | Welcome wizard, Setup flow, Tour |
| `checkout` | Cart, Payment, Order summary |
| `profile` | My account, User profile, Activity log |
| `error` | 404, 500, Maintenance, Access denied |

**Required fields:** `name`, `category`, `description`, `route`
**Key optional fields:** `dataSources`, `authRequired`, `permissions`, `templateIds`, `status`

**DesignPage naming convention:**
- Name by purpose: `AnalyticsDashboardPage`, `UserSettingsPage`
- Suffix with "Page": `LoginPage`, `OrderDetailPage`

---

### Data Model Reference (from design-te.txt)

#### Atom (label: `Atom`) — no children

```json
{
  "name": "Unique name of the atom component",
  "category": "Component type: interactive | display | form",
  "componentPath": "File path to the component source code",
  "figmaNodeId": "Node ID from Figma design file",
  "props": "Typed props the component accepts e.g. label:string, variant:enum(primary|secondary)",
  "events": "DOM/custom events the component emits e.g. click, focus, blur",
  "hasInternalState": "Whether the component manages its own state",
  "responsive": "Responsive behavior: fluid | fixed | adaptive",
  "ariaRole": "WAI-ARIA role for accessibility e.g. button",
  "status": "Component maturity: stable | draft | deprecated",
  "description": "Human-readable summary of what this atom does",
  "figmaUrl": "Direct URL to the Figma frame"
}
```

#### Molecule (label: `Molecule`) — children: Atoms

```json
{
  "name": "Unique name of the molecule component",
  "category": "Component type: search | form-field | card | menu-item | stat | breadcrumb | pagination | file-upload",
  "componentPath": "File path to the component source code",
  "figmaNodeId": "Node ID from Figma design file",
  "props": "Typed props e.g. value:string, onChange:function, placeholder:string",
  "events": "Events emitted e.g. change, submit, clear",
  "hasInternalState": "Whether the component manages its own state",
  "layoutDirection": "Child layout: horizontal | vertical | grid",
  "responsive": "Responsive behavior: fluid | fixed | adaptive",
  "ariaRole": "WAI-ARIA role e.g. search",
  "status": "Component maturity: stable | draft | deprecated",
  "atomIds": ["IDs of child Atom nodes composed into this molecule"],
  "description": "Human-readable summary of what this molecule does",
  "figmaUrl": "Direct URL to the Figma frame"
}
```

#### Organism (label: `Organism`) — children: Molecules, Atoms

```json
{
  "name": "Unique name of the organism component",
  "category": "Component type: header | sidebar | footer | toolbar | data-table | form-section | card-grid | modal | notification-center",
  "componentPath": "File path to the component source code",
  "figmaNodeId": "Node ID from Figma design file",
  "props": "Typed props e.g. user:User, nav_items:NavItem[], notifications:Notification[]",
  "slots": "Named content slots e.g. logo, actions",
  "events": "Events emitted e.g. navigate, search, logout",
  "hasInternalState": "Whether the component manages its own state",
  "contextConsumed": "React contexts consumed e.g. AuthContext, ThemeContext",
  "responsive": "Responsive behavior: fluid | fixed | adaptive",
  "mobileBehavior": "Mobile-specific UI pattern e.g. hamburger-menu, bottom-sheet",
  "ariaRole": "WAI-ARIA role e.g. navigation",
  "status": "Component maturity: stable | draft | deprecated",
  "moleculeIds": ["IDs of child Molecule nodes"],
  "atomIds": ["IDs of direct child Atom nodes"],
  "description": "Human-readable summary of what this organism does",
  "figmaUrl": "Direct URL to the Figma frame"
}
```

#### Template (label: `Template`) — children: Organisms, Molecules, Atoms

```json
{
  "name": "Unique name of the template layout",
  "type": "Always 'Template'",
  "category": "Layout type: dashboard-layout | detail-layout | list-layout | form-layout | split-layout | fullscreen-layout | wizard-layout | auth-layout",
  "componentPath": "File path to the component source code",
  "figmaNodeId": "Node ID from Figma design file",
  "zones": "Named layout zones e.g. header, sidebar, content, footer",
  "gridColumns": "Number of grid columns e.g. 12",
  "maxWidth": "Max container width e.g. 1440px",
  "isRouteLayout": "Whether this template wraps a route",
  "routePattern": "Route pattern this layout applies to e.g. /dashboard/*",
  "contextProvided": "React contexts this template provides e.g. LayoutContext",
  "responsive": "Responsive behavior: fluid | fixed | adaptive",
  "status": "Component maturity: stable | draft | deprecated",
  "organismIds": ["IDs of child Organism nodes"],
  "moleculeIds": ["IDs of direct child Molecule nodes"],
  "atomIds": ["IDs of direct child Atom nodes"],
  "order": "Display/render order index",
  "citations": "Linked requirement citations",
  "description": "Human-readable summary of what this template does",
  "figmaUrl": "Direct URL to the Figma frame"
}
```

#### DesignPage (label: `DesignPage`) — children: Templates, Organisms, Molecules, Atoms

```json
{
  "name": "Unique name of the page",
  "category": "Page type: analytics | listing | detail | editor | settings | auth | onboarding | checkout | profile | error",
  "componentPath": "File path to the page component source code",
  "figmaNodeId": "Node ID from Figma design file",
  "route": "URL route path e.g. /dashboard/analytics",
  "dataSources": "API endpoints this page fetches from e.g. /api/analytics/summary, /api/analytics/timeseries",
  "authRequired": "Whether authentication is required to access this page",
  "permissions": "Required permission strings e.g. analytics:read",
  "status": "Page maturity: stable | draft | deprecated",
  "templateIds": ["IDs of child Template nodes"],
  "organismIds": ["IDs of direct child Organism nodes"],
  "moleculeIds": ["IDs of direct child Molecule nodes"],
  "atomIds": ["IDs of direct child Atom nodes"],
  "description": "Human-readable summary of what this page does",
  "figmaUrl": "Direct URL to the Figma frame"
}
```

---

### Composition Hierarchy

```
DesignPage (1) ──HAS_TEMPLATE──► Template (many)
DesignPage (1) ──HAS_ORGANISM──► Organism (many, direct)
Template   (1) ──HAS_ORGANISM──► Organism (many)
Template   (1) ──HAS_MOLECULE──► Molecule (many, direct)
Organism   (1) ──HAS_MOLECULE──► Molecule (many)
Organism   (1) ──HAS_ATOM─────► Atom (many, direct)
Molecule   (1) ──HAS_ATOM─────► Atom (many)
```

**Key rule:** Children must be created BEFORE parents so that parent nodes can reference child IDs in their `atomIds`, `moleculeIds`, `organismIds`, `templateIds` arrays.

---

### Quick Decision Flowchart

```
Is it a complete routable page with data?
  YES → DesignPage
  NO ↓

Does it define spatial layout zones without real data?
  YES → Template
  NO ↓

Is it a major page section with multiple sub-components?
  YES → Organism
  NO ↓

Is it a small group of atoms with one focused purpose?
  YES → Molecule
  NO ↓

Is it indivisible, single-responsibility, no children?
  YES → Atom
```

---

### Classification Ambiguity Rules

When classification is unclear, use these tiebreakers:

1. **Molecule vs Organism**: If it has named content slots or consumes context → Organism. If it just groups atoms for one task → Molecule.
2. **Template vs DesignPage**: If it has a specific route and fetches data → DesignPage. If it is reusable layout structure → Template.
3. **Atom vs Molecule**: If removing any part still leaves it functional → Molecule (the removed part was an atom child). If removing any part breaks it entirely → Atom.
4. **When in doubt, go smaller**: Prefer classifying as a smaller component. It is easier to compose small components up than to decompose large ones down.

---

### MCP Tools Mapping

| Operation | Tool | Required Params |
|-----------|------|-----------------|
| Get existing design nodes by label | `Get_all_Design_By_Label` | `uuid`, `label` (Atom/Molecule/Organism/Template/DesignPage) |
| Search design graph nodes | `Design_Graph_Search` | `uuid`, `parameters0_Value` (search query) |
| Create a new design node | `Create_Design_Node` | `uuid`, `label`, `apiKey`, `data` |
| Update an existing design node | `Update_Design_Node` | `uuid`, `label`, `apiKey`, `id`, `data` |

---

### Reuse Rules

1. **Always search existing nodes FIRST** before creating new ones
2. **Match by name** — if a node with the same or semantically equivalent name exists, update it instead of creating a duplicate
3. **Prefer existing compositions** — if an organism already contains the molecules you need, reuse it
4. **Create bottom-up** — Atoms first, then Molecules, then Organisms, then Templates, then DesignPages
5. **Link IDs immediately** — after creating a child node, capture its ID and include it in the parent's `*Ids` array
