import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/meetings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/partial-sessions': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/users': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/settings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
      '/system': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass(req) {
          if (req.headers.accept?.includes('text/html')) {
            return '/index.html'
          }
        },
      },
    },
  },
})
