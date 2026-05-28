# Phase 34 — Dashboard UI Redesign (Premium Shell + Responsive Navigation)

## Goal

Redesign the React Dashboard (`apps/dashboard`) with a premium, production-grade
UI following Vercel/Stripe design principles.  Replace the current top-navigation
layout with a persistent collapsible sidebar on desktop and a bottom tab bar on
mobile.  Establish a shared design-token layer (CSS custom properties) and a
small set of reusable shell components so every existing and future page inherits
the new chrome with zero per-page layout work.

The redesign is **additive to functionality** — all routes, API clients, and data
contracts from Phases 12–14 and 33 remain unchanged.

---

## Design Principles

| Principle | Implementation rule |
|---|---|
| Neutral foundation | Background `#0a0a0a` (near-black), surface `#111111`, border `#1f1f1f` |
| Single accent | `#6366f1` (indigo-500) for primary actions, active states, and focus rings |
| Typographic clarity | Inter variable font; size scale 11 / 12 / 13 / 14 / 16 / 20 / 24 / 32 px |
| Breathing room | Consistent 16 / 24 / 32 px spacing rhythm; no content touches viewport edges |
| Motion restraint | Transitions ≤ 150 ms ease-out for hovers; ≤ 250 ms for panels; no decorative animations |
| Accessible contrast | All text ≥ 4.5:1 on its background (WCAG AA); interactive targets ≥ 44 × 44 px on mobile |

---

## Breakpoint System

| Name | Range | Layout |
|---|---|---|
| `mobile` | 0 – 639 px | Bottom tab bar; single-column content; collapsible sections |
| `tablet` | 640 – 1023 px | Bottom tab bar; content grid max 2 columns |
| `desktop-sm` | 1024 – 1279 px | Sidebar collapsed (icon-only, 56 px); content fills remaining width |
| `desktop-lg` | ≥ 1280 px | Sidebar expanded (232 px); content area has max-width guard (1200 px) |

The sidebar collapse state persists in `localStorage` under the key
`remediai.sidebar.collapsed`.

---

## Stack Additions

| Package | Purpose |
|---|---|
| `lucide-react` | Icon set (consistent 16 / 20 px strokes) |
| `@radix-ui/react-tooltip` | Accessible sidebar icon tooltips in collapsed mode |
| `@radix-ui/react-dialog` | Mobile drawers and confirmation modals |
| `@radix-ui/react-dropdown-menu` | Context menus and overflow actions |

All Radix primitives are unstyled — Tailwind classes provide all visual styles.
No additional UI kit or component library is introduced.

---

## Design Tokens (`src/styles/tokens.css`)

Define as CSS custom properties on `:root`.  Tailwind config extends these via
`var(--token-name)` so token values can be overridden in a future theme switch
without touching component classes.

```
--color-bg:          #0a0a0a
--color-surface:     #111111
--color-surface-2:   #161616
--color-border:      #1f1f1f
--color-border-2:    #2a2a2a
--color-accent:      #6366f1
--color-accent-hover:#818cf8
--color-text-1:      #f5f5f5   /* primary text   */
--color-text-2:      #a1a1aa   /* secondary text  */
--color-text-3:      #52525b   /* disabled / hint */
--color-success:     #22c55e
--color-warning:     #f59e0b
--color-error:       #ef4444
--color-critical:    #dc2626
--color-high:        #f97316
--color-medium:      #facc15
--color-low:         #4ade80
--radius-sm:         4px
--radius-md:         6px
--radius-lg:         10px
--shadow-sm:         0 1px 3px rgba(0,0,0,.5)
--shadow-md:         0 4px 12px rgba(0,0,0,.6)
```

---

## File Layout

