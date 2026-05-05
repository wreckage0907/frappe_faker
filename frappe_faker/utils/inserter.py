"""
Inserter — creates Frappe records from generated data.

Handles insertion, error recovery, and batch tracking.
"""

from __future__ import annotations

from typing import Any

import frappe


def insert_records(
	records: list[dict[str, Any]],
	ignore_permissions: bool = True,
	ignore_mandatory: bool = False,
) -> dict[str, Any]:
	"""
	Insert generated records into the database.

	Args:
		records: List of record dicts (with 'doctype' key)
		ignore_permissions: Skip permission checks (for admin seeding)
		ignore_mandatory: Skip mandatory field validation

	Returns:
		Summary dict with created, failed, and details.
	"""
	created: list[str] = []
	failed: list[dict[str, Any]] = []

	for i, record in enumerate(records):
		try:
			doc = frappe.get_doc(record)
			doc.flags.ignore_permissions = ignore_permissions
			doc.flags.ignore_mandatory = ignore_mandatory
			doc.flags.ignore_links = True
			doc.flags.ignore_validate = True
			# Nullify link fields that reference non-existent records
			_clear_broken_links(doc)
			doc.insert(ignore_permissions=ignore_permissions, ignore_links=True)
			created.append(doc.name)
		except Exception as e:
			failed.append(
				{
					"index": i,
					"error": str(e),
					"record": _safe_summary(record),
				}
			)
			# Continue with remaining records
			continue

	# Commit successful inserts
	if created:
		frappe.db.commit()

	return {
		"doctype": records[0]["doctype"] if records else None,
		"total": len(records),
		"created": created,
		"created_count": len(created),
		"failed_count": len(failed),
		"failed": failed,
	}


def generate_and_insert(
	doctype: str,
	count: int | None = None,
	skip: set[str] | None = None,
	custom_instructions: str | None = None,
	resolve_deps: bool = True,
) -> dict[str, Any]:
	"""
	High-level orchestrator: resolve deps, generate, and insert.

	Args:
		doctype: Target doctype to generate
		count: Number of records (defaults to Faker Settings default_count)
		skip: Doctypes to skip in dependency resolution
		custom_instructions: Extra instructions for the LLM
		resolve_deps: Whether to auto-generate dependencies first

	Returns:
		Full result dict with per-doctype summaries.
	"""
	from frappe_faker.utils.ai_generator import generate_records
	from frappe_faker.utils.dependency_graph import resolve_dependencies
	from frappe_faker.utils.meta_analyzer import get_generation_context

	if count is None:
		settings = frappe.get_single("Faker Settings")
		count = int(settings.default_count or 10)

	results: list[dict[str, Any]] = []
	skip = skip or set()

	if resolve_deps:
		dep_result = resolve_dependencies(doctype, skip=skip)
		order = dep_result["order"]

		# Generate dependencies first (skip those that already have data)
		for item in order:
			dt = item["doctype"]
			if dt == doctype:
				continue  # Handle target last
			if item["has_existing_data"]:
				continue  # Already has data, skip

			dep_count = min(count, 5)  # Generate fewer dependency records
			try:
				ctx = get_generation_context(dt)
				records = generate_records(ctx, dep_count, custom_instructions)
				result = insert_records(records)
				results.append(result)
			except Exception as e:
				results.append(
					{
						"doctype": dt,
						"total": 0,
						"created_count": 0,
						"failed_count": 0,
						"error": str(e),
					}
				)

	# Generate target doctype
	ctx = get_generation_context(doctype)
	records = generate_records(ctx, count, custom_instructions)
	result = insert_records(records)
	results.append(result)

	return {
		"target": doctype,
		"count_requested": count,
		"results": results,
		"total_created": sum(r.get("created_count", 0) for r in results),
		"total_failed": sum(r.get("failed_count", 0) for r in results),
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


def _clear_broken_links(doc) -> None:
	"""Clear Link fields that reference non-existent records to prevent on_update failures."""
	meta = frappe.get_meta(doc.doctype)
	for df in meta.get_link_fields():
		value = doc.get(df.fieldname)
		if not value:
			continue
		# Check if the linked record exists
		if not frappe.db.exists(df.options, value):
			if df.reqd:
				# Required link — leave it, let it fail visibly
				pass
			else:
				# Optional link — clear it to avoid post-save errors
				doc.set(df.fieldname, None)
