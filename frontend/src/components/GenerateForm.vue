<template>
	<div class="max-w-2xl mx-auto">
		<div class="mb-8">
			<h1 class="text-2xl font-semibold text-gray-900">Generate Fake Data</h1>
			<p class="text-sm text-gray-500 mt-1">
				Pick a DocType and generate realistic records using AI.
			</p>
		</div>

		<!-- No provider warning -->
		<Alert
			v-if="settingsLoaded && !settings.provider"
			theme="yellow"
			title="No AI provider configured"
			description="Configure one in Faker Settings before generating."
			class="mb-6"
		/>

		<!-- Error from previous attempt -->
		<Alert
			v-if="prevError"
			theme="red"
			title="Generation failed"
			:description="prevError"
			class="mb-6"
		/>

		<div class="space-y-5">
			<!-- DocType -->
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1.5">
					DocType <span class="text-red-500">*</span>
				</label>
				<DocTypeSelector v-model="doctype" />
			</div>

			<!-- Count -->
			<div>
				<label class="block text-sm font-medium text-gray-700 mb-1.5">
					Number of records
				</label>
				<TextInput
					v-model="countStr"
					type="number"
					min="1"
					max="500"
					:disabled="!settingsLoaded"
					class="w-32"
					@change="clampCount"
				/>
				<p class="text-xs text-gray-400 mt-1">Max 500 per generation run.</p>
			</div>

			<!-- Toggles: resolve deps + fast insert -->
			<div class="flex flex-col gap-3 pt-1">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-sm font-medium text-gray-700">Resolve dependencies</p>
						<p class="text-xs text-gray-400">
							Auto-generate linked doctypes in the correct order.
						</p>
					</div>
					<Switch v-model="resolveDeps" />
				</div>
				<div class="flex items-center justify-between">
					<div>
						<p class="text-sm font-medium text-gray-700">Fast insert</p>
						<p class="text-xs text-gray-400">
							Skips Python hooks — much faster, but side-effects won't run.
						</p>
					</div>
					<Switch v-model="fastInsert" />
				</div>
			</div>

			<!-- Advanced toggle -->
			<button
				type="button"
				class="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
				@click="showAdvanced = !showAdvanced"
			>
				<FeatherIcon
					:name="showAdvanced ? 'chevron-up' : 'chevron-down'"
					class="w-4 h-4"
				/>
				{{ showAdvanced ? "Hide" : "Show" }} advanced options
			</button>

			<div v-if="showAdvanced" class="space-y-4 pl-1">
				<div>
					<label class="block text-sm font-medium text-gray-700 mb-1.5">
						Custom instructions
						<span class="font-normal text-gray-400">(optional)</span>
					</label>
					<Textarea
						v-model="customInstructions"
						rows="3"
						placeholder="e.g. Make all companies based in India, use INR currency..."
						class="w-full"
					/>
				</div>
			</div>

			<!-- Generate button -->
			<div class="pt-2">
				<Button
					variant="solid"
					theme="blue"
					size="md"
					:disabled="!doctype || isGenerating"
					:loading="isGenerating"
					@click="handleGenerate"
				>
					Generate
				</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { createResource } from "frappe-ui";
import DocTypeSelector from "./DocTypeSelector.vue";

const props = defineProps({
	isGenerating: Boolean,
	prevError: { type: String, default: null },
	initialDoctype: { type: String, default: "" },
});

const emit = defineEmits(["submit"]);

const doctype = ref(props.initialDoctype);
const countStr = ref("10");
const resolveDeps = ref(true);
const fastInsert = ref(true);
const customInstructions = ref("");
const showAdvanced = ref(false);
const settingsLoaded = ref(false);
const settings = ref({ default_count: 10, provider: "", model_name: "" });

createResource({
	url: "frappe_faker.api.generate.get_faker_settings",
	auto: true,
	onSuccess(data) {
		settings.value = data;
		countStr.value = String(data.default_count || 10);
		settingsLoaded.value = true;
	},
	onError() {
		settingsLoaded.value = true;
	},
});

function clampCount() {
	let n = parseInt(countStr.value, 10);
	if (isNaN(n) || n < 1) n = 1;
	if (n > 500) n = 500;
	countStr.value = String(n);
}

function handleGenerate() {
	clampCount();
	emit("submit", {
		doctype: doctype.value,
		count: parseInt(countStr.value, 10),
		resolveDeps: resolveDeps.value,
		fastInsert: fastInsert.value,
		customInstructions: customInstructions.value.trim() || null,
		skipDoctypes: [],
	});
}

defineExpose({ doctype, submit: handleGenerate });
</script>
