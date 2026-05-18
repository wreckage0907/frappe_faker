# Frappe Faker — Frontend UI Implementation Plan

## Context

The backend (Phase 1 of PLAN.md) is fully implemented: meta analyzer, dependency graph, AI generator, record inserter, and the API layer (`enqueue_generation`, `get_job_status`, `generate_sync`). The Vue 3 frontend was scaffolded in the last commit but `Home.vue` is still the starter template. This plan builds the actual generator UI in three phases — Phase 1 is immediately usable end-to-end, Phases 2 and 3 add depth and polish without breaking anything.

---

## Stack & Constraints

- **Vue 3** + **frappe-ui 0.1.192** — no external UI libraries
- App served at `/frontend`, proxied to Frappe on port 8080
- Auth/session flow (`Login.vue`, `data/session.js`) stays unchanged
- All API calls use `call` (imperative) or `createResource` (declarative) from `frappe-ui`

---

## Phase 1 — Core Generator (MVP)

**Goal**: User picks a DocType, sets a count, hits Generate, watches polling, sees results. Fully usable end-to-end.

### Backend additions — `frappe_faker/api/generate.py`

Add one new whitelisted method:

```python
@frappe.whitelist()
def get_faker_settings() -> dict[str, Any]:
    _require_system_manager()
    settings = frappe.get_single("Faker Settings")
    return {
        "default_count": int(settings.default_count or 10),
        "provider": settings.ai_provider or "",
        "model_name": settings.model_name or "",
    }
```

### Frontend files

| File | Action |
|------|--------|
| `src/App.vue` | Wrap `<router-view>` in `<FrappeUIProvider>` (enables toasts) |
| `src/main.js` | Register additional global components (see below) |
| `src/pages/Home.vue` | Replace entirely — orchestrator page |
| `src/composables/useGeneration.js` | New — all polling + job state |
| `src/components/DocTypeSelector.vue` | New — debounced autocomplete |
| `src/components/GenerateForm.vue` | New — config panel |
| `src/components/JobProgress.vue` | New — polling progress view |
| `src/components/ResultsSummary.vue` | New — results view |

### Additional global components to register in `main.js`

```js
Spinner, Autocomplete, Badge, Switch, Textarea, Progress,
Divider, Alert, Tooltip, MultiSelect, ListView,
Sidebar, SidebarItem, SidebarHeader, SidebarSection, FrappeUIProvider
```

---

### `useGeneration.js` — composable (core of Phase 1)

State: `phase` (`idle | generating | done | error`), `jobId`, `jobStatus`, `result`, `error`

```
startGeneration(params):
  → sets phase='generating', calls enqueue_generation
  → on success: stores job_id, starts setInterval(pollOnce, 2000)
  → on API error: phase='error', error=message

pollOnce():
  → calls get_job_status(job_id)
  → 'finished' → result=resp.result, phase='done', stopPolling(), toast.success(...)
  → 'failed'   → error=resp.exc, phase='error', stopPolling(), toast.error(...)
  → 'not_found'→ error='Job not found', phase='error', stopPolling()
  → network error: increment failCount; after 3 consecutive → phase='error'

stopPolling(): clears interval
reset(): back to idle, clears all state
onUnmounted: stopPolling() (prevents memory leaks)
```

Use raw `call` from `frappe-ui` (not `createResource`) — imperative polling is cleaner than reactive.

---

### `DocTypeSelector.vue`

- **Component**: `Autocomplete` from frappe-ui
- Queries `frappe.client.get_list("DocType", { fields: ["name"], filters: [["name","like","%<query>%"]], limit: 20 })` with 300ms debounce
- Props: `modelValue: String` | Emits: `update:modelValue`

---

### `GenerateForm.vue`

frappe-ui components: `FormControl` + `TextInput` (count), `Switch` (×2), `Textarea` (instructions), `Button`, `Alert`

