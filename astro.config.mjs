// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import tailwindcss from "@tailwindcss/vite";
import tailwind from '@astrojs/tailwind';
import '@fontsource-variable/lora';
import starlightImageZoom from 'starlight-image-zoom';
import flowbite from 'flowbite';

// https://astro.build/config
export default defineConfig({
	site: 'https://judaicadh.github.io',
	base: '/pennjudaica',
	vite: {
		plugins: [tailwindcss()],
	},
	integrations: [
		starlight({
			customCss: [
				'./src/styles/tailwind.css',
				'@fontsource-variable/lora',
			],
			plugins: [ ],
			title: 'Judaica at Penn',
			lastUpdated: true,
			components: {
				// Override the default `SocialIcons` component.
				Footer: './src/components/Footer.astro',
			},
			tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 6 },
			// social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/withastro/starlight' }],
			sidebar: [
				{
					label: 'Resources ',
					autogenerate: { directory: 'resources' },
				},
				{
					label: 'Exhibits ',
					autogenerate: { directory: 'exhibits' },
				},

			],
		}),

	],
});
