# Atomic Design Classification Rules — Generate Design from UI

## Overview

**Atomic Design** is a methodology for building design systems through five distinct levels:
1. **Atoms** — Basic building blocks (buttons, inputs, labels)
2. **Molecules** — Simple groups of atoms (search bar, form field)
3. **Organisms** — Complex UI sections with state (nav bar, data table, sidebar)
4. **Templates** — Page-level layouts (form layout, list layout)
5. **Pages** — Specific instances of templates

This skill uses Atoms, Molecules, Organisms, and Templates. Pages are design nodes but not components.

---

## Classification Rules

### ATOM
**Definition:** Single UI element or thin wrapper. No internal state. Props-only interface.

**Code Patterns:**
- Single HTML element: `<button>`, `<input>`, `<label>`, `<img>`, `<svg>`
- Thin wrapper around HTML element: `<Button>`, `<TextField>`, `<Icon>`
- No `useState`, `useReducer`, or state management hooks
- Props-driven rendering only
- No composition of other components (except HTML elements)

**Examples:**
```tsx
// Button atom
export const Button = ({ label, onClick, variant }) => (
  <button className={variant} onClick={onClick}>
    {label}
  </button>
)

// TextInput atom
export const TextInput = ({ value, onChange, placeholder }) => (
  <input 
    type="text" 
    value={value} 
    onChange={onChange}
    placeholder={placeholder}
  />
)

// Icon atom
export const Icon = ({ name, size }) => (
  <i className={`icon-${name}`} style={{ fontSize: size }} />
)

// Label atom
export const Label = ({ text, htmlFor }) => (
  <label htmlFor={htmlFor}>{text}</label>
)
```

**Atomic Design Definition:**
"Atoms are the basic building blocks of matter. Applied to web interfaces, atoms are our HTML tags, such as a form label, an input, or a button. Atoms can also include more abstract elements like color palettes, fonts, and even more invisible aspects of an interface like animations."

**Naming Convention:**
- Use exact component name from codebase
- Common atoms: `Button`, `TextInput`, `Label`, `Icon`, `Checkbox`, `Radio`, `Select`, `Link`, `Image`, `Divider`, `Badge`, `Avatar`, `Spinner`, `Skeleton`

**Scope:** Always `GLOBAL` (reusable across entire app)

**supportingComponents:** Always `[]` (empty array)

---

### MOLECULE
**Definition:** 2-4 atoms composed together. Minimal internal state (or stateless). Single, focused purpose.

**Code Patterns:**
- Composed of 2-4 atoms
- May have minimal state (`useState` for local UI state only)
- Represents a single UI concept (search box, form field, card)
- Reusable across multiple pages
- No complex business logic

**Examples:**
```tsx
// TextInputField molecule
// Atoms: Label + TextInput + ErrorMessage
export const TextInputField = ({ label, value, onChange, error }) => (
  <div className="field">
    <Label text={label} />
    <TextInput value={value} onChange={onChange} />
    {error && <ErrorMessage text={error} />}
  </div>
)

// SearchBar molecule
// Atoms: TextInput + SearchButton + Icon
export const SearchBar = ({ onSearch }) => {
  const [query, setQuery] = useState('')
  return (
    <div className="search-bar">
      <Icon name="search" />
      <TextInput 
        value={query} 
        onChange={e => setQuery(e.target.value)}
        placeholder="Search..."
      />
      <Button label="Search" onClick={() => onSearch(query)} />
    </div>
  )
}

// DateRangePicker molecule
// Atoms: DateInput + DateInput + Label
export const DateRangePicker = ({ startDate, endDate, onChange }) => (
  <div className="date-range">
    <Label text="From" />
    <DateInput value={startDate} onChange={d => onChange('start', d)} />
    <Label text="To" />
    <DateInput value={endDate} onChange={d => onChange('end', d)} />
  </div>
)

// Card molecule
// Atoms: Image + Heading + Label + Button
export const Card = ({ title, description, imageUrl, onAction }) => (
  <div className="card">
    <Image src={imageUrl} />
    <Heading text={title} />
    <Label text={description} />
    <Button label="Learn More" onClick={onAction} />
  </div>
)
```

