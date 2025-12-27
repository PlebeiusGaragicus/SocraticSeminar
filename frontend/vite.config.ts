import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), sveltekit()],
  server: {
    port: 5173,
    host: true
  },
  optimizeDeps: {
    include: ['monaco-editor']
  },
  ssr: {
    // Don't externalize monaco - we only load it on client via dynamic import
    noExternal: ['monaco-editor']
  }
});
