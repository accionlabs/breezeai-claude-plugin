# Atomic Design Theory & Component Creation Guide

This document covers the theory behind atomic design and provides practical
examples for deciding component types when generating design graph nodes.

---

## 1. What is Atomic Design?

Atomic Design is a methodology for building UI systems by breaking interfaces
into five hierarchical levels inspired by chemistry:

```
TEMPLATE  (page-level skeleton)
   └── ORGANISM  (self-contained section)
         └── MOLECULE  (small functional group)
               └── ATOM  (indivisible element)
```

Each level builds on the one below it. The goal is **reusability** — build
small, focused pieces and compose them into larger structures.

---

## 2. The Four Levels (in our system)

### ATOM — The smallest indivisible UI element

An atom is a single HTML element or the simplest possible UI control. It
cannot be broken down further without losing meaning.

**Key question:** *"Can this be split into smaller meaningful UI pieces?"*
If **no** → it is an ATOM.

**Characteristics:**
- Renders exactly one interactive or display element
- Has no children components
- Controlled entirely by props/inputs
- `supportingComponents: []` (always empty)

**Examples:**

| Component    | Why it's an ATOM                                 |
| ------------ | ------------------------------------------------ |
| TextInput    | Single `<input>` element                         |
| Button       | Single `<button>` element                        |
| Checkbox     | Single toggle control                            |
| Label        | Single `<label>` text                            |
| Icon         | Single SVG/image                                 |
| Avatar       | Single image with fallback                       |
| Badge        | Single status indicator                          |
| Spinner      | Single loading animation                         |
| Divider      | Single `<hr>` separator                          |
| Select       | Single `<select>` dropdown (native)              |
| Toggle       | Single on/off switch                             |
| Slider       | Single range control                             |
| DatePicker   | Single date selection control                    |
| ProgressBar  | Single progress indicator                        |

**Real-world analogy:** Atoms are like individual LEGO bricks — a 2x4
block, a wheel, a window piece. Alone they do one thing.

---

### MOLECULE — A small group of atoms that work together as a unit

A molecule combines two or more atoms to create a single functional unit.
The atoms inside it lose independent meaning when separated.

**Key question:** *"Is this a small group of 2-4 elements that only make
sense together?"* If **yes** → it is a MOLECULE.

**Characteristics:**
- Combines 2-4 atoms into one functional group
- Has a single, focused purpose (one job)
- Atoms inside it are tightly coupled — removing one breaks the molecule
- `supportingComponents` contains only ATOMs

**Examples:**

| Component       | Atoms Inside                          | Why it's a MOLECULE              |
| --------------- | ------------------------------------- | -------------------------------- |
| FormField       | Label + TextInput + ErrorMessage      | Input without label is unusable  |
| SearchInput     | TextInput + IconButton (search icon)  | Search needs both input + action |
| PhoneInput      | Select (country) + TextInput (number) | Country code + number are paired |
| RadioGroup      | Multiple Radio ATOMs                  | Single selection needs the group |
| ButtonGroup     | Multiple Buttons                      | Actions that belong together     |
| Breadcrumb      | Multiple Links + Dividers             | Trail only works as a whole      |
| Tabs            | Multiple Tab ATOMs + indicator        | Tab set is the functional unit   |
| Stepper         | Multiple Step indicators + connector  | Progress needs all steps shown   |
| Alert           | Icon + Text + CloseButton             | Message with context and action  |
| Toast           | Icon + Text + timer                   | Temporary notification unit      |
| Pagination      | Buttons + Text (page info)            | Navigation needs all parts       |
| DateTimePicker  | DatePicker + TimePicker               | Combined selection               |
| DateRangePicker | DatePicker (start) + DatePicker (end) | Range needs both ends            |
| StatCard        | Label + Value + Trend Icon            | Metric display as a unit         |

**Real-world analogy:** Molecules are like a LEGO mini-assembly — a wheel
attached to an axle. The parts are meant to be used together.

**How to tell ATOM vs MOLECULE:**

```
Action: "Enter patient name"

Is it a single element?
├── YES, just an input field → ATOM (TextInput)
└── NO, it needs a label + input + error → MOLECULE (PatientNameField)

The difference depends on context:
- If the action is purely "type into a box" → ATOM
- If the action implies a complete field with label/validation → MOLECULE
```

---

### ORGANISM — A self-contained section made of molecules and atoms

An organism is a distinct section of the UI that can function independently.
It represents a complete piece of functionality — a form, a table, a card
with content.

**Key question:** *"Is this a complete, self-contained section of the page
that does something meaningful on its own?"* If **yes** → it is an ORGANISM.

**Characteristics:**
- Composed of multiple molecules and/or atoms
- Represents a complete functional section (not a whole page)
- Can be understood and used independently
- Has its own internal layout and behavior
- `supportingComponents` contains MOLECULEs and/or ATOMs
- **ORGANISM containers are always page-specific — always CREATE NEW**
  (but their child molecules/atoms can be reused)

**Examples:**

| Component              | Molecules/Atoms Inside                           | Why it's an ORGANISM                   |
| ---------------------- | ------------------------------------------------ | -------------------------------------- |
| PatientRegistrationForm| NameField + DOBField + GenderSelect + SubmitBtn  | Complete form, works on its own        |
| DataTable              | SearchInput + TableHeader + TableRows + Pagination| Complete data display with interaction |
| Navbar                 | Logo + NavLinks + SearchInput + UserMenu         | Complete navigation section            |
| Sidebar                | NavLinks + Accordion sections                    | Complete side navigation               |
| Card                   | CardHeader + CardBody + CardFooter               | Complete content container             |
| Modal                  | Header + Content + ActionButtons                 | Complete overlay dialog                |
| VitalsCard             | HeartRate + BP + Temperature + SpO2 fields       | Complete vitals display                |
| MedicationList         | SearchInput + MedItems + Pagination              | Complete medication browser            |
| FormSection            | SectionHeader + FormFields + Divider             | Complete section of a form             |
| Accordion              | Multiple collapsible Panel sections              | Complete expandable content area       |

