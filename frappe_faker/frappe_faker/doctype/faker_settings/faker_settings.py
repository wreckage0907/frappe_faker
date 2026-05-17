# Copyright (c) 2026, wreckage0907 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FakerSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ai_provider: DF.Literal["", "OpenAI", "Anthropic", "Gemini", "Ollama", "Custom"]
		api_endpoint: DF.Data | None
		api_key: DF.Password | None
		default_count: DF.Int
		model_name: DF.Data | None
	# end: auto-generated types

	pass
