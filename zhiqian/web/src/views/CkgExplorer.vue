<template>
  <div class="page">
    <el-card shadow="never">
      <template #header>CKG 代码知识图谱 · Cytoscape.js 可视化</template>
      <el-form inline>
        <el-form-item label="项目">
          <el-input-number v-model="projectId" :min="1" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="节点类型">
          <el-select v-model="selectedTypes" multiple collapse-tags placeholder="全部" style="width: 280px">
            <el-option v-for="t in allTypes" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="search" placeholder="节点名包含" style="width: 200px" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load" :loading="loading">加载</el-button>
          <el-button @click="doFit">适配视口</el-button>
        </el-form-item>
      </el-form>
      <div v-if="resp" class="stats">
        <el-tag size="small" v-text="'节点 ' + resp.nodes.length" />
        <el-tag size="small" type="success" v-text="'边 ' + resp.edges.length" />
        <el-tag v-if="resp.demo" size="small" type="warning">演示数据</el-tag>
      </div>
    </el-card>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="17">
        <el-card shadow="never" body-style="padding: 8px">
          <CkgGraph
            v-if="resp"
            ref="graphRef"
            :nodes="resp.nodes"
            :edges="resp.edges"
            :type-filter="selectedTypes"
            :search="search"
            @node-click="onNodeClick"
          />
          <el-empty v-else description="点击加载" />
        </el-card>
      </el-col>
      <el-col :span="7">
        <el-card shadow="never">
          <template #header>节点详情</template>
          <div v-if="selectedNode">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="ID"><span v-text="selectedNode.id" /></el-descriptions-item>
              <el-descriptions-item label="名称"><span v-text="selectedNode.label" /></el-descriptions-item>
              <el-descriptions-item label="类型">
                <el-tag size="small" v-text="selectedNode.type" />
              </el-descriptions-item>
            </el-descriptions>
            <div class="neighbors" v-if="neighbors.length">
              <div class="label">邻居 (共 <span v-text="neighbors.length" />):</div>
              <el-tag v-for="n in neighbors" :key="n.id" size="small" style="margin: 2px" v-text="n.label" />
            </div>
          </div>
          <el-empty v-else description="点击节点查看详情" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import CkgGraph from '@/components/CkgGraph.vue'
import { fetchCkgGraph } from '@/api/ckg'
import type { CkgGraphResp, CkgNode } from '@/api/ckg'

const projectId = ref(1)
const selectedTypes = ref<string[]>([])
const search = ref('')
const loading = ref(false)
const resp = ref<CkgGraphResp | null>(null)
const selectedNode = ref<CkgNode | null>(null)
const graphRef = ref<any>(null)

const allTypes = computed(() => {
  if (!resp.value) return ['File', 'Class', 'Method', 'Table', 'Column']
  const s = new Set<string>()
  for (const n of resp.value.nodes) s.add(n.type)
  return Array.from(s).sort()
})

const neighbors = computed(() => {
  if (!selectedNode.value || !resp.value) return []
  const id = selectedNode.value.id
  const ids = new Set<string>()
  for (const e of resp.value.edges) {
    if (e.source === id) ids.add(e.target)
    else if (e.target === id) ids.add(e.source)
  }
  return resp.value.nodes.filter((n) => ids.has(n.id))
})

async function load() {
  loading.value = true
  try {
    resp.value = await fetchCkgGraph(projectId.value)
    selectedNode.value = null
    ElMessage.success('加载成功: ' + resp.value.nodes.length + ' 节点 / ' + resp.value.edges.length + ' 边')
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

function onNodeClick(n: CkgNode) { selectedNode.value = n }
function doFit() { graphRef.value?.fit() }

load()
</script>

<style scoped>
.page { padding: 16px; }
.stats { display: flex; gap: 8px; margin-top: 8px; }
.neighbors { margin-top: 12px; }
.neighbors .label { font-size: 12px; color: #909399; margin-bottom: 4px; }
</style>
