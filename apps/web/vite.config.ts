import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // Suppress Firefox "No sources are declared in this source map" warnings
  // for pre-bundled dependencies (esbuild generates empty source maps).
  optimizeDeps: {
    esbuildOptions: { sourcemap: false },
  },
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
      // Avatar Engine WebSocket — explicit 127.0.0.1 to avoid Firefox
      // IPv6/IPv4 ambiguity (Firefox resolves localhost to ::1 first).
      '/api/avatar/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
      // All API requests (Synapse + Avatar Engine REST)
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/previews': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