```
apps/dashboard/src/
  styles/
    tokens.css              # CSS custom properties (imported in index.css)
  components/
    shell/
      AppShell.tsx          # root layout: sidebar + main slot
      Sidebar.tsx           # desktop persistent nav (expanded / icon-only)
      BottomTabBar.tsx      # mobile / tablet bottom nav
      TopBar.tsx            # mobile page header (title + back + overflow)
      NavItem.tsx           # shared nav link (used by Sidebar and BottomTabBar)
    ui/
      Badge.tsx             # replaces PriorityBadge + StatusBadge (unified variant API)
      Button.tsx            # primary / ghost / destructive variants
      Card.tsx              # surface card with optional header slot
      DataTable.tsx         # sortable, responsive table with skeleton rows
      EmptyState.tsx        # icon + heading + optional CTA
      PageHeader.tsx        # title + breadcrumb + right-side action slot
      SkeletonBlock.tsx     # generic shimmer placeholder
      StatCard.tsx          # metric tile (value / label / trend arrow)
      Toast.tsx             # success / warning / error toast (Radix portal)
      ToastProvider.tsx     # context + queue manager
    AppErrorFallback.tsx    # (unchanged)
    Layout.tsx              # thin wrapper — renders <AppShell> + <Outlet>
```

Existing `PriorityBadge.tsx` and `StatusBadge.tsx` are replaced by `Badge.tsx`
with a `variant` prop (`priority-critical | priority-high | priority-medium |
priority-low | status-open | status-triaged | status-resolved | ...`).

---

## AppShell Layout Contract

```
<AppShell>
  ├── <Sidebar />          hidden on mobile/tablet via CSS (display:none < 1024px)
  ├── <BottomTabBar />     hidden on desktop via CSS (display:none ≥ 1024px)
  └── <main>
        ├── <TopBar />     mobile-only page title bar (hidden ≥ 1024px)
        └── {children}     page content
```

`AppShell` applies the following CSS grid on desktop:

```css
display: grid;
grid-template-columns: var(--sidebar-width, 232px) 1fr;
min-height: 100dvh;
```

`--sidebar-width` is `56px` when collapsed, `232px` when expanded.  The
transition on `grid-template-columns` is `200ms ease-out`.

On mobile the grid drops to a single column and `padding-bottom: 64px` is
applied to `<main>` so content is never obscured by the bottom tab bar.

---

## Sidebar Component

### Structure

```
┌──────────────────────────────┐
│  [Logo]  RemediAI            │  ← brand section (hidden when collapsed; icon only)
│  ──────────────────────────  │
│  [Bug]   Incidents           │  ← primary nav
│  [BarChart] Metrics          │
│  [Server]  Targets           │
│  [FileText] Logs             │
│                              │
│  (flex-grow spacer)          │
│  ──────────────────────────  │
│  [Settings] Settings  (future)│  ← secondary nav
│  [ChevronLeft] Collapse      │  ← collapse toggle
└──────────────────────────────┘
```

### Behavior

- Active nav item: `background: var(--color-surface-2)`, left border
  `3px solid var(--color-accent)`, text `var(--color-text-1)`.
- Inactive: text `var(--color-text-2)`, no border; hover lifts to
  `var(--color-surface-2)`.
- Collapsed state shows icons only (20 px Lucide), centered in 56 px column.
  Each icon has a Radix Tooltip showing the label on hover.
- Collapse toggle button sits at the bottom of the sidebar; chevron rotates
  180 ° when collapsed.
- On `desktop-sm` (1024–1279 px) the sidebar defaults to collapsed unless
  the user has explicitly expanded it (persisted state).

---

## BottomTabBar Component

Shown only on `mobile` and `tablet` (< 1024 px).

```
┌─────────────────────────────────────────────┐
│  [Bug]        [BarChart]  [Server]  [FileText] │
│ Incidents     Metrics     Targets    Logs     │
└─────────────────────────────────────────────┘
```

- Fixed position, bottom 0, full width, height 64 px.
- Background `var(--color-surface)`, top border `1px solid var(--color-border)`.
- Backdrop blur `blur(12px)` with `background-color` at 90 % opacity for
  scroll-through legibility.
