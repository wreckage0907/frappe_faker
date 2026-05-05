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
) -> list[dict[str, Any]]:
	"""
	Resolve the full dependency tree for a doctype.

	Returns a list of dicts in generation order (dependencies first):
	[
		{"doctype": "Activity Type", "depth": 2, "has_existing_data": True},
		{"doctype": "Project", "depth": 1, "has_existing_data": False},
		{"doctype": "Timesheet", "depth": 0, "has_existing_data": False},
	]

	Args:
		doctype: The target doctype to generate data for
		skip: Set of doctype names to skip (user already has data)
		max_depth: Maximum recursion depth to prevent infinite loops
	"""
	skip = skip or set()
	graph: dict[str, set[str]] = {}  # doctype -> set of dependencies
	visited: set[str] = set()

	_build_graph(doctype, graph, visited, skip, max_depth, current_depth=0)

	# Topological sort
	order = _topological_sort(graph)

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
			}
		)

	return result


def _build_graph(
	doctype: str,
	graph: dict[str, set[str]],
	visited: set[str],
	skip: set[str],
	max_depth: int,
	current_depth: int,
) -> None:
	"""Recursively build the dependency graph."""
	if doctype in visited or doctype in SYSTEM_DOCTYPE_BLOCKLIST or doctype in skip:
		return
	if current_depth > max_depth:
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
		_build_graph(dep, graph, visited, skip, max_depth, current_depth + 1)

	graph[doctype] = deps


def _topological_sort(graph: dict[str, set[str]]) -> list[str]:
	"""
	Kahn's algorithm for topological sort.
	Returns doctypes in order: dependencies first, target last.
	Handles cycles by breaking them (nodes still in graph after sort are cyclic).
	"""
	# Compute in-degrees (only for nodes in our graph)
	in_degree: dict[str, int] = {node: 0 for node in graph}
	for _node, deps in graph.items():
		for dep in deps:
			if dep in in_degree:
				in_degree[dep] = in_degree.get(dep, 0)  # ensure exists
				# dep is depended upon by node, so dep must come first
				# Actually: node depends on dep, so dep has no extra in-degree from this
				pass

	# Reverse: who depends on whom
	# If A depends on B, B must come before A. So edge is B -> A in generation order.
	# in_degree[A] = number of deps A has that are in the graph
	in_degree = {node: 0 for node in graph}
	for node, deps in graph.items():
		for dep in deps:
			if dep in graph:
				in_degree[node] += 1  # node can't be generated until dep is done

	# Start with nodes that have no dependencies within the graph
	queue = [node for node, deg in in_degree.items() if deg == 0]
	result: list[str] = []

	while queue:
		# Sort for deterministic output
		queue.sort()
		node = queue.pop(0)
		result.append(node)

		# For each other node that depends on `node`, reduce their in-degree
		for other, deps in graph.items():
			if node in deps and other not in result:
				in_degree[other] -= 1
				if in_degree[other] == 0:
					queue.append(other)

	# Any remaining nodes are in cycles — append them anyway
	for node in graph:
		if node not in result:
			result.append(node)

	return result


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
	order = resolve_dependencies(doctype, skip=skip)
	lines = []
	lines.append(f"Generation order for: {doctype}")
	lines.append("=" * 50)
	for i, item in enumerate(order, 1):
		status = "✓ has data" if item["has_existing_data"] else "○ needs generation"
		indent = "  " * item["depth"] if item["depth"] >= 0 else ""
		lines.append(f"  {i}. {indent}{item['doctype']} [{status}]")
	lines.append("=" * 50)
	return "\n".join(lines)
