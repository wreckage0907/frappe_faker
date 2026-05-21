import { ref } from "vue";
import { call, createResource } from "frappe-ui";

export function useGenerationHistory() {
	const history = ref([]);
	const loading = ref(false);

	const runsResource = createResource({
		url: "frappe_faker.api.history.get_runs",
		auto: false,
		onSuccess(data) {
			history.value = data;
			loading.value = false;
		},
		onError() {
			loading.value = false;
		},
		onFetch() {
			loading.value = true;
		},
	});

	function reload() {
		runsResource.reload();
	}

	async function addRun({ doctype, count, total_created, total_failed, result }) {
		await call("frappe_faker.api.history.add_run", {
			target_doctype: doctype,
			count_requested: count,
			total_created,
			total_failed,
			result: JSON.stringify(result),
		});
		reload();
	}

	async function clearAll() {
		await call("frappe_faker.api.history.clear_runs");
		history.value = [];
	}

	return { history, loading, addRun, clearAll, reload };
}