- On mount: `createResource({ url: 'frappe_faker.api.generate.get_faker_settings', auto: true })` → prefills count
- "Advanced Options" chevron toggle reveals: custom instructions `Textarea`, `fast_insert` Switch, `resolve_deps` Switch
- Generate `Button` disabled when no doctype; shows built-in `:loading` spinner while `phase === 'generating'`
- If `provider` is empty in settings response: `Alert theme="yellow"` "No AI provider configured — go to Settings"

---

### `JobProgress.vue`

frappe-ui components: `Progress`, `Badge`, `Spinner`, `Alert`

- **Fake progress bar**: local `fakeProgress` ref increments ~0.5% every 500ms (capped at 90%), jumps to 100 on finish. No real server-side percentage available.
- Status badge colors: `queued`=gray, `started`=blue
- After 40 seconds in `queued`: `Alert theme="yellow"` "Background worker may be busy"
- After 3 minutes: `Alert theme="blue"` "Large batch — safe to close page, generation continues server-side"
- "Cancel" plain-text button → `generation.reset()` (does NOT cancel server job; note shown)

---

### `ResultsSummary.vue`

frappe-ui components: `Badge`, `FeatherIcon`, `Alert`, `Divider`, `Button`

- **Header**: FeatherIcon `check-circle` green + "Generated N records for [DocType]". If `total_failed > 0`: red Badge "N failed"
- **Per-doctype rows**: DocType name | green Badge (created) | red Badge (failed, hidden if 0) | FeatherIcon `alert-circle` with Tooltip if `result.error` exists
- **Expandable errors**: click row → shows `{ index, error }` list for each failed record
- **Footer**: "Generate Again" button → `reset()` (preserves last DocType in form)

---

### `Home.vue` layout (Phase 1)

```
<div class="flex h-screen">
  <Sidebar minimal />        ← just app title + logout
  <div class="flex-1 overflow-y-auto p-8">
    <GenerateForm v-if="phase==='idle' || phase==='error'" />
    <JobProgress  v-else-if="phase==='generating'" />
    <ResultsSummary v-else-if="phase==='done'" />
  </div>
</div>
```

Error state: `GenerateForm` renders with `Alert theme="red"` above it showing `generation.error`.

---

## Phase 2 — Dependency Tree & Skip Control

**Goal**: User sees the dependency tree before generating, can skip doctypes, understands cycles.

### Backend additions — `frappe_faker/api/generate.py`

```python
@frappe.whitelist()
def get_dependency_tree(doctype: str, skip: str | list | None = None) -> dict[str, Any]:
    _require_system_manager()
    from frappe_faker.utils.dependency_graph import resolve_dependencies
    return resolve_dependencies(doctype, skip=set(_parse_list(skip)))
```

Returns `{ order: [{doctype, depth, has_existing_data, is_cyclic}], truncated, cycles }`.

### New frontend files

| File | Action |
|------|--------|
| `src/composables/useDependencyTree.js` | New — wraps `get_dependency_tree`, debounced 500ms |
| `src/components/DependencyTree.vue` | New — tree visualization |
| `src/components/SkipDoctypesSelector.vue` | New — MultiSelect pre-seeded with `has_existing_data` nodes |
| `src/components/GenerateForm.vue` | Update — add Preview button + skip selector |

### `DependencyTree.vue`

frappe-ui components: `Tree`, `Badge`, `Alert`, `Tooltip`, `Spinner`, `LoadingText`