**Real-world analogy:** Organisms are like a complete LEGO sub-model — a
car body with wheels and doors. It is a recognizable, functional unit.

**How to tell MOLECULE vs ORGANISM:**

```
Action: "View patient appointments"

Is it a simple group of 2-4 tightly coupled elements?
├── YES → MOLECULE (e.g., AppointmentCard: date + doctor + status)
└── NO, it has multiple sub-groups and its own layout?
    └── YES → ORGANISM (e.g., AppointmentList: SearchInput + Cards + Pagination)

Rule of thumb:
- MOLECULE = one row, one field, one small group
- ORGANISM = one SECTION of a page (a form, a panel, a table, a card block)
```

---

### TEMPLATE — A page-level layout skeleton

A template defines the structural layout of a page — where organisms go,
not what they contain. Think of it as the wireframe grid.

**Key question:** *"Does this define WHERE things go on a page, rather than
WHAT they are?"* If **yes** → it is a TEMPLATE.

**Characteristics:**
- Defines page structure: header area, sidebar area, content area, footer area
- Contains slot/placeholder positions for organisms
- Reusable across multiple pages with different content
- `supportingComponents` contains ORGANISMs (the slots they fill)
- One template per page (optional — only when layout structure is reusable)

**Examples:**

| Component              | Structure                                    | Reuse                               |
| ---------------------- | -------------------------------------------- | ------------------------------------ |
| DashboardLayout        | Header + Sidebar + MainContent + Footer      | All dashboard-type pages             |
| FormPageLayout         | Header + Breadcrumb + FormArea + ActionBar   | All form pages                       |
| ListPageLayout         | Header + Filters + TableArea + Pagination    | All list/table pages                 |
| DetailPageLayout       | Header + InfoPanel + TabContent + ActionBar  | All detail/view pages                |
| SplitPaneLayout        | LeftPanel + RightPanel                       | Master-detail views                  |
| WizardLayout           | StepIndicator + StepContent + NavigationBar  | All multi-step wizard pages          |

**Real-world analogy:** Templates are like a LEGO baseplate with marked
zones — "put the house here, put the garden here." The zones are fixed;
what goes in them changes.

**When to create a TEMPLATE vs not:**

```
Page: "Patient Registration"

Does this page follow a layout pattern used by other pages?
├── YES, it's a standard form layout (header + form + actions)
│   └── CREATE TEMPLATE: FormPageLayout
└── NO, it's a unique one-off layout
    └── SKIP template, go straight to ORGANISMs
```

---

## 3. Decision Flowchart

Use this flowchart when mapping a functional Action to a component:

```
START with an Action from the functional graph
│
├── Does this action describe a PAGE LAYOUT structure?
│   └── YES → TEMPLATE
│
├── Does this action represent a COMPLETE SECTION of UI?
│   (a form, a table, a panel, a card block, navigation bar)
│   └── YES → ORGANISM
│
├── Does this action involve MULTIPLE ELEMENTS working as a UNIT?
│   (label + input + error, icon + text, button group)
│   └── YES → MOLECULE
│
└── Is this a SINGLE UI ELEMENT?
    (one button, one input, one label, one icon)
    └── YES → ATOM
```

---

## 4. Full Page Example

### Scenario: "Patient Registration"

**Page: Patient Registration Page**

```
TEMPLATE: FormPageLayout
│
├── ORGANISM: PageHeader
│   ├── MOLECULE: Breadcrumb (Link + Separator + Link)
│   ├── ATOM: Heading ("Register New Patient")
│   └── ATOM: Text (subtitle)
│
├── ORGANISM: PersonalInfoSection
│   ├── MOLECULE: FullNameField (Label + TextInput + ErrorMessage)
│   ├── MOLECULE: DOBField (Label + DatePicker + ErrorMessage)
│   ├── ATOM: GenderSelect
│   ├── MOLECULE: PhoneField (Label + PhoneInput + ErrorMessage)
│   └── MOLECULE: EmailField (Label + EmailInput + ErrorMessage)
│
├── ORGANISM: MedicalInfoSection
│   ├── MOLECULE: BloodGroupField (Label + Select + ErrorMessage)
│   ├── MOLECULE: AllergiesField (Label + MultiSelect + ErrorMessage)
│   └── MOLECULE: NotesField (Label + TextArea + ErrorMessage)
│
├── ORGANISM: InsuranceSection
│   ├── MOLECULE: ProviderField (Label + AutoComplete + ErrorMessage)
│   ├── MOLECULE: PolicyNumberField (Label + TextInput + ErrorMessage)
│   └── MOLECULE: FileUploadField (Label + FileUpload + ErrorMessage)
│
└── ORGANISM: FormActions
    ├── ATOM: Button ("Submit")
    ├── ATOM: Button ("Save Draft")
    └── ATOM: LinkButton ("Cancel")
```

**Component count:**
- TEMPLATEs: 1 (FormPageLayout)
- ORGANISMs: 5 (PageHeader, PersonalInfoSection, MedicalInfoSection, InsuranceSection, FormActions)
- MOLECULEs: 10 (Breadcrumb, FullNameField, DOBField, PhoneField, EmailField, BloodGroupField, AllergiesField, NotesField, ProviderField, PolicyNumberField, FileUploadField)
- ATOMs: 5 (Heading, Text, GenderSelect, Button x2, LinkButton)

---

### Scenario: "View Patient List"

**Page: Patient List Page**

```
TEMPLATE: ListPageLayout
│
├── ORGANISM: PageHeader
│   ├── ATOM: Heading ("Patients")
│   ├── MOLECULE: SearchInput (TextInput + IconButton)
│   └── ATOM: Button ("Add Patient")
│
├── ORGANISM: FilterPanel
│   ├── MOLECULE: DepartmentFilter (Label + Select)
│   ├── MOLECULE: DateRangeFilter (Label + DateRangePicker)
│   ├── MOLECULE: StatusFilter (Label + MultiSelect)
│   └── ATOM: Button ("Apply Filters")
│
├── ORGANISM: PatientTable
│   ├── MOLECULE: TableHeader (ColumnHeaders with sort)
│   ├── MOLECULE: TableRow (Avatar + Name + DOB + Status + Actions)
│   │   [repeats for each patient]
│   └── MOLECULE: Pagination (Buttons + PageInfo)
│
└── ORGANISM: EmptyState (shown when no results)
    ├── ATOM: Icon (empty illustration)
    ├── ATOM: Text ("No patients found")
    └── ATOM: Button ("Add First Patient")
```

