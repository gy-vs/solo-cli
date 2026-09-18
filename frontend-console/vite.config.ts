import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // ws 要显式开：容器终端走的是 /api 下的 WebSocket，不开的话 dev 下只有它连不上
      '/api': { target: 'http://localhost:8001', changeOrigin: true, ws: true },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})
