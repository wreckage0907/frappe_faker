<template>
	<svg
		width="300"
		height="300"
		viewBox="0 0 300 300"
		fill="none"
		xmlns="http://www.w3.org/2000/svg"
	>
		<!-- Rounded square background -->
		<rect width="300" height="300" rx="72" fill="#6D28D9" />

		<!-- Flask rim (wider cap at top) -->
		<rect x="108" y="60" width="84" height="22" rx="7" fill="white" />

		<!-- Flask neck -->
		<rect x="127" y="80" width="46" height="62" fill="white" />

		<!-- Flask body (trapezoid with rounded bottom) -->
		<path
			d="M127 140 L72 250 Q70 264 86 264 L214 264 Q230 264 228 250 L173 140 Z"
			fill="white"
		/>

		<!-- Liquid fill inside body (subtle tint) -->
		<path
			d="M106 210 L72 250 Q70 264 86 264 L214 264 Q230 264 228 250 L194 210 Z"
			fill="#C4B5FD"
		/>

		<!-- Bubbles (represent data points) -->
		<circle cx="150" cy="237" r="9" fill="#6D28D9" opacity="0.45" />
		<circle cx="172" cy="250" r="6" fill="#6D28D9" opacity="0.45" />
		<circle cx="133" cy="251" r="5" fill="#6D28D9" opacity="0.45" />
	</svg>
</template>
