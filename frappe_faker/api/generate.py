"""
API endpoints for Frappe Faker — whitelisted methods callable from the browser or CLI.

All methods require System Manager role.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def _require_system_manager() -> None:
	if not frappe.has_permission("Faker Settings", "write"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def enqueue_generation(
	doctype: str,
	count: int | None = None,
	skip: str | list | None = None,
	custom_instructions: str | None = None,
	resolve_deps: bool | str = True,
	fast_insert: bool | str = True,
) -> dict[str, Any]:
	"""
	Enqueue a background generation job and return a job ID for polling.

	Args:
		doctype: Target doctype to generate records for
		count: Number of records (defaults to Faker Settings default_count)
		skip: JSON string or list of doctype names to skip
		custom_instructions: Extra prompt instructions for the LLM
		resolve_deps: Whether to auto-generate dependencies first
		fast_insert: Use db_insert() path (bypasses Python hooks, much faster)

	Returns:
		{"job_id": str}
	"""
	_require_system_manager()

	# Normalise types — values from HTTP come in as strings
	skip_list: list[str] = _parse_list(skip)
	resolve_deps_bool = (
		frappe.parse_json(resolve_deps) if isinstance(resolve_deps, str) else bool(resolve_deps)
	)
	fast_insert_bool = frappe.parse_json(fast_insert) if isinstance(fast_insert, str) else bool(fast_insert)
	count_int = int(count) if count is not None else None

	job = frappe.enqueue(
		"frappe_faker.utils.inserter.generate_and_insert",
		queue="long",
		timeout=3600,
		# --- function kwargs ---
		doctype=doctype,
		count=count_int,
		skip=skip_list,  # list, not set — RQ args must be JSON-serialisable
		custom_instructions=custom_instructions or None,
		resolve_deps=resolve_deps_bool,
		fast_insert=fast_insert_bool,
	)

	return {"job_id": job.id}


@frappe.whitelist()
def get_job_status(job_id: str) -> dict[str, Any]:
	"""
	Poll the status of an enqueued generation job.

	Returns a dict with at least:
	  - status: "queued" | "started" | "finished" | "failed" | "deferred" | "not_found"
	  - result: the return value of generate_and_insert (only when finished)
	  - exc: exception string (only when failed)
	"""
	_require_system_manager()

	try:
		rq_job_doc = frappe.get_doc("RQ Job", job_id)
		payload: dict[str, Any] = {
			"job_id": job_id,
			"status": rq_job_doc.status,
		}
		if rq_job_doc.status == "finished":
			# serialize_job() doesn't expose the return value, so read it from the
			# underlying RQ Job object directly via the .job property.
			# Fall back to direct RQ if the result backend is unavailable or the
			# RQ/Frappe version doesn't support latest_result().
			try:
				job_result = rq_job_doc.job.latest_result()
				payload["result"] = job_result.return_value if job_result else {}
			except Exception:
				return _get_rq_job_status_direct(job_id)
		if rq_job_doc.status == "failed":
			payload["exc"] = rq_job_doc.exc_info or "Unknown error"
		return payload

	except frappe.DoesNotExistError:
		# Fall back to direct RQ inspection (older Frappe versions)
		return _get_rq_job_status_direct(job_id)


@frappe.whitelist()
def get_faker_settings() -> dict[str, Any]:
	"""Return current Faker Settings for UI defaults."""
	_require_system_manager()
	settings = frappe.get_single("Faker Settings")
	return {
		"default_count": int(settings.default_count or 10),
		"provider": settings.ai_provider or "",
		"model_name": settings.model_name or "",
	}


@frappe.whitelist()
def get_dependency_tree(doctype: str, skip: str | list | None = None) -> dict[str, Any]:
	"""Return the resolved dependency order for a doctype (for UI preview)."""
	_require_system_manager()
	from frappe_faker.utils.dependency_graph import resolve_dependencies

	return resolve_dependencies(doctype, skip=set(_parse_list(skip)))


@frappe.whitelist()
def generate_sync(
	doctype: str,
	count: int | None = None,
	skip: str | list | None = None,
	custom_instructions: str | None = None,
	resolve_deps: bool | str = True,
	fast_insert: bool | str = False,
) -> dict[str, Any]:
	"""
	Synchronous generation — runs inline in the request.

	Use only for small counts or interactive testing. For production use
	`enqueue_generation` so the work happens in a background worker.

	Returns the full result dict from generate_and_insert.
	"""
	_require_system_manager()

	from frappe_faker.utils.inserter import generate_and_insert

	skip_list = _parse_list(skip)
	resolve_deps_bool = (
		frappe.parse_json(resolve_deps) if isinstance(resolve_deps, str) else bool(resolve_deps)
	)
	fast_insert_bool = frappe.parse_json(fast_insert) if isinstance(fast_insert, str) else bool(fast_insert)
	count_int = int(count) if count is not None else None

	return generate_and_insert(
		doctype=doctype,
		count=count_int,
		skip=skip_list,
		custom_instructions=custom_instructions or None,
		resolve_deps=resolve_deps_bool,
		fast_insert=fast_insert_bool,
	)


@frappe.whitelist()
def rollback_batch(batch_name: str) -> dict[str, Any]:
	"""
	Delete all records created in a Faker Batch and mark it as rolled back.

	Records are deleted in reverse insertion order (dependency-safe).
	Already-rolled-back items are skipped. Partial failures are recorded
	in the response rather than aborting the rollback.

	Returns:
		{"deleted": int, "errors": list, "status": str}
	"""
	_require_system_manager()

	batch = frappe.get_doc("Faker Batch", batch_name)

	# Idempotent — return current state immediately if already rolled back.
	if batch.status in ("Rolled Back", "Partially Rolled Back"):
		return {"deleted": 0, "errors": [], "status": batch.status, "already_rolled_back": True}

	deleted = 0
	errors: list[dict[str, Any]] = []

	for item in reversed(batch.items):
		if item.rolled_back:
			continue
		try:
			frappe.delete_doc(item.doctype_name, item.record_name, force=True, ignore_missing=True)
			item.rolled_back = 1
			deleted += 1
		except Exception as e:
			errors.append({"doctype": item.doctype_name, "name": item.record_name, "error": str(e)})

	batch.status = "Rolled Back" if not errors else "Partially Rolled Back"
	batch.completed_at = frappe.utils.now()
	batch.save()
	frappe.db.commit()  # nosemgrep

	return {"deleted": deleted, "errors": errors, "status": batch.status, "already_rolled_back": False}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_list(value: str | list | None) -> list[str]:
	"""Normalise skip parameter: JSON string, Python list, comma string, or None."""
	if not value:
		return []
	if isinstance(value, list):
		return [str(v) for v in value]
	# Try JSON first
	try:
		parsed = frappe.parse_json(value)
		if isinstance(parsed, list):
			return [str(v) for v in parsed]
	except Exception:
		pass
	# Fall back to comma-separated
	return [v.strip() for v in str(value).split(",") if v.strip()]


def _get_rq_job_status_direct(job_id: str) -> dict[str, Any]:
	"""Direct RQ job status lookup for Frappe versions without RQ Job doctype."""
	try:
		from frappe.utils.background_jobs import get_redis_conn
		from rq.job import Job

		conn = get_redis_conn()
		job = Job.fetch(job_id, connection=conn)
		status = job.get_status()
		payload: dict[str, Any] = {"job_id": job_id, "status": str(status)}
		if status == "finished":
			payload["result"] = job.result
		if status == "failed":
			payload["exc"] = str(job.exc_info or "Unknown error")
		return payload
	except Exception:
		return {"job_id": job_id, "status": "not_found"}
