// v2-step-25: vue-i18n 初始化。
import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

const LS_KEY = 'zhiqian.locale'
const saved = (typeof localStorage !== 'undefined' && localStorage.getItem(LS_KEY)) || 'zh-CN'

export const i18n = createI18n({
  legacy: false,
  locale: saved,
  fallbackLocale: 'zh-CN',
  messages: { 'zh-CN': zhCN, 'en-US': enUS },
})

export function setLocale(locale: 'zh-CN' | 'en-US') {
  i18n.global.locale.value = locale
  if (typeof localStorage !== 'undefined') localStorage.setItem(LS_KEY, locale)
  document.documentElement.lang = locale
}

export const SUPPORTED_LOCALES = [
  { value: 'zh-CN', label: '中文' },
  { value: 'en-US', label: 'English' },
] as const
