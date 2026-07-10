import { defineConfig } from 'vitest/config'

export default defineConfig({
  server: {
    proxy: {
      '/affirmations': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
  },
})
