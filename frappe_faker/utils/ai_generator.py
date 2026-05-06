"""
AI Generator — calls the configured LLM to generate fake data.

Supports OpenAI-compatible APIs (OpenAI, Ollama, Custom endpoints)
and Anthropic's API.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
import requests
from frappe import _

from frappe_faker.utils.prompt_builder import SYSTEM_PROMPT, build_generation_prompt


class GenerationError(Exception):
	"""Raised when data generation fails."""

	pass


def generate_records(
	context: dict[str, Any],
	count: int,
	custom_instructions: str | None = None,
	max_retries: int = 2,
	settings: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	"""
	Generate fake records using the configured AI provider.

	Args:
		context: Output from meta_analyzer.get_generation_context()
		count: Number of records to generate
		custom_instructions: Optional user instructions
		max_retries: Number of retries on parse failure
		settings: Pre-loaded Faker Settings dict (avoids repeated DB reads)

	Returns:
		List of record dicts ready for insertion.
	"""
	if settings is None:
		settings = _get_settings()
	prompt = build_generation_prompt(context, count, custom_instructions)

	last_error = None
	for attempt in range(max_retries + 1):
		try:
			raw_response = _call_llm(settings, prompt, attempt_num=attempt)
			records = _parse_response(raw_response)

			if not isinstance(records, list):
				raise GenerationError("LLM response is not a JSON array")

			# Inject doctype into each record
			doctype = context["schema"]["doctype"]
			for record in records:
				if not isinstance(record, dict):
					raise GenerationError(f"Expected record to be a dict, got {type(record).__name__}")
				record["doctype"] = doctype
				# Inject doctype into child table rows
				for fieldname, child_info in context["schema"]["child_tables"].items():
					if fieldname in record and isinstance(record[fieldname], list):
						for row in record[fieldname]:
							row["doctype"] = child_info["doctype"]

			return records

		except (json.JSONDecodeError, GenerationError) as e:
			last_error = e
			if attempt < max_retries:
				# Add error context to prompt for retry
				prompt += f"\n\n[RETRY: Previous response was invalid JSON. Error: {e}. Please output ONLY a valid JSON array.]"
				continue

	raise GenerationError(f"Failed to generate valid records after {max_retries + 1} attempts: {last_error}")


def get_settings() -> dict[str, Any]:
	"""Load Faker Settings from the database (public alias)."""
	return _get_settings()


def _get_settings() -> dict[str, Any]:
	"""Load Faker Settings from the database."""
	doc = frappe.get_single("Faker Settings")
	provider = doc.ai_provider
	if not provider:
		frappe.throw(_("Please configure AI Provider in Faker Settings"))

	return {
		"provider": provider,
		"api_key": doc.get_password("api_key") if doc.api_key else None,
		"api_endpoint": doc.api_endpoint,
		"model_name": doc.model_name,
		"default_count": int(doc.default_count or 10),
	}


def _call_llm(settings: dict[str, Any], prompt: str, attempt_num: int = 0) -> str:
	"""Dispatch to the appropriate LLM API."""
	provider = settings["provider"]

	if provider in ("OpenAI", "Custom", "Ollama"):
		return _call_openai_compatible(settings, prompt)
	elif provider == "Anthropic":
		return _call_anthropic(settings, prompt)
	else:
		raise GenerationError(f"Unsupported AI provider: {provider}")


def _call_openai_compatible(settings: dict[str, Any], prompt: str) -> str:
	"""Call an OpenAI-compatible API (works for OpenAI, Ollama, any custom endpoint)."""
	endpoint = settings["api_endpoint"]
	if not endpoint:
		if settings["provider"] == "OpenAI":
			endpoint = "https://api.openai.com/v1/chat/completions"
		elif settings["provider"] == "Ollama":
			endpoint = "http://localhost:11434/v1/chat/completions"
		else:
			frappe.throw(_("API Endpoint is required for Custom provider"))

	headers = {"Content-Type": "application/json"}
	if settings["api_key"]:
		headers["Authorization"] = f"Bearer {settings['api_key']}"

	model = settings["model_name"] or "gpt-4o-mini"

	payload = {
		"model": model,
		"messages": [
			{"role": "system", "content": SYSTEM_PROMPT},
			{"role": "user", "content": prompt},
		],
		"temperature": 0.7,
	}

	response = requests.post(endpoint, json=payload, headers=headers, timeout=300)

	if response.status_code != 200:
		raise GenerationError(f"LLM API returned {response.status_code}: {response.text[:500]}")

	try:
		data = response.json()
		return data["choices"][0]["message"]["content"]
	except (ValueError, KeyError, IndexError) as e:
		raise GenerationError(f"Unexpected OpenAI-compatible API response format: {e}")


def _call_anthropic(settings: dict[str, Any], prompt: str) -> str:
	"""Call the Anthropic Messages API."""
	endpoint = settings["api_endpoint"] or "https://api.anthropic.com/v1/messages"
	api_key = settings["api_key"]
	if not api_key:
		frappe.throw(_("API Key is required for Anthropic provider"))

	model = settings["model_name"] or "claude-sonnet-4-20250514"

	headers = {
		"Content-Type": "application/json",
		"x-api-key": api_key,
		"anthropic-version": "2023-06-01",
	}

	payload = {
		"model": model,
		"max_tokens": 8192,
		"system": SYSTEM_PROMPT,
		"messages": [{"role": "user", "content": prompt}],
	}

	response = requests.post(endpoint, json=payload, headers=headers, timeout=300)

	if response.status_code != 200:
		raise GenerationError(f"Anthropic API returned {response.status_code}: {response.text[:500]}")

	try:
		data = response.json()
		return data["content"][0]["text"]
	except (ValueError, KeyError, IndexError) as e:
		raise GenerationError(f"Unexpected Anthropic API response format: {e}")


def _parse_response(raw: str) -> list[dict[str, Any]]:
	"""Parse LLM response, handling common formatting issues."""
	text = raw.strip()

	# Strip markdown code fences if present
	if text.startswith("```"):
		# Remove first line (```json or ```)
		text = text.split("\n", 1)[1] if "\n" in text else text[3:]
		if text.endswith("```"):
			text = text[:-3]
		text = text.strip()

	return json.loads(text)
