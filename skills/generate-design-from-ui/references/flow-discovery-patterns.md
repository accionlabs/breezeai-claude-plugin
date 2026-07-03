# Flow Discovery Patterns — Generate Design from UI

## Overview

**Flow discovery** determines how many distinct ways a user can complete a scenario. The functional graph tells us WHAT the user does; the UI code reveals HOW MANY WAYS they can do it.

This document provides grep patterns, classification rules, and examples for discovering flows from actual UI code.

---

## Two Types of Flow Discovery

### Type A: Entry-Point Flows
**Different navigation paths TO the target page**

Examples:
- Reaching `/ticket/:id` from project list vs dashboard vs sidebar
- Opening settings from top nav vs profile dropdown vs keyboard shortcut
- Accessing a feature via direct URL vs multi-step wizard

### Type B: On-Page Flows
**Conditional rendering ON the target page that creates different component trees**

Examples:
- Social login vs email form on registration page
- Quick mode vs advanced mode in creation flow
- Bulk edit vs single item edit

---

## Type A: Entry-Point Flow Discovery

### Step 1: Identify Target Route

From Step 3a (scenario mapping), determine the primary route/page:
- `/ticket/:id`
- `/settings/profile`
- `/dashboard`
- `/projects/:projectId/details`

### Step 2: Grep Entire Repo for Navigation Calls

**React Router:**
```bash
# navigate() calls
grep -rn "navigate\(.*ticket\|push\(.*ticket" --include="*.tsx" --include="*.jsx"

# <Link> components
grep -rn "<Link.*to=.*ticket\|<Link.*href.*ticket" --include="*.tsx" --include="*.jsx"

# useNavigate hook usage
grep -rn "useNavigate\|useHistory" --include="*.tsx" --include="*.jsx"
# Then read those files to see if they navigate to target route
```

**Next.js:**
```bash
# router.push
grep -rn "router\.push\(.*ticket\|router\.replace\(.*ticket" --include="*.tsx" --include="*.ts"

# <Link> components
grep -rn "<Link.*href=.*ticket" --include="*.tsx"

# useRouter hook
grep -rn "useRouter" --include="*.tsx"
```

**Vue Router:**
```bash
# router.push
grep -rn "router\.push\(.*ticket\|\$router\.push\(.*ticket" --include="*.vue" --include="*.ts"

# <router-link>
grep -rn "<router-link.*to=.*ticket" --include="*.vue"

# programmatic navigation
grep -rn "this\.\$router" --include="*.vue"
```

**Angular:**
```bash
# routerLink directive
grep -rn "routerLink=.*ticket\|\[routerLink\].*ticket" --include="*.html" --include="*.ts"

# router.navigate
grep -rn "router\.navigate\(.*ticket\|this\.router\.navigate" --include="*.ts"
```

**Generic (all frameworks):**
```bash
# Direct href
grep -rn "href=.*ticket" --include="*.tsx" --include="*.html" --include="*.vue"

# window.location
grep -rn "window\.location.*ticket\|window\.open\(.*ticket" --include="*.tsx" --include="*.ts"

# target="_blank" (opens in new tab)
grep -rn "target=\"_blank\".*ticket" --include="*.tsx"
```

### Step 3: Identify Source Pages

For each grep hit:
1. **Note the file path** — which component/page contains this navigation call?
2. **Determine the route** — which page is this component rendered on?
3. **Check the trigger** — button, card, link, menu item, keyboard shortcut?

Example:
```tsx
// File: src/pages/Dashboard/index.tsx
<Card onClick={() => navigate(`/ticket/${ticketId}`)}>
  {/* ... */}
</Card>

// File: src/components/Sidebar/index.tsx
<Link to={`/ticket/${id}`}>View Ticket</Link>

// File: src/pages/ProjectList/index.tsx
<Button onClick={() => router.push(`/ticket/${ticket.id}`)}>
  Open
</Button>
```

**Result:** 3 entry points found:
- Dashboard → Ticket (via card click)
- Sidebar → Ticket (via link)
- Project List → Ticket (via button)

### Step 4: Classify as Separate Flows or Not