---

### Scenario: "View Dashboard"

**Page: Dashboard Page**

```
TEMPLATE: DashboardLayout
│
├── ORGANISM: DashboardHeader
│   ├── ATOM: Heading ("Dashboard")
│   ├── MOLECULE: DateRangePicker (start + end)
│   └── ATOM: Button ("Export")
│
├── ORGANISM: MetricsRow
│   ├── MOLECULE: StatCard ("Total Patients" + count + trend)
│   ├── MOLECULE: StatCard ("Appointments Today" + count + trend)
│   ├── MOLECULE: StatCard ("Pending Reports" + count + trend)
│   └── MOLECULE: StatCard ("Revenue" + amount + trend)
│
├── ORGANISM: AppointmentsChart
│   ├── MOLECULE: ChartHeader (Title + FilterTabs)
│   └── ATOM: Chart (bar/line visualization)
│
├── ORGANISM: RecentPatients
│   ├── ATOM: Heading ("Recent Patients")
│   ├── MOLECULE: PatientRow (Avatar + Name + Date + Status)
│   │   [repeats]
│   └── ATOM: LinkButton ("View All")
│
└── ORGANISM: UpcomingAppointments
    ├── ATOM: Heading ("Upcoming")
    ├── MOLECULE: AppointmentCard (Time + Doctor + Patient + Status)
    │   [repeats]
    └── ATOM: LinkButton ("View Calendar")
```

---

## 5. CRITICAL — Generic Naming & Reuse Rule

> **ATOMs and MOLECULEs MUST be named generically, not per-instance.**
> Create ONE generic component and REUSE it everywhere. Never create
> instance-specific duplicates.

This is the single most important reuse rule. An atom represents a **type
of element**, not a specific usage of it.

### The Problem

A login form has two labels: "Username" and "Password". The WRONG approach
creates two atoms:

```
WRONG — instance-specific atoms (DO NOT DO THIS):

ORGANISM: LoginForm
├── ATOM: UsernameLabel          ← duplicate of Label
├── ATOM: UsernameTextInput      ← duplicate of TextInput
├── ATOM: PasswordLabel          ← duplicate of Label
├── ATOM: PasswordInput          ← duplicate of PasswordInput
└── ATOM: LoginButton            ← duplicate of Button
```

This creates 5 unique atoms when only 3 are needed.

### The Solution

```
RIGHT — generic atoms (reused) + purposeful variants:

ATOM: Label              ← created ONCE, reused by both molecules
ATOM: TextInput          ← created ONCE
ATOM: PasswordInput      ← VARIANT (different behavior from TextInput)
ATOM: SubmitButton       ← VARIANT (primary action, distinct styling)

ORGANISM: LoginForm
├── MOLECULE: UsernameField
│   ├── ATOM: Label          ← REUSE (same Label atom)
│   └── ATOM: TextInput      ← REUSE
├── MOLECULE: PasswordField
│   ├── ATOM: Label          ← REUSE (same Label atom, not "PasswordLabel")
│   └── ATOM: PasswordInput  ← REUSE
└── ATOM: SubmitButton        ← REUSE (variant for primary actions)
```

### The Rule

| Level    | Naming Rule                                                    | Example                                         |
| -------- | -------------------------------------------------------------- | ----------------------------------------------- |
| ATOM     | **Generic by type.** Name after the element TYPE, not its use. BUT create **variants** when the element has distinct behavior, appearance, or purpose (e.g., buttons, inputs). | `Label`, `TextInput`, `SubmitButton`, `SearchButton`, `ClearButton`, `Icon` |
| MOLECULE | **Generic by pattern, variants by purpose.** Reuse molecules that share the same structure. Create variants when the molecule has a distinct composition or behavior. | `TextInputField` (reuse), `SearchInput` (variant), `DateRangeFilter` (variant) |
| ORGANISM | **Always specific.** Name after the section it represents.     | `LoginForm`, `PatientTable`                     |
| TEMPLATE | **Always generic.** Name after the layout pattern.             | `FormPageLayout`, `DashboardLayout`             |

**Ask this before creating any ATOM:**
*"Does an atom of this element type already exist in `existingcomponents.json`?"*
- If YES → **REUSE** (link the existing atom, do not create a new one)
- If NO → **CREATE** with a generic name (e.g., `Label`, not `NameLabel`)

**When to create variants vs reuse the same atom:**

Variants are appropriate when the atom has a **distinct purpose, behavior,
or visual style** — not just different text content.

| Atom Type  | Create Variants?  | Reasoning                                        |
| ---------- | ----------------- | ------------------------------------------------ |
| **Button** | YES — variants    | SubmitButton, SearchButton, ClearButton, CancelButton, DeleteButton each have distinct intent, styling, and behavior (primary vs secondary vs danger) |
| **Label**  | NO — reuse one    | All labels render the same way; only the text differs |
| **Heading**| NO — reuse one    | All headings render the same way; only the text differs |
| **Badge**  | NO — reuse one    | Badge styling is driven by props (color, variant), not by creating separate atoms |
| **Icon**   | NO — reuse one    | Icons are the same component with different icon names as props |
| **Input**  | YES — by type     | TextInput, PasswordInput, EmailInput, NumberInput are functionally different input types |

**Examples of correct naming:**