**Atomic Design Definition:**
"Molecules are groups of atoms bonded together and are the smallest fundamental units of a compound. These molecules take on their own properties and serve as the backbone of our design systems. For example, a form label, input, and button can join together to create a search form molecule."

**Naming Convention:**
- Use exact component name from codebase
- Common molecules: `TextInputField`, `SelectField`, `CheckboxField`, `RadioGroup`, `SearchBar`, `DateRangePicker`, `Breadcrumb`, `Pagination`, `NotificationCard`, `UserAvatar`, `FilterChip`

**Scope:** `GLOBAL` (most common) or `DOMAIN` (domain-specific, e.g., `PatientCard`)

**supportingComponents:** Array of ATOM names only

---

### ORGANISM
**Definition:** Self-contained UI section with its own state management. Contains multiple molecules/atoms. Represents a distinct section of a page.

**Code Patterns:**
- Uses `useState`, `useReducer`, `useContext`, or external state (Redux, Zustand)
- Composed of multiple molecules and/or atoms (5+ child components typical)
- Represents a cohesive section: header, sidebar, data table, form
- May fetch data or handle complex interactions
- Page-specific or domain-specific (rarely global)

**Examples:**
```tsx
// DataTable organism
// Molecules: SearchBar, FilterPanel, Pagination
// Atoms: Button, Checkbox, Icon
export const DataTable = ({ data, columns, onRowClick }) => {
  const [filteredData, setFilteredData] = useState(data)
  const [sortConfig, setSortConfig] = useState(null)
  const [currentPage, setCurrentPage] = useState(1)
  
  return (
    <div className="data-table">
      <SearchBar onSearch={handleSearch} />
      <FilterPanel filters={filters} onApply={handleFilter} />
      <table>
        <thead>
          {columns.map(col => (
            <th onClick={() => handleSort(col.key)}>
              {col.label}
              <Icon name={getSortIcon(col.key)} />
            </th>
          ))}
        </thead>
        <tbody>
          {paginatedData.map(row => (
            <tr onClick={() => onRowClick(row)}>
              {/* ... */}
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination 
        current={currentPage}
        total={totalPages}
        onChange={setCurrentPage}
      />
    </div>
  )
}

// NavigationSidebar organism
// Molecules: UserProfile, NavMenuItem
// Atoms: Icon, Label, Divider
export const NavigationSidebar = () => {
  const [collapsed, setCollapsed] = useState(false)
  const { user } = useAuth()
  const { activeItem, setActiveItem } = useNavigation()
  
  return (
    <aside className={collapsed ? 'collapsed' : 'expanded'}>
      <UserProfile name={user.name} avatar={user.avatar} />
      <Divider />
      <nav>
        {menuItems.map(item => (
          <NavMenuItem 
            {...item}
            active={activeItem === item.id}
            onClick={() => setActiveItem(item.id)}
          />
        ))}
      </nav>
      <Button 
        icon="collapse" 
        onClick={() => setCollapsed(!collapsed)}
      />
    </aside>
  )
}

// RegistrationForm organism
// Molecules: TextInputField, SelectField, CheckboxField
// Atoms: Button, Label
export const RegistrationForm = ({ onSubmit }) => {
  const [formData, setFormData] = useState(initialState)
  const [errors, setErrors] = useState({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    const validationErrors = validate(formData)
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors)
      setIsSubmitting(false)
      return
    }
    await onSubmit(formData)
  }
  
  return (
    <form onSubmit={handleSubmit}>
      <TextInputField 
        label="Email"
        value={formData.email}
        onChange={e => setFormData({...formData, email: e.target.value})}
        error={errors.email}
      />
      <TextInputField 
        label="Password"
        type="password"
        value={formData.password}
        onChange={e => setFormData({...formData, password: e.target.value})}
        error={errors.password}
      />
      <SelectField 
        label="Country"
        options={countries}
        value={formData.country}
        onChange={val => setFormData({...formData, country: val})}
      />
      <CheckboxField 
        label="Accept Terms"
        checked={formData.acceptTerms}
        onChange={val => setFormData({...formData, acceptTerms: val})}
      />
      <Button 
        label="Register"
        type="submit"
        disabled={isSubmitting}
      />
    </form>
  )
}
```

