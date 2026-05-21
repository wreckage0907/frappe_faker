<template>
	<div class="max-w-2xl mx-auto">
		<div class="mb-8">
			<h1 class="text-2xl font-medium text-ink-gray-9">
				Generating
				<span class="text-blue-600">{{ doctype }}</span>
				<Spinner class="inline-block ml-2 w-5 h-5 text-blue-500" />
			</h1>
			<p class="text-sm text-ink-gray-5 mt-1">
				Records are being generated in the background.
			</p>
		</div>

		<!-- Progress bar -->
		<div class="mb-6">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm text-ink-gray-6">Progress</span>
				<Badge :label="statusLabel" :theme="statusTheme" size="sm" variant="subtle" />
			</div>
			<Progress :value="fakeProgress" size="lg" />
		</div>

		<!-- Stale queue warning (>40s) -->
		<Alert
			v-if="showStaleWarning"
			theme="yellow"
			title="Taking longer than expected"
			description="The job is still queued. Your background worker may be busy or not running."
			class="mb-4"
		/>

		<!-- Long-running alert (>3min) -->
		<Alert
			v-if="showLongRunning"
			theme="blue"
			title="Large batch in progress"
			description="Generation is still running on the server. It's safe to close this page — records are being created in the background."
			class="mb-4"
		/>

		<!-- Cancel -->
		<div class="mt-6">
			<Button variant="ghost" theme="gray" size="sm" @click="emit('cancel')">
				Cancel and go back
			</Button>
			<p class="text-xs text-ink-gray-4 mt-1">
				The background job will continue; records already created will remain.
			</p>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";

const props = defineProps({
	doctype: { type: String, default: "" },
	jobStatus: { type: String, default: null },
	pollCount: { type: Number, default: 0 },
});

const emit = defineEmits(["cancel"]);

// Fake progress: increments slowly to 90%, then jumps to 100 on finish
const fakeProgress = ref(0);
let progressTimer = null;

onMounted(() => {
	progressTimer = setInterval(() => {
		if (fakeProgress.value < 90) {
			fakeProgress.value = Math.min(90, fakeProgress.value + 0.4);
		}
	}, 500);
});

onUnmounted(() => {
	if (progressTimer) clearInterval(progressTimer);
});

watch(
	() => props.jobStatus,
	(status) => {
		if (status === "finished") {
			fakeProgress.value = 100;
			if (progressTimer) clearInterval(progressTimer);
		}
	}
);

const statusLabel = computed(() => {
	const map = { queued: "Queued", started: "Running", finished: "Done" };
	return map[props.jobStatus] ?? "Waiting";
});

const statusTheme = computed(() => {
	const map = { queued: "gray", started: "blue", finished: "green" };
	return map[props.jobStatus] ?? "gray";
});

// Stale queue: pollCount > 20 and still queued (~40s)
const showStaleWarning = computed(() => props.pollCount > 20 && props.jobStatus === "queued");

// Long-running: pollCount > 90 (~3 min)
const showLongRunning = computed(() => props.pollCount > 90);
</script>
