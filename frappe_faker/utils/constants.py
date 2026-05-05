# Doctypes that should never be auto-generated as dependencies.
# These are core system doctypes that either already exist or should not have fake data.
SYSTEM_DOCTYPE_BLOCKLIST = frozenset(
	[
		# Core framework
		"User",
		"Role",
		"Role Profile",
		"DocType",
		"Module Def",
		"Custom Field",
		"Property Setter",
		"Print Format",
		"Report",
		"Page",
		"Web Page",
		"Website Settings",
		"System Settings",
		# Permissions & workflow
		"Workflow",
		"Workflow State",
		"Workflow Action",
		"User Permission",
		"Has Role",
		# Communication
		"Communication",
		"Email Account",
		"Email Domain",
		"Notification",
		# File & media
		"File",
		# Misc system
		"Error Log",
		"Activity Log",
		"Comment",
		"Version",
		"Scheduled Job Type",
		"Server Script",
		"Client Script",
		# Setup (usually pre-configured)
		"Company",
		"Country",
		"Currency",
		"Fiscal Year",
	]
)

# Field types that don't hold user data (layout/UI fields)
LAYOUT_FIELDTYPES = frozenset(
	[
		"Section Break",
		"Column Break",
		"Tab Break",
		"HTML",
		"Heading",
		"Button",
		"Fold",
	]
)

# Field types that represent relationships
LINK_FIELDTYPES = frozenset(["Link", "Dynamic Link"])

# Field types for child tables
TABLE_FIELDTYPES = frozenset(["Table", "Table MultiSelect"])
