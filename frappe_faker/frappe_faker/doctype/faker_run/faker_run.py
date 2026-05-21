# Copyright (c) 2026, wreckage0907 and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class FakerRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		count_requested: DF.Int
		result: DF.JSON | None
		status: DF.Literal["Success", "Partial", "Failed"]
		target_doctype: DF.Data | None
		total_created: DF.Int
		total_failed: DF.Int
	# end: auto-generated types

	pass
