<template>
  <el-table :data="rows" stripe>
    <el-table-column prop="category" label="类别" width="120" />
    <el-table-column prop="target" label="目标" />
    <el-table-column prop="riskLevel" label="风险" width="100" />
    <el-table-column prop="confidence" label="置信度" width="100" />
    <el-table-column prop="reviewStatus" label="复核状态" width="120" />
  </el-table>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { http } from "@/api/client"
const props = defineProps<{ taskId: number }>()
const rows = ref<any[]>([])
onMounted(async () => {
  rows.value = await http.get(`/tasks/${props.taskId}/suggestions`)
})
</script>
