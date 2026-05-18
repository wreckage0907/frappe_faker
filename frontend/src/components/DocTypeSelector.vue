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
			<FeatherIcon name="search" class="w-4 h-4 text-gray-400 mr-1.5" />
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

async function fetchDoctypes(query) {
	loading.value = true;
	try {
		const rows = await call("frappe.client.get_list", {
			doctype: "DocType",
			fields: ["name"],
			filters: query ? [["name", "like", `%${query}%`]] : [],
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
