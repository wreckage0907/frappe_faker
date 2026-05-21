<template>
	<div class="flex h-screen bg-white">
		<!-- Sidebar -->
		<div class="flex w-56 flex-shrink-0 flex-col border-r border-gray-100">
			<div class="border-b border-gray-100 px-4 py-5">
				<div class="flex items-center gap-2">
					<span class="text-xl">🧪</span>
					<span class="text-sm font-semibold text-gray-800">Frappe Faker</span>
				</div>
			</div>

			<nav class="flex-1 space-y-0.5 px-2 py-3">
				<button
					v-for="item in navItems"
					:key="item.panel"
					class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors"
					:class="
						activePanel === item.panel
							? 'bg-blue-50 text-blue-700'
							: 'text-gray-600 hover:bg-gray-100'
					"
					@click="activePanel = item.panel"
				>
					<FeatherIcon :name="item.icon" class="h-4 w-4" />
					{{ item.label }}
				</button>
			</nav>

			<div class="border-t border-gray-100 px-2 py-3 space-y-0.5">
				<div class="flex items-center gap-2 px-3 py-2">
					<div
						class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700"
					>
						{{ userInitial }}
					</div>
					<span class="truncate text-xs text-gray-500">{{ session.user }}</span>
				</div>
				<button
					class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-100"
					@click="session.logout.submit()"
				>
					<FeatherIcon name="log-out" class="h-4 w-4" />
					Logout
				</button>
			</div>
		</div>

		<!-- Main content -->
		<div class="flex-1 overflow-y-auto">
			<div class="p-10">
				<!-- Generate panel -->
				<template v-if="activePanel === 'generate'">
					<GenerateForm
						v-if="
							generation.phase.value === 'idle' || generation.phase.value === 'error'
						"
						ref="formRef"
						:is-generating="false"
						:prev-error="generation.error.value"
						:initial-doctype="lastDoctype"
						@submit="handleSubmit"
					/>

					<JobProgress
						v-else-if="generation.phase.value === 'generating'"
						:doctype="currentDoctype"
						:job-status="generation.jobStatus.value"
						:poll-count="generation.pollCount.value"
						@cancel="generation.reset()"
					/>

					<ResultsSummary
						v-else-if="generation.phase.value === 'done'"
						:result="generation.result.value"
						@reset="generation.reset()"
					/>
				</template>

				<!-- History panel -->
				<GenerationHistory
					v-else-if="activePanel === 'history'"
					:history="genHistory.history.value"
					:loading="genHistory.loading.value"
					@clear="genHistory.clearAll()"
				/>

				<!-- Settings panel -->
				<SettingsPanel v-else-if="activePanel === 'settings'" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { session } from "../data/session";
import { useGeneration } from "../composables/useGeneration";
import { useGenerationHistory } from "../composables/useGenerationHistory";
import GenerateForm from "../components/GenerateForm.vue";
import JobProgress from "../components/JobProgress.vue";
import ResultsSummary from "../components/ResultsSummary.vue";
import GenerationHistory from "../components/GenerationHistory.vue";
import SettingsPanel from "../components/SettingsPanel.vue";

const navItems = [
	{ panel: "generate", icon: "zap", label: "Generate" },
	{ panel: "history", icon: "clock", label: "History" },
	{ panel: "settings", icon: "settings", label: "Settings" },
];

const activePanel = ref("generate");
const currentDoctype = ref("");
const lastDoctype = ref("");
const formRef = ref(null);

const generation = useGeneration();
const genHistory = useGenerationHistory();

const userInitial = computed(() => (session.user || "?").charAt(0).toUpperCase());

// Lazy-load history only when the panel is opened
watch(activePanel, (panel) => {
	if (panel === "history") genHistory.reload();
});

// Record completed runs to history; failures are non-critical so swallow errors
watch(
	() => generation.phase.value,
	async (phase) => {
		if (phase === "done" && generation.result.value) {
			try {
				await genHistory.addRun({
					doctype: currentDoctype.value,
					count: generation.result.value.count_requested ?? 0,
					total_created: generation.result.value.total_created ?? 0,
					total_failed: generation.result.value.total_failed ?? 0,
					result: generation.result.value,
				});
			} catch {
				// History write failure must not disrupt the generation result view
			}
		}
	}
);

function handleSubmit(params) {
	currentDoctype.value = params.doctype;
	lastDoctype.value = params.doctype;
	generation.startGeneration(params);
}

// Keyboard shortcuts
function handleKeydown(e) {
	const isGenPanel = activePanel.value === "generate";
	const phase = generation.phase.value;

	// Cmd/Ctrl+Enter → submit form
	if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
		if (isGenPanel && (phase === "idle" || phase === "error")) {
			e.preventDefault();
			formRef.value?.submit?.();
		}
		return;
	}

	// Escape → cancel in-progress generation
	if (e.key === "Escape" && phase === "generating") {
		generation.reset();
	}
}

onMounted(() => document.addEventListener("keydown", handleKeydown));
onUnmounted(() => document.removeEventListener("keydown", handleKeydown));
</script>