- Active item: icon + label in `var(--color-accent)`.
- Safe-area padding applied via `padding-bottom: env(safe-area-inset-bottom)`
  for iOS notch devices.
- Max 4 items visible.  If more routes are added, the 4th slot becomes a
  "More" item that opens a Radix Dialog drawer listing the overflow routes.

---

## TopBar Component (mobile page header)

Shown only on `mobile` and `tablet` (< 1024 px).

- Sticky, height 56 px, `z-index: 40`.
- Left slot: back chevron (rendered only on detail pages; clicking calls
  `navigate(-1)`).
- Center slot: current page title (string injected via `TopBarContext`).
- Right slot: overflow menu trigger (page-specific actions injected via context).
- Background matches `var(--color-surface)` with `border-bottom`.

Pages set their TopBar title and actions by calling `useTopBar({ title, actions })`
inside their component body.  `AppShell` consumes the context to render `TopBar`.

---

## PageHeader Component (desktop)

Shown only on desktop (≥ 1024 px), rendered at the top of each page's content area.

- Props: `title`, `breadcrumb?: BreadcrumbItem[]`, `actions?: ReactNode`.
- Breadcrumb renders as `Home / Section / Page` with `/` separators.
- Actions slot is right-aligned and accepts any `ReactNode` (buttons, dropdowns).

---

## Per-Page Responsive Behaviour

### Incident List (`/incidents`)

| Breakpoint | Layout |
|---|---|
| Mobile | Single-column card list (one card per incident); filters hidden behind a "Filter" button that opens a bottom sheet |
| Tablet | Same card list; filters shown inline in a horizontal scroll strip |
| Desktop | Full data table with all columns; filter dropdowns inline in table toolbar |

Each mobile/tablet incident card shows: exception type (bold), truncated message,
priority badge, status badge, relative timestamp, and a chevron-right icon.

### Incident Detail (`/incidents/:id`)

| Breakpoint | Layout |
|---|---|
| Mobile | Stacked single-column sections; collapsible `<details>` for stack trace and agent trace |
| Desktop | Two-column grid: left 60 % root cause + recommendations; right 40 % metadata, work items, agent trace |

### Metrics (`/metrics`)

| Breakpoint | Layout |
|---|---|
| Mobile | Stat cards stacked 1-up; charts full-width stacked vertically |
| Tablet | Stat cards 2-up grid; charts side-by-side |
| Desktop | Stat cards 3-up; charts side-by-side; top-errors table below |

### Targets (`/targets`)

| Breakpoint | Layout |
|---|---|
| Mobile | Single column; discovered pane collapses above selected pane; save button sticky at bottom |
| Desktop | Two-column split pane (unchanged from Phase 33 functionality) |

### Local Logs (`/logs`)

| Breakpoint | Layout |
|---|---|
| Mobile | Full-width log feed; filter bar scrolls horizontally |
| Desktop | Unchanged layout, inherits new typography and token colours |

---

## Loading and Empty States

- Every data-driven section renders `<SkeletonBlock>` rows during the initial
  `isLoading` query state.  Skeleton dimensions match the real content geometry
  so there is no layout shift on load.
- Empty states use `<EmptyState>` with a Lucide icon, a heading, an optional
  sub-text, and an optional CTA button.  Specific copy:
  - No incidents: icon `Inbox`, heading "No incidents yet", sub "Incidents appear
    here once the log bridge starts forwarding exceptions."
  - No targets configured: icon `ServerOff`, heading "No targets enabled",
    sub "Enable at least one target to start receiving incidents."
  - Metrics with zero data: icon `BarChart2`, heading "No data in range."

---

## Toast Notification System

- `<ToastProvider>` wraps the app in `App.tsx` and exposes `useToast()` hook.
- API: `toast.success(message)`, `toast.error(message)`, `toast.warning(message)`.
- Toasts render in a Radix portal, stacked bottom-right on desktop,
  bottom-center full-width on mobile.
- Auto-dismiss after 4 s; manual dismiss via × button.
- Used by: target save action, any mutation that can fail.

---

