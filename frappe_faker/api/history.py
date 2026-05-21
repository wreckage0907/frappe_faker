"""
API endpoints for Faker Run history — whitelisted methods callable from the browser.

All methods require System Manager role.
"""

from __future__ import annotations

import frappe
from frappe import _


def _require_system_manager() -> None:
	if not frappe.has_permission("Faker Settings", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def add_run(
	target_doctype: str,
	count_requested: int,
	total_created: int,
	total_failed: int,
	result: str,
) -> dict:
	"""
	Record a completed generation run for the current user.

	`result` is a JSON string containing the full result payload from
	generate_and_insert — stored in the JSON field for the detail view.
	"""
	_require_system_manager()

	total_created = int(total_created)
	total_failed = int(total_failed)

	if total_failed == 0:
		status = "Success"
	elif total_created == 0:
		status = "Failed"
	else:
		status = "Partial"

	doc = frappe.get_doc(
		{
			"doctype": "Faker Run",
			"target_doctype": target_doctype,
			"count_requested": int(count_requested),
			"total_created": total_created,
			"total_failed": total_failed,
			"status": status,
			"result": frappe.parse_json(result) if isinstance(result, str) else result,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist()
def get_runs(limit: int = 20) -> list:
	"""Return the last N Faker Run records owned by the current user, newest first."""
	_require_system_manager()
	rows = frappe.get_all(
		"Faker Run",
		filters={"owner": frappe.session.user},
		fields=[
			"name",
			"target_doctype",
			"count_requested",
			"total_created",
			"total_failed",
			"status",
			"creation",
			"result",
		],
		order_by="creation desc",
		limit=int(limit),
	)
	# frappe.get_all() returns JSON fields as raw strings in some Frappe versions;
	# parse them here so the frontend always receives a plain object.
	for row in rows:
		if isinstance(row.get("result"), str):
			row["result"] = frappe.parse_json(row["result"])
	return rows


@frappe.whitelist()
def clear_runs() -> dict:
	"""Delete all Faker Run records owned by the current user."""
	_require_system_manager()
	names = frappe.get_all(
		"Faker Run",
		filters={"owner": frappe.session.user},
		pluck="name",
	)
	for name in names:
		frappe.delete_doc("Faker Run", name, ignore_permissions=True)
	if names:
		frappe.db.commit()
	return {"deleted": len(names)}
