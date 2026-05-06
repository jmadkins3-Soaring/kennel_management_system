import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 9100,
    proxy: {
      '/api': {
        target: 'http://localhost:9101',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    exclude: ['**/node_modules/**', 'tests/e2e/**'],
  },
})
