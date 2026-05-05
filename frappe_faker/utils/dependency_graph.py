"""
Dependency Graph — resolves the generation order for doctypes.

Given a target doctype, builds a DAG of all its Link field dependencies,
performs topological sort, and returns the order in which doctypes should
be generated so that all references are satisfied.
"""

from __future__ import annotations

from typing import Any

import frappe

from frappe_faker.utils.constants import SYSTEM_DOCTYPE_BLOCKLIST
from frappe_faker.utils.meta_analyzer import analyze_doctype


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

	_build_graph(doctype, graph, visited, skip, max_depth, current_depth=0, truncated=truncated, is_root=True)

	# Topological sort
	order, cycles = _topological_sort(graph)

	# Enrich with metadata
	result = []
	for dt in order:
		depth = _get_depth(dt, graph, doctype)
		has_data = _has_existing_data(dt)
		result.append(
			{
				"doctype": dt,
				"depth": depth,
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
	schema = analyze_doctype(doctype)
	deps: set[str] = set()

	for dep in schema["link_dependencies"]:
		if dep == doctype:
			continue  # Self-reference
		if dep in SYSTEM_DOCTYPE_BLOCKLIST or dep in skip:
			continue
		deps.add(dep)
		# Recurse into dependency
		_build_graph(dep, graph, visited, skip, max_depth, current_depth + 1, truncated)

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


def _get_depth(doctype: str, graph: dict[str, set[str]], target: str) -> int:
	"""Get the depth of a doctype relative to the target (0 = target itself)."""
	if doctype == target:
		return 0

	# BFS from target
	from collections import deque

	queue = deque([(target, 0)])
	seen = {target}
	while queue:
		current, depth = queue.popleft()
		for dep in graph.get(current, set()):
			if dep == doctype:
				return depth + 1
			if dep not in seen:
				seen.add(dep)
				queue.append((dep, depth + 1))
	return -1  # not reachable (shouldn't happen)


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
