<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <span>迁移任务</span>
          <span class="count">共 {{ store.tasks.length }} 项</span>
        </div>
      </template>
      <div class="responsive-table">
      <el-table :data="store.tasks" stripe v-loading="loading" empty-text="暂无迁移任务">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名" min-width="220" show-overflow-tooltip />
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
        <el-table-column label="需人工复核" width="120">
          <template #default="{ row }">{{ row.reviewRequired ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/tasks/${row.id}`)">详情 / SSE</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
const store = useTaskStore()
const loading = ref(false)

function statusType(s: string) {
  if (s === 'DONE') return 'success'
  if (s === 'RUNNING') return 'primary'
  if (s === 'FAILED') return 'danger'
  if (s === 'REVIEW_REQUIRED') return 'warning'
  if (s === 'PENDING') return 'info'
  return 'warning'
}

onMounted(async () => {
  loading.value = true
  try { await store.refreshAll() } catch (e: any) { ElMessage.error(e?.message || '加载任务列表失败') } finally { loading.value = false }
})
</script>

<style scoped>
.page {
  padding: 20px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.count {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  font-weight: 400;
}

@media (max-width: 600px) {
  .page {
    padding: 12px;
  }
}
</style>
