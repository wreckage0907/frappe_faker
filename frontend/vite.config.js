import path from "node:path";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [
		frappeui({
			frappeProxy: {
				port: 8080,
			},
			jinjaBootData: true,
			lucideIcons: true,
			buildConfig: {
				outDir: "../frappe_faker/public/frontend",
				indexHtmlPath: "../frappe_faker/www/frontend.html",
				emptyOutDir: true,
				sourcemap: true,
			},
		}),
		vue(),
	],
	build: {
		chunkSizeWarningLimit: 1500,
		outDir: "../frappe_faker/public/frontend",
		emptyOutDir: true,
		target: "es2015",
		sourcemap: true,
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			"tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
		},
	},
	optimizeDeps: {
		include: ["feather-icons", "highlight.js/lib/core", "interactjs"],
		exclude: ["frappe-ui"],
	},
	server: {
		allowedHosts: true,
	},
});
