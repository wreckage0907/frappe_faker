<template>
	<div class="max-w-2xl">
		<div class="mb-8">
			<h1 class="text-2xl font-semibold text-ink-gray-9">Settings</h1>
			<p class="text-sm text-ink-gray-5 mt-1">Frappe Faker configuration.</p>
		</div>

		<Alert
			v-if="loaded && !settings.provider"
			theme="yellow"
			title="No AI provider configured"
			description="Frappe Faker needs an AI provider to generate realistic data. Open Faker Settings to configure one."
			class="mb-6"
		/>

		<!-- AI config -->
		<div class="mb-2">
			<p class="text-xs font-medium uppercase tracking-wide text-ink-gray-4 mb-2 px-1">
				AI Configuration
			</p>
			<div
				class="overflow-hidden rounded-lg border border-outline-gray-2 divide-y divide-outline-gray-1"
			>
				<div class="flex items-center justify-between px-4 py-3">
					<div>
						<p class="text-sm font-medium text-ink-gray-7">AI Provider</p>
						<p class="text-xs text-ink-gray-4 mt-0.5">
							The LLM used to generate fake records.
						</p>
					</div>
					<span class="text-sm font-medium text-ink-gray-9">
						{{ settings.provider || "—" }}
					</span>
				</div>
				<div class="flex items-center justify-between px-4 py-3">
					<div>
						<p class="text-sm font-medium text-ink-gray-7">Model</p>
						<p class="text-xs text-ink-gray-4 mt-0.5">
							Active model name sent to the provider.
						</p>
					</div>
					<span class="text-sm font-medium text-ink-gray-9 font-mono text-xs">
						{{ settings.model_name || "—" }}
					</span>
				</div>
				<div class="flex items-center justify-between px-4 py-3">
					<div>
						<p class="text-sm font-medium text-ink-gray-7">Default count</p>
						<p class="text-xs text-ink-gray-4 mt-0.5">
							Pre-filled record count on the Generate form.
						</p>
					</div>
					<span class="text-sm font-medium text-ink-gray-9">
						{{ settings.default_count ?? "—" }}
					</span>
				</div>
			</div>
		</div>

		<Button variant="outline" theme="gray" class="mt-4" @click="openFrappeSettings">
			<template #prefix>
				<FeatherIcon name="external-link" class="w-4 h-4" />
			</template>
			Open Faker Settings
		</Button>

		<!-- Keyboard shortcuts -->
		<div class="mt-8">
			<p class="text-xs font-medium uppercase tracking-wide text-ink-gray-4 mb-2 px-1">
				Keyboard shortcuts
			</p>
			<div
				class="overflow-hidden rounded-lg border border-outline-gray-2 divide-y divide-outline-gray-1"
			>
				<div class="flex items-center justify-between px-4 py-3">
					<span class="text-sm text-ink-gray-6">Trigger generation</span>
					<kbd
						class="rounded bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-6 border border-outline-gray-2"
						>⌘ Enter</kbd
					>
				</div>
				<div class="flex items-center justify-between px-4 py-3">
					<span class="text-sm text-ink-gray-6">Cancel in-progress job</span>
					<kbd
						class="rounded bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-6 border border-outline-gray-2"
						>Esc</kbd
					>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { createResource } from "frappe-ui";

const loaded = ref(false);
const settings = ref({ provider: "", model_name: "", default_count: 10 });

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
