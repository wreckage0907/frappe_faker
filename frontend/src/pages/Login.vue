<template>
	<div class="min-h-screen flex flex-col items-center justify-center bg-surface-gray-2 px-4">
		<!-- Brand mark -->
		<div class="flex flex-col items-center mb-6">
			<FakerLogo class="size-12 rounded-xl mb-3" />
			<h1 class="text-xl font-semibold text-ink-gray-9">Frappe Faker</h1>
			<p class="text-sm text-ink-gray-5 mt-0.5">AI-powered test data generator</p>
		</div>

		<div class="w-full max-w-sm">
			<Card class="shadow-sm">
				<h2 class="text-base font-semibold text-ink-gray-8 mb-4">Sign in to continue</h2>
				<form class="flex flex-col gap-3 w-full" @submit.prevent="submit">
					<Input
						required
						name="email"
						type="text"
						placeholder="administrator"
						label="User ID"
					/>
					<Input
						required
						name="password"
						type="password"
						placeholder="••••••"
						label="Password"
					/>
					<Button :loading="session.login.loading" variant="solid" class="mt-1">
						Sign in
					</Button>
				</form>
			</Card>
		</div>
	</div>
</template>

<script lang="ts" setup>
import FakerLogo from "../components/FakerLogo.vue";
import { session } from "../data/session";

function submit(e: SubmitEvent) {
	const formData = new FormData(e.target as HTMLFormElement);
	session.login.submit({
		email: formData.get("email"),
		password: formData.get("password"),
	});
}
</script>
