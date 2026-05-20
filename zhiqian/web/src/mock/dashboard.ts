// 仪表盘演示数据 —— 当后端尚未填充统计接口时直接渲染

export const dashboardKpis = [
  { key: 'projects',     label: '在迁项目', value: 6,   unit: '个',   trend: '+2' },
  { key: 'tasks',        label: '累计任务', value: 27,  unit: '次',   trend: '+5' },
  { key: 'suggestions',  label: '改造建议', value: 312, unit: '条',   trend: '+48' },
  { key: 'avg_conf',     label: '平均置信度', value: 0.86, unit: '',  trend: '+0.04' },
]

export const sevenDayTrend = {
  dates: ['05-14','05-15','05-16','05-17','05-18','05-19','05-20'],
  tasks: [2, 3, 1, 4, 5, 3, 6],
  suggestions: [18, 24, 9, 31, 42, 22, 51],
}

export const riskDistribution = [
  { name: '低风险 LOW', value: 196 },
  { name: '中风险 MEDIUM', value: 92 },
  { name: '高风险 HIGH', value: 24 },
]

export const recentTasks = [
  { id: 27, name: 'demo-incremental-2026-05-20', status: 'RUNNING', conf: 0.81 },
  { id: 26, name: 'demo-full-run-2026-05-17',    status: 'DONE',    conf: 0.89 },
  { id: 25, name: 'finance-mysql-2026-05-15',    status: 'DONE',    conf: 0.92 },
  { id: 24, name: 'crm-mysql-2026-05-12',        status: 'REVIEW',  conf: 0.74 },
]
