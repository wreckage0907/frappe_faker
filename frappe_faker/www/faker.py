import frappe
from frappe import _
from frappe.translate import get_messages_for_boot, get_translated_doctypes
from frappe.utils import get_system_timezone

no_cache = 1


def get_context():
	from frappe_faker.api.permission import has_app_permission

	if not has_app_permission():
		frappe.throw(_("You do not have permission to access Frappe Faker"), frappe.PermissionError)

	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	if not frappe.conf.developer_mode:
		frappe.throw(_("This method is only meant for developer mode"))
	return get_boot()


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"default_route": get_default_route(),
			"site_name": frappe.local.site,
			"read_only_mode": frappe.flags.read_only,
			"csrf_token": frappe.sessions.get_csrf_token(),
			"sysdefaults": frappe.defaults.get_defaults(),
			"translated_doctypes": get_translated_doctypes(),
			"translated_messages": get_messages_for_boot(),
			"timezone": {
				"system": get_system_timezone(),
				"user": frappe.db.get_value("User", frappe.session.user, "time_zone")
				or get_system_timezone(),
			},
		}
	)


def get_default_route():
	return "/faker"
