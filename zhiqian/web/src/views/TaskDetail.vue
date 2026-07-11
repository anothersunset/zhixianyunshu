<template>
  <div class="page task-detail">
    <el-page-header :content="headerText" @back="router.back()" />

    <el-card v-if="store.current" shadow="never" class="summary-card">
      <div class="task-summary">
        <div class="summary-copy">
          <div class="status-line">
            <el-tag :type="statusTagType(store.current.status)" effect="dark">
              {{ statusLabel(store.current.status) }}
            </el-tag>
            <span v-if="store.current.runId" class="run-id">运行 ID：{{ store.current.runId }}</span>
          </div>
          <p class="summary-message">{{ statusMessage }}</p>
        </div>
        <div class="summary-actions">
          <el-button
            v-if="canReconnect"
            type="primary"
            :icon="Connection"
            :disabled="store.starting"
            @click="reconnect"
          >
            重新连接
          </el-button>
          <el-button
            v-else
            type="primary"
            :icon="VideoPlay"
            :loading="store.starting"
            :disabled="store.streaming || store.current.status === 'RUNNING'"
            @click="start"
          >
            {{ isTerminal ? '重新执行' : '开始执行' }}
          </el-button>
          <el-button
            :icon="Close"
            :disabled="!store.streaming"
            @click="stop"
          >
            停止监听
          </el-button>
        </div>
      </div>
    </el-card>

    <el-alert
      v-if="store.streamStoppedByUser && store.current?.status === 'RUNNING'"
      class="state-alert"
      title="已停止页面监听，后台迁移任务仍在运行。可点击“重新连接”继续查看进度。"
      type="info"
      show-icon
      :closable="false"
    />
    <el-alert
      v-if="visibleError"
      class="state-alert"
      :title="visibleError"
      type="error"
      show-icon
      :closable="false"
    />
    <el-alert
      v-else-if="store.terminalStatus === 'REVIEW_REQUIRED'"
      class="state-alert"
      title="自动迁移已完成，但仍有规则未通过最终校验，请人工复核结果 SQL。"
      type="warning"
      show-icon
      :closable="false"
    />
    <el-alert
      v-else-if="store.terminalStatus === 'DONE'"
      class="state-alert"
      title="迁移与复核均已完成，结果已保存。"
      type="success"
      show-icon
      :closable="false"
    />

    <el-row :gutter="16" class="detail-grid">
      <el-col :xs="24" :sm="24" :md="24" :lg="14">
        <el-card shadow="never" class="timeline-card">
          <template #header>
            <div class="card-header">
              <span>Agent 执行时间线</span>
              <span class="progress-caption">{{ store.progress }}%</span>
            </div>
          </template>
          <el-progress
            :percentage="store.progress"
            :stroke-width="14"
            :status="progressStatus"
          />
          <el-empty
            v-if="store.steps.length === 0"
            :image-size="72"
            description="暂无执行步骤，开始任务后将在此显示 Agent 轨迹"
          />
          <el-timeline v-else class="agent-timeline">
            <el-timeline-item
              v-for="(step, index) in store.steps"
              :key="`${step.runId}-${step.stage}-${index}`"
              :timestamp="`${step.stage} · ${step.agentName}`"
              :type="timelineType(step.status)"
            >
              <div class="step-meta">
                <el-tag size="small" :type="stepTagType(step.status)">
                  {{ stepStatusLabel(step.status) }}
                </el-tag>
                <span>耗时 {{ step.elapsedMs ?? 0 }}ms</span>
                <span v-if="step.confidence != null">
                  置信度 {{ formatConfidence(step.confidence) }}
                </span>
              </div>
              <details v-if="step.payload && Object.keys(step.payload).length" class="payload-details">
                <summary>查看步骤输出</summary>
                <pre class="payload">{{ formatPayload(step.payload) }}</pre>
              </details>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :md="24" :lg="10">
        <el-card shadow="never" class="suggestion-card">
          <template #header>
            <div class="card-header">
              <span>改造建议</span>
              <el-tag type="info" size="small">{{ store.suggestions.length }} 条</el-tag>
            </div>
          </template>
          <el-empty
            v-if="store.suggestions.length === 0"
            :image-size="72"
            description="暂无改造建议"
          />
          <div v-else class="responsive-table compact">
            <el-table :data="store.suggestions" size="small">
              <el-table-column prop="target" label="目标对象" min-width="180" show-overflow-tooltip />
              <el-table-column prop="category" label="类别" width="110" />
              <el-table-column label="风险" width="100">
                <template #default="{ row }"><RiskBadge :level="row.riskLevel" /></template>
              </el-table-column>
              <el-table-column label="置信度" width="90">
                <template #default="{ row }">
                  <span>{{ row.confidence?.toFixed(2) ?? '-' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row v-if="store.current?.sourceSql || store.current?.resultSql" :gutter="16" class="sql-grid">
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>源 SQL</template>
          <pre class="sql-preview">{{ store.current?.sourceSql || '暂无源 SQL' }}</pre>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never">
          <template #header>迁移结果</template>
          <pre class="sql-preview">{{ store.current?.resultSql || '任务完成后显示结果 SQL' }}</pre>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Close, Connection, VideoPlay } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'
import RiskBadge from '@/components/RiskBadge.vue'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
type ProgressStatus = '' | 'success' | 'exception' | 'warning'

const route = useRoute()
const router = useRouter()
const id = computed(() => Number(route.params.id))
const store = useTaskStore()

const headerText = computed(() => `任务 #${id.value} ${store.current?.name || ''}`)
const isTerminal = computed(() => ['DONE', 'FAILED', 'REVIEW_REQUIRED'].includes(store.current?.status ?? ''))
const canReconnect = computed(() => (
  store.current?.status === 'RUNNING'
  && Boolean(store.current.runId)
  && !store.streaming
))
const visibleError = computed(() => store.streamError || store.current?.errorMessage || '')
const progressStatus = computed<ProgressStatus>(() => {
  if (store.terminalStatus === 'FAILED') return 'exception'
  if (store.terminalStatus === 'REVIEW_REQUIRED') return 'warning'
  if (store.terminalStatus === 'DONE') return 'success'
  return ''
})
const statusMessage = computed(() => {
  const status = store.current?.status
  if (status === 'RUNNING') return store.streaming ? '正在接收实时执行轨迹。' : '后台任务正在运行，当前未连接实时轨迹。'
  if (status === 'DONE') return '迁移任务已完成，结果和报告已持久化。'
  if (status === 'FAILED') return '迁移任务执行失败，请根据错误信息定位失败阶段后重试。'
  if (status === 'REVIEW_REQUIRED') return '自动迁移已结束，结果需要人工复核后再使用。'
  return '任务尚未开始执行。'
})

function statusTagType(status: string): TagType {
  if (status === 'DONE') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'REVIEW_REQUIRED') return 'warning'
  if (status === 'RUNNING') return 'primary'
  return 'info'
}

