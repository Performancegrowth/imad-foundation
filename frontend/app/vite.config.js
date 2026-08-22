import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Imad frontend — Vite configuration.
// API requests are proxied to the FastAPI dev server to avoid CORS friction.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})