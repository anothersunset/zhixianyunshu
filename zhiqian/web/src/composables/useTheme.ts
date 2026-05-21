// v2-step-25: 主题切换。light/dark/auto, localStorage 持久。
import { ref, watch, onMounted } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'auto'
const LS_KEY = 'zhiqian.theme'

export const themeMode = ref<ThemeMode>(
  (typeof localStorage !== 'undefined' && (localStorage.getItem(LS_KEY) as ThemeMode)) || 'auto'
)

function applyTheme(mode: ThemeMode) {
  const root = document.documentElement
  let isDark = false
  if (mode === 'dark') isDark = true
  else if (mode === 'light') isDark = false
  else isDark = window.matchMedia('(prefers-color-scheme: dark)').matches

  if (isDark) root.classList.add('dark')
  else root.classList.remove('dark')
  // Element Plus 粘接: 它他看 html.dark
  root.setAttribute('data-theme', isDark ? 'dark' : 'light')
}

export function useTheme() {
  onMounted(() => applyTheme(themeMode.value))

  watch(themeMode, (m) => {
    if (typeof localStorage !== 'undefined') localStorage.setItem(LS_KEY, m)
    applyTheme(m)
  })

  // 跟随系统
  if (typeof window !== 'undefined' && window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', () => {
      if (themeMode.value === 'auto') applyTheme('auto')
    })
  }

  return { themeMode, setTheme: (m: ThemeMode) => (themeMode.value = m) }
}