| Pattern | Separate Flow? | Why |
|---------|----------------|-----|
| Different source pages with different preceding steps | **YES** | User navigates through different pages to get there |
| Same source page, different trigger components (sidebar vs card vs button) | **NO** — same flow, different UI trigger | All start from the same page |
| Dashboard shortcut that skips listing page | **YES** | Different page sequence (1 page vs 2 pages) |
| Breadcrumb / back navigation | **NO** | Return path, not a forward flow |
| Deep link / direct URL entry | **YES** — if page behaves differently | Different entry context (no prior state) |
| Context menu vs toolbar button | **NO** | Same source page, same destination |
| Keyboard shortcut vs mouse click | **NO** | Same logical flow, different input method |

### Step 5: Check if Target Page Behaves Differently Per Entry Point

Grep the target page for entry-context patterns:

```bash
# Check for entry context usage
grep -rn "location\.state\|from\|source\|returnUrl\|referrer" src/pages/Ticket/

# Check for query parameter usage
grep -rn "searchParams\|useSearchParams\|query\|URLSearchParams" src/pages/Ticket/

# Check for navigation state
grep -rn "useLocation\|props\.location" src/pages/Ticket/
```

**If YES** (page reads where user came from and renders differently):
→ Confirms separate flows — different entry contexts produce different UIs

**If NO** (page renders identically regardless of entry):
→ Entry points share the same flow — different ways to reach the same destination don't create different flows

### Example: Entry-Point Classification

**Scenario:** "View Ticket Details"

**Grep results:**
```
src/pages/Dashboard/NotificationCard.tsx:42:  navigate(`/ticket/${id}`)
src/pages/Dashboard/RecentTickets.tsx:28:     navigate(`/ticket/${id}`)
src/pages/Projects/TicketList.tsx:156:        navigate(`/ticket/${id}`)
src/components/Sidebar/QuickLinks.tsx:19:     <Link to={`/ticket/${id}`}>
```

