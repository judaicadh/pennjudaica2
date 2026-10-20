/** @type {import('tailwindcss').Config} */
import starlightPlugin from '@astrojs/starlight-tailwind';
const accent = { 200: '#aed4b2', 600: '#005b20', 900: '#003e14', 950: '#092c11' };
const gray = { 100: '#f4f6fc', 200: '#e9eefa', 300: '#bcc2d0', 400: '#808ba6', 500: '#4e5870', 700: '#2f374e', 800: '#1e263c', 900: '#141822' };


export default {
	content: [
		'./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}',


	],

	theme: {
		extend: {
			fontFamily: {
				serif: ['Lora Variable', 'serif'],
			},
			colors: { accent,  gray }, // Add custom colors


		},
	},

	plugins: [
		require('@tailwindcss/typography'),
		require('@tailwindcss/forms'), // Optional form plugin
		require('flowbite/plugin'),
		starlightPlugin(),
	],
};

