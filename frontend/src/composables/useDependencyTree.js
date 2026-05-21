import { ref } from "vue";
import { call } from "frappe-ui";

export function useDependencyTree() {
	const tree = ref(null);
	const loading = ref(false);
	const error = ref(null);
	let debounceTimer = null;

	async function fetchTree(doctype, skip = []) {
		if (!doctype) {
			tree.value = null;
			return;
		}
		loading.value = true;
		error.value = null;
		try {
			tree.value = await call("frappe_faker.api.generate.get_dependency_tree", {
				doctype,
				skip: skip.length ? JSON.stringify(skip) : null,
			});
		} catch (e) {
			error.value = e.messages?.[0] || e.message || "Failed to load dependency tree.";
			tree.value = null;
		} finally {
			loading.value = false;
		}
	}

	function debouncedFetch(doctype, skip = []) {
		if (debounceTimer) clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => fetchTree(doctype, skip), 500);
	}

	function clear() {
		if (debounceTimer) {
			clearTimeout(debounceTimer);
			debounceTimer = null;
		}
		tree.value = null;
		error.value = null;
		loading.value = false;
	}

	return { tree, loading, error, fetchTree, debouncedFetch, clear };
}
