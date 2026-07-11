<template>
  <el-empty v-if="steps.length === 0" :image-size="72" description="暂无 Agent 执行轨迹" />
  <el-timeline v-else class="agent-timeline">
    <el-timeline-item
      v-for="(step, index) in steps"
      :key="`${step.stage}-${index}`"
      :type="timelineType(step.status)"
      :timestamp="step.stage"
    >
      <div class="row">
        <span class="name">{{ step.agentName || 'Agent' }}</span>
        <el-tag v-if="typeof step.confidence === 'number'" size="small">
          置信度 {{ Math.round(step.confidence * 100) }}%
        </el-tag>
        <el-tag size="small" type="info">{{ step.elapsedMs ?? 0 }}ms</el-tag>
        <el-tag v-if="step.status" size="small" :type="timelineType(step.status)">
          {{ step.status }}
        </el-tag>
      </div>
      <pre v-if="step.payload != null" class="payload">{{ formatPayload(step.payload) }}</pre>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { AgentStepEvent } from '@/composables/useTaskStream'

type TimelineType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

defineProps<{ steps: AgentStepEvent[] }>()

function timelineType(status?: string): TimelineType {
  if (['OK', 'DONE', 'SUCCESS'].includes(status ?? '')) return 'success'
  if (status === 'RUNNING') return 'primary'
  if (['FAIL', 'FAILED', 'ERROR'].includes(status ?? '')) return 'danger'
  if (status === 'REVIEW_REQUIRED') return 'warning'
  return 'info'
}

function formatPayload(value: unknown) {
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>

<style scoped>
.agent-timeline {
  min-width: 0;
}

.row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.name {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.payload {
  max-width: 100%;
  max-height: 240px;
  overflow: auto;
  margin: 8px 0 0;
  padding: 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 600px) {
  .agent-timeline {
    padding-left: 0;
  }

  .agent-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 20px;
  }
}
</style>
