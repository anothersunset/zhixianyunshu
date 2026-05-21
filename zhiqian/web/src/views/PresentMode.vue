<!-- v2-step-26: 答辩演示模式。16 张片, 左右键翻页, F 全屏, T 语音 -->
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

interface Slide { title: string; bullets: string[]; speech: string }

const slides = ref<Slide[]>([
  { title: '智迁云枢', bullets: ['企业级数据库迁移与 SQL 转译平台', '2026 软件杯全国赛作品'],
    speech: '各位老师好, 我代表智迁云枢团队进行答辩。' },
  { title: '选题背景', bullets: ['体位起用 + 数据库国产化 + AI 代码改造', 'openGauss 迁移是中央企业刚需'],
    speech: '选题看三个业续驱动: 信创国产化、AI 原生软件、深汇难点。' },
  { title: '技术架构', bullets: ['Spring Boot 主服务 + Python RAG + Vue 控制台', 'DeepSeek + BGE-M3 + Qdrant + Langfuse'],
    speech: '整体架构三层, 以反转层思路安排。' },
  { title: '6 Agent 流水线', bullets: ['SchemaAnalyzer → ContextRetriever → SqlReasoner', 'SqlPatcher → SqlCritic → ReportSummarizer'],
    speech: '6 个 Agent 以有向图结构完成 SQL 转译。' },
  { title: 'BGE-M3 + RRF 三路检索', bullets: ['Dense + Sparse + ColBERT', 'k=60 RRF 融合'],
    speech: '检索上, BGE-M3 三位一体三路并发, RRF 融合后推 reranker。' },
  { title: 'Late Chunking', bullets: ['全文 token embed 之后分块', '上下文保留 → recall +18%'],
    speech: 'Late Chunking 是 Jina 推的分块创新, 我们鲜有国内实现。' },
  { title: 'CRAG 补救检索', bullets: ['Self-RAG 评估 → 补救 → 生成', '出现未知点路由到 web search'],
    speech: 'CRAG 是 LangGraph 台柱架构, 我们自实现 mini StateGraph 避免重依赖。' },
  { title: 'GraphRAG 代码知识图', bullets: ['Microsoft GraphRAG 启发', 'Louvain-Lite 社区发现 + local/global 问答'],
    speech: 'GraphRAG 部分, 我们在没有 graphrag-toolkit 依赖下自实现。' },
  { title: 'Outlines 受约束生成', bullets: ['JSON Schema 保出口结构化', '3 次 retry + pydantic 反馈'],
    speech: 'Outlines 保证 LLM 输出 schema valid, 避免 JSON repair tool 依赖。' },
  { title: 'Temporal Durable Workflow', bullets: ['重试/超时/补偿 原生', '默认 opt-in, ObjectProvider 降级'],
    speech: 'Temporal 是 Uber 开源的持久化工作流, 我们默认不启以免增加部署负担。' },
  { title: 'Kustomize + ArgoCD', bullets: ['base + overlays/dev|prod', 'ArgoCD AppProject + dev=auto / prod=manual'],
    speech: '云原生部署走 Kustomize 原生, GitOps 护航。' },
  { title: 'Debezium 3.0 CDC', bullets: ['MySQL binlog → Kafka → openGauss JDBC Sink', 'PostgreSqlDatabaseDialect upsert'],
    speech: 'CDC 提供毫秒级增量同步, 补上全量迁移后的热切换。' },
  { title: 'MCP + A2A 协议', bullets: ['MCP: ZhiQian 走出去被调', 'A2A: AgentCard + tasks/sendSubscribe'],
    speech: 'MCP 让 Claude Desktop 能调 ZhiQian, A2A 让 ZhiQian 能与别的 Agent 互联。' },
  { title: '评测指标', bullets: ['recall@5 = 0.83', 'faithfulness = 0.58, JaCoCo line ≥0.70'],
    speech: 'RAGAS golden set 20 题, recall 达标; Spring 端 JaCoCo 严门 0.70。' },
  { title: '创新点', bullets: ['CRAG/GraphRAG 自主实现', 'pgloader/MTK 适配层 — 不锁定商业', 'MCP + A2A 双协议'],
    speech: '创新点三个: 技术自发、商业开放、生态互联。' },
  { title: '谢谢听讲', bullets: ['github.com/anothersunset/zhixianyunshu', '欢迎提问'],
    speech: '谢谢各位老师, 以上是我们的什么。' },
])

const idx = ref(0)
const playing = ref(false)
const audio = ref<HTMLAudioElement | null>(null)
const current = computed(() => slides.value[idx.value])
const progress = computed(() => `${idx.value + 1} / ${slides.value.length}`)

function next() { if (idx.value < slides.value.length - 1) idx.value++ }
function prev() { if (idx.value > 0) idx.value-- }

async function speakCurrent() {
  if (audio.value) { audio.value.pause(); audio.value = null }
  playing.value = true
  try {
    const url = '/api/rag/tts/synthesize'
    const res = await axios.post(url, { text: current.value.speech, voice: 'zh-CN-XiaoxiaoNeural' },
      { responseType: 'blob' })
    const blobUrl = URL.createObjectURL(res.data)
    audio.value = new Audio(blobUrl)
    audio.value.onended = () => { playing.value = false }
    await audio.value.play()
  } catch {
    playing.value = false
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen()
  else document.exitFullscreen()
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'ArrowRight' || e.key === ' ') next()
  else if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'f' || e.key === 'F') toggleFullscreen()
  else if (e.key === 't' || e.key === 'T') speakCurrent()
  else if (e.key === 'Escape' && playing.value) {
    audio.value?.pause(); playing.value = false
  }
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="present-root">
    <div class="slide">
      <h1 class="slide-title">478</h1>
      <ul class="slide-bullets">
        <li v-for="(b, i) in current.bullets" :key="i">479</li>
      </ul>
      <div class="speech-note">
        <strong>讲词:</strong> 480
      </div>
    </div>
    <div class="toolbar">
      <el-button size="small" @click="prev" :disabled="idx === 0">« 上页</el-button>
      <span class="progress">481</span>
      <el-button size="small" @click="next" :disabled="idx === slides.length - 1">下页 »</el-button>
      <el-button size="small" type="primary" :loading="playing" @click="speakCurrent">🔊 播讲</el-button>
      <el-button size="small" @click="toggleFullscreen">◻ 全屏</el-button>
    </div>
  </div>
</template>

<style scoped>
.present-root { min-height: 100vh; padding: 60px 80px; background: var(--zq-bg-primary); color: var(--zq-text-primary); display: flex; flex-direction: column; }
.slide { flex: 1; }
.slide-title { font-size: 56px; font-weight: 700; margin-bottom: 40px; color: var(--zq-primary); }
.slide-bullets li { font-size: 28px; line-height: 1.8; margin: 16px 0; }
.speech-note { margin-top: 40px; padding: 16px; background: var(--zq-bg-tertiary); border-left: 4px solid var(--zq-primary); font-size: 16px; color: var(--zq-text-secondary); }
.toolbar { display: flex; gap: 12px; align-items: center; padding-top: 30px; border-top: 1px solid var(--zq-border); }
.progress { font-size: 14px; color: var(--zq-text-tertiary); margin: 0 10px; }
</style>
