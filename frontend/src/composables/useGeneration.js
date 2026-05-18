import { ref, onUnmounted } from "vue";
import { call, toast } from "frappe-ui";

export function useGeneration() {
	const phase = ref("idle"); // idle | generating | done | error
	const jobId = ref(null);
	const jobStatus = ref(null);
	const result = ref(null);
	const error = ref(null);

	let pollTimer = null;
	let failCount = 0;
	const pollCount = ref(0);

	async function startGeneration({
		doctype,
		count,
		resolveDeps,
		fastInsert,
		customInstructions,
		skipDoctypes,
	}) {
		phase.value = "generating";
		jobId.value = null;
		jobStatus.value = null;
		result.value = null;
		error.value = null;
		failCount = 0;
		pollCount.value = 0;

		try {
			const resp = await call("frappe_faker.api.generate.enqueue_generation", {
				doctype,
				count,
				resolve_deps: resolveDeps,
				fast_insert: fastInsert,
				custom_instructions: customInstructions || null,
				skip: skipDoctypes && skipDoctypes.length ? JSON.stringify(skipDoctypes) : null,
			});
			jobId.value = resp.job_id;
			startPolling();
		} catch (e) {
			phase.value = "error";
			error.value =
				e.exc_type === "PermissionError"
					? "You need System Manager role to use Frappe Faker."
					: e.messages?.[0] || e.message || "Failed to start generation job.";
		}
	}

	function startPolling() {
		pollTimer = setInterval(pollOnce, 2000);
	}

	async function pollOnce() {
		pollCount.value++;
		try {
			const resp = await call("frappe_faker.api.generate.get_job_status", {
				job_id: jobId.value,
			});
			jobStatus.value = resp.status;
			failCount = 0;

			if (resp.status === "finished") {
				result.value = resp.result;
				phase.value = "done";
				stopPolling();
				const total = resp.result?.total_created ?? 0;
				const doctype = resp.result?.target ?? "";
				toast({
					title: "Generation complete",
					text: `Created ${total} records for ${doctype}`,
					icon: "check-circle",
					iconClasses: "text-green-600",
				});
			} else if (resp.status === "failed") {
				error.value = resp.exc || "Job failed on the server.";
				phase.value = "error";
				stopPolling();
				toast({
					title: "Generation failed",
					text: error.value,
					icon: "alert-circle",
					iconClasses: "text-red-600",
				});
			} else if (resp.status === "not_found") {
				error.value =
					"Job not found. The background worker may be offline — check your Frappe worker processes.";
				phase.value = "error";
				stopPolling();
				toast({
					title: "Job not found",
					text: error.value,
					icon: "alert-circle",
					iconClasses: "text-red-600",
				});
			}
		} catch {
			failCount++;
			if (failCount >= 3) {
				error.value = "Lost connection while polling for job status.";
				phase.value = "error";
				stopPolling();
			}
		}
	}

	function stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	function reset() {
		stopPolling();
		phase.value = "idle";
		jobId.value = null;
		jobStatus.value = null;
		result.value = null;
		error.value = null;
		failCount = 0;
		pollCount.value = 0;
	}

	onUnmounted(stopPolling);

	return { phase, jobId, jobStatus, result, error, pollCount, startGeneration, reset };
}
