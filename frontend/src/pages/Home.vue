<template>
	<div class="flex h-screen bg-surface-white">
		<!-- Sidebar -->
		<Sidebar :sections="[{ items: navItems }]" :disable-collapse="true">
			<template #header>
				<div
					class="flex items-center gap-2.5 border-b border-outline-gray-1 px-3 py-3.5 mb-1"
				>
					<FakerLogo class="size-7 rounded-lg flex-shrink-0" />
					<span class="text-sm font-medium text-ink-gray-8">Frappe Faker</span>
				</div>
			</template>

			<template #sidebar-item="{ item }">
				<SidebarItem
					:label="item.label"
					:is-active="activePanel === item.panel"
					:on-click="() => (activePanel = item.panel)"
				>
					<template #icon>
						<FeatherIcon :name="item.icon" class="size-4 text-ink-gray-6" />
					</template>
				</SidebarItem>
			</template>

			<template #footer-items>
				<div class="border-t border-outline-gray-1 pt-2 space-y-0.5">
					<div class="flex items-center gap-2 px-3 py-2">
						<div
							class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-3 text-xs font-medium text-ink-gray-7"
						>
							{{ userInitial }}
						</div>
						<span class="truncate text-xs text-ink-gray-5">{{ session.user }}</span>
					</div>
					<SidebarItem label="Logout" :on-click="() => session.logout.submit()">
						<template #icon>
							<FeatherIcon name="log-out" class="size-4 text-ink-gray-6" />
						</template>
					</SidebarItem>
				</div>
			</template>
		</Sidebar>

		<!-- Main content -->
		<div class="flex-1 overflow-y-auto">
			<div class="px-8 py-8">
				<Transition name="panel" mode="out-in">
					<!-- Generate panel -->
					<div v-if="activePanel === 'generate'" key="generate">
						<Transition name="panel" mode="out-in">
							<GenerateForm
								v-if="
									generation.phase.value === 'idle' ||
									generation.phase.value === 'error'
								"
								key="form"
								ref="formRef"
								:is-generating="false"
								:prev-error="generation.error.value"
								:initial-doctype="lastDoctype"
								@submit="handleSubmit"
							/>
							<JobProgress
								v-else-if="generation.phase.value === 'generating'"
								key="progress"
								:doctype="currentDoctype"
								:job-status="generation.jobStatus.value"
								:poll-count="generation.pollCount.value"
								@cancel="generation.reset()"
							/>
							<ResultsSummary
								v-else-if="generation.phase.value === 'done'"
								key="results"
								:result="generation.result.value"
								@reset="generation.reset()"
							/>
						</Transition>
					</div>

					<!-- History panel -->
					<GenerationHistory
						v-else-if="activePanel === 'history'"
						key="history"
						:history="genHistory.history.value"
						:loading="genHistory.loading.value"
						@clear="genHistory.clearAll()"
						@reload="genHistory.reload()"
					/>

					<!-- Settings panel -->
					<SettingsPanel v-else-if="activePanel === 'settings'" key="settings" />
				</Transition>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { session } from "../data/session";
import { useGeneration } from "../composables/useGeneration";
import { useGenerationHistory } from "../composables/useGenerationHistory";
import FakerLogo from "../components/FakerLogo.vue";
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

<style scoped>
.panel-enter-active,
.panel-leave-active {
	transition: opacity 0.12s ease, transform 0.12s ease;
}
.panel-enter-from {
	opacity: 0;
	transform: translateY(6px);
}
.panel-leave-to {
	opacity: 0;
	transform: translateY(-4px);
}
</style>
