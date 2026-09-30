import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Send /api/... requests to the FastAPI backend, so the browser only talks to one address.
    // API_TARGET lets a second copy talk to a different backend (e.g. a mock one); normally unset.
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
