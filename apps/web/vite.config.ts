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
      '/api/avatar/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        rewrite: (path) => '/api/avatar/engine' + path,
      },
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
