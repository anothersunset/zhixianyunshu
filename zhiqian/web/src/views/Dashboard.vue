<template>
  <div class="dashboard">
    <el-alert
      class="demo-notice"
      title="演示数据"
      description="当前仪表盘使用内置样例数据展示产品形态，不代表真实迁移项目统计。"
      type="warning"
      show-icon
      :closable="false"
    />

    <el-row :gutter="16" class="kpis">
      <el-col v-for="kpi in kpis" :key="kpi.key" :xs="12" :sm="12" :md="6">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-label">{{ kpi.label }}</div>
          <div class="kpi-value">
            <span>{{ kpi.value }}</span><span class="unit">{{ kpi.unit }}</span>
          </div>
          <div class="kpi-trend" :class="kpi.trend.startsWith('+') ? 'up' : 'down'">
            <span>{{ kpi.trend }}</span>
            <span>　较上周</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :sm="24" :md="24" :lg="16">
        <el-card shadow="hover" class="chart-card">
          <template #header>近 7 日任务与建议趋势</template>
          <v-chart class="chart" :option="trendOption" autoresize />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="24" :md="24" :lg="8">
        <el-card shadow="hover" class="chart-card secondary-chart">
          <template #header>风险分布</template>
          <v-chart class="chart" :option="riskOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" class="recent-card">
      <template #header>
        <div class="section-header">
          <span>最近任务</span>
          <el-tag type="warning" size="small">演示数据</el-tag>
        </div>
      </template>
      <div class="responsive-table">
        <el-table :data="recentTasks" stripe size="default">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="name" label="任务名称" min-width="220" />
          <el-table-column label="状态" width="140">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="平均置信度" width="180">
            <template #default="{ row }">
              <el-progress :percentage="Math.round(row.conf * 100)" :stroke-width="10" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { dashboardKpis, recentTasks, riskDistribution, sevenDayTrend } from '@/mock/dashboard'

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const kpis = dashboardKpis

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { data: ['任务', '建议'] },
  grid: { left: 40, right: 24, top: 40, bottom: 32, containLabel: true },
  xAxis: { type: 'category', data: sevenDayTrend.dates, boundaryGap: false },
  yAxis: [{ type: 'value', name: '任务' }, { type: 'value', name: '建议' }],
  series: [
    { name: '任务', type: 'line', smooth: true, data: sevenDayTrend.tasks, areaStyle: {} },
    { name: '建议', type: 'line', smooth: true, yAxisIndex: 1, data: sevenDayTrend.suggestions },
  ],
}))

const riskOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0, type: 'scroll' },
  series: [{
    type: 'pie',
    radius: ['42%', '68%'],
    center: ['50%', '44%'],
    data: riskDistribution,
    label: { formatter: '{b}: {d}%' },
  }],
}))

function statusType(status: string): TagType {
  if (status === 'DONE') return 'success'
  if (status === 'RUNNING') return 'primary'
  if (['REVIEW', 'REVIEW_REQUIRED'].includes(status)) return 'warning'
  if (status === 'FAILED') return 'danger'
  return 'info'
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.demo-notice {
  margin-bottom: 16px;
}

.kpis :deep(.el-col) {
  margin-bottom: 16px;
}

.kpi-card {
  height: 100%;
}

.kpi-card :deep(.el-card__body) {
  padding: 16px 18px;
}

.kpi-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.kpi-value {
  margin: 4px 0;
  color: var(--el-text-color-primary);
  font-size: 28px;
  font-weight: 600;
}

.kpi-value .unit {
  margin-left: 4px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.kpi-trend {
  font-size: 12px;
}

.kpi-trend.up {
  color: var(--el-color-success);
}

.kpi-trend.down {
  color: var(--el-color-danger);
}

.chart-row,
.recent-card {
  margin-top: 0;
}

.chart-card {
  height: 100%;
}

.chart {
  height: 320px;
  min-width: 0;
}

.recent-card {
  margin-top: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 1199px) {
  .secondary-chart {
    margin-top: 16px;
  }
}

@media (max-width: 600px) {
  .dashboard {
    padding: 12px;
  }

  .kpis {
    margin-inline: -6px !important;
  }

  .kpis :deep(.el-col) {
    padding-inline: 6px !important;
    margin-bottom: 12px;
  }

  .kpi-card :deep(.el-card__body) {
    padding: 14px;
  }

  .kpi-value {
    font-size: 24px;
  }

  .chart {
    height: 260px;
  }
}
</style>
