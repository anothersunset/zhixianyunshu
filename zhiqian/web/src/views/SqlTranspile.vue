<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="flex">
          <span style="font-weight:600">SQL 方言转译</span>
          <el-tag size="small">sqlglot AST</el-tag>
          <el-tag v-if="version" type="success" size="small" v-text="versionLabel" />
          <el-tag v-else type="warning" size="small">rag 未连接</el-tag>
        </div>
      </template>
      <el-row :gutter="16">
        <el-col :span="6">
          <el-form-item label="源方言">
            <el-select v-model="source" style="width:100%">
              <el-option v-for="d in dialects" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="目标方言">
            <el-select v-model="target" style="width:100%">
              <el-option v-for="d in dialects" :key="d" :label="d" :value="d" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="6">
          <el-form-item label="模式">
            <el-radio-group v-model="explain">
              <el-radio :value="true">解释</el-radio>
              <el-radio :value="false">仅转译</el-radio>
            </el-radio-group>
          </el-form-item>
        </el-col>
        <el-col :span="6" style="text-align:right;padding-top:6px">
          <el-button type="primary" :loading="loading" @click="doTranspile">
            <el-icon><Refresh /></el-icon> 转译
          </el-button>
          <el-button @click="loadExample">示例</el-button>
          <el-button @click="clearInput">清空</el-button>
        </el-col>
      </el-row>
      <el-input
        v-model="sql"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 12 }"
        placeholder="粘贴 MySQL SQL...例: SELECT DATE_FORMAT(t,'%Y-%m'), IFNULL(a,b) FROM users LIMIT 5,10"
        style="font-family:monospace;font-size:13px"
      />
    </el-card>

    <el-card v-if="result" style="margin-top:16px">
      <template #header>
        <div class="flex">
          <span style="font-weight:600">Diff 结果</span>
          <el-tag v-if="result.ok" type="success" size="small" v-text="dialectLabel" />
          <el-tag v-else type="danger" size="small">转译失败</el-tag>
          <el-tag v-if="result && result.sqlglot_version" size="small" v-text="sqlglotLabel" />
        </div>
      </template>
      <el-alert v-if="!result.ok" type="error" :title="result.error || '转译失败'" show-icon :closable="false" />
      <SqlDiffEditor v-else :original="result.source" :modified="result.target || ''" height="400px" />
      <div v-if="result.ok && result.notes && result.notes.length" style="margin-top:14px">
        <div style="font-weight:600;margin-bottom:8px" v-text="notesTitle" />
        <el-table :data="result.notes" border size="small">
          <el-table-column prop="keyword" label="函数/关键字" width="200" />
          <el-table-column prop="note" label="说明" />
        </el-table>
      </div>
      <div v-else-if="result.ok" style="margin-top:14px;color:#909399;font-size:13px">
        本 SQL 中未检测到需注意的跨方言函数。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import SqlDiffEditor from '@/components/SqlDiffEditor.vue'
import { transpile, getRagHealth } from '@/api/transpile'

const sql = ref('')
const source = ref('mysql')
const target = ref('opengauss')
const explain = ref(true)
const loading = ref(false)
const result = ref<any>(null)
const version = ref('')

const dialects = [
  'mysql', 'opengauss', 'postgres', 'sqlite', 'oracle', 'tsql', 'snowflake', 'bigquery',
]

const versionLabel = computed(() => 'v' + (version.value || ''))
const dialectLabel = computed(() => {
  const r = result.value
  if (!r || !r.ok) return ''
  return (r.source_dialect || '?') + ' → ' + (r.target_dialect || '?')
})
const sqlglotLabel = computed(() => 'sqlglot ' + (result.value?.sqlglot_version || ''))
const notesTitle = computed(() => '变动说明 (' + (result.value?.notes?.length || 0) + ')')

const EXAMPLE = `SELECT u.id,
       DATE_FORMAT(u.created_at, '%Y-%m') AS month,
       IFNULL(u.nick, u.name)             AS display,
       GROUP_CONCAT(o.id SEPARATOR ',')   AS order_ids
FROM \`users\` u
LEFT JOIN \`orders\` o ON o.user_id = u.id
WHERE u.created_at > FROM_UNIXTIME(1704067200)
GROUP BY month, display
LIMIT 10, 20`

function loadExample() {
  sql.value = EXAMPLE
}

function clearInput() {
  sql.value = ''
  result.value = null
}

async function doTranspile() {
  if (!sql.value.trim()) {
    ElMessage.warning('请先输入 SQL')
    return
  }
  loading.value = true
  try {
    const r = await transpile({
      sql: sql.value,
      source: source.value,
      target: target.value,
      explain: explain.value,
    })
    result.value = r
    if (r.ok) {
      const n = r.notes?.length || 0
      ElMessage.success('转译成功。' + n + ' 条变动说明。')
    } else {
      ElMessage.error('转译失败: ' + (r.error || '未知错误'))
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '网络异常 (rag service 未启动?)')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const h = await getRagHealth()
    version.value = h?.capabilities?.sqlglot_version || ''
  } catch {
    // rag 不可达 — 页面仍可加载, 转译时报错
  }
  loadExample()
})
</script>

<style scoped>
.page { padding: 8px; }
.flex { display: flex; align-items: center; gap: 10px; }
:deep(.el-form-item) { margin-bottom: 0; }
</style>
