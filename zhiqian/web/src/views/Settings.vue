<template>
  <div class="page">
    <el-card shadow="never"><template #header>系统设置</template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="当前用户"> me?.displayName || me?.username </el-descriptions-item>
        <el-descriptions-item label="角色"><el-tag> me?.role </el-tag></el-descriptions-item>
        <el-descriptions-item label="后端地址"> apiBase </el-descriptions-item>
        <el-descriptions-item label="RAG 地址"> ragBase </el-descriptions-item>
      </el-descriptions>
      <el-button style="margin-top:16px" type="danger" @click="logout">退出登录</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getMe } from '@/api/auth'

const me = ref<any>(null)
const apiBase = import.meta.env.VITE_API_BASE
const ragBase = import.meta.env.VITE_RAG_BASE

onMounted(async () => { try { me.value = await getMe() } catch {} })

function logout() {
  localStorage.removeItem('zq_token')
  window.location.hash = '#/login'
}
</script>

<style scoped>.page{padding:16px}</style>
