// v2-step-25: 装 vue-i18n + theme CSS。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'  // 启用 ElPlus 暗色 CSS 变量
// ECharts 5 需显式注册组件（vue-echarts 不会自动引入）
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
use([CanvasRenderer, LineChart, PieChart, TooltipComponent, LegendComponent, GridComponent])
import router from './router'
import App from './App.vue'
import { i18n } from './locales'
import './styles/theme.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.use(i18n)
app.mount('#app')
