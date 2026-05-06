# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Integration tests for frappe_faker.utils.inserter.

_sanitize_record and _batch_check_links need get_meta (DB).
insert_records* and generate_and_insert write real rows (rolled back by the
test framework's per-test transaction).
"""

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_faker.utils.inserter import (
	_batch_check_links,
	_build_summary,
	_safe_summary,
	_sanitize_record,
	generate_and_insert,
	insert_records,
	insert_records_fast,
)


def _note(title: str = "Test Note", content: str = "Test content") -> dict:
	return {"doctype": "Note", "title": title, "content": content}


def _make_settings() -> dict:
	return {
		"provider": "OpenAI",
		"api_key": "test-key",
		"api_endpoint": "https://api.openai.com/v1/chat/completions",
		"model_name": "gpt-4o-mini",
		"default_count": 3,
	}


# ---------------------------------------------------------------------------
# Pure-function tests (no DB needed but still run as integration for simplicity)
# ---------------------------------------------------------------------------


class TestBuildSummary(IntegrationTestCase):
	def test_summary_counts(self):
		records = [_note("A"), _note("B")]
		summary = _build_summary(records, ["name-1"], [{"index": 1, "error": "boom", "record": {}}])
		self.assertEqual(summary["total"], 2)
		self.assertEqual(summary["created_count"], 1)
		self.assertEqual(summary["failed_count"], 1)
		self.assertEqual(summary["doctype"], "Note")

	def test_empty_records(self):
		summary = _build_summary([], [], [])
		self.assertIsNone(summary["doctype"])
		self.assertEqual(summary["total"], 0)


class TestSafeSummary(IntegrationTestCase):
	def test_long_string_truncated(self):
		record = {"title": "x" * 200}
		result = _safe_summary(record)
		self.assertLessEqual(len(result["title"]), 110)  # 100 + "..."

	def test_list_replaced_with_count(self):
		record = {"items": [1, 2, 3, 4, 5]}
		result = _safe_summary(record)
		self.assertIn("5", result["items"])

	def test_short_values_unchanged(self):
		record = {"title": "Short"}
		result = _safe_summary(record)
		self.assertEqual(result["title"], "Short")


# ---------------------------------------------------------------------------
# _sanitize_record tests (needs get_meta)
# ---------------------------------------------------------------------------


class TestSanitizeRecord(IntegrationTestCase):
	def test_strips_z_suffix_from_datetime(self):
		record = {"doctype": "Note", "expire_notification_on": "2024-01-15T10:30:00Z"}
		result = _sanitize_record(record)
		self.assertNotIn("Z", result["expire_notification_on"])
		self.assertIn("2024-01-15", result["expire_notification_on"])

	def test_strips_timezone_offset_from_datetime(self):
		record = {"doctype": "Note", "expire_notification_on": "2024-01-15T10:30:00+05:30"}
		result = _sanitize_record(record)
		self.assertNotIn("+05:30", result["expire_notification_on"])

	def test_strips_time_from_date_field(self):
		# ToDo.date is a Date field — value with time component should be truncated to 10 chars
		record = {"doctype": "ToDo", "description": "test", "date": "2024-01-15T00:00:00"}
		result = _sanitize_record(record)
		self.assertEqual(result["date"], "2024-01-15")
		self.assertEqual(len(result["date"]), 10)

	def test_clean_datetime_unchanged(self):
		record = {"doctype": "Note", "expire_notification_on": "2024-01-15"}
		result = _sanitize_record(record)
		self.assertEqual(result["expire_notification_on"], "2024-01-15")

	def test_non_string_values_unchanged(self):
		record = {"doctype": "Note", "title": "Hello", "public": 1}
		result = _sanitize_record(record)
		self.assertEqual(result["public"], 1)

	def test_unknown_doctype_returns_record_unchanged(self):
		record = {"doctype": "NonExistentDocXYZ99", "title": "test"}
		result = _sanitize_record(record)
		self.assertEqual(result, record)


# ---------------------------------------------------------------------------
# _batch_check_links tests
# ---------------------------------------------------------------------------


class TestBatchCheckLinks(IntegrationTestCase):
	def test_empty_records_returns_empty(self):
		result = _batch_check_links([])
		self.assertEqual(result, {})

	def test_note_has_no_link_fields(self):
		# Note has no Link fields, so result should be empty
		records = [_note()]
		result = _batch_check_links(records)
		self.assertEqual(result, {})

	def test_returns_dict_with_sets(self):
		records = [{"doctype": "ToDo", "description": "Test", "status": "Open"}]
		result = _batch_check_links(records)
		self.assertIsInstance(result, dict)
		for _key, val in result.items():
			self.assertIsInstance(val, set)


# ---------------------------------------------------------------------------
# insert_records_fast integration tests
# ---------------------------------------------------------------------------


class TestInsertRecordsFast(IntegrationTestCase):
	def test_inserts_valid_note(self):
		records = [_note("Fast Insert Test")]
		result = insert_records_fast(records)
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["failed_count"], 0)
		self.assertEqual(len(result["created"]), 1)

	def test_created_name_exists_in_db(self):
		records = [_note("DB Existence Check")]
		result = insert_records_fast(records)
		name = result["created"][0]
		self.assertTrue(frappe.db.exists("Note", name))

	def test_handles_bad_record_gracefully(self):
		# A non-existent doctype will raise when frappe.get_doc() loads the meta
		bad = {"doctype": "NonExistentDoctype99999XYZ", "title": "will fail"}
		result = insert_records_fast([bad])
		self.assertEqual(result["failed_count"], 1)
		self.assertEqual(result["created_count"], 0)
		self.assertIn("error", result["failed"][0])

	def test_mixed_records_partial_success(self):
		good = _note("Good Record")
		bad = {"doctype": "NonExistentDoctype99999XYZ", "title": "will fail"}
		result = insert_records_fast([good, bad])
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["failed_count"], 1)

	def test_result_structure(self):
		result = insert_records_fast([_note("Structure Test")])
		self.assertIn("doctype", result)
		self.assertIn("total", result)
		self.assertIn("created", result)
		self.assertIn("created_count", result)
		self.assertIn("failed_count", result)
		self.assertIn("failed", result)


# ---------------------------------------------------------------------------
# insert_records (standard path) integration tests
# ---------------------------------------------------------------------------


class TestInsertRecords(IntegrationTestCase):
	def test_inserts_valid_note(self):
		records = [_note("Standard Insert Test")]
		result = insert_records(records)
		self.assertEqual(result["created_count"], 1)
		self.assertEqual(result["failed_count"], 0)

	def test_created_name_exists_in_db(self):
		records = [_note("Standard DB Check")]
		result = insert_records(records)
		name = result["created"][0]
		self.assertTrue(frappe.db.exists("Note", name))


# ---------------------------------------------------------------------------
# generate_and_insert (full pipeline, mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateAndInsert(IntegrationTestCase):
	def _fake_generate(self, context, count, custom_instructions=None, settings=None):
		"""Return deterministic fake Note records without calling any LLM."""
		doctype = context["schema"]["doctype"]
		return [
			{"doctype": doctype, "title": f"Mocked Note {i + 1}", "content": "mock"} for i in range(count)
		]

	# generate_records and get_settings are imported *inside* generate_and_insert()
	# at call time, so we must patch the source module, not the inserter module.
	@patch("frappe_faker.utils.ai_generator.generate_records")
	@patch("frappe_faker.utils.ai_generator.get_settings")
	def test_full_pipeline_creates_records(self, mock_get_settings, mock_generate):
		mock_get_settings.return_value = _make_settings()
		mock_generate.side_effect = self._fake_generate

		result = generate_and_insert("Note", count=2, resolve_deps=False, fast_insert=True)

		self.assertEqual(result["total_created"], 2)
		self.assertEqual(result["total_failed"], 0)
		self.assertEqual(result["target"], "Note")

	@patch("frappe_faker.utils.ai_generator.generate_records")
	@patch("frappe_faker.utils.ai_generator.get_settings")
	def test_full_pipeline_standard_insert(self, mock_get_settings, mock_generate):
		mock_get_settings.return_value = _make_settings()
		mock_generate.side_effect = self._fake_generate

		result = generate_and_insert("Note", count=2, resolve_deps=False, fast_insert=False)

		self.assertEqual(result["total_created"], 2)
		self.assertEqual(result["fast_insert"], False)

	@patch("frappe_faker.utils.ai_generator.generate_records")
	@patch("frappe_faker.utils.ai_generator.get_settings")
	def test_result_structure(self, mock_get_settings, mock_generate):
		mock_get_settings.return_value = _make_settings()
		mock_generate.side_effect = self._fake_generate

		result = generate_and_insert("Note", count=1, resolve_deps=False)

		self.assertIn("target", result)
		self.assertIn("count_requested", result)
		self.assertIn("fast_insert", result)
		self.assertIn("results", result)
		self.assertIn("total_created", result)
		self.assertIn("total_failed", result)

	@patch("frappe_faker.utils.ai_generator.generate_records")
	@patch("frappe_faker.utils.ai_generator.get_settings")
	def test_uses_default_count_from_settings(self, mock_get_settings, mock_generate):
		settings = _make_settings()
		settings["default_count"] = 4
		mock_get_settings.return_value = settings
		mock_generate.side_effect = self._fake_generate

		# count=None → should use default_count from settings (4)
		result = generate_and_insert("Note", count=None, resolve_deps=False)

		self.assertEqual(result["count_requested"], 4)

	@patch("frappe_faker.utils.ai_generator.generate_records")
	@patch("frappe_faker.utils.ai_generator.get_settings")
	def test_generation_error_reported_in_results(self, mock_get_settings, mock_generate):
		mock_get_settings.return_value = _make_settings()
		from frappe_faker.utils.ai_generator import GenerationError

		mock_generate.side_effect = GenerationError("LLM unavailable")

		result = generate_and_insert("Note", count=1, resolve_deps=False)

		self.assertEqual(result["total_created"], 0)
		self.assertEqual(len(result["results"]), 1)
		self.assertIn("error", result["results"][0])
