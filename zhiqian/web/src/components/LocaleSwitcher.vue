<!-- v2-step-25: 语言切换。 -->
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { setLocale, SUPPORTED_LOCALES } from '@/locales'
const { locale } = useI18n()
function onChange(v: string) { setLocale(v as 'zh-CN' | 'en-US') }
</script>

<template>
  <el-select :model-value="locale" size="small" style="width: 100px" @change="onChange">
    <el-option v-for="l in SUPPORTED_LOCALES" :key="l.value" :value="l.value" :label="l.label" />
  </el-select>
</template>