function statusLabel(status: string) {
  return {
    PENDING: '待执行',
    RUNNING: '执行中',
    DONE: '已完成',
    FAILED: '执行失败',
    REVIEW_REQUIRED: '需人工复核',
  }[status] ?? status
}

function timelineType(status: string): TagType {
  if (['OK', 'DONE', 'SUCCESS'].includes(status)) return 'success'
  if (status === 'RUNNING') return 'primary'
  if (['FAIL', 'FAILED', 'ERROR'].includes(status)) return 'danger'
  if (status === 'REVIEW_REQUIRED') return 'warning'
  return 'info'
}

function stepTagType(status: string): TagType {
  return timelineType(status)
}

function stepStatusLabel(status: string) {
  if (['OK', 'DONE', 'SUCCESS'].includes(status)) return '成功'
  if (status === 'RUNNING') return '执行中'
  if (['FAIL', 'FAILED', 'ERROR'].includes(status)) return '失败'
  if (status === 'REVIEW_REQUIRED') return '需复核'
  return status
}

function formatConfidence(value: number) {
  return value <= 1 ? `${Math.round(value * 100)}%` : `${Math.round(value)}%`
}

function formatPayload(payload: unknown) {
  try {
    return JSON.stringify(payload ?? {}, null, 2)
  } catch {
    return String(payload)
  }
}

function start() {
  void store.runTask(id.value)
}

function reconnect() {
  void store.resumeStream(id.value)
}

function stop() {
  store.stopStream()
}

onMounted(async () => {
  await store.loadOne(id.value)
})
onBeforeUnmount(() => store.stopStream(false))
</script>

<style scoped>
.page {
  padding: 20px;
}

.summary-card,
.detail-grid,
.sql-grid,
.state-alert {
  margin-top: 16px;
}

.task-summary,
.card-header,
.status-line,
.step-meta {
  display: flex;
  align-items: center;
}

.task-summary,
.card-header {
  justify-content: space-between;
  gap: 16px;
}

.summary-copy {
  min-width: 0;
}

.status-line,
.step-meta {
  flex-wrap: wrap;
  gap: 8px 12px;
}

.run-id,
.progress-caption,
.step-meta {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.run-id {
  overflow-wrap: anywhere;
}

.summary-message {
  margin: 10px 0 0;
  color: var(--el-text-color-regular);
}

.summary-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 8px;
}

.summary-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.timeline-card,
.suggestion-card {
  height: 100%;
}

.agent-timeline {
  margin-top: 20px;
  padding-left: 4px;
}

.payload-details {
  margin-top: 10px;
}

.payload-details summary {
  color: var(--el-color-primary);
  cursor: pointer;
  font-size: 13px;
}

.payload,
.sql-preview {
  max-width: 100%;
  overflow: auto;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-light);
  color: var(--el-text-color-regular);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.payload {
  max-height: 260px;
  margin: 8px 0 0;
  padding: 10px;
}

.sql-preview {
  min-height: 160px;
  max-height: 360px;
  margin: 0;
  padding: 14px;
}

@media (max-width: 1199px) {
  .suggestion-card,
  .sql-grid :deep(.el-col + .el-col) {
    margin-top: 16px;
  }
}

@media (max-width: 600px) {
  .page {
    padding: 12px;
  }

  .task-summary,
  .card-header {
    align-items: flex-start;
  }

  .task-summary {
    flex-direction: column;
  }

  .summary-actions {
    width: 100%;
  }

  .summary-actions :deep(.el-button) {
    flex: 1;
    min-width: 0;
    padding-inline: 10px;
  }

  .agent-timeline {
    padding-left: 0;
  }

  .agent-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 20px;
  }

  .agent-timeline :deep(.el-timeline-item__timestamp) {
    overflow-wrap: anywhere;
  }
}
</style>
