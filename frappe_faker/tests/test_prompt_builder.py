# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Unit tests for frappe_faker.utils.prompt_builder.

All tests are pure-Python — no DB or Frappe context required.
"""

from frappe.tests import UnitTestCase

from frappe_faker.utils.prompt_builder import SYSTEM_PROMPT, build_generation_prompt


def _make_context(
	doctype: str = "TestDoc",
	fields: list | None = None,
	child_tables: dict | None = None,
	existing_links: dict | None = None,
	autoname: str | None = None,
	is_submittable: bool = False,
) -> dict:
	"""Build a minimal context dict for prompt tests."""
	return {
		"schema": {
			"doctype": doctype,
			"autoname": autoname,
			"is_submittable": is_submittable,
			"is_child_table": False,
			"title_field": None,
			"fields": fields or [],
			"child_tables": child_tables or {},
		},
		"existing_links": existing_links or {},
	}


class TestSystemPrompt(UnitTestCase):
	def test_system_prompt_is_non_empty_string(self):
		self.assertIsInstance(SYSTEM_PROMPT, str)
		self.assertGreater(len(SYSTEM_PROMPT), 100)

	def test_system_prompt_contains_json_output_rule(self):
		self.assertIn("JSON array", SYSTEM_PROMPT)

	def test_system_prompt_forbids_timezone_suffix(self):
		# Rule 5 must forbid Z and +00:00 in Datetime fields
		self.assertIn("NO 'Z'", SYSTEM_PROMPT)
		self.assertIn("NO '+00:00'", SYSTEM_PROMPT)

	def test_system_prompt_forbids_system_fields(self):
		# Rule 9 must exclude name, owner, creation, etc.
		self.assertIn("name", SYSTEM_PROMPT)
		self.assertIn("docstatus", SYSTEM_PROMPT)


class TestBuildGenerationPrompt(UnitTestCase):
	def test_prompt_contains_doctype_name(self):
		ctx = _make_context(doctype="Sales Invoice")
		prompt = build_generation_prompt(ctx, 3)
		self.assertIn("Sales Invoice", prompt)

	def test_prompt_contains_count(self):
		ctx = _make_context()
		prompt = build_generation_prompt(ctx, 7)
		self.assertIn("7", prompt)

	def test_prompt_includes_autoname_hint(self):
		ctx = _make_context(autoname="field:title")
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("field:title", prompt)

	def test_prompt_omits_autoname_section_when_none(self):
		ctx = _make_context(autoname=None)
		prompt = build_generation_prompt(ctx, 1)
		self.assertNotIn("Naming rule:", prompt)

	def test_prompt_includes_submittable_warning(self):
		ctx = _make_context(is_submittable=True)
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("submittable", prompt)

	def test_prompt_required_marker_in_fields(self):
		ctx = _make_context(fields=[{"fieldname": "title", "fieldtype": "Data", "reqd": 1}])
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("REQUIRED", prompt)

	def test_prompt_link_doctype_arrow_in_fields(self):
		ctx = _make_context(
			fields=[{"fieldname": "customer", "fieldtype": "Link", "reqd": 0, "link_doctype": "Customer"}]
		)
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("-> Customer", prompt)

	def test_prompt_select_options_in_fields(self):
		ctx = _make_context(
			fields=[
				{
					"fieldname": "status",
					"fieldtype": "Select",
					"reqd": 0,
					"select_options": ["Open", "Closed", "Cancelled"],
				}
			]
		)
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("Open", prompt)

	def test_prompt_caps_link_values_at_15(self):
		many_values = [f"REC-{i:04d}" for i in range(30)]
		ctx = _make_context(existing_links={"Customer": many_values})
		prompt = build_generation_prompt(ctx, 2)
		# Only the first 15 should appear in the prompt
		self.assertIn("REC-0000", prompt)
		self.assertNotIn("REC-0015", prompt)

	def test_prompt_includes_custom_instructions(self):
		ctx = _make_context()
		prompt = build_generation_prompt(ctx, 1, custom_instructions="Only use Indian names.")
		self.assertIn("Only use Indian names.", prompt)

	def test_prompt_omits_custom_instructions_section_when_none(self):
		ctx = _make_context()
		prompt = build_generation_prompt(ctx, 1, custom_instructions=None)
		self.assertNotIn("Additional Instructions", prompt)

	def test_prompt_includes_child_table_section(self):
		ctx = _make_context(
			child_tables={
				"items": {
					"doctype": "Sales Invoice Item",
					"reqd": True,
					"fields": [
						{"fieldname": "item_code", "fieldtype": "Link", "reqd": 1, "link_doctype": "Item"}
					],
				}
			}
		)
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("Child Tables", prompt)
		self.assertIn("Sales Invoice Item", prompt)

	def test_prompt_child_table_required_label(self):
		ctx = _make_context(
			child_tables={
				"items": {
					"doctype": "Invoice Item",
					"reqd": True,
					"fields": [],
				}
			}
		)
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("REQUIRED", prompt)

	def test_prompt_no_link_values_section_when_empty(self):
		ctx = _make_context(existing_links={})
		prompt = build_generation_prompt(ctx, 1)
		self.assertNotIn("Available Link Values", prompt)

	def test_prompt_link_values_placeholder_when_no_records(self):
		ctx = _make_context(existing_links={"Customer": []})
		prompt = build_generation_prompt(ctx, 1)
		self.assertIn("no existing records", prompt)
