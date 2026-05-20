<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>迁移任务</template>
      <el-table :data="store.tasks" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" v-text="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="平均置信度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="Math.round((row.avgConfidence||0)*100)" />
          </template>
        </el-table-column>
        <el-table-column prop="reviewRequired" label="需人工复核" width="120" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/tasks/\${row.id}`)">详情 / SSE</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
const store = useTaskStore()
const loading = ref(false)

function statusType(s: string) {
  if (s === 'DONE') return 'success'
  if (s === 'RUNNING') return 'primary'
  if (s === 'PENDING') return 'info'
  return 'warning'
}

onMounted(async () => {
  loading.value = true
  try { await store.refreshAll() } finally { loading.value = false }
})
</script>

<style scoped>.page{padding:16px}</style>
