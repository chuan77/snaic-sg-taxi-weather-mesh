import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/llm': {
        target: process.env.LLM_PROXY_TARGET ?? 'http://localhost:12434',
        rewrite: (path) => path.replace(/^\/llm/, '/engines/v1'),
        changeOrigin: true,
      },
    },
  },
});
