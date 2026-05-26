# Frappe Faker — Architecture & Implementation Plan

## Core Concept

An AI-powered fake data generator that:
1. Reads doctype meta to understand structure & dependencies
2. Resolves a dependency graph from Link/Table fields
3. Uses an LLM to generate contextually realistic data
4. Inserts records in dependency order via Frappe ORM

---

## Status Overview

| Phase | Area | Status |
|-------|------|--------|
| 1 — Backend foundation | Meta analyzer, dep graph, AI generator, inserter | ✅ Done |
| 2 — API layer | `generate.py`, `history.py` whitelisted endpoints | ✅ Done |
| 2 — Frontend MVP | Login, Generate form, Job progress, Results, History, Settings | ✅ Done |
| 2 — Dependency tree UI | DependencyTree component + GenerateForm wiring | ✅ Done |
| 3 — CLI commands | `bench faker generate/plan/cleanup` | ⬜ Not started |
| 3 — Faker Profile doctype | User-defined generation presets | ⬜ Not started |
| 3 — Faker Batch doctype + Rollback | Batch tracking, rollback UI + CLI | ⬜ Not started |
| 3 — Claude Code skill | Agent skill for data-driven testing | ⬜ Not started |

---

## Phase 1: Foundation (Complete)

### 1.1 — Meta Analyzer (`frappe_faker/utils/meta_analyzer.py`) ✅

- Reads Frappe DocType meta into a JSON-serializable generation schema
- Extracts fields, child tables, link deps, select options, naming rules
- `get_generation_context()` merges schema with existing linked records for LLM prompt
- Shared `existing_cache` dict across multi-doctype runs avoids repeated DB queries

### 1.2 — Dependency Graph Resolver (`frappe_faker/utils/dependency_graph.py`) ✅

- Builds a DAG of Link field dependencies with recursive `_build_graph()`
- Topological sort via Kahn's algorithm; cyclic nodes appended at end
- `max_depth=5` guards against infinite recursion; truncated nodes reported
- Redis-cached adjacency map (`frappe_faker_dep_adjacency`) rebuilt on every `bench migrate` via `after_migrate` hook — avoids repeated `get_meta()` calls on hot path
- `SYSTEM_DOCTYPE_BLOCKLIST` prevents auto-generating Company, User, Currency, etc.

### 1.3 — AI Data Generator (`frappe_faker/utils/ai_generator.py`) ✅

- Supports OpenAI/Custom/Ollama (OpenAI-compatible), Anthropic Messages API, Google Gemini
- `generate_records()` retries up to 2× on invalid JSON, appending error context to prompt
- Strips markdown code fences from LLM response before JSON parse
- Falls back to raw array extraction if well-formed array is followed by prose

### 1.4 — Record Inserter (`frappe_faker/utils/inserter.py`) ✅

- **Standard path**: `insert_records()` via `doc.insert()` — runs all Python hooks
- **Fast path**: `insert_records_fast()` via `doc.db_insert()` — bypasses all hooks; handles child table rows, set_new_name, set_user_and_timestamp
- `generate_and_insert()` orchestrator: serial context builds → parallel LLM calls (ThreadPoolExecutor, up to 8 workers) → serial DB inserts (FK integrity)
- `_batch_check_links()`: one `frappe.get_all()` per link doctype, not per record
- `_sanitize_record()`: strips timezone suffixes from Datetime fields (MariaDB rejects them)

---

## Phase 2: User Interface (Complete)

### 2.1 — API Layer (`frappe_faker/api/`) ✅

**`generate.py`** — 5 whitelisted endpoints:
- `enqueue_generation` — enqueues RQ job on `long` queue (3600s timeout), returns `job_id`
- `get_job_status` — polls `RQ Job` doctype; falls back to direct Redis inspection for older Frappe
- `generate_sync` — synchronous path for small counts / testing
- `get_faker_settings` — returns `{default_count, provider, model_name}` for UI defaults
- `get_dependency_tree` — returns resolved `{order, truncated, cycles}` for UI preview

**`history.py`** — 3 whitelisted endpoints:
- `add_run` — inserts `Faker Run` doc with status (Success/Partial/Failed)
- `get_runs` — last 20 runs for current user, newest first
- `clear_runs` — deletes all runs for current user

### 2.2 — Vue 3 Frontend (`frontend/`) ✅

**Pages:**
- `Login.vue` — branded login with FakerLogo, vertically centered layout
- `Home.vue` — 3-panel sidebar app (Generate / History / Settings); keyboard shortcuts (⌘Enter to generate, Esc to cancel)

