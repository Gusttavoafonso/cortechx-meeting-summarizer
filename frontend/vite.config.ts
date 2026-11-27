import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import type { IncomingMessage } from 'http'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (
    env.VITE_API_PROXY_TARGET ||
    env.VITE_API_URL ||
    'http://127.0.0.1:8000'
  ).replace(/\/+$/, '')

  const htmlBypass = (req: IncomingMessage) => {
    if (req.headers.accept?.includes('text/html')) {
      return '/index.html'
    }
  }

  return {
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
          target: proxyTarget,
          changeOrigin: true,
          bypass(req) {
            if (
              req.headers.accept?.includes('text/html') &&
              !req.url?.includes('/audio/file')
            ) {
              return '/index.html'
            }
          },
        },
        '/auth': {
          target: proxyTarget,
          changeOrigin: true,
          bypass: htmlBypass,
        },
        '/partial-sessions': {
          target: proxyTarget,
          changeOrigin: true,
          bypass: htmlBypass,
        },
        '/users': {
          target: proxyTarget,
          changeOrigin: true,
          bypass: htmlBypass,
        },
        '/settings': {
          target: proxyTarget,
          changeOrigin: true,
          bypass: htmlBypass,
        },
        '/system': {
          target: proxyTarget,
          changeOrigin: true,
          bypass: htmlBypass,
        },
        '/health': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
