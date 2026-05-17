# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Unit tests for frappe_faker.utils.ai_generator.

All LLM network calls are mocked — no Ollama or external API required.
"""

import json
from unittest.mock import MagicMock, patch

from frappe.tests import UnitTestCase

from frappe_faker.utils.ai_generator import (
	GenerationError,
	_build_gemini_endpoint,
	_call_llm,
	_parse_response,
	generate_records,
)


def _make_context(doctype: str = "Note", child_tables: dict | None = None) -> dict:
	"""Minimal context dict for generate_records tests."""
	return {
		"schema": {
			"doctype": doctype,
			"autoname": None,
			"is_submittable": False,
			"is_child_table": False,
			"title_field": "title",
			"fields": [{"fieldname": "title", "fieldtype": "Data", "reqd": 1}],
			"child_tables": child_tables or {},
		},
		"existing_links": {},
	}


def _make_settings() -> dict:
	return {
		"provider": "OpenAI",
		"api_key": "test-key",
		"api_endpoint": "https://api.openai.com/v1/chat/completions",
		"model_name": "gpt-4o-mini",
		"default_count": 10,
	}


def _make_gemini_settings(
	api_endpoint: str | None = None, model_name: str | None = "gemini-2.5-flash"
) -> dict:
	return {
		"provider": "Gemini",
		"api_key": "test-gemini-key",
		"api_endpoint": api_endpoint,
		"model_name": model_name,
		"default_count": 10,
	}


# ---------------------------------------------------------------------------
# _parse_response tests (pure unit tests)
# ---------------------------------------------------------------------------


class TestParseResponse(UnitTestCase):
	def test_plain_json_array(self):
		raw = '[{"title": "Hello"}, {"title": "World"}]'
		result = _parse_response(raw)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["title"], "Hello")

	def test_strips_json_code_fence(self):
		raw = '```json\n[{"title": "Hello"}]\n```'
		result = _parse_response(raw)
		self.assertEqual(result[0]["title"], "Hello")

	def test_strips_plain_code_fence(self):
		raw = '```\n[{"title": "Hello"}]\n```'
		result = _parse_response(raw)
		self.assertEqual(result[0]["title"], "Hello")

	def test_raises_on_invalid_json(self):
		with self.assertRaises(json.JSONDecodeError):
			_parse_response("not valid json at all")

	def test_raises_on_empty_string(self):
		with self.assertRaises((json.JSONDecodeError, ValueError)):
			_parse_response("")

	def test_single_record_array(self):
		raw = '[{"title": "Only one"}]'
		result = _parse_response(raw)
		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 1)

	def test_extracts_json_array_with_trailing_text(self):
		raw = '[{"title": "Hello"}]\nGenerated one note.'
		result = _parse_response(raw)
		self.assertEqual(result[0]["title"], "Hello")

	def test_extracts_json_array_with_leading_text(self):
		raw = 'Here is the JSON:\n[{"title": "Hello"}]'
		result = _parse_response(raw)
		self.assertEqual(result[0]["title"], "Hello")


# ---------------------------------------------------------------------------
# generate_records tests (mock _call_llm)
# ---------------------------------------------------------------------------


class TestGenerateRecords(UnitTestCase):
	def _mock_llm_response(self, records: list) -> str:
		return json.dumps(records)

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_doctype_injected_into_records(self, mock_call):
		mock_call.return_value = self._mock_llm_response([{"title": "Test Note"}])
		ctx = _make_context(doctype="Note")
		records = generate_records(ctx, 1, settings=_make_settings())
		self.assertEqual(len(records), 1)
		self.assertEqual(records[0]["doctype"], "Note")

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_multiple_records_all_get_doctype(self, mock_call):
		mock_call.return_value = self._mock_llm_response([{"title": "A"}, {"title": "B"}, {"title": "C"}])
		ctx = _make_context(doctype="Note")
		records = generate_records(ctx, 3, settings=_make_settings())
		self.assertEqual(len(records), 3)
		for r in records:
			self.assertEqual(r["doctype"], "Note")

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_child_table_doctype_injected(self, mock_call):
		records_payload = [
			{
				"title": "Invoice 1",
				"items": [{"item_code": "ITEM-001", "qty": 2}],
			}
		]
		mock_call.return_value = self._mock_llm_response(records_payload)
		ctx = _make_context(
			doctype="Sales Invoice",
			child_tables={
				"items": {
					"doctype": "Sales Invoice Item",
					"reqd": True,
					"fields": [{"fieldname": "item_code", "fieldtype": "Link", "reqd": 1}],
				}
			},
		)
		records = generate_records(ctx, 1, settings=_make_settings())
		self.assertEqual(records[0]["items"][0]["doctype"], "Sales Invoice Item")

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_retries_on_invalid_json_then_succeeds(self, mock_call):
		# First call returns bad JSON, second returns valid
		mock_call.side_effect = [
			"this is not json {{{{",
			self._mock_llm_response([{"title": "Retry Success"}]),
		]
		ctx = _make_context(doctype="Note")
		records = generate_records(ctx, 1, max_retries=1, settings=_make_settings())
		self.assertEqual(records[0]["title"], "Retry Success")
		self.assertEqual(mock_call.call_count, 2)

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_raises_generation_error_after_exhausting_retries(self, mock_call):
		mock_call.return_value = "{{{{ bad json always !!!!"
		ctx = _make_context(doctype="Note")
		with self.assertRaises(GenerationError):
			generate_records(ctx, 1, max_retries=1, settings=_make_settings())

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_raises_if_response_is_not_array(self, mock_call):
		mock_call.return_value = '{"title": "Not an array"}'
		ctx = _make_context(doctype="Note")
		with self.assertRaises(GenerationError):
			generate_records(ctx, 1, max_retries=0, settings=_make_settings())

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_custom_instructions_passed_to_prompt(self, mock_call):
		mock_call.return_value = self._mock_llm_response([{"title": "Custom"}])
		ctx = _make_context()
		generate_records(ctx, 1, custom_instructions="Only Indian names.", settings=_make_settings())
		# The prompt passed to _call_llm should contain the custom instruction
		call_args = mock_call.call_args
		prompt_arg = call_args[0][1]  # second positional arg to _call_llm
		self.assertIn("Only Indian names.", prompt_arg)

	@patch("frappe_faker.utils.ai_generator._call_llm")
	def test_settings_none_triggers_get_settings(self, mock_call):
		"""When settings=None, generate_records must call _get_settings() itself."""
		mock_call.return_value = self._mock_llm_response([{"title": "Auto Settings"}])
		ctx = _make_context()
		fake_settings = _make_settings()
		with patch("frappe_faker.utils.ai_generator._get_settings", return_value=fake_settings) as mock_gs:
			generate_records(ctx, 1, settings=None)
			mock_gs.assert_called_once()


# ---------------------------------------------------------------------------
# Gemini provider tests (mock requests.post)
# ---------------------------------------------------------------------------


class TestGeminiProvider(UnitTestCase):
	def _mock_response(self, payload: dict, status_code: int = 200):
		response = MagicMock()
		response.status_code = status_code
		response.text = json.dumps(payload)
		response.json.return_value = payload
		return response

	def test_default_gemini_endpoint(self):
		endpoint = _build_gemini_endpoint(None, "gemini-2.5-flash")
		self.assertEqual(
			endpoint,
			"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
		)

	def test_gemini_endpoint_accepts_model_path(self):
		endpoint = _build_gemini_endpoint(None, "models/gemini-2.5-flash")
		self.assertEqual(
			endpoint,
			"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
		)

	def test_gemini_endpoint_custom_model_placeholder(self):
		endpoint = _build_gemini_endpoint("https://example.test/{model}:generateContent", "gemini-test")
		self.assertEqual(endpoint, "https://example.test/gemini-test:generateContent")

	@patch("frappe_faker.utils.ai_generator.requests.post")
	def test_call_llm_dispatches_to_gemini(self, mock_post):
		mock_post.return_value = self._mock_response(
			{
				"candidates": [
					{
						"content": {
							"parts": [{"text": '[{"title": "Generated by Gemini"}]'}],
						}
					}
				]
			}
		)

		result = _call_llm(_make_gemini_settings(), "Generate a note")

		self.assertEqual(result, '[{"title": "Generated by Gemini"}]')
		call_kwargs = mock_post.call_args.kwargs
		self.assertEqual(call_kwargs["headers"]["x-goog-api-key"], "test-gemini-key")
		self.assertEqual(call_kwargs["headers"]["Content-Type"], "application/json")
		self.assertEqual(call_kwargs["json"]["contents"][0]["parts"][0]["text"], "Generate a note")
		self.assertEqual(call_kwargs["json"]["generationConfig"]["response_mime_type"], "application/json")

	@patch("frappe_faker.utils.ai_generator.requests.post")
	def test_gemini_non_200_raises_generation_error(self, mock_post):
		mock_post.return_value = self._mock_response({"error": {"message": "bad key"}}, status_code=400)

		with self.assertRaises(GenerationError):
			_call_llm(_make_gemini_settings(), "Generate a note")

	@patch("frappe_faker.utils.ai_generator.requests.post")
	def test_gemini_empty_text_raises_generation_error(self, mock_post):
		mock_post.return_value = self._mock_response(
			{
				"candidates": [
					{
						"finishReason": "SAFETY",
						"content": {"parts": []},
					}
				]
			}
		)

		with self.assertRaises(GenerationError):
			_call_llm(_make_gemini_settings(), "Generate a note")
