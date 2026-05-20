<template>
  <div class="src-citation">
    <el-icon><Link /></el-icon>
    <span class="path" v-text="chunk.source" />
    <el-tag size="small" effect="plain" v-text="`score \${chunk.score.toFixed(3)}`" />
  </div>
  <div class="text" v-text="chunk.text" />
</template>

<script setup lang="ts">
import { Link } from '@element-plus/icons-vue'
defineProps<{ chunk: { id: string; text: string; score: number; source: string } }>()
</script>

<style scoped>
.src-citation { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #606266; }
.src-citation .path { font-family: 'JetBrains Mono', Consolas, monospace; }
.text { margin: 4px 0 12px; font-size: 13px; line-height: 1.6; color: #303133; }
</style>
