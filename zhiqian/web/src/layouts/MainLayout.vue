<template>
  <el-container class="app">
    <el-aside width="220px" class="side">
      <div class="logo">智迁云枢</div>
      <el-menu :default-active="route.path" router :collapse="false" background-color="#0f172a" text-color="#cbd5e1" active-text-color="#38bdf8">
        <el-menu-item index="/"><el-icon><Odometer /></el-icon><span>仪表盘</span></el-menu-item>
        <el-menu-item index="/projects"><el-icon><FolderOpened /></el-icon><span>项目</span></el-menu-item>
        <el-menu-item index="/tasks"><el-icon><Operation /></el-icon><span>任务</span></el-menu-item>
        <el-menu-item index="/knowledge"><el-icon><Reading /></el-icon><span>知识库</span></el-menu-item>
        <el-menu-item index="/reports"><el-icon><Document /></el-icon><span>报告</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>设置</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="hdr"><div> title </div><el-dropdown><el-button text> username  <el-icon><CaretBottom /></el-icon></el-button>
        <template #dropdown><el-dropdown-menu><el-dropdown-item @click="logout">退出登录</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Odometer, FolderOpened, Operation, Reading, Document, Setting, CaretBottom } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const title = import.meta.env.VITE_APP_TITLE || '智迁云枢'
const username = localStorage.getItem('zq_role') === 'ADMIN' ? '管理员' : '用户'

function logout() { localStorage.removeItem('zq_token'); router.push('/login') }
</script>

<style scoped>
.app{height:100vh}
.side{background:#0f172a;color:#cbd5e1}
.logo{height:56px;display:flex;align-items:center;justify-content:center;color:#38bdf8;font-weight:700;font-size:18px;letter-spacing:2px}
.hdr{display:flex;justify-content:space-between;align-items:center;background:#fff;border-bottom:1px solid #ebeef5;padding:0 16px;font-weight:600;color:#303133}
</style>
