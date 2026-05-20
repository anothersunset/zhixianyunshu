<template>
  <div class="login-page">
    <el-card class="box">
      <h2>智迁云枢控制台</h2>
      <el-form :model="form" label-width="60px">
        <el-form-item label="账号"><el-input v-model="form.username"/></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password"/></el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { http } from "@/api/client"

const router = useRouter()
const form = reactive({ username: "", password: "" })
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    const r = await http.post<{ token: string }>("/auth/login", form)
    localStorage.setItem("zhiqian_jwt", r.token)
    router.replace("/dashboard")
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display:flex;justify-content:center;align-items:center;height:100vh;background:#f3f5f9; }
.box { width: 360px; }
</style>