**Components:**
- `GenerateForm.vue` — DocType autocomplete, count input, resolve-deps/fast-insert toggles (in card), inline dependency tree preview, advanced options (custom instructions), Generate button
- `DocTypeSelector.vue` — Autocomplete with 300ms debounce, loads full list on mount
- `DependencyTree.vue` — bordered rows with depth indent, skip checkboxes, Target/Has data/Cyclic/Skip badges, auto-selects nodes with existing data
- `JobProgress.vue` — fake progress bar (increments 0.4%/500ms to 90%), status badge, stale-queue alert (>40s), long-run alert (>3min), Cancel button
- `ResultsSummary.vue` — icon+title+subtitle header, per-doctype created/failed badges, expandable error detail rows, "Generate Again" + "Copy summary" actions
- `GenerationHistory.vue` — ListView of Faker Runs, row-click opens ResultsSummary in Dialog, relative timestamps, empty state
- `SettingsPanel.vue` — AI config rows (provider, model, default count), keyboard shortcuts reference, link to Frappe Settings
- `FakerLogo.vue` — SVG logo component used in sidebar header and login page

**Composables:**
- `useGeneration.js` — job lifecycle: idle → generating → done/error; `startGeneration()`, `pollOnce()` (2s interval), `reset()`; 3-consecutive-network-error guard
- `useGenerationHistory.js` — `get_runs`/`add_run`/`clear_runs` wrappers; `reload()` on panel open
- `useDependencyTree.js` — `fetchTree()`, `debouncedFetch()` (500ms), `clear()`

---

## Phase 3: Remaining Work

### 3.1 — CLI Commands (`frappe_faker/commands.py`)

Extend `bench` with a `faker` command group. Register via `hooks.py` `commands` list.

```
bench --site <site> faker generate --doctype "Timesheet" --count 50
bench --site <site> faker generate --doctype "Timesheet" --count 50 --skip "Employee,Project"
bench --site <site> faker plan --doctype "Timesheet"      # show dep tree, no generation
bench --site <site> faker cleanup --batch <batch_id>     # delete a batch of records
```

Implementation notes:
- Use `click` (already a Frappe dep) for the command group
- `generate` command calls `generate_and_insert()` directly (no RQ — runs synchronously in terminal)
- `plan` command calls `print_dependency_tree()` from `dependency_graph.py` (already implemented)
- `cleanup` requires `Faker Batch` doctype (Phase 3.3)
- Register in `hooks.py`: `commands = ["frappe_faker.commands"]`

```python
# frappe_faker/commands.py skeleton
import click
import frappe
from frappe.commands import pass_context

@click.group()
def faker():
    """Frappe Faker CLI — generate fake data for doctypes."""
    pass

@faker.command("generate")
@click.option("--doctype", required=True)
@click.option("--count", default=None, type=int)
@click.option("--skip", default=None)
@click.option("--fast-insert/--no-fast-insert", default=True)
@pass_context
def generate_cmd(context, doctype, count, skip, fast_insert):
    ...

@faker.command("plan")
@click.option("--doctype", required=True)
@pass_context
def plan_cmd(context, doctype):
    ...

commands = [faker]
```

### 3.2 — Faker Profile Doctype

User-defined generation presets — shareable "seeds" for common setups.

**Fields:**
- `profile_name` (Data, reqd, unique) — e.g. "Full HR Setup"
- `description` (Small Text)
- `items` (Table → `Faker Profile Item`)
  - `doctype_name` (Link → DocType, reqd)
  - `count` (Int, default 5)
  - `skip` (Small Text) — comma-separated doctypes to skip
  - `custom_instructions` (Text)

**Use case:** Save a profile from the UI after configuring a generation run; run a full profile in one click or via CLI (`bench faker profile run "Full HR Setup"`).

### 3.3 — Faker Batch Doctype + Rollback

Batch tracking for every generation run — enables full rollback from both the UI and CLI.

**Doctype fields:**
- `target_doctype` (Data) — primary doctype
- `status` (Select: Running / Completed / Rolled Back)
- `started_at`, `completed_at` (Datetime)
- `created_by` (Link → User)
- `items` (Table → `Faker Batch Item`)
  - `doctype_name` (Data)
  - `record_name` (Data) — the `name` of the created record
  - `rolled_back` (Check)

**Backend — `inserter.py` changes:**
- `generate_and_insert()` creates a `Faker Batch` doc before starting, sets status = "Running"
- As each record is inserted, appends a `Faker Batch Item` row immediately (not at the end — partial rollback is possible if the job crashes)
- On completion sets status = "Completed"; job failure sets status = "Failed"
- Returns `batch_name` in the result payload alongside existing `total_created` / `total_failed`

