<template>
	<div class="flex h-screen bg-white">
		<!-- Sidebar -->
		<div class="w-56 flex-shrink-0 border-r border-gray-100 flex flex-col">
			<div class="px-4 py-5 border-b border-gray-100">
				<div class="flex items-center gap-2">
					<span class="text-xl">🧪</span>
					<span class="font-semibold text-gray-800 text-sm">Frappe Faker</span>
				</div>
			</div>

			<nav class="flex-1 px-2 py-3 space-y-0.5">
				<button
					class="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors"
					:class="
						activePanel === 'generate'
							? 'bg-blue-50 text-blue-700'
							: 'text-gray-600 hover:bg-gray-100'
					"
					@click="activePanel = 'generate'"
				>
					<FeatherIcon name="zap" class="w-4 h-4" />
					Generate
				</button>
			</nav>

			<div class="px-2 py-3 border-t border-gray-100">
				<button
					class="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-gray-500 hover:bg-gray-100 transition-colors"
					@click="session.logout.submit()"
				>
					<FeatherIcon name="log-out" class="w-4 h-4" />
					Logout
				</button>
			</div>
		</div>

		<!-- Main content -->
		<div class="flex-1 overflow-y-auto">
			<div class="p-10">
				<GenerateForm
					v-if="generation.phase.value === 'idle' || generation.phase.value === 'error'"
					:is-generating="false"
					:prev-error="generation.error.value"
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
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { session } from "../data/session";
import { useGeneration } from "../composables/useGeneration";
import GenerateForm from "../components/GenerateForm.vue";
import JobProgress from "../components/JobProgress.vue";
import ResultsSummary from "../components/ResultsSummary.vue";

const activePanel = ref("generate");
const currentDoctype = ref("");

const generation = useGeneration();

function handleSubmit(params) {
	currentDoctype.value = params.doctype;
	generation.startGeneration(params);
}
</script>