- Transform flat `order[]` (with `depth`) into nested structure for `Tree` component
- Node badges: `[Target]` blue (depth=0), `[Has data]` green, `[Cyclic]` red
- Alerts: truncated → yellow; cycles → red (don't block generation, just warn)
- Empty state: "No dependencies — [DocType] generates standalone"

### `SkipDoctypesSelector.vue`

- `MultiSelect` with options from `tree.order` (all except target)
- Auto-selects nodes where `has_existing_data === true` as initial value
- On change → debounce-refetch tree (skip changes affect depth/resolution)

### `GenerateForm.vue` updates

- "Preview Dependencies" ghost Button appears after DocType is selected (only when `resolve_deps === true`)
- Clicking fetches tree and expands an inline `DependencyTree` panel below the DocType selector
- `SkipDoctypesSelector` appears inside Advanced Options (populated from tree)
- `skip` param forwarded into `startGeneration`

---

## Phase 3 — Polish & Full Shell

**Goal**: Sidebar navigation, generation history, settings panel, toasts (already wired in Phase 1), keyboard shortcuts.

### New frontend files

| File | Action |
|------|--------|
| `src/components/GenerationHistory.vue` | New — last 20 runs, via localStorage |
| `src/composables/useGenerationHistory.js` | New — read/write localStorage |
| `src/components/SettingsPanel.vue` | New — shows provider/model, links to `/app/faker-settings` |
| `src/pages/Home.vue` | Update — full 3-item Sidebar + panel switching |

### Sidebar (Phase 3)

```
SidebarHeader: title="Frappe Faker", icon emoji or logo
SidebarItem: icon="zap"     label="Generate"  → activePanel='generate'
SidebarItem: icon="clock"   label="History"   → activePanel='history'
SidebarItem: icon="settings" label="Settings" → activePanel='settings'
Footer: Avatar (session user) + Logout SidebarItem
```

Main area renders `<GenerateFlow>`, `<GenerationHistory>`, or `<SettingsPanel>` based on `activePanel`.

### `GenerationHistory.vue`

- `ListView` with columns: DocType | Created (green Badge) | Failed (red Badge, hidden if 0) | Timestamp
- `ListEmptyState`: "No generations yet"
- Row click → shows full `ResultsSummary` in a `Dialog`
- Stores: `{ doctype, count, total_created, total_failed, timestamp, result }` per run

### `SettingsPanel.vue`

- Shows `provider` and `model_name` from `get_faker_settings`
- `Alert theme="yellow"` if no provider configured
- `Button` → opens `/app/faker-settings` in new tab

### Keyboard shortcuts (wired in `Home.vue`)

- `Cmd/Ctrl+Enter` when `phase==='idle'` and doctype set → trigger Generate
- `Escape` when `phase==='generating'` → cancel (reset)

---

## Edge Case Handling Summary

| Scenario | Handling |
|----------|----------|
| Empty DB (no linked records) | Blue Alert in tree: "All dependencies will be generated" |
| Cyclic deps | Red Badge on nodes + Alert; generation still proceeds |
| Truncated tree (depth >5) | Yellow Alert in tree; generation still proceeds |
| No dependencies | Tree shows "standalone" message; skip selector hidden |
| Very large count (>5min) | Extra Alert at 3min mark; reassures user job continues server-side |
| RQ worker offline | `not_found` status → error message with worker hint |
| Permission error (403) | Catch in `startGeneration`; show Alert with role hint |
| All records failed | Red Alert header in ResultsSummary; "Generate Again" still shown |
| No AI provider in Settings | Yellow Alert in GenerateForm on mount |
| User navigates away during poll | `onUnmounted(stopPolling)` clears interval; job continues server-side |

---

## Verification

1. `cd frontend && yarn dev` — dev server starts at `localhost:8080/frontend`
2. Log in → see GenerateForm (doctype autocomplete empty, count filled from settings)
3. Type "ToDo" → select → click Generate → see JobProgress with animated bar
4. Poll resolves → ResultsSummary shows per-doctype created counts
5. Click "Generate Again" → returns to form with "ToDo" pre-filled
6. Phase 2: click "Preview Dependencies" → tree renders with correct depth/badges
7. Phase 3: click History sidebar item → shows previous run with full results on row click
8. `bench build --app frappe_faker` → production build copies to `frappe_faker/public/frontend`
