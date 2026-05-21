<!-- v2-step-25: 主题切换下拉。 -->
<script setup lang="ts">
import { useTheme, type ThemeMode } from '@/composables/useTheme'
import { useI18n } from 'vue-i18n'
const { themeMode, setTheme } = useTheme()
const { t } = useI18n()
function onChange(v: string) { setTheme(v as ThemeMode) }
</script>

<template>
  <el-select :model-value="themeMode" size="small" style="width: 120px" @change="onChange">
    <el-option value="light" :label="t('theme.light')" />
    <el-option value="dark"  :label="t('theme.dark')" />
    <el-option value="auto"  :label="t('theme.auto')" />
  </el-select>
</template>
