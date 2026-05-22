import frappe


def has_app_permission():
	if frappe.session.user == "Administrator":
		return True
	return frappe.has_permission("Faker Settings", ptype="read", raise_exception=False)