**Backend — `api/generate.py` addition:**
```python
@frappe.whitelist()
def rollback_batch(batch_name: str) -> dict[str, Any]:
    _require_system_manager()
    batch = frappe.get_doc("Faker Batch", batch_name)
    if batch.status == "Rolled Back":
        frappe.throw("Batch already rolled back")
    deleted, errors = 0, []
    for item in reversed(batch.items):   # reverse = dependency-safe delete order
        if item.rolled_back:
            continue
        try:
            frappe.delete_doc(item.doctype_name, item.record_name, force=True, ignore_missing=True)
            item.rolled_back = 1
            deleted += 1
        except Exception as e:
            errors.append({"doctype": item.doctype_name, "name": item.record_name, "error": str(e)})
    batch.status = "Rolled Back" if not errors else "Partially Rolled Back"
    batch.save()
    return {"deleted": deleted, "errors": errors}
```

**Frontend — UI rollback flow:**
- `ResultsSummary.vue`: add a "Rollback" ghost button next to "Generate Again" (only shown when `result.batch_name` exists and status != "Rolled Back")
- Clicking shows a confirmation `Dialog`: "Delete N records across M doctypes?"
- On confirm: calls `rollback_batch(batch_name)`, shows success toast or error summary
- `GenerationHistory.vue`: each history row with a batch shows a "Rollback" action in the row-click Dialog
- After rollback, the history row status badge updates to "Rolled Back" (red)

**CLI:**
```
bench --site <site> faker cleanup --batch <batch_name>
```

**Key design note:** Records are appended to the batch item table as they are inserted (not buffered until the end). This means a crashed job can still be partially rolled back — only successfully inserted records are in the table.

### 3.4 — Claude Code Skill

A `.claude/skills/` skill file that teaches an AI agent how to use Frappe Faker from the CLI to generate contextually specific test data on demand.

**Motivation:** When testing an API endpoint in another app and local data is missing, an agent can describe the requirement in natural language and Faker will generate correctly linked records. The `custom_instructions` field in the LLM prompt is the key hook — it accepts free-text constraints like "all employees in Chennai office, joined 2024, salary 50k–80k".

**Skill file location:** `frappe_faker/.claude/skills/faker-data.md`

**What the skill teaches an agent:**
1. **Inspect first** — run `bench faker plan --doctype <DocType>` to see the dependency tree and understand which linked records will be auto-generated
2. **Generate with requirements** — run `bench faker generate --doctype <DocType> --count <N> --instructions "<free-text requirement>"` where the instructions describe the specific data shape needed for the test
3. **Verify** — check the CLI output for `total_created` / `total_failed`; if any failed, re-run with a reduced count or adjusted instructions
4. **Clean up** — after testing, run `bench faker cleanup --batch <batch_name>` (printed by `generate`) to roll back all records; this leaves the DB clean for the next test run

**Example agent workflow (encoded in the skill):**
```
# Testing the Payroll Entry API — need realistic Salary Structures + Employees
bench --site demo.localhost faker plan --doctype "Salary Slip"
# → shows: Salary Structure Assignment → Employee → Department (has data) → Company (has data)

bench --site demo.localhost faker generate \
  --doctype "Salary Slip" --count 3 \
  --instructions "Employees are software engineers in Bangalore. Monthly salary 80k-120k INR. Use existing company."
# → Batch: FAKER-BATCH-0001 | Created: Salary Slip ×3, Employee ×3, Salary Structure ×3

# ... run API tests ...

bench --site demo.localhost faker cleanup --batch FAKER-BATCH-0001
# → Deleted 9 records
```

**Dependency on Phase 3.1:** The skill requires CLI commands to be implemented first. Once 3.1 is done, the skill file itself is a short markdown document — no additional Python code needed.

---

## Key Design Decisions (Reference)

| Decision | Approach |
|----------|----------|
| **Blocklist** | `SYSTEM_DOCTYPE_BLOCKLIST` in `constants.py` — never auto-generate User, Role, DocType, Company, etc. |
| **Existing data** | Before generating link deps, check `frappe.db.count()`; if records exist, skip generation and pass existing names to LLM |
| **LLM prompt strategy** | Structured JSON schema + existing link values → strict JSON array response |
| **Error handling** | Per-record savepoints; failures logged in summary; batch continues |
| **Rate limiting** | All records for a doctype in one LLM call; parallel across doctypes (ThreadPoolExecutor) |
| **Child tables** | Generated inline with parent in same LLM call for coherence |
| **Fast insert** | Default `True` — bypasses Python hooks; standard path available when hook fidelity matters |
| **Dep cache** | Redis adjacency map, no TTL, rebuilt on every `bench migrate` |
| **Job polling** | Frontend polls `get_job_status` every 2s; falls back to direct Redis inspection for older Frappe |
