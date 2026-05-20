<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>知识库检索（Self-RAG 演示）</template>
      <el-form inline @submit.prevent="doSearch">
        <el-form-item label="问题">
          <el-input v-model="q" style="width:480px" placeholder="例如：MySQL 的 DATE_FORMAT 在 openGauss 怎么改？" />
        </el-form-item>
        <el-form-item><el-checkbox v-model="rewrite">查询重写</el-checkbox></el-form-item>
        <el-form-item><el-checkbox v-model="critic">Self-RAG critic</el-checkbox></el-form-item>
        <el-form-item><el-button type="primary" :icon="Search" @click="doSearch" :loading="loading">检索</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="16">
        <el-card shadow="never"><template #header>检索结果 ( result?.chunks?.length || 0 )</template>
          <div v-if="result?.rewritten" class="rew">查询重写：<code> result.rewritten </code></div>
          <SourceCitation v-for="c in (result?.chunks || [])" :key="c.id" :chunk="c" />
          <el-empty v-if="!loading && !(result?.chunks?.length)" description="暂无结果" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" v-if="result?.critique"><template #header>Self-RAG 评估</template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="判定"><el-tag :type="verdictType(result.critique.verdict)"> result.critique.verdict </el-tag></el-descriptions-item>
            <el-descriptions-item label="综合分"> result.critique.score </el-descriptions-item>
            <el-descriptions-item label="原因"><ul style="padding-left:18px;margin:0"><li v-for="(r,i) in result.critique.reasons" :key="i"> r </li></ul></el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import axios from 'axios'
import SourceCitation from '@/components/SourceCitation.vue'

const q = ref('MySQL 的 DATE_FORMAT 在 openGauss 怎么改？')
const rewrite = ref(true)
const critic = ref(true)
const loading = ref(false)
const result = ref<any>(null)

function verdictType(v: string) { return v === 'SUPPORTED' ? 'success' : v === 'PARTIAL' ? 'warning' : 'danger' }

async function doSearch() {
  loading.value = true
  try {
    const base = import.meta.env.VITE_RAG_BASE || '/rag'
    const resp = await axios.post(`${base}/query`, { question: q.value, top_k: 5, rewrite: rewrite.value, critic: critic.value })
    result.value = resp.data
  } finally { loading.value = false }
}
</script>

<style scoped>.page{padding:16px}.rew{margin-bottom:12px;color:#606266;font-size:13px}</style>