**Atomic Design Definition:**
"Organisms are groups of molecules joined together to form a relatively complex, distinct section of an interface. Organisms can consist of similar and/or different molecule types. For example, a masthead organism might consist of a logo, primary navigation, and search form."

**Naming Convention:**
- Use exact component name from codebase
- Page-specific organisms often named by location: `TopDetails`, `SidebarContacts`, `TabDetails`, `MainContent`
- Common organisms: `Header`, `Footer`, `Sidebar`, `NavigationBar`, `DataTable`, `FilterPanel`, `DashboardWidget`, `CommentSection`, `UserProfile`, `NotificationList`

**Scope:** Usually `PAGE` (specific to one page) or `DOMAIN` (shared across a domain like "Patient Management")

**supportingComponents:** Array of MOLECULE and ATOM names (no ORGANISMs — organisms don't nest)

---

### TEMPLATE
**Definition:** Page-level layout structure. Defines WHERE things go, not WHAT they are. Layout-only, no business logic.

**Code Patterns:**
- Contains `children`, `slots`, or named props for content areas
- Defines page structure: header, sidebar, main, footer
- No business logic, no data fetching, no state (except layout state like sidebar collapsed)
- Uses CSS Grid, Flexbox, or layout primitives
- Reusable across many pages of the same type

**Examples:**
```tsx
// FormPageLayout template
export const FormPageLayout = ({ header, form, actions }) => (
  <div className="form-page-layout">
    <header className="page-header">
      {header}
    </header>
    <main className="form-container">
      {form}
    </main>
    <footer className="form-actions">
      {actions}
    </footer>
  </div>
)

// ListPageLayout template
export const ListPageLayout = ({ toolbar, filters, list, pagination }) => (
  <div className="list-page-layout">
    <div className="toolbar-area">
      {toolbar}
    </div>
    <div className="content-area">
      <aside className="filters-sidebar">
        {filters}
      </aside>
      <main className="list-main">
        {list}
        <footer className="pagination-footer">
          {pagination}
        </footer>
      </main>
    </div>
  </div>
)

// DetailPageLayout template
export const DetailPageLayout = ({ breadcrumb, sidebar, details, tabs }) => (
  <div className="detail-page-layout">
    <nav className="breadcrumb-nav">
      {breadcrumb}
    </nav>
    <div className="detail-content">
      <aside className="info-sidebar">
        {sidebar}
      </aside>
      <main className="detail-main">
        <section className="top-details">
          {details}
        </section>
        <section className="tabbed-content">
          {tabs}
        </section>
      </main>
    </div>
  </div>
)

// DashboardLayout template
export const DashboardLayout = ({ header, widgets, footer }) => (
  <div className="dashboard-layout">
    <header className="dashboard-header">
      {header}
    </header>
    <div className="widget-grid">
      {widgets.map(widget => (
        <div className="widget-slot" key={widget.id}>
          {widget}
        </div>
      ))}
    </div>
    {footer && (
      <footer className="dashboard-footer">
        {footer}
      </footer>
    )}
  </div>
)
```

**Atomic Design Definition:**
"Templates consist mostly of groups of organisms stitched together to form pages. Templates are very concrete and provide context to all these relatively abstract molecules and organisms. Templates are where we start to see our design coming together."

**Naming Convention:**
- **ALWAYS use generic layout pattern name**, never specific page name
- ✅ Correct: `FormPageLayout`, `ListPageLayout`, `DetailPageLayout`, `DashboardLayout`
- ❌ Wrong: `PatientRegistrationTemplate`, `ProjectDetailTemplate`, `UserDashboardTemplate`
- Reason: Templates are reused across many pages of the same type

**Common Templates:**
- `FormPageLayout` — form, create, edit, register pages
- `ListPageLayout` — list, table, search pages
- `DetailPageLayout` — detail, view, profile pages
- `DashboardLayout` — dashboard, overview pages
- `WizardLayout` — multi-step, wizard pages
- `SplitPaneLayout` — master-detail, split views
- `AuthPageLayout` — login, signup, reset password
- `SettingsPageLayout` — settings, preferences pages
- `ModalLayout` — modal dialogs
- `BlankLayout` — minimal pages (404, error, coming soon)

**Scope:** Always `GLOBAL` (templates are maximally reusable)

**supportingComponents:** Array of ORGANISM names only (templates contain organisms, which contain molecules, which contain atoms)

---

## Classification Decision Tree

```
START: Looking at a component in the UI codebase

├─ Is it a single HTML element or thin wrapper?
│  └─ YES → ATOM
│
├─ Does it define page-level layout (header/main/footer slots)?
│  └─ YES → TEMPLATE
│
├─ Does it have state management (useState, useReducer, context)?
│  ├─ YES → ORGANISM
│  └─ NO → Continue
│
├─ Is it composed of 2-4 atoms?
│  └─ YES → MOLECULE
│
└─ Is it composed of 5+ child components or has complex interactions?
   └─ YES → ORGANISM
```

---

## Real-World Examples from Codebases

### Example 1: Notification System

**ATOM:**
```tsx
<Icon name="bell" />
<Badge count={3} />
<Typography variant="body">You have new notifications</Typography>
```

**MOLECULE:**
```tsx
<NotificationCard 
  icon={<Icon name="info" />}
  title="System Update"
  message="New features available"
  timestamp="2 hours ago"
/>
// Contains: Icon (atom) + Typography (atom) + Typography (atom) + Label (atom)
```

**ORGANISM:**
```tsx
<NotificationList 
  notifications={data}
  onMarkAllRead={handleMarkRead}
  onFilter={handleFilter}
/>
// Contains: SearchBar (molecule) + FilterChips (molecule) + NotificationCard[] (molecules) + Pagination (molecule)
// Has state: filteredNotifications, selectedFilter, currentPage
```

**TEMPLATE:**
```tsx
<ListPageLayout 
  toolbar={<NotificationToolbar />}
  filters={<NotificationFilters />}
  list={<NotificationList />}
  pagination={<Pagination />}
/>
```

---

### Example 2: Project Management

**ATOM:**
```tsx
<Avatar src={user.photo} />
<StatusBadge status="active" />
<Chip label="Frontend" />
```

**MOLECULE:**
```tsx
<UserCard 
  avatar={<Avatar src={user.photo} />}
  name={user.name}
  role={user.role}
  status={<StatusBadge status={user.status} />}
/>
// Contains: Avatar + Typography + Typography + StatusBadge
```

**ORGANISM:**
```tsx
<ProjectCard 
  project={projectData}
  onEdit={handleEdit}
  onDelete={handleDelete}
>
  <CardHeader 
    title={project.name}
    tags={project.tags.map(t => <Chip label={t} />)}
    menu={<OptionsMenu />}
  />
  <CardBody>
    <ProgressBar value={project.completion} />
    <UserList users={project.team} />
    <DateRange start={project.startDate} end={project.endDate} />
  </CardBody>
  <CardFooter>
    <Button label="View Details" onClick={() => navigate(`/project/${project.id}`)} />
  </CardFooter>
</ProjectCard>
// Contains: Multiple molecules, has state for hover, expanded, menu open
```

**TEMPLATE:**
```tsx
<DashboardLayout 
  header={<DashboardHeader />}
  widgets={[
    <ProjectCard />,
    <TaskSummary />,
    <TeamActivity />,
    <DeadlineWidget />
  ]}
/>
```

---

## Component Composition Rules

### ATOM Composition
- ✅ Can contain: HTML elements only
- ❌ Cannot contain: Other components (except primitives like `<span>`, `<div>`)
- **supportingComponents:** `[]` (always empty)

### MOLECULE Composition
- ✅ Can contain: ATOMs only (2-4 typical)
- ❌ Cannot contain: Other MOLECULEs, ORGANISMs, TEMPLATEs
- **supportingComponents:** `["AtomName1", "AtomName2", ...]`

**Exception:** If a MOLECULE uses another MOLECULE as an atom-level primitive (e.g., `UserAvatar` used as a unit within `CommentCard`), treat it as composition.

### ORGANISM Composition
- ✅ Can contain: MOLECULEs and/or ATOMs (5+ child components typical)
- ❌ Cannot contain: Other ORGANISMs, TEMPLATEs
- **supportingComponents:** `["MoleculeName1", "MoleculeName2", "AtomName1", ...]`

**Why no nested organisms:** Organisms are meant to be distinct sections. If an organism contains another organism, reclassify one as a molecule or split into separate page sections.

### TEMPLATE Composition
- ✅ Can contain: ORGANISMs only (defines slots for them)
- ❌ Cannot contain: MOLECULEs, ATOMs directly (they live inside the organisms)
- **supportingComponents:** `["OrganismName1", "OrganismName2", ...]`

---

## Scope Assignment Rules

| Type | Scope Options | Default | Notes |
|------|---------------|---------|-------|
| ATOM | `GLOBAL` | `GLOBAL` | Atoms are always maximally reusable |
| MOLECULE | `GLOBAL`, `DOMAIN` | `GLOBAL` | Most molecules are global; domain-specific ones (e.g., `PatientCard`) use `DOMAIN` |
| ORGANISM | `PAGE`, `DOMAIN`, `GLOBAL` | `PAGE` | Most organisms are page-specific; shared ones (e.g., `Header`, `Sidebar`) use `GLOBAL` |
| TEMPLATE | `GLOBAL` | `GLOBAL` | Templates are always maximally reusable |

**Scope Decision Tree:**

```
Is this component used on multiple pages?
├─ NO → `PAGE`
└─ YES → Is it used across multiple domains?
    ├─ NO → `DOMAIN`
    └─ YES → `GLOBAL`
```

---

## Common Misclassifications

### ❌ WRONG: Form as MOLECULE
```tsx
// This is an ORGANISM, not a MOLECULE
<RegistrationForm />
```
**Why:** Forms have state (form data, validation, submission). MOLECULEs have minimal/no state.

### ❌ WRONG: Data Table as MOLECULE
```tsx
// This is an ORGANISM, not a MOLECULE
<DataTable columns={cols} data={rows} />
```
**Why:** Tables have state (sorting, filtering, pagination). MOLECULEs are simple.

### ❌ WRONG: Navigation Bar as MOLECULE
```tsx
// This is an ORGANISM, not a MOLECULE
<NavigationBar items={menuItems} />
```
**Why:** Nav bars have state (active item, mobile menu open/closed). MOLECULEs don't.

### ❌ WRONG: Search Bar with Results as MOLECULE
```tsx
// This is an ORGANISM, not a MOLECULE
<SearchBarWithResults onSelect={handleSelect} />
```
**Why:** Managing search results + selection state = organism complexity.

### ✅ CORRECT: Search Bar as MOLECULE
```tsx
// This IS a MOLECULE (just input + button, minimal state)
<SearchBar value={query} onChange={setQuery} onSubmit={handleSubmit} />
```
**Why:** Just captures input and triggers callback. No results management.

---

## Edge Cases

### Case 1: Icon Button
```tsx
<IconButton icon="delete" onClick={handleDelete} />
```
**Classification:** ATOM (single interactive element, no composition)

**vs.**

```tsx
<IconButtonWithTooltip icon="delete" tooltip="Delete item" onClick={handleDelete} />
```
**Classification:** MOLECULE (Icon + Button + Tooltip = 3 atoms)

---

### Case 2: Avatar
```tsx
<Avatar src={user.photo} />
```
**Classification:** ATOM (single element)

**vs.**

```tsx
<AvatarWithName 
  src={user.photo} 
  name={user.name}
  subtitle={user.role}
/>
```
**Classification:** MOLECULE (Avatar + Typography + Typography)

---

### Case 3: Tabs
```tsx
<Tabs activeTab={active} onChange={setActive}>
  <Tab label="Overview" />
  <Tab label="Settings" />
</Tabs>
```
**Classification:** MOLECULE (tab navigation component)

**vs.**

```tsx
<TabbedContent>
  <TabPanel label="Overview">
    <OverviewSection />
  </TabPanel>
  <TabPanel label="Settings">
    <SettingsSection />
  </TabPanel>
</TabbedContent>
```
**Classification:** ORGANISM (manages tab state + renders complex content sections)

---

### Case 4: Modal/Dialog

**Simple Modal (MOLECULE):**
```tsx
<Modal 
  isOpen={isOpen} 
  onClose={handleClose}
  title="Confirm Action"
>
  <p>Are you sure?</p>
  <Button label="Confirm" onClick={handleConfirm} />
</Modal>
```
**Why:** Just displays content, minimal logic.

**Complex Modal (ORGANISM):**
```tsx
<EditProfileModal 
  user={userData}
  onSave={handleSave}
>
  {/* Contains entire form with state, validation, image upload */}
  <ProfileEditForm />
</EditProfileModal>
```
**Why:** Has complex state management, validation, data handling.

---

## Naming Components in Design Graph

### Use Exact Repo Names

**Priority:**
1. **Exported component name** (if named export)
   ```tsx
   export const SearchFilterPanel = () => { ... }
   ```
   → Design node name: `SearchFilterPanel`

2. **File name** (if default export)
   ```tsx
   // File: search-filter-panel.tsx
   export default function SearchFilterPanel() { ... }
   ```
   → Design node name: `SearchFilterPanel` (PascalCase)

3. **Common library name** (if third-party)
   ```tsx
   import { DataGrid } from '@mui/x-data-grid'
   ```
   → Design node name: `DataGrid`

### Examples

| Code | Design Node Name | Type |
|------|------------------|------|
| `export const DataTable` | `DataTable` | ORGANISM |
| `export const SearchFilterPanel` | `SearchFilterPanel` | ORGANISM |
| File: `text-input-field.tsx` | `TextInputField` | MOLECULE |
| `export const IconButton` | `IconButton` | ATOM |
| `<Button>` from `ui/button.tsx` | `Button` | ATOM |
| Default export in `project-card.tsx` | `ProjectCard` | MOLECULE |
| Layout in `page-layout.tsx` | `PageLayout` | TEMPLATE |

---

## Quick Reference Table

| Type | State | Composition | Scope | supportingComponents |
|------|-------|-------------|-------|----------------------|
| **ATOM** | None (props only) | HTML elements only | GLOBAL | `[]` |
| **MOLECULE** | Minimal (UI state) | 2-4 ATOMs | GLOBAL or DOMAIN | ATOM names |
| **ORGANISM** | Complex (hooks, context) | 5+ MOLECULEs/ATOMs | PAGE, DOMAIN, or GLOBAL | MOLECULE + ATOM names |
| **TEMPLATE** | Layout state only | Slots for ORGANISMs | GLOBAL | ORGANISM names |

---

## Validation Checklist

Before classifying a component, ask:

**For ATOM:**
- [ ] Is it a single HTML element or thin wrapper?
- [ ] Does it have NO internal state?
- [ ] Is it props-only?

**For MOLECULE:**
- [ ] Is it composed of 2-4 atoms?
- [ ] Does it have minimal/no state?
- [ ] Does it serve a single, focused purpose?

**For ORGANISM:**
- [ ] Does it have state management (`useState`, `useReducer`, etc.)?
- [ ] Is it composed of 5+ child components?
- [ ] Does it represent a distinct page section?

**For TEMPLATE:**
- [ ] Does it define page-level layout structure?
- [ ] Is it layout-only (no business logic)?
- [ ] Is it named by layout pattern (not specific page)?

---

## Further Reading

- [Atomic Design by Brad Frost](https://atomicdesign.bradfrost.com/)
- [Component-Driven Development](https://www.componentdriven.org/)
- [Design Systems Handbook](https://www.designbetter.co/design-systems-handbook)
