# Copyright (c) 2026, wreckage0907 and Contributors
# See license.txt

"""
Tests for frappe_faker.utils.dependency_graph.

Pure-function tests (topological sort, depth computation) use UnitTestCase.
Tests that call resolve_dependencies() use IntegrationTestCase (needs get_meta + frappe.db).
"""

from frappe.tests import IntegrationTestCase, UnitTestCase

from frappe_faker.utils.dependency_graph import (
	_compute_depths,
	_topological_sort,
	print_dependency_tree,
	resolve_dependencies,
)

# ---------------------------------------------------------------------------
# Pure-function unit tests (no DB)
# ---------------------------------------------------------------------------


class TestTopologicalSort(UnitTestCase):
	def test_linear_chain_sorted_deps_first(self):
		# C <- B <- A  (A depends on B, B depends on C)
		graph = {"A": {"B"}, "B": {"C"}, "C": set()}
		order, cycles = _topological_sort(graph)
		self.assertEqual(cycles, [])
		self.assertLess(order.index("C"), order.index("B"))
		self.assertLess(order.index("B"), order.index("A"))

	def test_no_dependencies_any_order(self):
		graph = {"X": set(), "Y": set(), "Z": set()}
		order, cycles = _topological_sort(graph)
		self.assertEqual(set(order), {"X", "Y", "Z"})
		self.assertEqual(cycles, [])

	def test_cycle_detected(self):
		# A -> B -> A  (mutual cycle)
		graph = {"A": {"B"}, "B": {"A"}}
		order, cycles = _topological_sort(graph)
		self.assertIn("A", cycles)
		self.assertIn("B", cycles)
		# Both nodes still appear in the overall order
		self.assertIn("A", order)
		self.assertIn("B", order)

	def test_partial_cycle_with_clean_node(self):
		# C is clean; A <-> B are cyclic
		graph = {"A": {"B"}, "B": {"A"}, "C": set()}
		order, cycles = _topological_sort(graph)
		self.assertIn("C", order)
		self.assertNotIn("C", cycles)
		self.assertIn("A", cycles)
		self.assertIn("B", cycles)

	def test_all_nodes_present_in_output(self):
		graph = {"A": {"B", "C"}, "B": {"C"}, "C": set()}
		order, _cycles = _topological_sort(graph)
		self.assertEqual(set(order), {"A", "B", "C"})


class TestComputeDepths(UnitTestCase):
	def test_target_has_depth_zero(self):
		graph = {"A": {"B"}, "B": set()}
		depths = _compute_depths(graph, "A")
		self.assertEqual(depths["A"], 0)

	def test_direct_dependency_has_depth_one(self):
		graph = {"A": {"B"}, "B": set()}
		depths = _compute_depths(graph, "A")
		self.assertEqual(depths["B"], 1)

	def test_transitive_dependency_has_depth_two(self):
		graph = {"A": {"B"}, "B": {"C"}, "C": set()}
		depths = _compute_depths(graph, "A")
		self.assertEqual(depths["C"], 2)

	def test_shortest_path_wins(self):
		# A -> B -> C and A -> C directly: C should be at depth 1, not 2
		graph = {"A": {"B", "C"}, "B": {"C"}, "C": set()}
		depths = _compute_depths(graph, "A")
		self.assertEqual(depths["C"], 1)

	def test_unreachable_node_absent(self):
		# D is disconnected from A
		graph = {"A": {"B"}, "B": set(), "D": set()}
		depths = _compute_depths(graph, "A")
		self.assertNotIn("D", depths)

	def test_empty_graph(self):
		depths = _compute_depths({}, "A")
		self.assertEqual(depths, {"A": 0})


# ---------------------------------------------------------------------------
# Integration tests (require DB / frappe.get_meta)
# ---------------------------------------------------------------------------


class TestResolveDependencies(IntegrationTestCase):
	def test_note_has_no_dependencies(self):
		result = resolve_dependencies("Note")
		order = [item["doctype"] for item in result["order"]]
		self.assertIn("Note", order)
		# Note has no non-blocklisted link fields that need generation
		self.assertEqual(order, ["Note"])

	def test_note_result_structure(self):
		result = resolve_dependencies("Note")
		self.assertIn("order", result)
		self.assertIn("truncated", result)
		self.assertIn("cycles", result)
		item = result["order"][0]
		self.assertIn("doctype", item)
		self.assertIn("depth", item)
		self.assertIn("has_existing_data", item)
		self.assertIn("is_cyclic", item)

	def test_note_depth_is_zero(self):
		result = resolve_dependencies("Note")
		note_item = next(i for i in result["order"] if i["doctype"] == "Note")
		self.assertEqual(note_item["depth"], 0)

	def test_todo_contains_todo(self):
		result = resolve_dependencies("ToDo")
		order = [item["doctype"] for item in result["order"]]
		self.assertIn("ToDo", order)

	def test_todo_blocklisted_types_not_in_deps(self):
		from frappe_faker.utils.constants import SYSTEM_DOCTYPE_BLOCKLIST

		result = resolve_dependencies("ToDo")
		# Only the root doctype can bypass the blocklist.
		# No dep should be in the blocklist (ToDo itself is not blocklisted).
		non_target_order = [i["doctype"] for i in result["order"] if i["doctype"] != "ToDo"]
		for dt in non_target_order:
			self.assertNotIn(dt, SYSTEM_DOCTYPE_BLOCKLIST, f"{dt} is blocklisted but appeared as a dep")

	def test_skip_removes_doctype_from_order(self):
		# Resolve without skip to get the full list
		full = resolve_dependencies("ToDo")
		full_doctypes = {i["doctype"] for i in full["order"]}
		# Pick any dep to skip (if there are any beyond ToDo itself)
		deps = full_doctypes - {"ToDo"}
		if not deps:
			self.skipTest("ToDo has no non-blocked deps to skip in this environment")
		to_skip = next(iter(deps))
		skipped = resolve_dependencies("ToDo", skip={to_skip})
		skipped_doctypes = {i["doctype"] for i in skipped["order"]}
		self.assertNotIn(to_skip, skipped_doctypes)

	def test_has_existing_data_is_bool(self):
		result = resolve_dependencies("Note")
		for item in result["order"]:
			self.assertIsInstance(item["has_existing_data"], bool)

	def test_print_dependency_tree_returns_string(self):
		tree = print_dependency_tree("Note")
		self.assertIsInstance(tree, str)
		self.assertIn("Note", tree)
		self.assertGreater(len(tree), 0)
