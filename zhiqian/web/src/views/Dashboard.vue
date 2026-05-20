<template>
  <div class="dashboard">
    <el-row :gutter="16" class="kpis">
      <el-col :span="6" v-for="k in kpis" :key="k.key">
        <el-card shadow="hover">
          <div class="kpi-label" v-text="k.label" />
          <div class="kpi-value">
            <span v-text="k.value" /><span class="unit" v-text="k.unit" />
          </div>
          <div class="kpi-trend" :class="k.trend.startsWith('+') ? 'up' : 'down'">
            <span v-text="k.trend" />
            <span>　较上周</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>近 7 日任务与建议趋势</template>
          <v-chart class="chart" :option="trendOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>风险分布</template>
          <v-chart class="chart" :option="riskOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>最近任务</template>
      <el-table :data="recentTasks" stripe size="default">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名称" />
        <el-table-column label="状态" width="140">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" v-text="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="平均置信度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.conf*100)" :stroke-width="10" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { dashboardKpis, sevenDayTrend, riskDistribution, recentTasks } from '@/mock/dashboard'

const kpis = dashboardKpis

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['任务', '建议'] },
  grid: { left: 32, right: 24, top: 32, bottom: 32 },
  xAxis: { type: 'category', data: sevenDayTrend.dates, boundaryGap: false },
  yAxis: [{ type: 'value', name: '任务' }, { type: 'value', name: '建议' }],
  series: [
    { name: '任务', type: 'line', smooth: true, data: sevenDayTrend.tasks, areaStyle: {} },
    { name: '建议', type: 'line', smooth: true, yAxisIndex: 1, data: sevenDayTrend.suggestions },
  ],
}))

const riskOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{ type: 'pie', radius: ['45%', '70%'], data: riskDistribution, label: { formatter: '{b}: {d}%' } }],
}))

function statusType(s: string) {
  if (s === 'DONE') return 'success'
  if (s === 'RUNNING') return 'primary'
  if (s === 'REVIEW') return 'warning'
  return 'info'
}
</script>

<style scoped>
.dashboard { padding: 16px; }
.kpis :deep(.el-card__body) { padding: 16px 18px; }
.kpi-label { font-size: 13px; color: #909399; }
.kpi-value { font-size: 28px; font-weight: 600; margin: 4px 0; color: #303133; }
.kpi-value .unit { font-size: 14px; color: #909399; margin-left: 4px; }
.kpi-trend.up { color: #67c23a; font-size: 12px; }
.kpi-trend.down { color: #f56c6c; font-size: 12px; }
.chart { height: 320px; }
</style>
