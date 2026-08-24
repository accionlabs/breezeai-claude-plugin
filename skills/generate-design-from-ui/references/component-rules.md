# Component Rules — Classification, Naming & Composition

## Atomic Design Levels

| Level | Definition | When to Use |
|---|---|---|
| **TEMPLATE** | Page-level layout skeleton | Defines WHERE things go, not WHAT they are |
| **ORGANISM** | Self-contained section with own logic | Forms, tables, nav bars, card grids |
| **MOLECULE** | Small group of atoms working as unit | Label + input + error, search with button |
| **ATOM** | Single indivisible UI element | Button, input, label, icon, badge |

---

## Classification from UI Code

When reading actual UI code, classify components by analyzing their
structure, not just their name:

**ATOM indicators:**
- Single HTML element or thin wrapper (`<button>`, `<input>`, `<img>`)
- No internal state management
- Props-only interface
- Examples: `Button`, `Input`, `Label`, `Icon`, `Badge`, `Avatar`,
  `Checkbox`, `Radio`, `Switch`, `Tooltip`

**MOLECULE indicators:**
- 2-4 atoms composed together as a functional unit
- Minimal internal state (e.g. input focus, dropdown open)
- Examples: `SearchBar` (input + button), `FormField` (label + input +
  error), `MenuItem` (icon + label + badge), `Pagination` (buttons +
  page numbers)

**ORGANISM indicators:**
- Self-contained section with own state management
- Uses hooks (`useState`, `useReducer`, `useQuery`, `useMutation`)
- Contains multiple molecules/atoms
- Examples: `LoginForm`, `DataTable`, `NavigationBar`, `UserCard`,
  `FilterPanel`, `CommentThread`

**TEMPLATE indicators:**
- Layout-only component — defines grid/flex structure
- No business logic, just slots for children
- Examples: `PageLayout`, `SplitPane`, `DashboardGrid`,
  `FormPageLayout`, `WizardLayout`

---

## Naming Conventions

**CRITICAL: Use the actual component names from the codebase.**

Since this skill reads the real UI repo, design node names should
match the code — not be invented generic names. This is the key
difference from `generate-design`.

**Naming priority:**

1. **Exact exported component name** from the repo
   (`export const SearchFilterPanel` → `SearchFilterPanel`)
2. **File name in PascalCase** for default exports
   (`search-filter-panel.tsx` → `SearchFilterPanel`)
3. **Library component name** for third-party components
   (`AgGridReact`, `ReactSelect`, `ChakraModal`)
4. **Standard name** only for raw HTML elements with no wrapper
   (`<input>` → `TextInput`, `<button>` → `Button`)

**Reuse matching by repo name:**

Two scenarios that both use `<SearchFilterPanel>` from the same file
must map to the **same** design node. Match by actual component name
first in `existingcomponents.json`.

**TEMPLATEs are the exception** — named by layout pattern
(`FormPageLayout`, `ListPageLayout`) since they represent layout
structure, not a specific code component.

**ORGANISM containers are page-specific** — always create new, but
reuse their children (molecules/atoms).

---

## supportingComponents Array Rules

| Component Type | supportingComponents contains | Minimum |
|---|---|---|
| TEMPLATE | ORGANISM names only | ≥ 2 |
| ORGANISM | MOLECULE and/or ATOM names | ≥ 2 |
| MOLECULE | ATOM names only | ≥ 2 |
| ATOM | `[]` (empty array) | 0 |

> **⛔ Minimum 2 supporting components for non-ATOMs.** If a
> MOLECULE, ORGANISM, or TEMPLATE has fewer than 2 children, it is
> likely misclassified:
> - MOLECULE with 1 child → probably an ATOM (thin wrapper)
> - ORGANISM with 1 child → probably a MOLECULE
> - TEMPLATE with 1 child → probably an ORGANISM acting as layout
>
> Re-read the source file and verify the classification before
> accepting < 2 supporting components on any non-ATOM.

Order within `supportingComponents` reflects visual/logical order.

**NO `children` field** — composition is expressed solely through
`supportingComponents`.

---

## Reuse Resolution (Priority Order)

Before creating any component, read `existingcomponents.json`:

1. **Exact name match** → backend deduplicates by `projectUuid + name`
   (case-insensitive). Same name = same node, new parent edges added.
2. **`designSystemRef` for metadata** — still include for design system
   traceability, but NOT the dedup key.
3. **Semantic + type match in same domain** → REUSE (same name)
4. **Template/layout match** → REUSE (same name)
5. **Create new** → narrowest correct scope

**Hard rules:**
- Always check `existingcomponents.json` BEFORE creating
- ORGANISM containers are page-specific → always CREATE NEW
- Never downgrade scope on reuse
- Ties: prefer higher scope and more linked nodes

**Scope levels:**

| Scope | Description | Examples |
|---|---|---|
| `GLOBAL` | Entire application | Button, TextInput, Label, Pagination |
| `DOMAIN` | Business domain | PatientCard, AppointmentSlot |
| `PAGE` | Single page only | DashboardHeader, ReportFooter |