| WRONG (duplicate)               | RIGHT                                   |
| ------------------------------- | --------------------------------------- |
| `NameLabel`                     | `Label` (reuse)                         |
| `PasswordLabel`                 | `Label` (reuse)                         |
| `EmailTextInput`                | `TextInput` (reuse)                     |
| `PhoneNumberTextInput`          | `TextInput` (reuse)                     |
| `PatientNameHeading`            | `Heading` (reuse)                       |
| `DashboardHeading`              | `Heading` (reuse)                       |
| `StatusBadge`                   | `Badge` (reuse)                         |
| `PriorityBadge`                 | `Badge` (reuse)                         |

**Examples of correct variants (OK to create):**

| Variant Atom       | Why it's a valid variant                                 |
| ------------------- | -------------------------------------------------------- |
| `SubmitButton`      | Primary action, distinct styling (filled, primary color) |
| `CancelButton`      | Secondary action, distinct styling (outlined, neutral)   |
| `DeleteButton`      | Danger action, distinct styling (red, destructive)       |
| `SearchButton`      | Search-specific, often icon-only with distinct placement |
| `ClearButton`       | Reset/clear action, distinct intent                      |
| `TextInput`         | Plain text entry                                         |
| `PasswordInput`     | Masked text entry with show/hide toggle                  |
| `EmailInput`        | Email format validation built in                         |
| `NumberInput`       | Numeric-only with increment/decrement                    |

**Molecule variants (same rules apply):**

Molecules that share the same internal structure should be reused. Create
variants only when the molecule has a **different composition of atoms**.

| WRONG (duplicate molecules)                 | RIGHT                                          |
| ------------------------------------------- | ---------------------------------------------- |
| `PatientNameField` (Label + TextInput + Error) | `TextInputField` (reuse for all text inputs) |
| `AddressField` (Label + TextInput + Error)  | `TextInputField` (reuse)                       |
| `NotesField` (Label + TextInput + Error)    | `TextInputField` (reuse)                       |

| Variant Molecule      | Why it's a valid variant                                    |
| --------------------- | ----------------------------------------------------------- |
| `TextInputField`      | Label + TextInput + ErrorMessage                            |
| `SelectField`         | Label + Select + ErrorMessage (different control atom)      |
| `DatePickerField`     | Label + DatePicker + ErrorMessage (different control atom)  |
| `FileUploadField`     | Label + FileUpload + ErrorMessage (different control atom)  |
| `SearchInput`         | TextInput + SearchButton (no label, different composition)  |
| `DateRangeFilter`     | Label + DateRangePicker (different composite control)       |
| `PhoneInputField`     | Label + Select (country) + TextInput (number) + Error (3 controls) |

**The rule of thumb (applies to both atoms and molecules):**
- If two components **have the same structure** and only differ by text/content → **REUSE** (Label, Heading, TextInputField)
- If two components have **different composition, behavior, or purpose** → **CREATE VARIANT** (SubmitButton vs DeleteButton, TextInputField vs SelectField)

### Full Correct Example: Registration Form

```
Generic ATOMs (created ONCE each, reused everywhere):
  - Label
  - TextInput
  - Select
  - DatePicker
  - Button
  - ErrorMessage

Specific MOLECULEs (each reuses the generic atoms above):
  - FullNameField     → Label + TextInput + ErrorMessage
  - EmailField        → Label + TextInput + ErrorMessage   (same atoms!)
  - GenderField       → Label + Select + ErrorMessage      (same Label + ErrorMessage!)
  - DOBField          → Label + DatePicker + ErrorMessage   (same Label + ErrorMessage!)

Specific ORGANISM:
  - RegistrationForm  → FullNameField + EmailField + GenderField + DOBField + Button
```

**Result:** 6 atoms created total, reused across 4 molecules. Without this
rule you would create 16+ instance-specific atoms.

---

## 6. Common Mistakes

### Mistake 1: Creating instance-specific ATOMs (MOST COMMON)

**Wrong:**
```
ATOM: NameLabel
ATOM: PasswordLabel
ATOM: EmailLabel
```

**Right:**
```
ATOM: Label  ← created once, reused 3 times
```

**Rule:** ATOMs are named after WHAT they are (Label, Button, TextInput),
never after WHERE they are used (NameLabel, SubmitButton). Check
`existingcomponents.json` before creating any atom.

---

### Mistake 2: Making everything an ORGANISM

**Wrong:**
```
ORGANISM: PatientNameInput  ← too small for an ORGANISM
```

**Right:**
```
MOLECULE: PatientNameField (Label + TextInput + ErrorMessage)
```

**Rule:** If it only has 2-3 atoms and does one small job, it is a MOLECULE.

---

### Mistake 3: Making grouped inputs into separate ATOMs

**Wrong:**
```
ATOM: FirstNameLabel
ATOM: FirstNameInput
ATOM: FirstNameError
```

**Right:**
```
MOLECULE: FirstNameField
├── ATOM: Label
├── ATOM: TextInput
└── ATOM: ErrorMessage
```

**Rule:** If elements are always shown together and removing one breaks the
UX, group them as a MOLECULE.

---

### Mistake 4: Skipping the MOLECULE level

**Wrong:**
```
ORGANISM: RegistrationForm
├── ATOM: Label
├── ATOM: TextInput
├── ATOM: Label
├── ATOM: Select
├── ATOM: Button
```

**Right:**
```
ORGANISM: RegistrationForm
├── MOLECULE: NameField (Label + TextInput + Error)
├── MOLECULE: GenderField (Label + Select + Error)
└── ATOM: SubmitButton
```

**Rule:** Always look for natural groupings. Form fields almost always form
molecules (label + control + validation).

---

### Mistake 5: Creating a TEMPLATE for every page

**Wrong:** Every page gets its own unique template.

**Right:** Templates are **reusable layout patterns**. Only create a template
when 2+ pages share the same structural layout. If a page has a unique
layout, skip the template and start with organisms.

---

### Mistake 6: Putting content logic in TEMPLATE

**Wrong:**
```
TEMPLATE: PatientRegistrationTemplate
├── ORGANISM: PatientForm (with specific fields)
```

**Right:**
```
TEMPLATE: FormPageLayout (generic slots: header, form-area, actions)
```

