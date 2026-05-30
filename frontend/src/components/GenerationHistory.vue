<template>
	<div class="max-w-2xl">
		<div class="mb-8 flex items-center justify-between">
			<div>
				<h1 class="text-2xl font-semibold text-ink-gray-9">History</h1>
				<p class="text-sm text-ink-gray-5 mt-1">Last 20 generation runs.</p>
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
			class="flex items-center gap-2 py-16 justify-center text-sm text-ink-gray-4"
		>
			<Spinner class="w-4 h-4" />
			Loading history...
		</div>

		<!-- Empty state -->
		<div
			v-else-if="!history.length"
			class="flex flex-col items-center justify-center py-24 text-ink-gray-4"
		>
			<FeatherIcon name="clock" class="w-10 h-10 mb-3 opacity-40" />
			<p class="text-sm">No generations yet — run one to see results here.</p>
		</div>

		<!-- Run list -->
		<div v-else class="overflow-hidden rounded-lg border border-outline-gray-2">
			<div
				v-for="run in history"
				:key="run.name"
				class="flex cursor-pointer items-center justify-between border-b border-outline-gray-1 px-4 py-3 last:border-b-0 transition-colors hover:bg-surface-gray-1"
				@click="openDetail(run)"
			>
				<div class="flex min-w-0 items-center gap-3">
					<FeatherIcon
						:name="run.total_failed === 0 ? 'check-circle' : 'alert-triangle'"
						class="h-4 w-4 flex-shrink-0"
						:class="run.total_failed === 0 ? 'text-green-500' : 'text-yellow-500'"
					/>
					<span class="truncate text-sm font-medium text-ink-gray-9">
						{{ run.target_doctype }}
					</span>
				</div>
				<div class="ml-4 flex flex-shrink-0 items-center gap-2">
					<span class="text-xs text-ink-gray-4 mr-1">
						req.&nbsp;{{ run.count_requested }}
					</span>
					<Badge
						:label="`${run.total_created} created`"
						theme="green"
						size="sm"
						variant="subtle"
					/>
					<Badge
						v-if="run.total_failed > 0"
						:label="`${run.total_failed} failed`"
						theme="red"
						size="sm"
						variant="subtle"
					/>
					<Badge
						v-if="isRolledBack(run)"
						label="Rolled back"
						theme="gray"
						size="sm"
						variant="subtle"
					/>
					<span class="w-16 text-right text-xs text-ink-gray-4">
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
						@rolledback="onRolledBack"
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
const rolledBackBatches = ref(new Set());

function parseResult(run) {
	if (typeof run.result !== "string") return run.result || null;
	try {
		return JSON.parse(run.result);
	} catch {
		return null;
	}
}

function openDetail(run) {
	selectedRun.value = { ...run, result: parseResult(run) };
	showDetail.value = true;
}

function isRolledBack(run) {
	const batchName = parseResult(run)?.batch_name;
	return batchName ? rolledBackBatches.value.has(batchName) : false;
}

function onRolledBack({ batchName }) {
	if (batchName) {
		rolledBackBatches.value = new Set([...rolledBackBatches.value, batchName]);
	}
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
