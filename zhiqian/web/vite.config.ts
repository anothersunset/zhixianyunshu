import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    chunkSizeWarningLimit: 3000,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('monaco-editor')) return 'monaco'
          if (id.includes('@huggingface/transformers') || id.includes('onnxruntime')) return 'edge-ai'
          if (id.includes('cytoscape')) return 'graph'
          if (id.includes('echarts') || id.includes('vue-echarts')) return 'charts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
          if (id.includes('/vue') || id.includes('pinia') || id.includes('vue-router') || id.includes('vue-i18n')) return 'vue-vendor'
          return 'vendor'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api':  { target: 'http://localhost:8080', changeOrigin: true },
      '/rag':  { target: 'http://localhost:8001', changeOrigin: true, rewrite: (p) => p.replace(/^\/rag/, '') },
    },
  },
})
