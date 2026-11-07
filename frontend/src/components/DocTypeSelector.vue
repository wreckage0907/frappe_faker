<template>
	<Autocomplete
		:model-value="selectedOption"
		:options="options"
		:loading="loading"
		placeholder="Search DocType..."
		@update:query="onQuery"
		@change="onSelect"
	>
		<template #prefix>
			<FeatherIcon name="search" class="w-4 h-4 text-ink-gray-4 mr-1.5" />
		</template>
	</Autocomplete>
</template>

<script setup>
import { ref, computed } from "vue";
import { call } from "frappe-ui";

const props = defineProps({ modelValue: String });
const emit = defineEmits(["update:modelValue"]);

const loading = ref(false);
const rawNames = ref([]);
let debounceTimer = null;

const options = computed(() => rawNames.value.map((name) => ({ label: name, value: name })));

const selectedOption = computed(() =>
	props.modelValue ? { label: props.modelValue, value: props.modelValue } : null
);

function onSelect(option) {
	emit("update:modelValue", option?.value ?? "");
}

function escapeLike(q) {
	return q.replace(/[%_\\]/g, "\\$&");
}

// Only DocTypes that hold standalone rows can be generation targets: child tables are
// generated inside their parent, Singles have one record, and virtual ones have no table.
const GENERATABLE_FILTERS = [
	["istable", "=", 0],
	["issingle", "=", 0],
	["is_virtual", "=", 0],
];

async function fetchDoctypes(query) {
	loading.value = true;
	try {
		const filters = [...GENERATABLE_FILTERS];
		if (query) filters.push(["name", "like", `%${escapeLike(query)}%`]);
		const rows = await call("frappe.client.get_list", {
			doctype: "DocType",
			fields: ["name"],
			filters,
			limit: 20,
			order_by: "name asc",
		});
		rawNames.value = rows.map((r) => r.name);
	} catch {
		rawNames.value = [];
	} finally {
		loading.value = false;
	}
}

function onQuery(q) {
	clearTimeout(debounceTimer);
	debounceTimer = setTimeout(() => fetchDoctypes(q), 300);
}

// Load initial options on mount
fetchDoctypes("");
</script>
