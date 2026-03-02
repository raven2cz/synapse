import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
    // Deduplicate React/ReactDOM when using npm-linked @avatar-engine packages.
    // Without this, linked packages resolve their own React copy → dual instance crash.
    dedupe: ['react', 'react-dom', 'i18next', 'react-i18next'],
  },
  server: {
    port: 5173,
    proxy: {
      // Avatar Engine WebSocket (must be before /api catch-all)
      '/api/avatar/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      // All API requests (Synapse + Avatar Engine — no rewriting needed,
      // avatar-engine is mounted at /api/avatar with empty internal prefix)
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/previews': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
