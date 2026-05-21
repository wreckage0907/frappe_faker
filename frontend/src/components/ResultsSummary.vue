<template>
	<div class="max-w-2xl">
		<!-- Header -->
		<div class="mb-6">
			<div v-if="totalFailed === 0" class="flex items-start gap-3">
				<div
					class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-green-50"
				>
					<FeatherIcon name="check-circle" class="w-5 h-5 text-green-500" />
				</div>
				<div>
					<h1 class="text-2xl font-semibold text-ink-gray-9">
						Generated {{ totalCreated }} records
					</h1>
					<p class="text-sm text-ink-gray-5 mt-0.5">
						DocType:
						<span class="font-medium text-ink-gray-7">{{ result.target }}</span>
					</p>
				</div>
			</div>
			<div v-else class="flex items-start gap-3">
				<div
					class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-yellow-50"
				>
					<FeatherIcon name="alert-triangle" class="w-5 h-5 text-yellow-500" />
				</div>
				<div>
					<h1 class="text-2xl font-semibold text-ink-gray-9">
						{{ totalCreated }} created
						<span v-if="totalFailed > 0" class="text-red-500"
							>, {{ totalFailed }} failed</span
						>
					</h1>
					<p class="text-sm text-ink-gray-5 mt-0.5">
						DocType:
						<span class="font-medium text-ink-gray-7">{{ result.target }}</span>
					</p>
				</div>
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
		<div class="border border-outline-gray-2 rounded-lg overflow-hidden mb-6">
			<div
				v-for="(row, idx) in result.results"
				:key="row.doctype"
				class="border-b border-outline-gray-1 last:border-b-0"
			>
				<!-- Row header -->
				<div
					class="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-surface-gray-1 transition-colors"
					:class="{ 'bg-red-50': row.failed_count > 0 || row.error }"
					@click="toggleExpanded(idx)"
				>
					<div class="flex items-center gap-2">
						<FeatherIcon
							v-if="row.error"
							name="alert-circle"
							class="w-4 h-4 text-red-500 flex-shrink-0"
						/>
						<span class="text-sm font-medium text-ink-gray-8">{{ row.doctype }}</span>
					</div>
					<div class="flex items-center gap-2">
						<Badge
							v-if="row.created_count > 0"
							:label="`${row.created_count} created`"
							theme="green"
							size="sm"
							variant="subtle"
						/>
						<Badge
							v-if="row.failed_count > 0"
							:label="`${row.failed_count} failed`"
							theme="red"
							size="sm"
							variant="subtle"
						/>
						<Badge
							v-if="row.error && row.total === 0"
							label="Error"
							theme="red"
							size="sm"
							variant="subtle"
						/>
						<FeatherIcon
							v-if="row.failed_count > 0 || row.error"
							:name="expanded[idx] ? 'chevron-up' : 'chevron-down'"
							class="w-4 h-4 text-ink-gray-4"
						/>
					</div>
				</div>

				<!-- Expanded error details -->
				<div v-if="expanded[idx]" class="bg-surface-gray-1 px-4 pb-3 pt-1 space-y-2">
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
						class="text-xs text-ink-gray-6 bg-surface-white rounded border border-outline-gray-2 p-2"
					>
						<span class="font-medium text-ink-gray-5"
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
