# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Integration tests for batch tracking (Faker Batch / Faker Batch Item) and
rollback via frappe_faker.api.generate.rollback_batch.

generate_and_insert() and rollback_batch() commit, so rows persist between
tests; every test uses its own unique Note titles and its own batch.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from frappe_faker.api.generate import rollback_batch
from frappe_faker.utils.inserter import generate_and_insert


def _settings() -> dict:
	return {
		"provider": "OpenAI",
		"api_key": "test-key",
		"api_endpoint": "https://api.openai.com/v1/chat/completions",
		"model_name": "gpt-4o-mini",
		"default_count": 2,
	}


class TestFakerBatch(IntegrationTestCase):
	def _generate_notes(self, count: int = 3) -> dict:
		"""Run the real pipeline for Note with the LLM call replaced by fixed records."""
		prefix = f"Faker Batch Test {frappe.generate_hash(length=8)}"

		def fake_generate(context, cnt, custom_instructions=None, settings=None):
			return [
				{"doctype": context["schema"]["doctype"], "title": f"{prefix} {i}", "content": "x"}
				for i in range(cnt)
			]

		with (
			patch("frappe_faker.utils.ai_generator.get_settings", return_value=_settings()),
			patch("frappe_faker.utils.ai_generator.generate_records", side_effect=fake_generate),
		):
			return generate_and_insert("Note", count=count, resolve_deps=False, fast_insert=True)

	def test_generation_records_every_insert_in_a_completed_batch(self):
		result = self._generate_notes(count=3)

		self.assertTrue(result["batch_name"])
		batch = frappe.get_doc("Faker Batch", result["batch_name"])
		self.assertEqual(batch.status, "Completed")
		self.assertEqual(batch.target_doctype, "Note")
		self.assertEqual(batch.created_by, frappe.session.user)
		self.assertTrue(batch.started_at)
		self.assertTrue(batch.completed_at)

		created = result["results"][0]["created"]
		self.assertEqual(len(created), 3)
		self.assertEqual([item.record_name for item in batch.items], created)
		self.assertTrue(all(item.doctype_name == "Note" for item in batch.items))
		self.assertTrue(all(not item.rolled_back for item in batch.items))

	def test_rollback_deletes_records_and_marks_batch(self):
		result = self._generate_notes(count=3)
		created = result["results"][0]["created"]

		response = rollback_batch(result["batch_name"])

		self.assertEqual(response["deleted"], 3)
		self.assertEqual(response["errors"], [])
		self.assertEqual(response["status"], "Rolled Back")
		self.assertFalse(response["already_rolled_back"])
		for name in created:
			self.assertFalse(frappe.db.exists("Note", name))

		batch = frappe.get_doc("Faker Batch", result["batch_name"])
		self.assertEqual(batch.status, "Rolled Back")
		self.assertTrue(all(item.rolled_back for item in batch.items))

	def test_rollback_is_idempotent(self):
		result = self._generate_notes(count=1)
		rollback_batch(result["batch_name"])

		second = rollback_batch(result["batch_name"])

		self.assertEqual(second["deleted"], 0)
		self.assertTrue(second["already_rolled_back"])
		self.assertEqual(second["status"], "Rolled Back")

	def test_rollback_deletes_in_reverse_insertion_order(self):
		result = self._generate_notes(count=3)
		created = result["results"][0]["created"]
		deleted_order: list[str] = []
		real_delete = frappe.delete_doc

		def recording_delete(doctype, name, *args, **kwargs):
			deleted_order.append(name)
			return real_delete(doctype, name, *args, **kwargs)

		with patch.object(frappe, "delete_doc", side_effect=recording_delete):
			rollback_batch(result["batch_name"])

		self.assertEqual(deleted_order, list(reversed(created)))

	def test_rollback_reports_failures_and_keeps_going(self):
		result = self._generate_notes(count=3)
		created = result["results"][0]["created"]
		failing = created[1]
		real_delete = frappe.delete_doc

		def flaky_delete(doctype, name, *args, **kwargs):
			if name == failing:
				raise frappe.LinkExistsError("still linked")
			return real_delete(doctype, name, *args, **kwargs)

		with patch.object(frappe, "delete_doc", side_effect=flaky_delete):
			response = rollback_batch(result["batch_name"])

		self.assertEqual(response["status"], "Partially Rolled Back")
		self.assertEqual(response["deleted"], 2)
		self.assertEqual([e["name"] for e in response["errors"]], [failing])
		self.assertTrue(frappe.db.exists("Note", failing))
		self.assertFalse(frappe.db.exists("Note", created[0]))
		self.assertFalse(frappe.db.exists("Note", created[2]))

		batch = frappe.get_doc("Faker Batch", result["batch_name"])
		flags = {item.record_name: item.rolled_back for item in batch.items}
		self.assertEqual(flags, {created[0]: 1, failing: 0, created[2]: 1})

		frappe.delete_doc("Note", failing, force=True)
		frappe.db.commit()  # nosemgrep

	def test_batch_marked_failed_when_pipeline_raises(self):
		with patch(
			"frappe_faker.utils.inserter.insert_records_fast",
			side_effect=RuntimeError("database went away"),
		):
			with self.assertRaises(RuntimeError):
				self._generate_notes(count=1)

		batch_name = frappe.get_all(
			"Faker Batch",
			filters={"target_doctype": "Note"},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)[0]
		batch = frappe.get_doc("Faker Batch", batch_name)
		self.assertEqual(batch.status, "Failed")
		self.assertTrue(batch.completed_at)

	def test_rollback_requires_faker_settings_write_access(self):
		result = self._generate_notes(count=1)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				rollback_batch(result["batch_name"])
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Faker Batch", result["batch_name"], "status"), "Completed")
		rollback_batch(result["batch_name"])