**Rule:** Templates define WHERE things go, not WHAT they are. A template
named after a specific page is probably just an organism in disguise.

---

## 7. Quick Reference Decision Table

| Action Description                         | Type       | Example Component             | Naming Note                              |
| ------------------------------------------ | ---------- | ----------------------------- | ---------------------------------------- |
| "Click submit"                             | ATOM       | Button                        | Generic name, NOT "SubmitButton"         |
| "Enter patient name"                       | ATOM       | TextInput                     | Generic name, NOT "PatientNameInput"     |
| "Enter patient name" (with label + error)  | MOLECULE   | PatientNameField              | Molecules CAN be specific                |
| "Select date and time"                     | MOLECULE   | DateTimePicker                |                                          |
| "Search patients"                          | MOLECULE   | SearchInput                   |                                          |
| "Fill registration form"                   | ORGANISM   | RegistrationForm              |                                          |
| "View patient list"                        | ORGANISM   | PatientTable                  |                                          |
| "View patient details card"                | ORGANISM   | PatientDetailCard             |                                          |
| "Navigate to section"                      | ORGANISM   | Sidebar / Navbar              |                                          |
| "Show confirmation dialog"                 | ORGANISM   | ConfirmationModal             |                                          |
| Standard form page structure               | TEMPLATE   | FormPageLayout                | Generic name, NOT "RegistrationTemplate" |
| Standard list page structure               | TEMPLATE   | ListPageLayout                |                                          |
| Standard dashboard structure               | TEMPLATE   | DashboardLayout               |                                          |

---

## 8. Hierarchy Rules Summary

```
TEMPLATE
├── contains → ORGANISMs (layout slots)
├── supportingComponents → [ORGANISM names]
└── scope → GLOBAL (always reusable across pages)

ORGANISM
├── contains → MOLECULEs and ATOMs
├── supportingComponents → [MOLECULE and/or ATOM names]
└── scope → PAGE (container is page-specific, but children can be reused)

MOLECULE
├── contains → ATOMs only
├── supportingComponents → [ATOM names]
└── scope → GLOBAL or DOMAIN (high reuse potential)

ATOM
├── contains → nothing
├── supportingComponents → [] (always empty)
└── scope → GLOBAL (maximum reuse)
```

**Nesting rules (strict):**
- TEMPLATE can only contain ORGANISMs
- ORGANISM can contain MOLECULEs and ATOMs
- MOLECULE can only contain ATOMs
- ATOM cannot contain anything

**Never skip levels in nesting.** An ATOM cannot be a direct child of a
TEMPLATE. A MOLECULE cannot be a direct child of a TEMPLATE.

---

## 9. Cross-Scenario Reuse — The Compound Effect

The real power of atomic design emerges when processing **multiple
scenarios**. Components created in Scenario 1 get reused in Scenarios
2, 3, 4... This section shows how reuse compounds across an application.

### Example: Hospital Management System (4 Scenarios)

#### Scenario 1: "Patient Registration"

**New components created:**

```
ATOMs (8 new):
  Label, TextInput, EmailInput, Select, DatePicker,
  SubmitButton, CancelButton, ErrorMessage

MOLECULEs (5 new):
  TextInputField, EmailInputField, SelectField,
  DatePickerField, Breadcrumb

ORGANISMs (3 new):
  PersonalInfoSection, ContactInfoSection, FormActions

TEMPLATE (1 new):
  FormPageLayout
```

**Total new: 17 components**

---

#### Scenario 2: "Schedule Appointment"

**Check `existingcomponents.json` first!**

```
ATOMs:
  Label              ← REUSE (from Scenario 1)
  TextInput          ← REUSE
  Select             ← REUSE
  DatePicker         ← REUSE
  SubmitButton       ← REUSE
  CancelButton       ← REUSE
  ErrorMessage       ← REUSE
  TimePicker         ← NEW (time selection is different from date)
  TextArea           ← NEW (multi-line input for notes)

MOLECULEs:
  TextInputField     ← REUSE (for "Reason" field)
  SelectField        ← REUSE (for "Doctor" dropdown)
  DatePickerField    ← REUSE (for "Appointment Date")
  TimePickerField    ← NEW (Label + TimePicker + ErrorMessage)
  TextAreaField      ← NEW (Label + TextArea + ErrorMessage)

ORGANISMs:
  AppointmentForm    ← NEW (page-specific)
  DoctorSelection    ← NEW (page-specific)
  FormActions        ← REUSE (same submit/cancel pattern)

TEMPLATE:
  FormPageLayout     ← REUSE (same form layout)
```

**New: 5 components | Reused: 12 components | Reuse rate: 71%**

---

#### Scenario 3: "View Patient List"

```
ATOMs:
  Label              ← REUSE
  TextInput          ← REUSE
  Select             ← REUSE
  SubmitButton       ← REUSE
  SearchButton       ← NEW (icon-only search trigger)
  Heading            ← NEW
  Badge              ← NEW (status indicator)
  Avatar             ← NEW (patient photo)
  Icon               ← NEW (sort/action icons)
  LinkButton         ← NEW (navigation link style)

MOLECULEs:
  SearchInput        ← NEW (TextInput + SearchButton)
  SelectField        ← REUSE
  Pagination         ← NEW
  TableRow           ← NEW (Avatar + text cells + Badge + actions)
  Breadcrumb         ← REUSE

ORGANISMs:
  FilterPanel        ← NEW
  PatientTable       ← NEW
  PageHeader         ← NEW
  EmptyState         ← NEW

TEMPLATE:
  ListPageLayout     ← NEW (different layout from form)
```

**New: 13 components | Reused: 6 components | Reuse rate: 32%**
(Lower rate expected — this is a new page type with different patterns)

---

#### Scenario 4: "View Patient Dashboard"

