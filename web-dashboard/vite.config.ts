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
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq) => {
            // Docker Model Runner rejects requests with an Origin header it doesn't recognise.
            // The browser sends Origin on POST fetches even for same-origin requests.
            // Strip it here so DMR never sees it.
            proxyReq.removeHeader('origin');
            proxyReq.removeHeader('referer');
          });
        },
      },
    },
  },
});
