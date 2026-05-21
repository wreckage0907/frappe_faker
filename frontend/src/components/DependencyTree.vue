<template>
	<div>
		<!-- Loading -->
		<div v-if="loading" class="flex items-center gap-2 py-3 text-sm text-gray-500">
			<Spinner class="w-4 h-4" />
			Analyzing dependencies...
		</div>

		<!-- Error -->
		<Alert
			v-else-if="error"
			theme="red"
			title="Could not load dependency tree"
			:description="error"
		/>

		<!-- Standalone: no dependencies -->
		<p
			v-else-if="tree && tree.order.length <= 1"
			class="flex items-center gap-1.5 py-2 text-sm text-gray-500"
		>
			<FeatherIcon name="check-circle" class="h-4 w-4 text-green-500" />
			{{ targetDoctype }} has no dependencies — it generates standalone.
		</p>

		<!-- Tree -->
		<div v-else-if="tree" class="space-y-3">
			<Alert
				v-if="tree.truncated.length"
				theme="yellow"
				title="Tree truncated at depth 5"
				:description="`Some sub-dependencies were cut off: ${tree.truncated.join(', ')}`"
			/>
			<Alert
				v-if="tree.cycles.length"
				theme="red"
				title="Circular dependencies detected"
				:description="`${tree.cycles.join(
					', '
				)} form a cycle — generation proceeds but some records may link incorrectly.`"
			/>

			<div class="overflow-hidden rounded-lg border border-gray-200">
				<div
					v-for="row in sortedOrder"
					:key="row.doctype"
					class="flex items-center gap-2.5 border-b border-gray-100 py-2.5 pr-4 text-sm last:border-b-0"
					:style="{ paddingLeft: `${16 + row.depth * 16}px` }"
				>
					<input
						v-if="row.depth > 0"
						type="checkbox"
						:checked="skipped.has(row.doctype)"
						class="h-3.5 w-3.5 flex-shrink-0 cursor-pointer rounded border-gray-300 accent-blue-600"
						@change="toggleSkip(row.doctype)"
					/>
					<div v-else class="h-3.5 w-3.5 flex-shrink-0" />

					<FeatherIcon
						v-if="row.depth > 0"
						name="corner-down-right"
						class="h-3.5 w-3.5 flex-shrink-0 text-gray-300"
					/>

					<span
						class="flex-1 font-medium"
						:class="
							skipped.has(row.doctype)
								? 'text-gray-400 line-through'
								: 'text-gray-800'
						"
					>
						{{ row.doctype }}
					</span>

					<div class="flex items-center gap-1.5">
						<Badge v-if="row.depth === 0" label="Target" theme="blue" size="sm" />
						<Badge
							v-if="row.has_existing_data && !skipped.has(row.doctype)"
							label="Has data"
							theme="green"
							size="sm"
						/>
						<Badge v-if="row.is_cyclic" label="Cyclic" theme="red" size="sm" />
						<Badge
							v-if="skipped.has(row.doctype)"
							label="Skip"
							theme="gray"
							size="sm"
						/>
					</div>
				</div>
			</div>

			<p class="text-xs text-gray-400">
				Check a dependency to skip it — Frappe Faker will use existing records for that
				DocType.
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, watch } from "vue";

const props = defineProps({
	tree: { type: Object, default: null },
	loading: { type: Boolean, default: false },
	error: { type: String, default: null },
	modelValue: { type: Array, default: () => [] },
});

const emit = defineEmits(["update:modelValue"]);

const targetDoctype = computed(() => props.tree?.order?.find((r) => r.depth === 0)?.doctype ?? "");

const sortedOrder = computed(() => {
	if (!props.tree) return [];
	return [...props.tree.order].sort((a, b) => a.depth - b.depth);
});

const skipped = computed(() => new Set(props.modelValue));

// Auto-select nodes that already have data when the tree first loads
watch(
	() => props.tree,
	(newTree) => {
		if (!newTree) return;
		const autoSkip = newTree.order
			.filter((r) => r.has_existing_data && r.depth > 0)
			.map((r) => r.doctype);
		emit("update:modelValue", autoSkip);
	}
);

function toggleSkip(doctype) {
	const next = new Set(props.modelValue);
	if (next.has(doctype)) {
		next.delete(doctype);
	} else {
		next.add(doctype);
	}
	emit("update:modelValue", [...next]);
}
</script>
