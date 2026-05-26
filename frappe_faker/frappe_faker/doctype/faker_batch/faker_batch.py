# Copyright (c) 2026, wreckage0907 and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class FakerBatch(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from frappe_faker.frappe_faker.doctype.faker_batch_item.faker_batch_item import FakerBatchItem

		completed_at: DF.Datetime | None
		created_by: DF.Link | None
		items: DF.Table[FakerBatchItem]
		started_at: DF.Datetime | None
		status: DF.Literal["Running", "Completed", "Failed", "Rolled Back", "Partially Rolled Back"]
		target_doctype: DF.Data | None
	# end: auto-generated types

	pass
