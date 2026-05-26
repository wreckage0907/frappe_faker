"""
Inserter — creates Frappe records from generated data.

Handles insertion, error recovery, and batch tracking.

Two insertion paths:
  insert_records()      — standard path via doc.insert() with flags
  insert_records_fast() — fast path via doc.db_insert(), bypasses ALL Python hooks
                          (validate, before_insert, after_insert, on_update, etc.)
                          Use this for bulk seeding where hook fidelity is not needed.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import frappe

# ---------------------------------------------------------------------------
# Public insertion functions
# ---------------------------------------------------------------------------


def insert_records(
	records: list[dict[str, Any]],
	ignore_permissions: bool = True,
	ignore_mandatory: bool = False,
	ignore_validate: bool = False,
) -> dict[str, Any]:
	"""
	Insert generated records via the standard doc.insert() path.

	Validation hooks (validate, before_insert, etc.) still run unless
	ignore_validate is True. Use insert_records_fast() to skip all hooks.

	Args:
		records: List of record dicts (with 'doctype' key)
		ignore_permissions: Skip permission checks
		ignore_mandatory: Skip mandatory field validation
		ignore_validate: Skip DocType validate/before_save hooks

	Returns:
		Summary dict with created, failed, and details.
	"""
	created: list[str] = []
	failed: list[dict[str, Any]] = []

	# Batch check all Link field values in one query-per-doctype pass
	valid_link_values = _batch_check_links(records)

	for i, record in enumerate(records):
		try:
			frappe.db.savepoint("faker_insert")
			record = _sanitize_record(record)
			doc = frappe.get_doc(record)
			doc.flags.ignore_permissions = ignore_permissions
			doc.flags.ignore_mandatory = ignore_mandatory
			doc.flags.ignore_links = True
			if ignore_validate:
				doc.flags.ignore_validate = True
			_clear_broken_links(doc, valid_link_values)
			doc.insert(ignore_permissions=ignore_permissions, ignore_links=True)
			created.append(doc.name)
		except Exception as e:
			frappe.db.rollback(save_point="faker_insert")
			failed.append({"index": i, "error": str(e), "record": _safe_summary(record)})
			continue

	if created:
		frappe.db.commit()  # nosemgrep

	return _build_summary(records, created, failed)


def insert_records_fast(
	records: list[dict[str, Any]],
	ignore_permissions: bool = True,
) -> dict[str, Any]:
	"""
	Insert generated records via doc.db_insert() — bypasses ALL Python hooks.

	This skips: validate, before_insert, after_insert, on_update, on_change,
	controller business logic, etc. It only does the raw SQL INSERT after
	resolving the document name.

	Trade-offs vs insert_records():
	  ✓ Much faster (no hook overhead, no repeated DB round-trips for validation)
	  ✓ Won't fail due to custom validation rules in target doctypes
	  ✗ Side-effects from hooks won't happen (ledger entries, notifications, etc.)
	  ✗ Some field defaults set by controllers won't be populated

	Recommended for test data seeding where hook fidelity is not required.

	Args:
		records: List of record dicts (with 'doctype' key)
		ignore_permissions: Skip permission checks (passed to naming)

	Returns:
		Summary dict with created, failed, and details.
	"""
	created: list[str] = []
	failed: list[dict[str, Any]] = []

	valid_link_values = _batch_check_links(records)

	for i, record in enumerate(records):
		try:
			frappe.db.savepoint("faker_fast_insert")
			record = _sanitize_record(record)
			name = _db_insert_record(record, valid_link_values, ignore_permissions)
			created.append(name)
		except Exception as e:
			frappe.db.rollback(save_point="faker_fast_insert")
			failed.append({"index": i, "error": str(e), "record": _safe_summary(record)})
			continue

	if created:
		frappe.db.commit()  # nosemgrep

	return _build_summary(records, created, failed)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def generate_and_insert(
	doctype: str,
	count: int | None = None,
	skip: set[str] | list[str] | None = None,
	custom_instructions: str | None = None,
	resolve_deps: bool = True,
	fast_insert: bool = True,
) -> dict[str, Any]:
	"""
	High-level orchestrator: resolve deps, generate via LLM, and insert.

	Optimisations:
	- Settings loaded once, reused for all LLM calls
	- All generation contexts built serially (fast DB reads), then LLM calls
	  are fired in parallel via ThreadPoolExecutor (network I/O, no DB)
	- Records inserted in dependency order (serial, for FK integrity)
	- Shared existing-record cache across context builds
	- skip accepts both set and list so it is JSON-serialisable for RQ workers

	Args:
		doctype: Target doctype to generate
		count: Number of records (defaults to Faker Settings default_count)
		skip: Doctypes to skip; accepts set or list (RQ requires list)
		custom_instructions: Extra instructions for the LLM
		resolve_deps: Whether to auto-generate dependencies first
		fast_insert: Use db_insert() path (much faster, skips Python hooks)

	Returns:
		Full result dict with per-doctype summaries including batch_name.
	"""
	from frappe_faker.utils.ai_generator import GenerationError, generate_records, get_settings
	from frappe_faker.utils.dependency_graph import resolve_dependencies
	from frappe_faker.utils.meta_analyzer import get_generation_context

	# Load settings once — avoids N+1 frappe.get_single() calls
	settings = get_settings()

	if count is None:
		count = settings.get("default_count", 10)

	results: list[dict[str, Any]] = []
	# Normalise skip — accepts set or list (RQ requires JSON-serialisable list)
	skip_set: set[str] = set(skip) if skip else set()

	# ------------------------------------------------------------------
	# Build task list: (doctype, count_to_generate)
	# ------------------------------------------------------------------
	tasks: list[tuple[str, int]] = []

	if resolve_deps:
		dep_result = resolve_dependencies(doctype, skip=skip_set)
		for item in dep_result["order"]:
			dt = item["doctype"]
			if dt == doctype or item["has_existing_data"]:
				continue
			tasks.append((dt, min(count, 5)))

	tasks.append((doctype, count))

	# Create a Faker Batch doc to track every record inserted in this run.
	# Failures here are non-fatal — batch tracking is best-effort.
	batch_doc = _create_batch(doctype)

	try:
		# ------------------------------------------------------------------
		# Build all generation contexts (serial — DB reads are fast)
		# Shared cache avoids repeated frappe.get_all() for the same linked
		# doctype across multiple get_generation_context() calls.
		# ------------------------------------------------------------------
		existing_cache: dict[str, list[str]] = {}
		contexts: dict[str, dict[str, Any]] = {}
		# Track context failures to avoid duplicate result entries (context error
		# + generation "Context not available" error for the same doctype).
		context_failed: set[str] = set()

		for dt, _cnt in tasks:
			try:
				contexts[dt] = get_generation_context(dt, existing_cache=existing_cache)
			except Exception as e:
				context_failed.add(dt)
				results.append(
					{
						"doctype": dt,
						"total": 0,
						"created_count": 0,
						"failed_count": 0,
						"error": f"Context build failed: {e}",
					}
				)

		# ------------------------------------------------------------------
		# Fire LLM API calls in parallel
		# LLM calls are pure network I/O — no Frappe DB involved — so
		# threading here is safe.
		# ------------------------------------------------------------------
		generated: dict[str, list[dict[str, Any]] | None] = {}
		generation_errors: dict[str, str] = {}

		def _generate(dt: str, cnt: int) -> tuple[str, list[dict[str, Any]] | None, str | None]:
			if dt not in contexts:
				return dt, None, "Context not available"
			try:
				records = generate_records(contexts[dt], cnt, custom_instructions, settings=settings)
				return dt, records, None
			except (GenerationError, Exception) as exc:
				return dt, None, str(exc)

		with ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as executor:
			futures = {
				executor.submit(_generate, dt, cnt): (dt, cnt)
				for dt, cnt in tasks
				if dt not in context_failed
			}
			for future in as_completed(futures):
				dt, records, error = future.result()
				if error:
					generation_errors[dt] = error
				else:
					generated[dt] = records

		# ------------------------------------------------------------------
		# Insert in dependency order (serial — FK integrity)
		# ------------------------------------------------------------------
		_insert = insert_records_fast if fast_insert else insert_records

		for dt, _cnt in tasks:
			if dt in context_failed:
				continue  # already recorded a result during context build
			if dt in generation_errors:
				results.append(
					{
						"doctype": dt,
						"total": 0,
						"created_count": 0,
						"failed_count": 0,
						"error": generation_errors[dt],
					}
				)
				continue

			records = generated.get(dt)
			if not records:
				results.append(
					{
						"doctype": dt,
						"total": 0,
						"created_count": 0,
						"failed_count": 0,
						"error": "No records generated",
					}
				)
				continue

			result = _insert(records)
			results.append(result)

			# Append committed records to the batch immediately so a crashed job
			# can still be partially rolled back.
			_append_to_batch(batch_doc, dt, result.get("created", []))

		_finalize_batch(batch_doc)

	except Exception:
		# Ensure the batch is never left in Running state on an unhandled error.
		if batch_doc:
			try:
				batch_doc.status = "Failed"
				batch_doc.completed_at = frappe.utils.now()
				batch_doc.save()
				frappe.db.commit()  # nosemgrep
			except Exception:
				pass
		raise

	return {
		"target": doctype,
		"count_requested": count,
		"fast_insert": fast_insert,
		"batch_name": batch_doc.name if batch_doc else None,
		"results": results,
		"total_created": sum(r.get("created_count", 0) for r in results),
		"total_failed": sum(r.get("failed_count", 0) for r in results),
	}


# ---------------------------------------------------------------------------
# Fast-path: db_insert without Python hooks
# ---------------------------------------------------------------------------


def _db_insert_record(
	record: dict[str, Any],
	valid_link_values: dict[str, set[str]],
	ignore_permissions: bool = True,
) -> str:
	"""
	Insert a single record directly via db_insert(), bypassing all Python hooks.

	Steps:
	1. Instantiate the doc (loads controller class but does NOT call any hooks)
	2. Assign name via set_new_name() (handles autoname, naming series, etc.)
	3. Set system fields (owner, creation, modified, modified_by, docstatus)
	4. Clear broken optional links
	5. db_insert() — single SQL INSERT for the parent
	6. For each child table row: repeat steps 2-5 with parent linkage set

	Does NOT run: validate, before_insert, after_insert, on_update, on_change.
	"""
	doc = frappe.get_doc(record)
	doc.flags.ignore_permissions = ignore_permissions
	doc.flags.ignore_links = True

	# Assign name from autoname / naming series / prompt
	doc.set_new_name(force=True)

	# Set owner, creation, modified, modified_by, docstatus
	# Method name changed between Frappe versions
	_set_user_and_timestamp(doc)

	# Clear broken optional links without individual db.exists() calls
	_clear_broken_links(doc, valid_link_values)

	# Raw SQL INSERT for the parent row (no Python hooks fire)
	doc.db_insert()

	# Handle child table rows
	_db_insert_children(doc)

	return doc.name


def _set_user_and_timestamp(doc) -> None:
	"""Set owner/creation/modified fields — handles API differences across Frappe versions."""
	if hasattr(doc, "set_user_and_timestamp"):
		doc.set_user_and_timestamp()
	elif hasattr(doc, "set_user_fields"):
		# Older Frappe versions
		doc.set_user_fields()
	else:
		# Manual fallback
		from frappe.utils import now

		user = frappe.session.user if frappe.session else "Administrator"
		now_dt = now()
		if not doc.owner:
			doc.owner = user
		doc.modified_by = user
		if not doc.creation:
			doc.creation = now_dt
		doc.modified = now_dt


def _db_insert_children(doc) -> None:
	"""Insert all child table rows for a document via db_insert()."""
	meta = frappe.get_meta(doc.doctype)
	for df in meta.get_table_fields():
		rows = doc.get(df.fieldname) or []
		for idx, row in enumerate(rows, start=1):
			# Set required parent-linkage fields
			row.parent = doc.name
			row.parenttype = doc.doctype
			row.parentfield = df.fieldname
			row.idx = idx
			if not row.name:
				row.set_new_name()
			_set_user_and_timestamp(row)
			row.db_insert()


# ---------------------------------------------------------------------------
# Link validation helpers (shared by both insert paths)
# ---------------------------------------------------------------------------


def _batch_check_links(records: list[dict[str, Any]]) -> dict[str, set[str]]:
	"""
	Check which Link field values actually exist in the DB in bulk.

	Groups all values by link_doctype and does one frappe.get_all() per doctype
	instead of one frappe.db.exists() per field per record.

	Returns:
		dict mapping link_doctype -> set of names confirmed to exist
	"""
	if not records:
		return {}

	doctype = records[0].get("doctype")
	if not doctype:
		return {}

	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return {}

	link_fields = {df.fieldname: df for df in meta.get_link_fields()}
	values_by_doctype: dict[str, set[str]] = {}

	for record in records:
		for fieldname, df in link_fields.items():
			value = record.get(fieldname)
			if value and df.options:
				values_by_doctype.setdefault(df.options, set()).add(str(value))

	# One frappe.get_all() per link doctype — not per record
	valid: dict[str, set[str]] = {}
	for link_dt, values in values_by_doctype.items():
		try:
			existing = frappe.get_all(link_dt, filters={"name": ["in", list(values)]}, pluck="name")
			valid[link_dt] = set(existing)
		except Exception:
			valid[link_dt] = set()

	return valid


def _clear_broken_links(doc, valid_link_values: dict[str, set[str]]) -> None:
	"""
	Clear optional Link fields that reference non-existent records.

	Uses pre-fetched `valid_link_values` from _batch_check_links() for O(1)
	lookups. Falls back to frappe.db.exists() for any doctype not pre-checked.
	"""
	meta = frappe.get_meta(doc.doctype)
	for df in meta.get_link_fields():
		value = doc.get(df.fieldname)
		if not value:
			continue
		link_dt = df.options
		if link_dt in valid_link_values:
			exists = str(value) in valid_link_values[link_dt]
		else:
			exists = bool(frappe.db.exists(link_dt, value))

		if not exists and not df.reqd:
			doc.set(df.fieldname, None)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _sanitize_record(record: dict[str, Any]) -> dict[str, Any]:
	"""
	Clean LLM-generated values before insertion.

	- Strips timezone suffixes from Datetime strings (Z, +HH:MM, etc.)
	  which MariaDB rejects.  Frappe expects 'YYYY-MM-DD HH:MM:SS'.
	- Strips time component from Date-only fields.
	"""
	import re

	doctype = record.get("doctype")
	if not doctype:
		return record

	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return record

	field_types = {df.fieldname: df.fieldtype for df in meta.fields}
	cleaned = dict(record)

	for fieldname, value in record.items():
		if not isinstance(value, str):
			continue
		ft = field_types.get(fieldname)
		if ft == "Datetime":
			# Remove timezone: '2023-01-01T10:00:00Z' -> '2023-01-01 10:00:00'
			v = re.sub(r"[TZ]", lambda m: " " if m.group() == "T" else "", value)
			v = re.sub(r"[+-]\d{2}:\d{2}$", "", v).strip()
			cleaned[fieldname] = v
		elif ft == "Date":
			# Keep only the date part
			cleaned[fieldname] = value[:10]

	return cleaned


def _build_summary(
	records: list[dict[str, Any]],
	created: list[str],
	failed: list[dict[str, Any]],
) -> dict[str, Any]:
	return {
		"doctype": records[0]["doctype"] if records else None,
		"total": len(records),
		"created": created,
		"created_count": len(created),
		"failed_count": len(failed),
		"failed": failed,
	}


def _safe_summary(record: dict[str, Any]) -> dict[str, Any]:
	"""Return a truncated summary of a record for error reporting."""
	summary = {}
	for key, value in record.items():
		if isinstance(value, list):
			summary[key] = f"[{len(value)} rows]"
		elif isinstance(value, str) and len(value) > 100:
			summary[key] = value[:100] + "..."
		else:
			summary[key] = value
	return summary


# ---------------------------------------------------------------------------
# Batch tracking helpers
# ---------------------------------------------------------------------------


def _create_batch(doctype: str) -> Any | None:
	"""Create a Faker Batch doc to track this generation run. Returns None on failure."""
	try:
		user = frappe.session.user if frappe.session else "Administrator"
		doc = frappe.get_doc(
			{
				"doctype": "Faker Batch",
				"target_doctype": doctype,
				"status": "Running",
				"started_at": frappe.utils.now(),
				"created_by": user,
			}
		)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		return doc
	except Exception:
		return None


def _append_to_batch(batch_doc: Any, doctype_name: str, record_names: list[str]) -> None:
	"""Append a doctype's newly inserted records to the batch and commit."""
	if not batch_doc or not record_names:
		return
	try:
		for name in record_names:
			batch_doc.append("items", {"doctype_name": doctype_name, "record_name": name})
		batch_doc.save()
		frappe.db.commit()  # nosemgrep
	except Exception:
		pass


def _finalize_batch(batch_doc: Any) -> None:
	"""Mark the batch as Completed after all inserts finish."""
	if not batch_doc:
		return
	try:
		batch_doc.status = "Completed"
		batch_doc.completed_at = frappe.utils.now()
		batch_doc.save()
		frappe.db.commit()  # nosemgrep
	except Exception:
		pass
