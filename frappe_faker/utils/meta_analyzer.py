"""
Meta Analyzer — extracts a generation schema from a Frappe DocType's metadata.

The schema is a JSON-serializable dict that describes everything an LLM needs
to generate realistic fake records for a given doctype.
"""

from __future__ import annotations

from typing import Any

import frappe

from frappe_faker.utils.constants import LAYOUT_FIELDTYPES, SYSTEM_DOCTYPE_BLOCKLIST


def analyze_doctype(doctype: str) -> dict[str, Any]:
	"""
	Analyze a doctype and return a generation schema.

	Returns a dict with:
	- doctype: str
	- autoname: str | None
	- is_submittable: bool
	- is_child_table: bool
	- fields: list of field descriptors
	- child_tables: dict mapping fieldname -> child doctype schema
	- link_dependencies: list of linked doctypes that need to exist
	"""
	meta = frappe.get_meta(doctype)

	schema: dict[str, Any] = {
		"doctype": doctype,
		"autoname": meta.autoname or None,
		"is_submittable": bool(meta.is_submittable),
		"is_child_table": bool(meta.istable),
		"title_field": meta.title_field or None,
		"fields": [],
		"child_tables": {},
		"link_dependencies": [],
	}

	link_deps: set[str] = set()

	for df in meta.fields:
		if df.fieldtype in LAYOUT_FIELDTYPES:
			continue

		field_info = _extract_field_info(df)
		if field_info is None:
			continue

		schema["fields"].append(field_info)

		# Track link dependencies
		if df.fieldtype == "Link" and df.options and df.options not in SYSTEM_DOCTYPE_BLOCKLIST:
			link_deps.add(df.options)

	# Process child tables
	for df in meta.get_table_fields():
		child_doctype = df.options
		if not child_doctype:
			continue
		child_schema = _analyze_child_table(child_doctype)
		schema["child_tables"][df.fieldname] = {
			"doctype": child_doctype,
			"label": df.label,
			"reqd": bool(df.reqd),
			"fields": child_schema["fields"],
			"link_dependencies": child_schema["link_dependencies"],
		}
		# Child table link deps bubble up to parent
		for dep in child_schema["link_dependencies"]:
			if dep not in SYSTEM_DOCTYPE_BLOCKLIST:
				link_deps.add(dep)

	schema["link_dependencies"] = sorted(link_deps)
	return schema


def _analyze_child_table(doctype: str) -> dict[str, Any]:
	"""Analyze a child table doctype (simpler, no recursion into nested tables)."""
	meta = frappe.get_meta(doctype)
	fields = []
	link_deps: set[str] = set()

	for df in meta.fields:
		if df.fieldtype in LAYOUT_FIELDTYPES:
			continue
		field_info = _extract_field_info(df)
		if field_info is None:
			continue
		fields.append(field_info)

		if df.fieldtype == "Link" and df.options and df.options not in SYSTEM_DOCTYPE_BLOCKLIST:
			link_deps.add(df.options)

	return {"fields": fields, "link_dependencies": sorted(link_deps)}


def _extract_field_info(df) -> dict[str, Any] | None:
	"""Extract generation-relevant info from a single DocField."""
	info: dict[str, Any] = {
		"fieldname": df.fieldname,
		"fieldtype": df.fieldtype,
		"label": df.label or df.fieldname,
		"reqd": bool(df.reqd),
		"unique": bool(df.unique),
	}

	# Add type-specific metadata
	if df.fieldtype == "Link":
		info["link_doctype"] = df.options
	elif df.fieldtype == "Dynamic Link":
		info["options_field"] = df.options  # fieldname that holds the doctype
	elif df.fieldtype == "Select":
		options = (df.options or "").strip()
		info["select_options"] = [o for o in options.split("\n") if o.strip()]
	elif df.fieldtype in ("Int", "Float", "Currency", "Percent"):
		# No min/max in meta, but we note the type for the LLM
		pass
	elif df.fieldtype == "Data" and df.options:
		# Data field with validation (Email, Phone, URL, Name, etc.)
		info["data_type"] = df.options
	elif df.fieldtype in ("Table", "Table MultiSelect"):
		# Handled separately in child_tables
		return None

	# Default value hint
	if df.default:
		info["default"] = df.default

	# Length constraint
	if df.length:
		info["max_length"] = df.length

	return info


def get_existing_records(doctype: str, limit: int = 20) -> list[str]:
	"""Get names of existing records for a doctype (for Link field references)."""
	try:
		return frappe.get_all(doctype, pluck="name", limit_page_length=limit, order_by="creation desc")
	except Exception:
		return []


def get_generation_context(doctype: str) -> dict[str, Any]:
	"""
	Build full context for generation: schema + existing linked records.

	This is what gets sent to the LLM for data generation.
	"""
	schema = analyze_doctype(doctype)

	# For each link dependency, fetch existing records
	existing_links: dict[str, list[str]] = {}
	for dep in schema["link_dependencies"]:
		records = get_existing_records(dep)
		existing_links[dep] = records

	# Also check child table link deps
	for _fieldname, child_info in schema["child_tables"].items():
		for dep in child_info["link_dependencies"]:
			if dep not in existing_links:
				existing_links[dep] = get_existing_records(dep)

	return {
		"schema": schema,
		"existing_links": existing_links,
	}
