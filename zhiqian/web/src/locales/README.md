# i18n + 暗色 (v2-step-25)

## 使用

```vue
<script setup>
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()
</script>
<template>
  <h1> t('app.title') </h1>
</template>
```

## 加新语言

1. 复制 `zh-CN.ts` 为 `ja-JP.ts`
2. 在 `index.ts` 里面记 messages
3. 在 SUPPORTED_LOCALES 加一项

## 主题

- `light` / `dark` / `auto` (跟随 system, 听 prefers-color-scheme)
- Element Plus 2.7 原生看 `html.dark`
- 自定义 CSS 变量在 `styles/theme.css`

## 面板示例

TopBar 同时摆 `<LocaleSwitcher />` 与 `<ThemeSwitcher />` 二个下拉。