```
ATOMs:
  Heading            ← REUSE (from Scenario 3)
  Badge              ← REUSE
  Avatar             ← REUSE
  Icon               ← REUSE
  LinkButton         ← REUSE
  Label              ← REUSE
  Select             ← REUSE

MOLECULEs:
  StatCard           ← NEW (Label + value + trend Icon)
  SearchInput        ← REUSE (from Scenario 3)
  Pagination         ← REUSE
  DateRangePicker    ← NEW (DatePicker + DatePicker)
  Tabs               ← NEW
  TableRow           ← REUSE

ORGANISMs:
  MetricsRow         ← NEW
  RecentPatientsPanel← NEW
  AppointmentsChart  ← NEW
  ActivityTimeline   ← NEW
  DashboardHeader    ← NEW

TEMPLATE:
  DashboardLayout    ← NEW
```

**New: 9 components | Reused: 10 components | Reuse rate: 53%**

---

#### Cumulative Reuse Summary

| Scenario                | New | Reused | Total Needed | Reuse Rate |
| ----------------------- | --- | ------ | ------------ | ---------- |
| 1. Patient Registration | 17  | 0      | 17           | 0%         |
| 2. Schedule Appointment | 5   | 12     | 17           | 71%        |
| 3. View Patient List    | 13  | 6      | 19           | 32%        |
| 4. View Dashboard       | 9   | 10     | 19           | 53%        |
| **TOTAL**               | **44** | **28** | **72**    | **39%**    |

Without reuse: 72 components. With reuse: 44 unique components.
**28 components saved (39% reduction).**

As more scenarios are processed, the reuse rate climbs because the
foundational atoms and molecules are already in `existingcomponents.json`.

---

## 10. Reuse Checklist (Run Before Creating ANY Component)

Before creating a component at any level, walk through this checklist:

```
STEP 1: Read existingcomponents.json

STEP 2: For each component you plan to create:
  │
  ├── ATOM?
  │   ├── Does an atom of this TYPE already exist?
  │   │   (e.g., creating a Label? Is "Label" already listed?)
  │   │   └── YES → REUSE. Do not create.
  │   ├── Is this a valid VARIANT? (different behavior/styling)
  │   │   (e.g., SubmitButton vs CancelButton)
  │   │   └── YES → Check if this variant already exists → REUSE or CREATE
  │   └── Is this instance-specific naming? (e.g., "PatientNameLabel")
  │       └── YES → STOP. Rename to generic ("Label") and REUSE.
  │
  ├── MOLECULE?
  │   ├── Does a molecule with the SAME atom composition exist?
  │   │   (e.g., Label + TextInput + ErrorMessage = TextInputField)
  │   │   └── YES → REUSE. Do not create.
  │   ├── Is the composition genuinely different?
  │   │   (e.g., Label + Select + ErrorMessage ≠ TextInputField)
  │   │   └── YES → CREATE as a new variant (SelectField)
  │   └── Is this just a renamed copy? (same atoms, different name)
  │       └── YES → STOP. Use the existing molecule.
  │
  ├── ORGANISM?
  │   └── ORGANISMs are page-specific containers → always CREATE NEW
  │       But check: are the molecules/atoms inside it reusable?
  │       └── YES → Reuse existing molecules/atoms as supportingComponents
  │
  └── TEMPLATE?
      ├── Does a template for this page layout type exist?
      │   (e.g., FormPageLayout for any form page)
      │   └── YES → REUSE. Do not create.
      └── Is this a genuinely new layout pattern?
          └── YES → CREATE (but name generically: "ListPageLayout", not
              "PatientListTemplate")
```

---

## 11. Standard Component Catalog

This is the baseline set of components that most applications will need.
When generating design nodes, prefer these standard names over inventing
new ones. Check `existingcomponents.json` first — if a standard component
was already created in a prior scenario, reuse it.

### Standard ATOMs

| Category     | Components                                                      |
| ------------ | --------------------------------------------------------------- |
| **Text**     | `Label`, `Heading`, `Text`, `ErrorMessage`, `HelperText`        |
| **Input**    | `TextInput`, `PasswordInput`, `EmailInput`, `NumberInput`, `TextArea`, `PhoneInput` |
| **Selection**| `Select`, `Checkbox`, `Toggle`, `Slider`, `RadioButton`, `DatePicker`, `TimePicker` |
| **Button**   | `SubmitButton`, `CancelButton`, `DeleteButton`, `SearchButton`, `ClearButton`, `LinkButton`, `IconButton` |
| **Display**  | `Avatar`, `Badge`, `Tag`, `Icon`, `Image`, `Divider`           |
| **Feedback** | `Spinner`, `ProgressBar`, `Skeleton`, `Tooltip`                 |

### Standard MOLECULEs

| Category        | Components                                                    |
| --------------- | ------------------------------------------------------------- |
| **Form Fields** | `TextInputField`, `PasswordField`, `EmailField`, `NumberField`, `SelectField`, `DatePickerField`, `TimePickerField`, `TextAreaField`, `FileUploadField`, `CheckboxField`, `ToggleField` |
| **Compound**    | `SearchInput`, `PhoneInputField`, `DateTimePicker`, `DateRangePicker`, `RadioGroup`, `MultiSelect` |
| **Navigation**  | `Breadcrumb`, `Tabs`, `Stepper`, `Pagination`, `Menu`         |
| **Display**     | `StatCard`, `TableRow`, `Alert`, `Toast`, `ButtonGroup`        |

### Standard ORGANISMs

| Category        | Components                                                     |
| --------------- | -------------------------------------------------------------- |
| **Forms**       | `FormSection`, `FormActions` (reusable pattern)                |
| **Data**        | `DataTable`, `DataGrid`, `List`, `Timeline`, `Chart`           |
| **Navigation**  | `Navbar`, `Sidebar`                                            |
| **Containers**  | `Card`, `Panel`, `Accordion`, `Modal`, `Drawer`                |
| **Page Parts**  | `PageHeader`, `FilterPanel`, `EmptyState`                      |

> **Note:** Organisms are page-specific containers and are always created
> new. But organisms with the SAME functional pattern (e.g., `FormActions`
> with Submit + Cancel) CAN be reused across pages.

### Standard TEMPLATEs