**Analysis:**
- Dashboard (2 components) → Ticket — **1 flow** (same source page)
- Project Ticket List → Ticket — **2nd flow** (different source, user was browsing project tickets)
- Sidebar Quick Links → Ticket — **Same as Dashboard** (sidebar is global, doesn't change page sequence)

**Final:** 2 entry-point flows
1. "Dashboard to Ticket Details"
2. "Project List to Ticket Details"

---

## Type B: On-Page Flow Discovery

### Step 1: Grep Target Page for Branching Patterns

**Conditional Rendering:**
```bash
# Ternaries (most common)
grep -rn "?\s*<\|:\s*<" src/pages/TargetPage/ --include="*.tsx"

# Logical AND short-circuit
grep -rn "&&\s*<" src/pages/TargetPage/ --include="*.tsx"

# if/else rendering
grep -rn "if\s*\(" src/pages/TargetPage/ --include="*.tsx"
```

**Tab/Stepper Variants:**
```bash
grep -rn "<Tab\|<Tabs\|<Stepper\|<Step\|activeStep\|activeTab\|TabPanel\|TabList" src/pages/TargetPage/
```

**Auth Method Switches:**
```bash
grep -rn "authMethod\|loginType\|signInWith\|provider\|OAuth\|SSO\|socialLogin\|loginWith" src/pages/TargetPage/
```

**Feature Flags / Mode Toggles:**
```bash
grep -rn "isAdvanced\|viewMode\|editMode\|quickMode\|expressMode\|isBulk\|batchMode\|featureFlag" src/pages/TargetPage/
```

**Modal vs Page Alternatives:**
```bash
grep -rn "openModal\|showDrawer\|useDisclosure\|isInline\|isFullPage\|showDialog" src/pages/TargetPage/
```

**Error State Routing:**
```bash
grep -rn "error\?\.status\|statusCode\|404\|401\|403\|NotFound\|Unauthorized" src/pages/TargetPage/
```

**Template/Layout Switching:**
```bash
grep -rn "template\|layout\|variant\|mode\|type.*==\|switch\s*\(" src/pages/TargetPage/
```

### Step 2: Read and Classify Each Pattern

| Pattern Found | Separate Flow? | Example |
|---------------|----------------|---------|
| **Ternary with different component trees** | **YES** | `isOAuth ? <SocialAuth/> : <EmailForm/>` |
| **Tab group with distinct workflows** | **YES** | `<Tab label="Import CSV">` / `<Tab label="Manual Entry">` |
| **Auth method switch** | **YES** | `method === 'email' ? <EmailLogin/> : <GoogleLogin/>` |
| **Wizard express/skip mode** | **YES** | `quickMode ? skipToStep3() : showAllSteps()` |
| **Modal vs full-page** | **YES** | `isInline ? <InlineEditor/> : navigate("/edit")` |
| **Bulk vs single operation** | **YES** | `isBulk ? <BulkConfirm/> : <SingleConfirm/>` |
| **Error state redirect** | **YES** | `status === 404 ? <NotFound/> : <Content/>` |
| **Template registry switch** | **YES** | `templates[type] ?? <DefaultTemplate/>` |
| **Show/hide optional fields** | **NO** | `showAdvanced && <AdvancedOptions/>` — same flow, expanded UI |
| **Loading/error states** | **NO** | `isLoading ? <Spinner/> : <Content/>` — temporary state |
| **Permission-gated sections** | **NO** | `canEdit && <EditButton/>` — same page, conditional permissions |
| **Responsive layout switches** | **NO** | `isMobile ? <MobileLayout/> : <DesktopLayout/>` — handled by modality, not separate flow |
| **Collapsed/expanded sections** | **NO** | `isExpanded ? <FullView/> : <Summary/>` — same data, different display |

### Decision Tree: Is This a Separate Flow?

```
Does the pattern create different component trees?
├─ NO → Not a separate flow
└─ YES → Does it represent a different user workflow?
    ├─ NO (just UI variation) → Not a separate flow
    └─ YES → Separate flow
        └─ Does it span different pages or just swap components?
            ├─ Just swap components → Single-page flow variant
            └─ Different pages → Multi-page flow variant
```

### Example: On-Page Classification

**Scenario:** "User Registration"

**Grep results in `src/pages/Register/index.tsx`:**

```tsx
// Pattern 1: Auth method switch
{authMethod === 'email' ? (
  <EmailRegistrationForm onSubmit={handleEmailSubmit} />
) : (
  <SocialAuthPanel providers={['google', 'github']} />
)}

// Pattern 2: Show/hide terms acceptance
{showTerms && <TermsCheckbox />}

// Pattern 3: Loading state
{isSubmitting ? <LoadingOverlay /> : null}

// Pattern 4: Error display
{error && <ErrorMessage text={error} />}
```

**Classification:**
- Pattern 1: **YES** — separate flow ("Email Registration" vs "Social Registration")
- Pattern 2: **NO** — optional field, same flow
- Pattern 3: **NO** — temporary state, same flow
- Pattern 4: **NO** — error feedback, same flow

**Final:** 2 on-page flows
1. "Email Registration"
2. "Social Registration"

---

## Multi-Page Flow Detection

### Step 1: Grep Each Page for Outbound Navigation

For every page identified in the flow, check if it navigates to another page:

```bash
# React Router
grep -rn "navigate\(\|<Link\|to=\|href=" src/pages/TargetPage/ --include="*.tsx"

# Next.js
grep -rn "router\.push\|router\.replace\|<Link.*href" src/pages/TargetPage/

# Vue
grep -rn "router\.push\|\$router\.push\|<router-link" src/pages/TargetPage/

# target="_blank" (opens new tab = separate page)
grep -rn "target=\"_blank\"\|window\.open" src/pages/TargetPage/
```

### Step 2: Classify Multi-Page Patterns

| Pattern | Pages in Flow | Example |
|---------|---------------|---------|
| **Form → Confirmation** | 2 pages | Registration form → Email verification page |
| **List → Detail** | 2 pages | Project list → Project detail page |
| **Wizard / Stepper** | 3+ pages | Account setup Step 1 → Step 2 → Step 3 |
| **Deep link target="_blank"** | 2 pages (separate tabs) | Notification → Project detail (opens in new tab) |
| **Settings → Sub-page** | 2 pages | Settings page → Change password page |
| **Error redirect** | 1 page (replaced) | API returns 404 → render NotFound component |
| **Single-page interactions** | 1 page | Filter, select, scroll — no navigation |

### Step 3: Follow Navigation Chains

**Example:** Registration Flow

**Page 1:** `/register`
```tsx
// src/pages/Register/index.tsx
<form onSubmit={() => {
  await api.register(data)
  navigate('/verify-email')  // ← Outbound navigation found
}}>
```

**Page 2:** `/verify-email`
```tsx
// src/pages/VerifyEmail/index.tsx
<Button onClick={() => {
  await api.verify(code)
  navigate('/dashboard')  // ← Second outbound navigation found
}}>
```

**Result:** 3-page flow
1. Registration Form
2. Email Verification
3. Dashboard (final destination)

---

## Combining Type A + Type B + Multi-Page

### Example: "Generate User Stories" Scenario

**Step 1: Type A Discovery** (entry points)

Grep for `navigate('/user-stories/generate')`:
```
src/pages/Dashboard/QuickActions.tsx:     navigate('/user-stories/generate')
src/pages/Projects/Detail/Toolbar.tsx:    navigate('/user-stories/generate')
src/components/TopNav/Menu.tsx:           navigate('/user-stories/generate')
```

**Entry points found:**
- Dashboard → Generate (shortcut button)
- Project Detail → Generate (toolbar action)
- Top Nav → Generate (menu item)

**Classification:**
- Dashboard vs Project Detail = **different source pages** → 2 entry-point flows
- Top Nav = global, doesn't change page sequence → merge with Dashboard

**Type A Result:** 2 entry-point flows

---

**Step 2: Type B Discovery** (on-page branching)

Grep `/user-stories/generate` page for conditionals:

```tsx
// src/pages/UserStories/Generate/index.tsx

// Pattern 1: Input method choice
{inputMode === 'manual' ? (
  <ManualEntryForm />
) : inputMode === 'csv' ? (
  <CSVImportPanel />
) : (
  <AIGeneratePanel />
)}

// Pattern 2: Bulk vs single
{isBulk && <BulkPreviewTable />}
{!isBulk && <SingleStoryEditor />}
```

**Classification:**
- Pattern 1: **YES** — 3 distinct input methods
  - Manual entry
  - CSV import
  - AI generate
- Pattern 2: **YES** — bulk vs single (but conditional, not always shown)

**Type B Result:** 3 input method flows

---

**Step 3: Multi-Page Detection**

Grep each page variant for navigation:

```tsx
// Manual entry → navigates to review page
<Button onClick={() => navigate('/user-stories/review')}>

// CSV import → navigates to review page
<Button onClick={() => navigate('/user-stories/review')}>

// AI generate → navigates to review page
<Button onClick={() => navigate('/user-stories/review')}>
```

**Multi-Page Result:** All 3 paths navigate to `/user-stories/review` → 2 pages per flow

---

**Step 4: Combine All**

**Entry Points (Type A):** 2
1. Dashboard → Generate
2. Project Detail → Generate

**On-Page Variants (Type B):** 3
1. Manual Entry
2. CSV Import
3. AI Generate

**Pages per variant:** 2 (Generate page → Review page)

**Final Flow Count:** 2 × 3 = **6 flows**

| Flow Name | Entry | Variant | Pages |
|-----------|-------|---------|-------|
| Generate User Stories via Dashboard - Manual | Dashboard | Manual | 2 |
| Generate User Stories via Dashboard - CSV | Dashboard | CSV | 2 |
| Generate User Stories via Dashboard - AI | Dashboard | AI | 2 |
| Generate User Stories via Project Detail - Manual | Project Detail | Manual | 2 |
| Generate User Stories via Project Detail - CSV | Project Detail | CSV | 2 |
| Generate User Stories via Project Detail - AI | Project Detail | AI | 2 |

**Per Modality:** If user selected web + mobile → 6 × 2 = **12 flows total**

---

## Common Edge Cases

### Responsive Layouts
```tsx
{isMobile ? <MobileNav /> : <DesktopNav />}
```
**NOT a separate flow** — handled by modality selection, not flow discovery.

### Loading States
```tsx
{isLoading ? <Skeleton /> : <Content />}
```
**NOT a separate flow** — temporary UI state.

### Permission Gates
```tsx
{user.role === 'admin' && <AdminPanel />}
```
**NOT a separate flow** — same page, conditional visibility based on role.

### Error States
```tsx
{error?.status === 404 ? <NotFoundPage /> : <Content />}
```
**IS a separate flow** — 404 path leads to a completely different page/component tree.

### Feature Flags
```tsx
{featureFlags.newEditor ? <NewEditor /> : <LegacyEditor />}
```
**IS a separate flow** — different implementations of the same feature.

### A/B Testing
```tsx
{experiment.variant === 'A' ? <VariantA /> : <VariantB />}
```
**IS a separate flow** — distinct user experiences being tested.

### Tabs on a Detail Page
```tsx
<Tabs>
  <Tab label="Overview"><OverviewPanel /></Tab>
  <Tab label="Settings"><SettingsPanel /></Tab>
  <Tab label="History"><HistoryPanel /></Tab>
</Tabs>
```
**NOT separate flows** — tabs are navigation within the same page. Treat as a single page with multiple sections.

---

## Framework-Specific Patterns

### React Router v6
```tsx
// Declarative navigation
<Link to="/path">...</Link>
<NavLink to="/path">...</NavLink>

// Programmatic navigation
const navigate = useNavigate()
navigate('/path')
navigate(-1)  // back

// With state
navigate('/path', { state: { from: 'dashboard' } })
```

### Next.js
```tsx
// Link component
<Link href="/path">...</Link>

// Programmatic
const router = useRouter()
router.push('/path')
router.replace('/path')

// With query params
router.push({ pathname: '/path', query: { id: 1 } })
```

### Vue Router
```vue
<!-- Template -->
<router-link to="/path">...</router-link>

<script>
// Programmatic
this.$router.push('/path')
this.$router.push({ name: 'RouteName', params: { id: 1 } })

// Composition API
const router = useRouter()
router.push('/path')
</script>
```

### Angular
```typescript
// Template
<a routerLink="/path">...</a>
<a [routerLink]="['/path', id]">...</a>

// Programmatic
constructor(private router: Router) {}
this.router.navigate(['/path'])
this.router.navigateByUrl('/path')
```

---

## Output Format: Flow Discovery Evidence Block

For each scenario, produce this block BEFORE proceeding to Step 4:

```
┌─── FLOW DISCOVERY EVIDENCE: "Scenario Name" ───┐
│                                                   │
│ TARGET ROUTE: /user-stories/generate              │
│ TARGET FILES: src/pages/UserStories/Generate/    │
│                                                   │
│ TYPE A GREPS (entry-point flows):                 │
│   grep command: grep -rn "navigate.*user-stories/generate" --include="*.tsx"
│   hits: 3 results                                 │
│   entry points found:                             │
│     1. Dashboard/QuickActions.tsx → /generate     │
│     2. Projects/Detail/Toolbar.tsx → /generate    │
│     3. TopNav/Menu.tsx → /generate (global)       │
│   classification: 2 distinct flows (Dashboard, Project Detail)
│                                                   │
│ TYPE B GREPS (on-page branching):                 │
│   grep command: grep -rn "?\s*<\|:\s*<" src/pages/UserStories/Generate/
│   hits: 8 results                                 │
│   branching patterns found:                       │
│     1. inputMode ternary → YES (3 variants: manual/csv/ai)
│     2. isBulk conditional → NO (optional display, same flow)
│   classification: 3 additional flows (input methods)
│                                                   │
│ PAGE NAV GREPS (multi-page detection):            │
│   grep command: grep -rn "navigate\|<Link" src/pages/UserStories/Generate/
│   hits: 3 results                                 │
│   outbound links found:                           │
│     1. /user-stories/review (all 3 variants)      │
│   classification: 2 pages per flow                │
│                                                   │
│ FINAL: 6 flows (2 entry × 3 variants), 2 pages   │
│ EVIDENCE: grep-confirmed                          │
└───────────────────────────────────────────────────┘
```

---

## Quick Reference: Decision Matrix

| Question | Answer → Result |
|----------|-----------------|
| **Do multiple pages navigate TO this target?** | YES → Type A flows (check if different page sequences) |
| **Does the target page have ternaries/tabs?** | YES → Type B flows (check if different component trees) |
| **Does this page navigate to ANOTHER page?** | YES → Multi-page flow (follow the chain) |
| **Are responsive layouts involved?** | Use modality selection, not separate flows |
| **Are there loading/error states?** | Not separate flows (temporary UI states) |
| **Are there permission gates?** | Not separate flows (conditional visibility) |
| **Is there A/B testing or feature flags?** | Separate flows (distinct user experiences) |

---

## Performance Tips

### Cache Grep Results
Many scenarios share the same target pages. Cache grep results per route:
```
routeGrepCache = {
  '/ticket/:id': { entryPoints: [...], patterns: [...] }
}
```

### Parallelize Greps
Type A, Type B, and page nav greps are independent — run them in parallel:
```
await Promise.all([
  grepTypeA(route),
  grepTypeB(targetPage),
  grepPageNav(targetPage)
])
```

### Use Citations First
If the outcome has citations, read those files directly instead of grepping. Faster and more accurate.
