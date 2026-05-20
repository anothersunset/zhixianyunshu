import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElIcons from '@element-plus/icons-vue'

import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, GridComponent,
  LegendComponent, DatasetComponent, ToolboxComponent,
} from 'echarts/components'
import ECharts from 'vue-echarts'

import App from './App.vue'
import router from './router'
import './style.css'

use([
  CanvasRenderer, LineChart, PieChart, BarChart,
  TitleComponent, TooltipComponent, GridComponent,
  LegendComponent, DatasetComponent, ToolboxComponent,
])

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
for (const [k, v] of Object.entries(ElIcons)) {
  app.component(k, v as any)
}
app.component('v-chart', ECharts)
app.mount('#app')
