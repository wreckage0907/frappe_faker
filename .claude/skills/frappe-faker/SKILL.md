---
name: frappe-faker
description: Generate realistic, correctly-linked fake test data for any Frappe/ERPNext DocType using the `bench faker` CLI, then roll it back when done. Use when a test or local repro needs seed records (e.g. "I need some Sales Orders with line items", "create test Employees in the Chennai office", "seed data for the payroll API") and the database is missing them.
---

# Frappe Faker

Frappe Faker uses an LLM to generate fake-but-realistic records for any DocType,
auto-resolving and creating linked dependencies first. Every run is tracked as a
**Faker Batch** so it can be deleted again with one command.

Prerequisite: an AI provider must be configured in **Faker Settings** (Desk UI).
All commands need a site: `bench --site <site> faker ...`.

## Workflow

### 1. Inspect first
See what will be generated (dependencies are created before the target):

```
bench --site <site> faker plan --doctype "<DocType>"
```

Records marked `[has data]` are reused; `[needs generation]` will be created.

### 2. Generate with requirements
Describe the exact data shape in `--instructions` — this is the key hook for
test-specific data:

```
bench --site <site> faker generate \
  --doctype "<DocType>" --count <N> \
  --instructions "<free-text requirement>"
```

Useful options:
- `--no-deps` — only generate the target, don't auto-create linked records
- `--skip "DocType A,DocType B"` — skip specific dependencies (you already have them)
- `--standard-insert` — run full Python hooks/validation instead of the fast path
  (slower, but produces side effects like ledger entries)

The command prints a **batch name** (e.g. `FAKER-BATCH-00007`) and a ready-to-run
cleanup command. Note the batch name.

### 3. Verify
Check the printed `Created` / `Failed` counts. If records failed, the per-doctype
breakdown shows why — re-run with a lower `--count` or clearer `--instructions`.

### 4. Clean up
After the test, delete everything the run created (reverse dependency order):

```
bench --site <site> faker cleanup --batch <BATCH_NAME>
```

Safe to run twice — already-deleted records are skipped.

## Example

```
# Need realistic Salary Slips + the Employees/Salary Structures they link to
bench --site demo.localhost faker plan --doctype "Salary Slip"

bench --site demo.localhost faker generate \
  --doctype "Salary Slip" --count 3 \
  --instructions "Software engineers in Bangalore, monthly salary 80k-120k INR, use existing company."
# -> Batch: FAKER-BATCH-00007 | Created: 9

# ... run the tests ...

bench --site demo.localhost faker cleanup --batch FAKER-BATCH-00007
# -> deleted 9 records
```

## Notes
- System DocTypes (User, Company, Currency, Role, etc.) are never auto-generated;
  existing values are reused for links instead.
- `--count` defaults to the value in Faker Settings when omitted.
- Generation runs inline and calls a live LLM, so it can take a few seconds.
