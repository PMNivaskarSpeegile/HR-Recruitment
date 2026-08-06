import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        // Split large third-party libs into cacheable vendor chunks.
        // (rolldown requires manualChunks as a function.)
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return;
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-vendor')) return 'charts';
          if (id.includes('@tanstack/react-table')) return 'table';
          if (id.includes('@tanstack/react-query')) return 'query';
          if (id.includes('react-hook-form') || id.includes('@hookform') || id.includes('/zod')) return 'forms';
          if (id.includes('react-router') || id.includes('react-dom') || id.includes('/react/')) return 'react-vendor';
        },
      },
    },
  },
})
