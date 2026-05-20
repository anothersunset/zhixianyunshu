<template>
  <el-container class="app-layout">
    <el-aside width="200px">
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/dashboard">仪表盘</el-menu-item>
        <el-menu-item index="/projects">项目</el-menu-item>
        <el-menu-item index="/tasks">迁移任务</el-menu-item>
        <el-menu-item index="/kb">知识库</el-menu-item>
        <el-menu-item index="/reports">报告中心</el-menu-item>
        <el-menu-item index="/settings">设置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-main><router-view /></el-main>
  </el-container>
</template>

<script setup lang="ts"></script>

<style scoped>
.app-layout { height: 100vh; }
</style>
