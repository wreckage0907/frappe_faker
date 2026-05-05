# Frappe Faker — Architecture & Implementation Plan

## Core Concept

An AI-powered fake data generator that:
1. Reads doctype meta to understand structure & dependencies
2. Resolves a dependency graph from Link/Table fields
3. Uses an LLM to generate contextually realistic data
4. Inserts records in dependency order via Frappe ORM

---

## Phase 1: Foundation (Core Engine)

### 1.1 — Meta Analyzer (`frappe_faker/utils/meta_analyzer.py`)

- For a given doctype, extract a structured "generation schema":
  - Mandatory fields, their types, options/constraints
  - Link fields → what existing records to reference (or generate)
  - Select fields → valid options
  - Child tables → their own field schemas
  - Naming rules (autoname patterns)
  - Unique constraints
- Output a JSON-serializable schema that the LLM can consume

### 1.2 — Dependency Graph Resolver (`frappe_faker/utils/dependency_graph.py`)

- Walk `meta.get_link_fields()` and `meta.get_table_fields()` recursively
- Build a DAG (directed acyclic graph) of doctype dependencies
- Topological sort to determine insertion order
- Handle circular references gracefully (e.g., Employee → User → Employee)
- Skip system doctypes that shouldn't be generated — maintain a blocklist

### 1.3 — AI Data Generator (`frappe_faker/utils/ai_generator.py`)

- Takes the generation schema + count
- Builds a prompt describing the doctype structure, constraints, and context
- Calls the configured LLM (from Faker Settings)
- Parses structured JSON response into insertable records
- Handles retries on malformed responses

### 1.4 — Record Inserter (`frappe_faker/utils/inserter.py`)

- Takes generated records, inserts via `frappe.get_doc(data).insert()`
- Handles save errors: logs failures, optionally retries with AI correction
- Tracks what was created (for potential rollback/cleanup)
- Respects workflows (submit if needed for certain doctypes)

---

## Phase 2: User Interface

### 2.1 — Web Page

- Doctype picker (autocomplete)
- Show resolved dependency tree visually
- Per-doctype count configuration
- Checkboxes to skip dependencies user already has data for
- "Generate" button with progress indicator
- Log/results panel

### 2.2 — CLI Command (extend `bench` via `hooks.py` → `commands`)

```
bench faker generate --doctype "Timesheet" --count 50
bench faker generate --doctype "Timesheet" --count 50 --skip "Employee,Project"
bench faker plan --doctype "Timesheet"  # show dependency tree without generating
bench faker cleanup --batch <batch_id>  # delete a batch of generated records
```

---

## Phase 3: Intelligence & Polish

### 3.1 — Context Enrichment

- Read custom server scripts and validate methods to understand business rules
- Optionally read existing data to match patterns (e.g., naming conventions)
- Use doctype documentation (`description` field) as context for LLM

### 3.2 — Generation Profiles (new doctype: `Faker Profile`)

- User-defined presets: "Full HR Setup", "Project Management Seed", etc.
- Stores: target doctypes, counts, skip list, custom instructions per doctype
- Shareable across teams

### 3.3 — Batch Tracking (new doctype: `Faker Batch`)

- Records every generation run: what was created, when, by whom
- Enables rollback (delete all records from a batch)
- Useful for test environments

---

## Key Design Decisions

| Decision | Approach |
|----------|----------|
| **Blocklist** | Maintain a list of system doctypes to never auto-generate (User, Role, DocType, etc.) |
| **Existing data** | Before generating Link dependencies, check if records already exist; use them if available |
| **LLM prompt strategy** | Send field schema as structured JSON, ask for array of records in exact schema format |
| **Error handling** | Log failures per record, continue batch, report summary at end |
| **Rate limiting** | Batch LLM calls (generate 10-50 records per call to minimize API usage) |
| **Child tables** | Generated inline with parent in same LLM call for coherence |

---

## File Structure

```
frappe_faker/
├── frappe_faker/
│   ├── api/
│   │   └── generate.py          # Whitelisted API for UI
│   ├── utils/
│   │   ├── constants.py         # Blocklists, defaults
│   │   ├── dependency_graph.py  # DAG resolution
│   │   ├── meta_analyzer.py     # Schema extraction
│   │   ├── ai_generator.py      # LLM integration
│   │   ├── inserter.py          # Record creation
│   │   └── prompt_builder.py    # Prompt templates
│   ├── commands.py              # bench CLI commands
│   ├── frappe_faker/
│   │   └── doctype/
│   │       ├── faker_settings/  # (exists)
│   │       ├── faker_profile/   # Phase 3
│   │       └── faker_batch/     # Phase 3
│   └── templates/
│       └── pages/
│           └── generate/        # Web UI
```

---

## Implementation Order

1. Meta Analyzer — get the schema extraction working and tested
2. Dependency Graph — resolve and topologically sort dependencies
3. AI Generator — LLM integration with prompt building
4. Inserter — save records with error handling
5. CLI — `bench faker generate` command
6. Web UI — page with dependency tree visualization
7. Profiles & Batches — Phase 3 doctypes
