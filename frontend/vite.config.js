import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api is served by the Python backend (uv run qroute-server)
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
