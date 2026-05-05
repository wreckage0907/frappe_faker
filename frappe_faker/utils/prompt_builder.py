"""
Prompt Builder — constructs LLM prompts from generation schemas.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are a realistic test data generator for a business application (ERPNext/Frappe).
Your job is to generate fake but realistic records that could plausibly exist in a real company's database.

Rules:
1. Generate data as a JSON array of objects. Each object is one record.
2. Field names must match EXACTLY as specified in the schema.
3. For Link fields, you MUST use one of the provided existing record names. If none are provided, use a realistic placeholder name that follows the doctype's naming convention.
4. For Select fields, ONLY use one of the provided options.
5. For Date/Datetime fields, use ISO format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS). Use dates within the last 2 years.
6. For Currency/Float/Int fields, use realistic business values.
7. For Check fields, use 0 or 1.
8. For child tables, include them as arrays under the fieldname key.
9. Do NOT include fields like name, owner, creation, modified, docstatus — those are auto-generated.
10. Make the data internally consistent (e.g., end_date > start_date, totals match line items).
11. Respond ONLY with the JSON array. No explanation, no markdown fences."""


def build_generation_prompt(
	context: dict[str, Any],
	count: int,
	custom_instructions: str | None = None,
) -> str:
	"""
	Build a user prompt for data generation.

	Args:
		context: Output from meta_analyzer.get_generation_context()
		count: Number of records to generate
		custom_instructions: Optional user-provided instructions for customization
	"""
	schema = context["schema"]
	existing_links = context["existing_links"]

	parts: list[str] = []

	parts.append(f"Generate {count} realistic records for the DocType: **{schema['doctype']}**\n")

	# Naming info
	if schema["autoname"]:
		parts.append(f"Naming rule: {schema['autoname']} (do NOT include a 'name' field)\n")

	if schema["is_submittable"]:
		parts.append("This is a submittable document. Do NOT include docstatus (it defaults to 0/Draft).\n")

	# Field schema
	parts.append("## Fields\n")
	fields_desc = _describe_fields(schema["fields"])
	parts.append(fields_desc)

	# Child tables
	if schema["child_tables"]:
		parts.append("\n## Child Tables\n")
		for fieldname, child in schema["child_tables"].items():
			parts.append(f"### `{fieldname}` ({child['doctype']})")
			if child["reqd"]:
				parts.append(" [REQUIRED - must have at least 1 row]")
			parts.append("\n")
			parts.append(_describe_fields(child["fields"]))
			parts.append("")

	# Existing linked records
	if existing_links:
		parts.append("\n## Available Link Values\n")
		parts.append("Use ONLY these values for Link fields (pick randomly from them):\n")
		for doctype_name, records in existing_links.items():
			if records:
				display = records[:15]  # Limit display
				parts.append(f"- **{doctype_name}**: {json.dumps(display)}")
			else:
				parts.append(f"- **{doctype_name}**: (no existing records — use a realistic name)")
		parts.append("")

	# Custom instructions
	if custom_instructions:
		parts.append(f"\n## Additional Instructions\n{custom_instructions}\n")

	parts.append(f"\nRespond with a JSON array of exactly {count} record objects.")

	return "\n".join(parts)


def _describe_fields(fields: list[dict[str, Any]]) -> str:
	"""Format field list for the prompt."""
	lines: list[str] = []
	for f in fields:
		desc = f"- `{f['fieldname']}` ({f['fieldtype']})"
		extras: list[str] = []
		if f.get("reqd"):
			extras.append("REQUIRED")
		if f.get("unique"):
			extras.append("UNIQUE")
		if f.get("link_doctype"):
			extras.append(f"-> {f['link_doctype']}")
		if f.get("select_options"):
			extras.append(f"options: {f['select_options']}")
		if f.get("data_type"):
			extras.append(f"format: {f['data_type']}")
		if f.get("default"):
			extras.append(f"default: {f['default']}")
		if f.get("max_length"):
			extras.append(f"max_length: {f['max_length']}")
		if extras:
			desc += f" [{', '.join(extras)}]"
		lines.append(desc)
	return "\n".join(lines)
