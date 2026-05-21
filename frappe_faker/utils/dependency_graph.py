"""
Dependency Graph — resolves the generation order for doctypes.

Given a target doctype, builds a DAG of all its Link field dependencies,
performs topological sort, and returns the order in which doctypes should
be generated so that all references are satisfied.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import frappe

from frappe_faker.utils.constants import SYSTEM_DOCTYPE_BLOCKLIST
from frappe_faker.utils.meta_analyzer import analyze_doctype

# ---------------------------------------------------------------------------
# Adjacency map cache — built eagerly on after_migrate, persisted to file + Redis
# ---------------------------------------------------------------------------

_REDIS_KEY = "frappe_faker_dep_adjacency"
_REDIS_TTL = 86400 * 30  # 30 days


def _cache_file_path() -> str:
	return frappe.get_site_path("frappe_faker_dep_index.json")


def _load_adjacency_map() -> dict[str, list[str]] | None:
	"""Load cached adjacency map from Redis (fast) then file (durable). Returns None on miss."""
	try:
		cached = frappe.cache.get_value(_REDIS_KEY)
		if cached:
			return cached
	except Exception:
		pass
	try:
		path = _cache_file_path()
		if os.path.exists(path):
			with open(path) as f:  # nosemgrep: python.lang.security.audit.path-traversal.path-traversal-open
				return json.load(f)
	except Exception:
		pass
	return None


def _save_adjacency_map(adj: dict[str, list[str]]) -> None:
	"""Atomically write adjacency map to file and prime Redis."""
	file_saved = False
	path = _cache_file_path()
	try:
		dir_ = os.path.dirname(path)
		with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as tmp:
			json.dump(adj, tmp)
			tmp.flush()
			tmp_path = tmp.name
		os.replace(tmp_path, path)
		file_saved = True
	except Exception:
		pass

	redis_saved = False
	try:
		frappe.cache.set_value(_REDIS_KEY, adj, expires_in_sec=_REDIS_TTL)
		redis_saved = True
	except Exception:
		pass

	if not file_saved and not redis_saved:
		raise RuntimeError("frappe_faker: failed to persist dependency adjacency map to both file and Redis")


def _build_global_adjacency_map() -> dict[str, list[str]]:
	"""Scan every non-child DocType and return doctype → direct link dependencies."""
	all_doctypes: list[str] = frappe.get_all("DocType", filters={"istable": 0}, pluck="name")
	adj: dict[str, list[str]] = {}
	for dt in all_doctypes:
		try:
			schema = analyze_doctype(dt)
			adj[dt] = schema["link_dependencies"]
		except Exception:
			adj[dt] = []
	return adj


def after_migrate() -> None:
	"""Hook: rebuild and persist the dependency adjacency map after every bench migrate."""
	import click

	try:
		click.echo("Building frappe_faker dependency index...", nl=False)
		adj = _build_global_adjacency_map()
		_save_adjacency_map(adj)
		click.echo(f" {len(adj)} doctypes indexed")
	except Exception:
		click.echo(" failed (see Error Log)")
		frappe.log_error("frappe_faker: failed to build dependency adjacency cache")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_dependencies(
	doctype: str,
	skip: set[str] | None = None,
	max_depth: int = 5,
) -> dict[str, Any]:
	"""
	Resolve the full dependency tree for a doctype.

	Returns a dict with:
	- order: list of dicts in generation order (dependencies first)
	- truncated: list of doctypes that were cut off by max_depth
	- cycles: list of doctypes involved in circular dependencies

	Args:
		doctype: The target doctype to generate data for
		skip: Set of doctype names to skip (user already has data)
		max_depth: Maximum recursion depth to prevent infinite loops
	"""
	skip = skip or set()
	graph: dict[str, set[str]] = {}  # doctype -> set of dependencies
	visited: set[str] = set()
	truncated: list[str] = []

	adj_cache = _load_adjacency_map()
	_build_graph(
		doctype,
		graph,
		visited,
		skip,
		max_depth,
		current_depth=0,
		truncated=truncated,
		is_root=True,
		adj_cache=adj_cache,
	)

	# Topological sort
	order, cycles = _topological_sort(graph)

	# Compute all depths in one BFS pass from the target (O(N) instead of O(N²))
	depths = _compute_depths(graph, doctype)

	# Batch check for existing data (one frappe.db.count per doctype, but avoid
	# repeated calls for the same doctype if it appears multiple times)
	result = []
	for dt in order:
		has_data = _has_existing_data(dt)
		result.append(
			{
				"doctype": dt,
				"depth": depths.get(dt, -1),
				"has_existing_data": has_data,
				"is_cyclic": dt in cycles,
			}
		)

	return {
		"order": result,
		"truncated": truncated,
		"cycles": cycles,
	}


def _build_graph(
	doctype: str,
	graph: dict[str, set[str]],
	visited: set[str],
	skip: set[str],
	max_depth: int,
	current_depth: int,
	truncated: list[str],
	is_root: bool = False,
	adj_cache: dict[str, list[str]] | None = None,
) -> None:
	"""Recursively build the dependency graph."""
	if doctype in visited:
		return
	# Only apply blocklist to non-root doctypes. The root is explicitly requested by the user.
	if not is_root and doctype in SYSTEM_DOCTYPE_BLOCKLIST:
		return
	if doctype in skip:
		return
	if current_depth > max_depth:
		truncated.append(doctype)
		return

	visited.add(doctype)

	# Use pre-built adjacency cache when available to avoid repeated get_meta() calls
	if adj_cache is not None and doctype in adj_cache:
		raw_deps: list[str] = adj_cache[doctype]
	else:
		schema = analyze_doctype(doctype)
		raw_deps = schema["link_dependencies"]

	deps: set[str] = set()

	for dep in raw_deps:
		if dep == doctype:
			continue  # Self-reference
		if dep in SYSTEM_DOCTYPE_BLOCKLIST or dep in skip:
			continue
		deps.add(dep)
		# Recurse into dependency
		_build_graph(dep, graph, visited, skip, max_depth, current_depth + 1, truncated, adj_cache=adj_cache)

	graph[doctype] = deps


def _topological_sort(graph: dict[str, set[str]]) -> tuple[list[str], list[str]]:
	"""
	Kahn's algorithm for topological sort.
	Returns (ordered_list, cyclic_nodes).
	ordered_list: doctypes in generation order (dependencies first).
	cyclic_nodes: doctypes involved in cycles (appended at end in arbitrary order).
	"""
	# in_degree[node] = number of its dependencies that are also in the graph
	in_degree: dict[str, int] = {node: 0 for node in graph}
	for node, deps in graph.items():
		for dep in deps:
			if dep in graph:
				in_degree[node] += 1

	# Start with nodes that have no unresolved dependencies
	queue = sorted(node for node, deg in in_degree.items() if deg == 0)
	result: list[str] = []

	while queue:
		node = queue.pop(0)
		result.append(node)

		# For each other node that depends on `node`, reduce their in-degree
		for other, deps in graph.items():
			if node in deps and other not in result:
				in_degree[other] -= 1
				if in_degree[other] == 0:
					queue.append(other)
		queue.sort()

	# Any remaining nodes are in cycles
	cycles = [node for node in graph if node not in result]
	result.extend(sorted(cycles))

	return result, cycles


def _compute_depths(graph: dict[str, set[str]], target: str) -> dict[str, int]:
	"""
	Compute depths for all nodes relative to the target in one BFS pass (O(N)).
	target has depth 0, its direct deps have depth 1, etc.
	"""
	from collections import deque

	depths: dict[str, int] = {target: 0}
	queue = deque([target])
	while queue:
		current = queue.popleft()
		for dep in graph.get(current, set()):
			if dep not in depths:
				depths[dep] = depths[current] + 1
				queue.append(dep)
	return depths


def _has_existing_data(doctype: str) -> bool:
	"""Check if a doctype already has records."""
	try:
		return frappe.db.count(doctype) > 0
	except Exception:
		return False


def print_dependency_tree(doctype: str, skip: set[str] | None = None) -> str:
	"""Return a human-readable dependency tree string."""
	result = resolve_dependencies(doctype, skip=skip)
	order = result["order"]
	lines = []
	lines.append(f"Generation order for: {doctype}")
	lines.append("=" * 50)
	for i, item in enumerate(order, 1):
		status = "has data" if item["has_existing_data"] else "needs generation"
		marker = "~" if item.get("is_cyclic") else ""
		indent = "  " * item["depth"] if item["depth"] >= 0 else ""
		lines.append(f"  {i}. {indent}{marker}{item['doctype']} [{status}]")
	if result["truncated"]:
		lines.append(f"\n  WARNING: Truncated at depth {5}: {', '.join(result['truncated'])}")
	if result["cycles"]:
		lines.append(f"\n  WARNING: Circular dependencies detected: {', '.join(result['cycles'])}")
	lines.append("=" * 50)
	return "\n".join(lines)
