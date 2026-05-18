<template>
	<div class="max-w-2xl mx-auto">
		<!-- Header -->
		<div class="mb-6">
			<div v-if="totalFailed === 0" class="flex items-center gap-2">
				<FeatherIcon name="check-circle" class="w-6 h-6 text-green-500" />
				<h1 class="text-2xl font-semibold text-gray-900">
					Generated {{ totalCreated }} records for
					<span class="text-blue-600">{{ result.target }}</span>
				</h1>
			</div>
			<div v-else class="flex items-center gap-2">
				<FeatherIcon name="alert-triangle" class="w-6 h-6 text-yellow-500" />
				<h1 class="text-2xl font-semibold text-gray-900">
					{{ totalCreated }} created,
					<span class="text-red-600">{{ totalFailed }} failed</span>
					for {{ result.target }}
				</h1>
			</div>

			<Alert
				v-if="totalCreated === 0 && totalFailed > 0"
				theme="red"
				title="All records failed"
				description="No records were created. Check the error details below."
				class="mt-4"
			/>
		</div>

		<!-- Per-doctype breakdown -->
		<div class="border border-gray-200 rounded-lg overflow-hidden mb-6">
			<div
				v-for="(row, idx) in result.results"
				:key="row.doctype"
				class="border-b border-gray-100 last:border-b-0"
			>
				<!-- Row header -->
				<div
					class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
					:class="{ 'bg-red-50': row.failed_count > 0 || row.error }"
					@click="toggleExpanded(idx)"
				>
					<div class="flex items-center gap-2">
						<FeatherIcon
							v-if="row.error"
							name="alert-circle"
							class="w-4 h-4 text-red-500 flex-shrink-0"
						/>
						<span class="text-sm font-medium text-gray-800">{{ row.doctype }}</span>
					</div>
					<div class="flex items-center gap-2">
						<Badge
							v-if="row.created_count > 0"
							:label="`${row.created_count} created`"
							theme="green"
							size="sm"
						/>
						<Badge
							v-if="row.failed_count > 0"
							:label="`${row.failed_count} failed`"
							theme="red"
							size="sm"
						/>
						<Badge
							v-if="row.error && row.total === 0"
							label="Error"
							theme="red"
							size="sm"
						/>
						<FeatherIcon
							v-if="row.failed_count > 0 || row.error"
							:name="expanded[idx] ? 'chevron-up' : 'chevron-down'"
							class="w-4 h-4 text-gray-400"
						/>
					</div>
				</div>

				<!-- Expanded error details -->
				<div v-if="expanded[idx]" class="bg-gray-50 px-4 pb-3 pt-1 space-y-2">
					<!-- Context/generation error -->
					<div
						v-if="row.error"
						class="text-sm text-red-600 font-mono bg-red-50 rounded p-2"
					>
						{{ row.error }}
					</div>

					<!-- Per-record failures -->
					<div
						v-for="fail in row.failed"
						:key="fail.index"
						class="text-xs text-gray-600 bg-white rounded border border-gray-200 p-2"
					>
						<span class="font-medium text-gray-500"
							>Record #{{ fail.index + 1 }}:</span
						>
						{{ fail.error }}
					</div>
				</div>
			</div>
		</div>

		<!-- Footer actions -->
		<div class="flex items-center gap-3">
			<Button variant="solid" theme="blue" @click="emit('reset')"> Generate Again </Button>
			<Button variant="ghost" theme="gray" @click="copyToClipboard">
				<template #prefix>
					<FeatherIcon name="copy" class="w-4 h-4" />
				</template>
				Copy summary
			</Button>
		</div>
	</div>
</template>

<script setup>
import { ref, computed } from "vue";

const props = defineProps({
	result: { type: Object, required: true },
});

const emit = defineEmits(["reset"]);

const expanded = ref({});

const totalCreated = computed(() => props.result.total_created ?? 0);
const totalFailed = computed(() => props.result.total_failed ?? 0);

function toggleExpanded(idx) {
	const row = props.result.results[idx];
	if (row.failed_count > 0 || row.error) {
		expanded.value[idx] = !expanded.value[idx];
	}
}

function copyToClipboard() {
	const lines = [
		`Frappe Faker — ${props.result.target}`,
		`Created: ${totalCreated.value} | Failed: ${totalFailed.value}`,
		"",
		...props.result.results.map(
			(r) =>
				`  ${r.doctype}: ${r.created_count} created, ${r.failed_count} failed${
					r.error ? ` (${r.error})` : ""
				}`
		),
	];
	navigator.clipboard.writeText(lines.join("\n")).catch(() => {});
}
</script>
