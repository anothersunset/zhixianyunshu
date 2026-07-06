// v2-step-25: 瑁?vue-i18n + theme CSS銆?
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'  // 鍚敤 ElPlus 鏆楄壊 CSS 鍙橀噺
// ECharts 6 闇€鏄惧紡娉ㄥ唽缁勪欢锛坴ue-echarts 涓嶄細鑷姩寮曞叆锛?
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
