<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="hdr">
          <span>迁移报告</span>
          <div class="hdr-right">
            <el-select v-model="selectedTaskId" placeholder="选择任务查看报告" clearable style="width:280px"
              @change="onTaskChange">
              <el-option v-for="t in taskStore.tasks" :key="t.id" :label="`#${t.id} ${t.name}`" :value="t.id" />
            </el-select>
            <el-button type="primary" :disabled="!hasData" @click="generatePdf" :loading="generating">
              导出 PDF
            </el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!selectedTaskId" description="请先选择一个任务" :image-size="80" />
      <div v-else-if="loading" v-loading="true" style="min-height:200px" />
      <template v-else-if="hasData">
        <!-- 统计摘要 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="4">
            <div class="stat-card">
              <div class="stat-value" v-text="stats.total" />
              <div class="stat-label">改造建议</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card stat-ok">
              <div class="stat-value" v-text="stats.autoOk" />
              <div class="stat-label">自动通过</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card stat-warn">
              <div class="stat-value" v-text="stats.needReview" />
              <div class="stat-label">待复核</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card stat-danger">
              <div class="stat-value" v-text="stats.highRisk" />
              <div class="stat-label">高风险</div>
            </div>
          </el-col>
          <el-col :span="4">
            <div class="stat-card">
              <div class="stat-value" v-text="(avgConf * 100).toFixed(0) + '%'" />
              <div class="stat-label">平均置信度</div>
            </div>
          </el-col>
        </el-row>

        <!-- 风险分布 + 改造建议清单 -->
        <el-row :gutter="16" style="margin-top:16px">
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header>风险分布</template>
              <v-chart class="chart" :option="riskChartOption" autoresize />
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header>改造建议清单</template>
              <el-table :data="taskStore.suggestions" stripe size="small" max-height="320">
                <el-table-column prop="category" label="类别" width="110" />
                <el-table-column prop="target" label="目标对象" min-width="180" show-overflow-tooltip />
                <el-table-column label="风险" width="90">
                  <template #default="{ row }"><RiskBadge :level="row.riskLevel" /></template>
                </el-table-column>
                <el-table-column label="置信度" width="90">
                  <template #default="{ row }">
                    <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :stroke-width="8" />
                  </template>
                </el-table-column>
                <el-table-column prop="rationale" label="理由" min-width="160" show-overflow-tooltip />
              </el-table>
            </el-card>
          </el-col>
        </el-row>

        <!-- 详细 diff -->
        <el-card shadow="hover" style="margin-top:16px" v-if="taskStore.suggestions.length">
          <template #header>改造明细（diff）</template>
          <el-collapse accordion>
            <el-collapse-item v-for="s in taskStore.suggestions" :key="s.id"
              :title="`[${s.category}] ${s.target}`">
              <pre class="diff" v-text="s.unifiedDiff || '(无 diff 数据)'" />
            </el-collapse-item>
          </el-collapse>
        </el-card>
      </template>
      <el-empty v-else description="该任务暂无建议数据" :image-size="80" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { useTaskStore } from '@/stores/task'
import { generatePdf as generatePdfApi, type ReportPayload } from '@/api/reports'
import RiskBadge from '@/components/RiskBadge.vue'

const taskStore = useTaskStore()
const selectedTaskId = ref<number | null>(null)
const loading = ref(false)
const generating = ref(false)

const hasData = computed(() => taskStore.suggestions.length > 0)

const stats = computed(() => {
  const list = taskStore.suggestions
  const highRisk = list.filter(s => s.riskLevel === 'HIGH' || s.riskLevel === '高').length
  const needReview = list.filter(s => s.reviewStatus !== 'PASSED').length
  const confs = list.map(s => s.confidence || 0).filter(c => c > 0)
  const avgConf = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : 0
  return {
    total: list.length,
    autoOk: list.length - needReview,
    needReview,
    highRisk,
    avgConf,
  }
})

const riskChartOption = computed(() => {
  const low = taskStore.suggestions.filter(s => s.riskLevel === 'LOW' || s.riskLevel === '低').length
  const med = taskStore.suggestions.filter(s => s.riskLevel === 'MEDIUM' || s.riskLevel === '中').length
  const high = taskStore.suggestions.filter(s => s.riskLevel === 'HIGH' || s.riskLevel === '高').length
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['45%', '75%'],
      data: [
        { name: '低风险', value: low, itemStyle: { color: '#67c23a' } },
        { name: '中风险', value: med, itemStyle: { color: '#e6a23c' } },
        { name: '高风险', value: high, itemStyle: { color: '#f56c6c' } },
      ],
      label: { formatter: '{b}: {d}%' },
    }],
  }
})

async function onTaskChange(id: number | null) {
  if (!id) return
  loading.value = true
  try {
    await taskStore.loadOne(id)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载任务数据失败')
  } finally {
    loading.value = false
  }
}

async function generatePdf() {
  const task = taskStore.current
  if (!task) return
  generating.value = true
  try {
    const payload: ReportPayload = {
      project_name: task.name,
      stats: {
        total_sql: stats.value.total,
        high_risk: stats.value.highRisk,
      },
      risks: taskStore.suggestions.map(s => ({
        kind: s.category,
        description: s.rationale || s.target,
        level: s.riskLevel === 'HIGH' ? '高' : s.riskLevel === 'MEDIUM' ? '中' : '低',
        suggestion: s.unifiedDiff || '',
      })),
      examples: taskStore.suggestions.slice(0, 5).map(s => ({
        title: `[${s.category}] ${s.target}`,
        source: '',
        target: s.unifiedDiff?.split('\n').filter(l => l.startsWith('+')).join('\n') || '',
        explanation: s.rationale || '',
      })),
    }
    const blob = await generatePdfApi(payload)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `migration-report-${task.name}.pdf`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('PDF 报告已生成')
  } catch (e: any) {
    ElMessage.error(e?.message || '报告生成失败，请确认 RAG 服务可用')
  } finally {
    generating.value = false
  }
}

// 初始化加载任务列表
taskStore.refreshAll().catch(() => {})
</script>

<style scoped>
.page { padding: 16px; }
.hdr { display: flex; justify-content: space-between; align-items: center; }
.hdr-right { display: flex; gap: 12px; align-items: center; }
.stats-row { text-align: center; }
.stat-card { padding: 12px 0; background: #f5f7fa; border-radius: 6px; }
.stat-card.stat-ok { background: #f0f9eb; }
.stat-card.stat-warn { background: #fdf6ec; }
.stat-card.stat-danger { background: #fef0f0; }
.stat-value { font-size: 26px; font-weight: 700; color: #303133; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.chart { height: 280px; }
.diff { background: #f5f7fa; border-radius: 4px; padding: 8px 12px; font-size: 12px; color: #606266; white-space: pre-wrap; font-family: 'JetBrains Mono', Consolas, monospace; margin: 0; }
</style>