## Security Touchpoints

- New LLM call introduced? **No.**
- Agent decision written? **No.**
- New credential introduced? **No.**
- New HTTP endpoint introduced? **No.**
- XSS risk: all incident content (exception messages, stack traces) is rendered
  inside `<pre>` or text nodes — never with `dangerouslySetInnerHTML`.
- External links (work item URLs) must use `rel="noopener noreferrer"` and
  `target="_blank"`.

---

## Deliverables

| Artifact | Description |
|---|---|
| `src/styles/tokens.css` | CSS custom property definitions |
| `src/components/shell/AppShell.tsx` | Root grid layout |
| `src/components/shell/Sidebar.tsx` | Desktop persistent sidebar with collapse |
| `src/components/shell/BottomTabBar.tsx` | Mobile/tablet bottom navigation |
| `src/components/shell/TopBar.tsx` | Mobile sticky page header |
| `src/components/shell/NavItem.tsx` | Shared nav link primitive |
| `src/components/ui/Badge.tsx` | Unified priority + status badge |
| `src/components/ui/Button.tsx` | Primary / ghost / destructive button |
| `src/components/ui/Card.tsx` | Surface card shell |
| `src/components/ui/DataTable.tsx` | Responsive table with skeleton state |
| `src/components/ui/EmptyState.tsx` | Icon + heading + CTA empty template |
| `src/components/ui/PageHeader.tsx` | Desktop page title + breadcrumb + actions |
| `src/components/ui/SkeletonBlock.tsx` | Shimmer loader block |
| `src/components/ui/StatCard.tsx` | Metric tile |
| `src/components/ui/Toast.tsx` + `ToastProvider.tsx` | Toast notification system |
| Updated `src/components/Layout.tsx` | Renders `<AppShell>` + `<Outlet>` |
| Updated `src/pages/IncidentList.tsx` | Mobile card list + desktop table |
| Updated `src/pages/IncidentDetail.tsx` | Two-column desktop / stacked mobile |
| Updated `src/pages/MetricsPage.tsx` | Responsive stat grid + charts |
| Updated `src/pages/TargetsPage.tsx` | Mobile single-column / desktop split |
| Updated `src/pages/LocalLogsPage.tsx` | Token colours + responsive filter bar |
| Updated `tailwind.config.js` | Extend with token references and breakpoints |
| Updated `package.json` | Add `lucide-react`, `@radix-ui/react-tooltip`, `@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu` |

---

## Acceptance Criteria

- `tsc --noEmit` reports zero errors across the dashboard package.
- `npm run build` produces a clean Vite bundle with no size regression > 20 %.
- Sidebar is visible and functional on all desktop viewports ≥ 1024 px.
- Bottom tab bar is visible and functional on all viewports < 1024 px.
- Sidebar collapse state persists across page refresh via `localStorage`.
- Active route is visually highlighted in both sidebar and bottom tab bar.
- All pages render without horizontal scroll on a 375 px (iPhone SE) viewport.
- All pages render without horizontal scroll on a 768 px (iPad) viewport.
- Incident list shows card layout on mobile and table layout on desktop.
- Incident detail shows two-column layout on desktop ≥ 1024 px.
- Metrics page stat cards are 1-up on mobile, 2-up on tablet, 3-up on desktop.
- Empty states render when API returns zero items.
- Skeleton loaders render during `isLoading` on every data-driven page.
- Toast success renders after saving target selection.
- All external links use `rel="noopener noreferrer"`.
- No `dangerouslySetInnerHTML` usage in any new or modified component.
- Colour contrast ≥ 4.5:1 verified for primary text on all surface colours.
- iOS safe-area inset applied to bottom tab bar on viewport simulation.

---

## Out of Scope

- Dark/light theme toggle (tokens layer makes this straightforward to add in a
  follow-up phase).
- Animations beyond the specified transition durations.
- Storybook or component documentation site.
- Keyboard shortcut navigation.
- Any changes to backend API contracts, agents, or data models.
