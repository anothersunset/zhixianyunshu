<template>
  <el-tag :type="tagType" effect="light" round size="small"> label </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ level?: string }>()
const label = computed(() => (props.level || 'UNKNOWN').toUpperCase())
const tagType = computed(() => {
  switch (label.value) {
    case 'LOW': return 'success'
    case 'MEDIUM': return 'warning'
    case 'HIGH': return 'danger'
    default: return 'info'
  }
})
</script>
