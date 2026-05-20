<template>
  <el-timeline>
    <el-timeline-item
      v-for="s in steps"
      :key="s.stage"
      :type="s.status === 'FAIL' ? 'danger' : 'success'"
      :timestamp="s.stage"
    >
      <div class="row">
        <span class="name" v-text="s.agentName"></span>
        <el-tag size="small" v-if="typeof s.confidence === 'number'">
          <span v-text="'置信 ' + Math.round((s.confidence as number) * 100) + '%'"></span>
        </el-tag>
        <el-tag size="small" type="info">
          <span v-text="(s.elapsedMs ?? 0) + 'ms'"></span>
        </el-tag>
      </div>
      <pre class="payload" v-text="formatPayload(s.payload)"></pre>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { AgentStepEvent } from "@/composables/useTaskStream"
defineProps<{ steps: AgentStepEvent[] }>()
function formatPayload(v: unknown) {
  return v == null ? "" : JSON.stringify(v, null, 2)
}
</script>

<style scoped>
.row { display:flex; gap: 8px; align-items: center; }
.name { font-weight: 600; }
.payload { background: #f7f7f9; padding: 8px; border-radius: 4px; max-height: 200px; overflow: auto; }
</style>
