<template>
	<div class="max-w-2xl">
		<div class="mb-8">
			<h1 class="text-2xl font-semibold text-ink-gray-9">Generate Fake Data</h1>
			<p class="text-sm text-ink-gray-5 mt-1">
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
				<label class="block text-sm font-medium text-ink-gray-7 mb-1.5">
					DocType <span class="text-red-500">*</span>
				</label>
				<DocTypeSelector v-model="doctype" @update:model-value="onDoctypeChange" />
			</div>

			<!-- Dependency tree preview -->
			<div v-if="doctype && resolveDeps">
				<button
					type="button"
					class="flex items-center gap-1.5 text-sm text-ink-gray-5 hover:text-ink-gray-7 transition-colors"
					@click="toggleDepTree"
				>
					<FeatherIcon
						:name="showDepTree ? 'chevron-up' : 'chevron-down'"
						class="w-4 h-4"
					/>
					{{ showDepTree ? "Hide" : "Preview" }} dependencies
				</button>
				<div v-if="showDepTree" class="mt-3">
					<DependencyTree
						v-model="skipDoctypes"
						:tree="depTree.tree.value"
						:loading="depTree.loading.value"
						:error="depTree.error.value"
					/>
				</div>
			</div>

			<!-- Count -->
			<div>
				<label class="block text-sm font-medium text-ink-gray-7 mb-1.5">
					Number of records
				</label>
				<TextInput
					v-model="countStr"
					type="number"
					min="1"
					max="500"
					:disabled="!settingsLoaded"
					class="w-28"
					@change="clampCount"
				/>
				<p class="text-xs text-ink-gray-4 mt-1">Max 500 per generation run.</p>
			</div>

			<!-- Toggles: resolve deps + fast insert -->
			<div class="rounded-lg border border-outline-gray-2 divide-y divide-outline-gray-1">
				<div class="flex items-center justify-between px-4 py-3">
					<div>
						<p class="text-sm font-medium text-ink-gray-7">Resolve dependencies</p>
						<p class="text-xs text-ink-gray-4 mt-0.5">
							Auto-generate linked doctypes in the correct order.
						</p>
					</div>
					<Switch v-model="resolveDeps" @update:model-value="onResolveDepsChange" />
				</div>
				<div class="flex items-center justify-between px-4 py-3">
					<div>
						<p class="text-sm font-medium text-ink-gray-7">Fast insert</p>
						<p class="text-xs text-ink-gray-4 mt-0.5">
							Skips Python hooks — much faster, but side-effects won't run.
						</p>
					</div>
					<Switch v-model="fastInsert" />
				</div>
			</div>

			<!-- Advanced toggle -->
			<button
				type="button"
				class="flex items-center gap-1.5 text-sm text-ink-gray-5 hover:text-ink-gray-7 transition-colors"
				@click="showAdvanced = !showAdvanced"
			>
				<FeatherIcon
					:name="showAdvanced ? 'chevron-up' : 'chevron-down'"
					class="w-4 h-4"
				/>
				{{ showAdvanced ? "Hide" : "Show" }} advanced options
			</button>

			<div v-if="showAdvanced" class="space-y-4">
				<div>
					<label class="block text-sm font-medium text-ink-gray-7 mb-1.5">
						Custom instructions
						<span class="font-normal text-ink-gray-4">(optional)</span>
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
			<div class="pt-1">
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
import { ref, watch } from "vue";
import { createResource } from "frappe-ui";
import DocTypeSelector from "./DocTypeSelector.vue";
import DependencyTree from "./DependencyTree.vue";
import { useDependencyTree } from "../composables/useDependencyTree";

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
const showDepTree = ref(false);
const skipDoctypes = ref([]);
const settingsLoaded = ref(false);
const settings = ref({ default_count: 10, provider: "", model_name: "" });

const depTree = useDependencyTree();

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

function onDoctypeChange(val) {
	skipDoctypes.value = [];
	if (showDepTree.value && val && resolveDeps.value) {
		depTree.debouncedFetch(val, []);
	} else if (!val) {
		depTree.clear();
		showDepTree.value = false;
	}
}

function onResolveDepsChange(val) {
	if (!val) {
		showDepTree.value = false;
		depTree.clear();
	}
}

function toggleDepTree() {
	showDepTree.value = !showDepTree.value;
	if (showDepTree.value && doctype.value) {
		depTree.fetchTree(doctype.value, skipDoctypes.value);
	} else {
		depTree.clear();
	}
}

// Refetch when skip list changes
watch(skipDoctypes, (newSkip) => {
	if (showDepTree.value && doctype.value) {
		depTree.debouncedFetch(doctype.value, newSkip);
	}
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
		skipDoctypes: skipDoctypes.value,
	});
}

defineExpose({ doctype, submit: handleGenerate });
</script>
