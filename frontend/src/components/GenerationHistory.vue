<template>
	<div class="max-w-3xl mx-auto">
		<div class="mb-8 flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-semibold text-gray-900">History</h1>
				<p class="text-sm text-gray-500 mt-1">Last 20 generation runs.</p>
			</div>
			<Button
				v-if="history.length"
				variant="ghost"
				theme="gray"
				size="sm"
				@click="emit('clear')"
			>
				Clear history
			</Button>
		</div>

		<!-- Loading -->
		<div
			v-if="loading"
			class="flex items-center gap-2 py-16 justify-center text-sm text-gray-400"
		>
			<Spinner class="w-4 h-4" />
			Loading history...
		</div>

		<!-- Empty state -->
		<div
			v-else-if="!history.length"
			class="flex flex-col items-center justify-center py-24 text-gray-400"
		>
			<FeatherIcon name="clock" class="w-10 h-10 mb-3 opacity-40" />
			<p class="text-sm">No generations yet — run one to see results here.</p>
		</div>

		<!-- Run list -->
		<div v-else class="overflow-hidden rounded-lg border border-gray-200">
			<div
				v-for="run in history"
				:key="run.name"
				class="flex cursor-pointer items-center justify-between border-b border-gray-100 px-4 py-3 last:border-b-0 transition-colors hover:bg-gray-50"
				@click="openDetail(run)"
			>
				<div class="flex min-w-0 items-center gap-3">
					<FeatherIcon
						:name="run.total_failed === 0 ? 'check-circle' : 'alert-triangle'"
						class="h-4 w-4 flex-shrink-0"
						:class="run.total_failed === 0 ? 'text-green-500' : 'text-yellow-500'"
					/>
					<span class="truncate text-sm font-medium text-gray-900">
						{{ run.target_doctype }}
					</span>
				</div>
				<div class="ml-4 flex flex-shrink-0 items-center gap-2">
					<Badge :label="`${run.total_created} created`" theme="green" size="sm" />
					<Badge
						v-if="run.total_failed > 0"
						:label="`${run.total_failed} failed`"
						theme="red"
						size="sm"
					/>
					<span class="w-16 text-right text-xs text-gray-400">
						{{ formatTime(run.creation) }}
					</span>
				</div>
			</div>
		</div>

		<!-- Detail dialog -->
		<Dialog
			v-model="showDetail"
			:options="{ title: selectedRun?.target_doctype, size: '3xl' }"
		>
			<template #body-content>
				<div class="px-1 py-2">
					<ResultsSummary
						v-if="selectedRun"
						:result="selectedRun.result"
						@reset="showDetail = false"
					/>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { ref } from "vue";
import ResultsSummary from "./ResultsSummary.vue";

const props = defineProps({
	history: { type: Array, default: () => [] },
	loading: { type: Boolean, default: false },
});

const emit = defineEmits(["clear"]);

const showDetail = ref(false);
const selectedRun = ref(null);

function openDetail(run) {
	const result = typeof run.result === "string" ? JSON.parse(run.result) : run.result;
	selectedRun.value = { ...run, result };
	showDetail.value = true;
}

function formatTime(frappe_creation) {
	const diffMs = Date.now() - new Date(frappe_creation).getTime();
	const mins = Math.floor(diffMs / 60000);
	if (mins < 1) return "just now";
	if (mins < 60) return `${mins}m ago`;
	const hours = Math.floor(mins / 60);
	if (hours < 24) return `${hours}h ago`;
	return `${Math.floor(hours / 24)}d ago`;
}
</script>