| Template            | Structure                                  | Use For                |
| ------------------- | ------------------------------------------ | ---------------------- |
| `FormPageLayout`    | Header + Breadcrumb + FormArea + Actions   | Any form page          |
| `ListPageLayout`    | Header + Filters + Table + Pagination      | Any list/table page    |
| `DetailPageLayout`  | Header + InfoPanel + Tabs + Actions        | Any detail/view page   |
| `DashboardLayout`   | Header + Metrics + Charts + Panels         | Any dashboard page     |
| `WizardLayout`      | Stepper + StepContent + Navigation         | Any multi-step wizard  |
| `SplitPaneLayout`   | LeftPanel + RightPanel                     | Master-detail views    |
| `AuthPageLayout`    | Logo + CenteredForm + Footer               | Login, Register, Reset |

---

## 12. Reuse Patterns by Page Type

Different page types have predictable component patterns. Use these as a
starting point when generating design nodes for a new scenario.

### Form Pages (Registration, Edit, Create)

```
Highly reusable (check existingcomponents.json first):
├── TEMPLATE: FormPageLayout          ← likely exists
├── ATOMs: Label, TextInput, Select, SubmitButton, CancelButton, ErrorMessage
│   ← almost certainly exist after first form page
├── MOLECULEs: TextInputField, SelectField, DatePickerField
│   ← almost certainly exist after first form page
└── ORGANISM: FormActions             ← pattern likely exists

Likely new per page:
└── ORGANISMs: specific form sections (PersonalInfoSection, etc.)
```

### List/Table Pages (Patient List, Order History)

```
Highly reusable:
├── TEMPLATE: ListPageLayout          ← likely exists
├── ATOMs: Heading, SearchButton, Badge, Icon, LinkButton
├── MOLECULEs: SearchInput, Pagination, Breadcrumb
└── ORGANISM: PageHeader, EmptyState  ← pattern may exist

Likely new per page:
├── MOLECULEs: domain-specific TableRow
└── ORGANISMs: specific table/filter panels
```

### Dashboard Pages

```
Highly reusable:
├── TEMPLATE: DashboardLayout         ← likely exists
├── ATOMs: Heading, Badge, Icon, LinkButton, Avatar
├── MOLECULEs: StatCard, Tabs, DateRangePicker
└── These are commonly shared with list pages

Likely new per page:
└── ORGANISMs: domain-specific chart panels and data sections
```

### Detail/View Pages (Patient Detail, Order Detail)

```
Highly reusable:
├── TEMPLATE: DetailPageLayout        ← likely exists
├── ATOMs: Heading, Label, Text, Badge, Avatar, Icon
├── MOLECULEs: Tabs, Breadcrumb, ButtonGroup
└── Shared with list and form pages

Likely new per page:
└── ORGANISMs: domain-specific info panels and tab content
```

---

## 13. Multi-Scenario Worked Example: E-Commerce App

This end-to-end example shows component creation across 3 scenarios with
full reuse tracking.

### Scenario 1: "User Registration"

**Actions from functional graph:**
1. Enter first name
2. Enter last name
3. Enter email
4. Enter password
5. Confirm password
6. Accept terms and conditions
7. Click register

**Component breakdown:**

```
NEW ATOMs: Label, TextInput, EmailInput, PasswordInput, Checkbox,
           SubmitButton, ErrorMessage, Heading, Text
           → 9 atoms

NEW MOLECULEs: TextInputField (Label+TextInput+ErrorMessage),
               EmailInputField (Label+EmailInput+ErrorMessage),
               PasswordInputField (Label+PasswordInput+ErrorMessage),
               CheckboxField (Checkbox+Label)
               → 4 molecules

NEW ORGANISMs: RegistrationForm, FormActions
               → 2 organisms

NEW TEMPLATE: AuthPageLayout
              → 1 template

TOTAL NEW: 16 components
```

**Update `existingcomponents.json` with all 16.**

---

### Scenario 2: "User Login"

**Actions:**
1. Enter email
2. Enter password
3. Click login
4. Click forgot password

**Component breakdown:**

```
REUSE ATOMs: Label, EmailInput, PasswordInput, SubmitButton,
             ErrorMessage, Heading, Text
             → 7 reused

NEW ATOMs: LinkButton
           → 1 new

REUSE MOLECULEs: EmailInputField, PasswordInputField
                 → 2 reused

NEW ORGANISMs: LoginForm
               → 1 new

REUSE TEMPLATE: AuthPageLayout
                → 1 reused

TOTAL: 12 components needed, 10 reused, 2 new
REUSE RATE: 83%
```

**Update `existingcomponents.json` with 2 new components.**

---

### Scenario 3: "Browse Product Catalog"

**Actions:**
1. Search products
2. Filter by category
3. Filter by price range
4. Sort results
5. View product card (image + name + price + rating)
6. Add to cart
7. Navigate pages

**Component breakdown:**

```
REUSE ATOMs: Label, TextInput, Select, Heading, Text, Icon, Badge
             → 7 reused

NEW ATOMs: Image, Slider (price range), SearchButton
           → 3 new

REUSE MOLECULEs: SelectField
                 → 1 reused

NEW MOLECULEs: SearchInput (TextInput+SearchButton),
               PriceRangeFilter (Label+Slider+Slider),
               Pagination, StarRating,
               ProductCard (Image+Heading+Text+Badge+Button)
               → 5 new

NEW ORGANISMs: FilterSidebar, ProductGrid, PageHeader
               → 3 new

NEW TEMPLATE: ListPageLayout
              → 1 new

TOTAL: 20 components needed, 8 reused, 12 new
REUSE RATE: 40%
```

**Cumulative after 3 scenarios:**

| Component Level | Total Unique | Times Reused |
| --------------- | ------------ | ------------ |
| ATOMs           | 13           | 14           |
| MOLECULEs       | 10           | 3            |
| ORGANISMs       | 6            | 0            |
| TEMPLATEs       | 2            | 1            |
| **TOTAL**       | **31**       | **18**       |