---

## Component-Import Drill-Down Rule

For every imported component matching
`/(Panel|Drawer|Modal|Sheet|Layout|Tab(s|Layout|Content))$/` AND
that has its own `useState`/`useReducer`/`useStore` hook, you MUST
read the file before drafting design nodes.

---

## Angular-Specific Component Rules

### Naming Convention — Angular

Angular components have a `selector` (kebab-case) and a class name
(PascalCase). **Always use the PascalCase class name** for design
graph nodes, NOT the selector.

| Code | Design Node Name | NOT |
|---|---|---|
| `@Component({ selector: 'app-user-table' }) export class UserTableComponent` | `UserTableComponent` | `app-user-table` |
| `@Component({ selector: 'app-search-bar' }) export class SearchBarComponent` | `SearchBarComponent` | `app-search-bar` |
| Standalone with `selector: 'shared-badge'` class `BadgeComponent` | `BadgeComponent` | `shared-badge` |

**Exception:** If the component class is named generically (e.g.,
`Component` from a third-party library), use the selector as a
PascalCase name instead.

### Template Reading — Angular

Angular templates can be inline or external:

- **Inline:** `template: \`...\`` in the `@Component` decorator
- **External:** `templateUrl: './component.component.html'`

For external templates, you MUST read BOTH the `.ts` file (for class
logic, services, state) AND the `.html` file (for component composition
and structure). Missing either gives an incomplete picture.

### Service Injection → State Signal

In React/Vue, hooks indicate state. In Angular, **injected services**
are the equivalent signal:

```typescript
// These ALL indicate the component manages state → ORGANISM
constructor(
  private userService: UserService,      // data service
  private store: Store<AppState>,        // NgRx store
  private fb: FormBuilder,              // reactive forms
  private dialog: MatDialog,            // dialog management
  private router: Router                // navigation (not state by itself)
)

// Or inject() style (Angular 14+)
private userService = inject(UserService)
private store = inject(Store)
```

**Exception:** `Router` and `ActivatedRoute` injection alone does NOT
make a component an ORGANISM — they're navigation utilities. But if
the component also injects data services or has `FormGroup`, it's an
ORGANISM.

### supportingComponents — Angular

Angular composition is found in the template, not JSX:

```html
<!-- Template of UserManagementComponent (ORGANISM) -->
<app-search-bar (search)="onSearch($event)"></app-search-bar>
<app-filter-chips [filters]="activeFilters"></app-filter-chips>
<app-user-table [data]="filteredUsers" (rowClick)="onSelect($event)"></app-user-table>
<mat-paginator [length]="total" [pageSize]="10"></mat-paginator>
```

→ `supportingComponents: ["SearchBarComponent", "FilterChipsComponent", "UserTableComponent", "MatPaginator"]`

**For standalone components:** Check `imports` array for composition:
```typescript
@Component({
  standalone: true,
  imports: [SearchBarComponent, FilterChipsComponent, MatTableModule],
  // ...
})
```

**For NgModule components:** Check the module's `declarations` and
`imports` to understand what's available, but read the TEMPLATE to
determine actual composition.

### Angular Material Components as Children

When an Angular component uses Material components, map them:

| Material Component | Design Node Type | Notes |
|---|---|---|
| `<mat-button>` / `<button mat-button>` | ATOM | Wraps button |
| `<mat-icon>` | ATOM | Icon element |
| `<mat-form-field>` + `<input matInput>` | MOLECULE | Form field group |
| `<mat-select>` + `<mat-option>` | MOLECULE | Select dropdown |
| `<mat-checkbox>`, `<mat-radio-button>` | ATOM | Single input |
| `<mat-table>` with sort + paginator | ORGANISM | Complex data display |
| `<mat-dialog>` content component | ORGANISM | Modal with state |
| `<mat-sidenav-container>` | TEMPLATE | Layout structure |
| `<mat-toolbar>` | ATOM or MOLECULE | Depends on composition |
| `<mat-card>` | MOLECULE | Content container |
| `<mat-tab-group>` | ORGANISM | Tab state management |
| `<mat-stepper>` | ORGANISM | Step state management |
| `<mat-chip-listbox>` | MOLECULE | Multi-select chips |
| `<mat-autocomplete>` | MOLECULE | Input + suggestions |
| `<mat-datepicker>` | MOLECULE | Date input + calendar |
| `<mat-snack-bar>` | ATOM | Notification toast |
| `<mat-progress-bar>` / `<mat-spinner>` | ATOM | Loading indicator |

### Angular Component-Import Drill-Down

The React rule checks for `/(Panel|Drawer|Modal|Sheet|Layout|Tab)$/`.
For Angular, also drill down into:

- Components opened via `MatDialog.open(<Component>)` — read the dialog component
- Components opened via `MatBottomSheet.open(<Component>)` — read the sheet component
- Components referenced in `<ng-template>` with `*ngIf` guards — read the template content
- Components in `entryComponents` (legacy) or `providers` with `ComponentFactoryResolver`
- Lazy-loaded route components (`loadComponent`) — read the target component
