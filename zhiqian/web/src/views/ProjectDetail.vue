<template>
  <div class="page">
    <el-page-header :content="project?.name || '项目详情'" @back="router.back()" />
    <el-descriptions :column="2" border style="margin-top:16px" v-if="project">
      <el-descriptions-item label="源库"><span v-text="project.sourceDb" /></el-descriptions-item>
      <el-descriptions-item label="目标库"><span v-text="project.targetDb" /></el-descriptions-item>
      <el-descriptions-item label="技术栈"><span v-text="project.framework" /></el-descriptions-item>
      <el-descriptions-item label="状态"><el-tag v-text="project.status" /></el-descriptions-item>
      <el-descriptions-item label="描述" :span="2"><span v-text="project.description" /></el-descriptions-item>
    </el-descriptions>

    <el-card shadow="never" style="margin-top:16px">
      <template #header>本项目下的任务</template>
      <el-table :data="taskStore.tasks.filter(t => t.projectId === id)" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="任务名" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }"><el-tag v-text="row.status" /></template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/tasks/\${row.id}`)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getProject, type Project } from '@/api/project'
import { useTaskStore } from '@/stores/task'

const route = useRoute()
const router = useRouter()
const id = computed(() => Number(route.params.id))
const project = ref<Project | null>(null)
const taskStore = useTaskStore()

onMounted(async () => {
  project.value = await getProject(id.value)
  if (!taskStore.tasks.length) await taskStore.refreshAll()
})
</script>

<style scoped>.page{padding:16px}</style>