Without reuse: 48 components. With reuse: 31.
**18 components saved (37% reduction), growing with each scenario.**

---

## 14. Scope Assignment Rules

Every component has a **scope** that determines where it can be reused.
Assigning the right scope is critical for maximizing reuse.

| Scope    | Meaning                    | When to Use                                        | Examples                            |
| -------- | -------------------------- | -------------------------------------------------- | ----------------------------------- |
| `GLOBAL` | Reusable across the entire app | Generic UI elements with no domain logic         | Label, TextInput, SubmitButton, TextInputField, SearchInput, Pagination |
| `DOMAIN` | Reusable within a business domain | Components tied to a specific domain concept     | PatientCard, AppointmentRow, OrderSummary, VitalsDisplay |
| `PAGE`   | Used on a single page only | Page-specific containers and one-off layouts        | RegistrationForm, DashboardMetrics, ProductGrid |

**Scope decision flowchart:**

```
Is this component tied to a specific domain concept?
├── NO → Could it appear on any page in any app?
│   ├── YES → GLOBAL (Label, Button, TextInputField, Pagination)
│   └── NO → Still likely GLOBAL if it's a standard UI pattern
└── YES → Could it appear on multiple pages within that domain?
    ├── YES → DOMAIN (PatientCard used in list + detail + dashboard)
    └── NO → PAGE (RegistrationForm used only on registration page)
```

**Key rules:**
- All ATOMs should be `GLOBAL` (they are generic by definition)
- Most MOLECULEs should be `GLOBAL` unless they contain domain-specific logic
- ORGANISMs are typically `PAGE`, but reusable patterns like `FormActions` can be `GLOBAL`
- TEMPLATEs should always be `GLOBAL`
- **Never downgrade scope** — if a component is currently `GLOBAL`, don't make it `DOMAIN` when reusing
- **Prefer higher scope** — when in doubt, use `GLOBAL` over `DOMAIN`, `DOMAIN` over `PAGE`

---

## 15. Recognizing Reuse Opportunities

These patterns signal that a component should be reused rather than created
new. Train yourself to spot them.

### Pattern 1: Same verb, different noun

```
"Enter patient name"     → TextInputField (REUSE)
"Enter doctor name"      → TextInputField (REUSE)
"Enter medication name"  → TextInputField (REUSE)
"Enter address"          → TextInputField (REUSE)
```

All of these are "enter text into a field." Same molecule, different label text.

### Pattern 2: Same structure, different data

```
"View patient list"      → DataTable (with patient columns)
"View appointment list"  → DataTable (with appointment columns)
"View order list"        → DataTable (with order columns)
```

The table structure (header + rows + pagination + search) is the same.
The ORGANISM template is reusable; only the column config changes.

### Pattern 3: Same action, different context

```
"Submit registration"    → SubmitButton (REUSE)
"Submit appointment"     → SubmitButton (REUSE)
"Submit order"           → SubmitButton (REUSE)
"Cancel registration"    → CancelButton (REUSE)
"Cancel appointment"     → CancelButton (REUSE)
```

Submit is submit. Cancel is cancel. The context doesn't change the button.

### Pattern 4: Same layout, different content

```
"Patient Registration page"  → FormPageLayout (REUSE template)
"Appointment Booking page"   → FormPageLayout (REUSE template)
"Edit Profile page"          → FormPageLayout (REUSE template)
```

All form pages share the same skeleton: header, breadcrumb, form area, action bar.

### Pattern 5: Repeated field patterns in forms

```
Form with 5 text fields → ONE TextInputField molecule reused 5 times
Form with 3 dropdowns   → ONE SelectField molecule reused 3 times
Form with 2 dates       → ONE DatePickerField molecule reused 2 times
```

**Never create `FirstNameField`, `LastNameField`, `AddressField` as separate
molecules if they are all Label + TextInput + ErrorMessage.**

### Pattern 6: Navigation patterns across pages

```
Every page has breadcrumbs  → ONE Breadcrumb molecule, REUSE everywhere
Every page has a header     → ONE PageHeader organism pattern
Every list has pagination   → ONE Pagination molecule, REUSE everywhere
Every form has submit/cancel→ ONE FormActions organism, REUSE everywhere
```

### Pattern 7: Feedback patterns

```
Form validation error     → ErrorMessage atom (REUSE)
API error notification    → Alert molecule (REUSE)  
Success confirmation      → Toast molecule (REUSE)
Loading state             → Spinner atom (REUSE)
Empty list state          → EmptyState organism (REUSE)
```

These appear across every page type. Create once, reuse everywhere.

---

## 16. Anti-Patterns Summary

| Anti-Pattern                           | Why It's Wrong                                | Correct Approach                            |
| -------------------------------------- | --------------------------------------------- | ------------------------------------------- |
| `NameLabel` + `EmailLabel`             | Same component, different text                | One `Label` atom, reuse                     |
| `PatientNameField` + `DoctorNameField` | Same structure (Label+TextInput+Error)        | One `TextInputField` molecule, reuse        |
| `PatientSearchInput` + `DoctorSearchInput` | Same composition (TextInput+SearchButton) | One `SearchInput` molecule, reuse           |
| `RegistrationSubmitButton` + `LoginSubmitButton` | Same button variant               | One `SubmitButton` atom, reuse              |
| `PatientListTemplate` + `OrderListTemplate` | Same layout pattern                    | One `ListPageLayout` template, reuse        |
| Separate `Heading` atoms per page      | Same element, different text                  | One `Heading` atom, reuse                   |
| `PatientFormActions` + `OrderFormActions` | Same Submit+Cancel pattern                 | One `FormActions` organism, reuse           |
| Creating `LoadingSpinner` + `TableSpinner` | Same spinner in different contexts        | One `Spinner` atom, reuse                   |
| Creating `SuccessToast` + `ErrorToast` | Same toast structure, different styling       | One `Toast` molecule, reuse (style via props)|
| New `Pagination` per list page         | Same prev/next/page pattern everywhere        | One `Pagination` molecule, reuse            |
