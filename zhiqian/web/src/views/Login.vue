<template>
  <div class="login">
    <el-card class="box">
      <h2 class="title">智迁云枢 · ZhiQian YunShu</h2>
      <div class="sub">中国软件杯 · 数据库智能迁移平台</div>
      <el-form :model="form" label-width="60px" @submit.prevent="submit">
        <el-form-item label="账户"><el-input v-model="form.username" autocomplete="username" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-button type="primary" :loading="loading" @click="submit" style="width:100%">登录</el-button>
      </el-form>
      <div class="hint">默认管理员：admin / admin123</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '@/api/auth'

const form = reactive({ username: 'admin', password: 'admin123' })
const loading = ref(false)
const route = useRoute()
const router = useRouter()

// 登录后优先回到守卫记录的深链; 仅接受以单个 '/' 开头的站内路径 (排除 '//' 防 open redirect)
function safeRedirectTarget(): string {
  const target = route.query.redirect
  if (typeof target === 'string' && target.startsWith('/') && !target.startsWith('//')) {
    return target
  }
  return '/'
}

async function submit() {
  loading.value = true
  try {
    const r = await login(form.username, form.password)
    localStorage.setItem('zq_token', r.token)
    localStorage.setItem('zq_role', r.role)
    ElMessage.success(`欢迎回来，${r.displayName || r.username}`)
    router.push(safeRedirectTarget())
  } catch (e: any) {
    ElMessage.error(e?.message || '登录失败')
  } finally { loading.value = false }
}
</script>

<style scoped>
.login{height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#1e3a8a,#0ea5e9)}
.box{width:380px;padding:8px}
.title{margin:0 0 4px;text-align:center;color:#303133}
.sub{text-align:center;color:#909399;font-size:12px;margin-bottom:18px}
.hint{margin-top:14px;text-align:center;color:#909399;font-size:12px}
</style>
