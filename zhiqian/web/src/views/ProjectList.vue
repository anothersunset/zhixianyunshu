<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>
        <div class="hdr"><span>项目列表</span><el-button type="primary" :icon="Plus" disabled>新建项目（演示）</el-button></div>
      </template>
      <el-table :data="items" stripe v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="sourceDb" label="源库" width="140" />
        <el-table-column prop="targetDb" label="目标库" width="140" />
        <el-table-column prop="framework" label="技术栈" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }"><el-tag> row.status </el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }"><el-button link type="primary" @click="router.push(`/projects/${row.id}`)">详情</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listProjects, type Project } from '@/api/project'

const router = useRouter()
const items = ref<Project[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try { items.value = await listProjects() } finally { loading.value = false }
})
</script>

<style scoped>.page{padding:16px}.hdr{display:flex;justify-content:space-between;align-items:center}</style>
