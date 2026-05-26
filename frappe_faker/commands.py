"""
Frappe Faker CLI — bench commands for generating and managing fake data.

Usage:
    bench --site <site> faker generate --doctype "Timesheet" --count 5
    bench --site <site> faker plan --doctype "Timesheet"
    bench --site <site> faker cleanup --batch FAKER-BATCH-XXXX
"""

from __future__ import annotations

import click
from frappe.commands import pass_context


@click.group()
def faker() -> None:
	"""Frappe Faker — generate fake data for Frappe doctypes."""


@faker.command("generate")
@click.option("--doctype", "-d", required=True, help="Target DocType to generate records for")
@click.option("--count", "-n", default=None, type=int, help="Number of records (default from Faker Settings)")
@click.option("--skip", default=None, help="Comma-separated DocTypes to skip during dependency resolution")
@click.option(
	"--fast-insert/--no-fast-insert", default=True, help="Use fast db_insert path (bypasses Python hooks)"
)
@click.option("--instructions", default=None, help="Custom free-text instructions for the LLM")
@pass_context
def generate_cmd(
	context: click.Context,
	doctype: str,
	count: int | None,
	skip: str | None,
	fast_insert: bool,
	instructions: str | None,
) -> None:
	"""Generate fake records for a DocType."""
	import frappe

	site = context.sites[0]
	frappe.init(site=site)
	frappe.connect()
	try:
		frappe.set_user("Administrator")  # nosemgrep
		from frappe_faker.utils.inserter import generate_and_insert

		skip_list = [s.strip() for s in skip.split(",") if s.strip()] if skip else []
		count_label = str(count) if count is not None else "default"
		click.echo(f"Generating {count_label} record(s) for {doctype}...")

		result = generate_and_insert(
			doctype=doctype,
			count=count,
			skip=skip_list,
			fast_insert=fast_insert,
			custom_instructions=instructions,
		)

		batch = result.get("batch_name") or "N/A"
		click.echo(
			f"\nBatch: {batch} | Created: {result['total_created']} | Failed: {result['total_failed']}"
		)
		for r in result.get("results", []):
			status = f"{r['created_count']} created"
			if r.get("failed_count"):
				status += f", {r['failed_count']} failed"
			if r.get("error"):
				status += f" — {r['error']}"
			click.echo(f"  {r['doctype']}: {status}")

		frappe.db.commit()  # nosemgrep
	finally:
		frappe.destroy()


@faker.command("plan")
@click.option("--doctype", "-d", required=True, help="Target DocType to inspect")
@pass_context
def plan_cmd(context: click.Context, doctype: str) -> None:
	"""Show the dependency tree for a DocType without generating anything."""
	import frappe

	site = context.sites[0]
	frappe.init(site=site)
	frappe.connect()
	try:
		frappe.set_user("Administrator")  # nosemgrep
		from frappe_faker.utils.dependency_graph import resolve_dependencies

		result = resolve_dependencies(doctype)
		click.echo(f"\nDependency plan for: {doctype}\n")

		for item in result["order"]:
			indent = "  " * item["depth"]
			badges = []
			if item["depth"] == 0:
				badges.append("[Target]")
			if item.get("has_existing_data"):
				badges.append("[Has data — will skip]")
			if item.get("is_cyclic"):
				badges.append("[Cyclic]")
			badge_str = ("  " + " ".join(badges)) if badges else ""
			click.echo(f"{indent}{item['doctype']}{badge_str}")

		if result.get("truncated"):
			click.echo("\n  [!] Tree truncated at max depth (5). Some dependencies may not be shown.")
		if result.get("cycles"):
			click.echo(f"\n  [!] Cyclic dependencies: {', '.join(result['cycles'])}")
	finally:
		frappe.destroy()


@faker.command("cleanup")
@click.option("--batch", "-b", required=True, help="Batch name to rollback (e.g. abc123xyz)")
@pass_context
def cleanup_cmd(context: click.Context, batch: str) -> None:
	"""Rollback all records created in a batch."""
	import frappe

	site = context.sites[0]
	frappe.init(site=site)
	frappe.connect()
	try:
		frappe.set_user("Administrator")  # nosemgrep
		from frappe_faker.api.generate import rollback_batch

		click.echo(f"Rolling back batch {batch}...")
		result = rollback_batch(batch_name=batch)
		click.echo(f"Deleted {result['deleted']} record(s). Status: {result['status']}")

		if result.get("errors"):
			click.echo(f"  {len(result['errors'])} error(s):", err=True)
			for err in result["errors"]:
				click.echo(f"    {err['doctype']} {err['name']}: {err['error']}", err=True)
	finally:
		frappe.destroy()


commands = [faker]
