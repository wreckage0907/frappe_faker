"""
Bench CLI commands for Frappe Faker.

Exposed as `bench --site <site> faker <subcommand>`:

  faker plan      — print the dependency generation order for a DocType
  faker generate  — generate fake records for a DocType (inline)
  faker cleanup   — roll back (delete) all records created by a batch

Discovered by bench via the module-level `commands` list at the bottom.
"""

import click
import frappe
from frappe.commands import get_site, pass_context


@click.group()
def faker():
	"""Generate and manage fake test data with Frappe Faker."""
	pass


@faker.command("plan")
@click.option("--doctype", required=True, help="Target DocType to plan generation for")
@click.option("--skip", default="", help="Comma-separated doctypes to skip")
@pass_context
def plan(context, doctype, skip):
	"""Print the dependency generation order for a DocType (no data is created)."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		from frappe_faker.utils.dependency_graph import print_dependency_tree

		skip_set = {s.strip() for s in skip.split(",") if s.strip()}
		click.echo(print_dependency_tree(doctype, skip=skip_set))
	finally:
		frappe.destroy()


@faker.command("generate")
@click.option("--doctype", required=True, help="Target DocType to generate records for")
@click.option("--count", type=int, default=None, help="Number of records (defaults to Faker Settings)")
@click.option("--skip", default="", help="Comma-separated doctypes to skip")
@click.option("--instructions", default=None, help="Free-text instructions passed to the LLM")
@click.option("--no-deps", is_flag=True, default=False, help="Do not auto-generate linked dependencies")
@click.option(
	"--standard-insert",
	is_flag=True,
	default=False,
	help="Use the standard insert path (runs Python hooks) instead of fast db_insert",
)
@pass_context
def generate(context, doctype, count, skip, instructions, no_deps, standard_insert):
	"""Generate fake records for a DocType. Prints the batch name for later cleanup."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	frappe.set_user("Administrator")
	try:
		from frappe_faker.utils.inserter import generate_and_insert

		skip_list = [s.strip() for s in skip.split(",") if s.strip()]
		result = generate_and_insert(
			doctype=doctype,
			count=count,
			skip=skip_list,
			custom_instructions=instructions,
			resolve_deps=not no_deps,
			fast_insert=not standard_insert,
		)
		_print_result(result)
	finally:
		frappe.destroy()


@faker.command("cleanup")
@click.option("--batch", "batch_name", required=True, help="Faker Batch name to roll back")
@pass_context
def cleanup(context, batch_name):
	"""Roll back a batch: delete every record it created, in dependency-safe order."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	frappe.set_user("Administrator")
	try:
		from frappe_faker.api.generate import rollback_batch

		if not frappe.db.exists("Faker Batch", batch_name):
			raise click.ClickException(f"Faker Batch '{batch_name}' not found")

		resp = rollback_batch(batch_name)
		click.echo(f"Batch {resp['batch_name']}: {resp['status']} — deleted {resp['deleted']} records")
		for e in resp.get("errors", []):
			click.echo(f"  ! {e['doctype']} {e['name']}: {e['error']}")
	finally:
		frappe.destroy()


def _print_result(result):
	"""Render a generate_and_insert result dict for the terminal."""
	click.echo("")
	click.echo(f"Batch:   {result.get('batch_name')}")
	click.echo(f"Target:  {result['target']}  (requested {result['count_requested']})")
	click.echo(f"Created: {result['total_created']}   Failed: {result['total_failed']}")
	for r in result["results"]:
		line = f"  - {r['doctype']}: {r.get('created_count', 0)} created, {r.get('failed_count', 0)} failed"
		if r.get("error"):
			line += f"  ({r['error']})"
		click.echo(line)
	if result.get("batch_name") and result.get("total_created"):
		click.echo("")
		click.echo(f"Roll back with:  bench --site <site> faker cleanup --batch {result['batch_name']}")


commands = [faker]
