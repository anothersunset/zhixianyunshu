<template>
  <div class="page">
    <el-page-header :content="`任务 #${id} ${store.current?.name || ''}`" @back="router.back()" />

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>
            <div class="hdr">
              <span>Agent 执行时间线</span>
              <div>
                <el-button :icon="VideoPlay" type="primary" size="small" :disabled="streaming" @click="start">开始演示</el-button>
                <el-button :icon="Close" size="small" :disabled="!streaming" @click="stop">停止</el-button>
              </div>
            </div>
          </template>
          <el-progress :percentage="store.progress" :stroke-width="14" status="success" />
          <el-timeline style="margin-top:16px">
            <el-timeline-item v-for="(s, i) in store.steps" :key="i"
                              :timestamp="`${s.stage} · ${s.agentName}`"
                              :type="timelineType(s.status)">
              <div><b>耗时</b>  s.elapsedMs ?? 0 ms<span v-if="s.confidence != null"> · <b>置信度</b>  s.confidence </span></div>
              <pre class="payload"> JSON.stringify(s.payload, null, 2) </pre>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never">
          <template #header>改造建议</template>
          <el-table :data="store.suggestions" size="small">
            <el-table-column prop="target" label="目标对象" min-width="180" show-overflow-tooltip />
            <el-table-column prop="category" label="类别" width="110" />
            <el-table-column label="风险" width="100">
              <template #default="{ row }"><RiskBadge :level="row.riskLevel" /></template>
            </el-table-column>
            <el-table-column label="置信" width="90">
              <template #default="{ row }"> row.confidence?.toFixed?.(2) ?? '-' </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { VideoPlay, Close } from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'
import RiskBadge from '@/components/RiskBadge.vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => Number(route.params.id))
const store = useTaskStore()
const streaming = ref(false)

function timelineType(s: string) { return s === 'OK' ? 'success' : s === 'RUNNING' ? 'primary' : 'info' }
async function start() { streaming.value = true; store.streamTask(id.value) }
function stop() { streaming.value = false; store.stopStream() }

onMounted(async () => { await store.loadOne(id.value) })
onBeforeUnmount(() => store.stopStream())
</script>

<style scoped>
.page{padding:16px}
.hdr{display:flex;justify-content:space-between;align-items:center}
.payload{background:#f5f7fa;border-radius:4px;padding:6px 10px;font-size:12px;color:#606266;margin-top:4px}
</style>
