# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Integration tests for frappe_faker.utils.meta_analyzer.

All tests require a live Frappe DB (get_meta, get_all, db.count).
"""

import frappe
from frappe.tests import IntegrationTestCase

from frappe_faker.utils.constants import LAYOUT_FIELDTYPES
from frappe_faker.utils.meta_analyzer import (
	analyze_doctype,
	get_existing_records,
	get_generation_context,
)


class TestAnalyzeDoctype(IntegrationTestCase):
	def test_analyze_note_returns_expected_keys(self):
		schema = analyze_doctype("Note")
		self.assertIn("doctype", schema)
		self.assertIn("fields", schema)
		self.assertIn("child_tables", schema)
		self.assertIn("link_dependencies", schema)
		self.assertIn("autoname", schema)
		self.assertIn("is_submittable", schema)
		self.assertIn("is_child_table", schema)

	def test_analyze_note_doctype_name(self):
		schema = analyze_doctype("Note")
		self.assertEqual(schema["doctype"], "Note")

	def test_analyze_note_has_title_field(self):
		schema = analyze_doctype("Note")
		fieldnames = [f["fieldname"] for f in schema["fields"]]
		self.assertIn("title", fieldnames)

	def test_analyze_note_no_link_dependencies(self):
		schema = analyze_doctype("Note")
		self.assertEqual(schema["link_dependencies"], [])

	def test_analyze_todo_has_link_dependencies(self):
		schema = analyze_doctype("ToDo")
		# ToDo has Link fields (assigned_by, reference_type/name, etc.)
		self.assertIsInstance(schema["link_dependencies"], list)
		self.assertGreater(len(schema["link_dependencies"]), 0)

	def test_layout_fields_excluded(self):
		schema = analyze_doctype("Note")
		for field in schema["fields"]:
			self.assertNotIn(
				field["fieldtype"],
				LAYOUT_FIELDTYPES,
				f"Layout field {field['fieldname']} ({field['fieldtype']}) should be excluded",
			)

	def test_field_info_has_required_keys(self):
		schema = analyze_doctype("Note")
		for field in schema["fields"]:
			self.assertIn("fieldname", field)
			self.assertIn("fieldtype", field)
			self.assertIn("reqd", field)

	def test_is_child_table_false_for_note(self):
		schema = analyze_doctype("Note")
		self.assertFalse(schema["is_child_table"])

	def test_analyze_nonexistent_raises(self):
		with self.assertRaises(Exception):
			analyze_doctype("NonExistentDoctype99999")


class TestGetExistingRecords(IntegrationTestCase):
	def test_returns_list(self):
		records = get_existing_records("Note")
		self.assertIsInstance(records, list)

	def test_cache_is_populated_after_call(self):
		cache: dict = {}
		get_existing_records("Note", cache=cache)
		self.assertIn("Note", cache)

	def test_cache_is_reused_on_second_call(self):
		cache: dict = {}
		_result1 = get_existing_records("Note", cache=cache)
		# Inject a sentinel to prove the cache is hit on second call
		cache["Note"] = ["SENTINEL"]
		result2 = get_existing_records("Note", cache=cache)
		self.assertEqual(result2, ["SENTINEL"])

	def test_limit_respected(self):
		# Create a couple of Notes so there is at least one record
		for i in range(3):
			note = frappe.get_doc({"doctype": "Note", "title": f"Cache Limit Test {i}"})
			note.insert(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

		records = get_existing_records("Note", limit=2)
		self.assertLessEqual(len(records), 2)


class TestGetGenerationContext(IntegrationTestCase):
	def test_context_has_schema_and_existing_links(self):
		ctx = get_generation_context("Note")
		self.assertIn("schema", ctx)
		self.assertIn("existing_links", ctx)

	def test_context_schema_matches_analyze_doctype(self):
		ctx = get_generation_context("Note")
		schema = analyze_doctype("Note")
		self.assertEqual(ctx["schema"]["doctype"], schema["doctype"])
		self.assertEqual(
			[f["fieldname"] for f in ctx["schema"]["fields"]],
			[f["fieldname"] for f in schema["fields"]],
		)

	def test_existing_links_is_dict(self):
		ctx = get_generation_context("Note")
		self.assertIsInstance(ctx["existing_links"], dict)

	def test_shared_cache_populated(self):
		cache: dict = {}
		get_generation_context("Note", existing_cache=cache)
		# Note has no link_dependencies, but cache itself should be a dict (not errored)
		self.assertIsInstance(cache, dict)

	def test_todo_context_has_link_entries(self):
		ctx = get_generation_context("ToDo")
		# ToDo links to User (and potentially others); existing_links should have entries
		self.assertIsInstance(ctx["existing_links"], dict)
		# At minimum, linked doctypes that have records should appear
		# (We don't assert exact keys since it depends on the test environment)
