<template>
	<div class="max-w-2xl mx-auto">
		<div class="mb-8">
			<h1 class="text-2xl font-semibold text-gray-900">Settings</h1>
			<p class="text-sm text-gray-500 mt-1">Frappe Faker configuration.</p>
		</div>

		<Alert
			v-if="loaded && !settings.provider"
			theme="yellow"
			title="No AI provider configured"
			description="Frappe Faker needs an AI provider to generate realistic data. Open Faker Settings to configure one."
			class="mb-6"
		/>

		<div
			class="overflow-hidden rounded-lg border border-gray-200 divide-y divide-gray-100 mb-6"
		>
			<div class="flex items-center justify-between px-4 py-3">
				<span class="text-sm text-gray-500">AI Provider</span>
				<span class="text-sm font-medium text-gray-900">{{
					settings.provider || "—"
				}}</span>
			</div>
			<div class="flex items-center justify-between px-4 py-3">
				<span class="text-sm text-gray-500">Model</span>
				<span class="text-sm font-medium text-gray-900">{{
					settings.model_name || "—"
				}}</span>
			</div>
		</div>

		<Button variant="outline" theme="gray" @click="openFrappeSettings">
			<template #prefix>
				<FeatherIcon name="external-link" class="w-4 h-4" />
			</template>
			Open Faker Settings
		</Button>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { createResource } from "frappe-ui";

const loaded = ref(false);
const settings = ref({ provider: "", model_name: "" });

createResource({
	url: "frappe_faker.api.generate.get_faker_settings",
	auto: true,
	onSuccess(data) {
		settings.value = data;
		loaded.value = true;
	},
	onError() {
		loaded.value = true;
	},
});

function openFrappeSettings() {
	window.open("/app/faker-settings", "_blank");
}
</script>
