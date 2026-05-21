<!-- v2-step-26: 答辩演示模式。路由 /present, 10 张幻灯片 覆盖定位/架构/创新点/演示。-->
<script setup lang="ts">
import SlideDeck from '@/components/SlideDeck.vue'
import type { Slide } from '@/components/SlideDeck.vue'

const slides: Slide[] = [
  {
    title: '智迁云枢 ZhiQian YunShu',
    body: 'LLM Agent + Knowledge Graph 驱动的跨方言数据库迁移智体',
    bullets: ['MySQL / Oracle / SQLServer → openGauss / PostgreSQL', '一键智迁, AI 可解释, 生态互联'],
    notes: '报告开场 30s, 点清、点亮。背景概述不超三句。',
  },
  {
    title: '面临的问题',
    bullets: [
      '数据库国产化: Oracle → openGauss 是金融/政务刚需',
      '传统迁移工具不看语义 — PL/SQL / 存储过程留给人工',
      '仅表结构迁, 指令难跨方言 (LIMIT / IFNULL / sequence)',
    ],
    notes: '询问听众: 你们公司在迁移上花过多少人月?',
  },
  {
    title: '架构一眼看',
    bullets: [
      'Web (Vue3) + Backend (Spring Boot) + RAG (FastAPI) 三层',
      '6 Agent 流水线: SchemaAnalyzer → ContextRetriever → SqlReasoner → Patcher → Critic → Reporter',
      'Debezium 3.0 + Kafka Connect 拼出 CDC 路径, KubeRay 拼出弹性推理',
    ],
    notes: '架构图详 docs/architecture/00-overall.md',
  },
  {
    title: '创新点 (1/2) — 检索与解码',
    bullets: [
      'BGE-M3 三路 (Dense / Sparse / ColBERT) + RRF k=60',
      'CRAG mini StateGraph: retrieve → evaluate → correct → generate',
      'GraphRAG 自实现 Louvain-Lite, 能回答跨表 PL/SQL 依赖',
      'Outlines 受约束解码 + pydantic 3 轮 retry',
    ],
  },
  {
    title: '创新点 (2/2) — 生态与体验',
    bullets: [
      '双协议: MCP server (被 Claude/Cursor 调) + A2A peer (与其他 Agent 互联)',
      'MigrationToolFactory 适配: pgloader / Ora2Pg / ZhiQian 同位 → score 推荐',
      'transformers.js 端侧 Phi-3.5-mini (WebGPU / WASM), 隐私场景可脱后端',
      'Typst PDF 迁移报告: 编译<1s, 中文原生, 免装 TeX Live',
    ],
  },
  {
    title: 'Demo 路径',
    bullets: [
      '登录 → 选 benchmark-sakila 项目',
      '走一次 MySQL → openGauss 转译, 看 6 Agent trace',
      '下载 Typst PDF 报告, 含风险表 + SQL 示例',
      'Claude Desktop 调 MCP: "帮我把这段 SQL 转为 openGauss"',
    ],
  },
  {
    title: '同类产品对比',
    bullets: [
      'AWS DMS / Alibaba DTS — 云锁定, 不能本地',
      'pgloader / DataX — 吞吐高, 无 LLM, 跨方言复杂语句着创',
      'Ora2Pg — Oracle 专精, 多源不胜',
      'ZhiQian: 智能层 + 适配层 + 生态层, 同类产品是点, ZhiQian 是面',
    ],
  },
  {
    title: '供应链与质量',
    bullets: [
      'Syft CycloneDX SBOM + Trivy SARIF + Cosign keyless OIDC',
      'SLSA Build L2 定位, Rekor public ledger 透明',
      'JaCoCo BUNDLE ≥0.70 + Spring Boot Test 4 集成',
      'Langfuse 全链 trace, OpenAI compatible + DeepSeek Chat',
    ],
  },
  {
    title: '路线图',
    bullets: [
      'Q3 2026: 生产级性能 benchmark + 5 条真实客户迁移案例',
      'Q4 2026: Spring AI / LangChain4j 集成, 多 Agent 协作复杂项目',
      '2027 H1: openGauss CloudNativePG, AI 驱动 Index Tuning',
    ],
  },
  {
    title: '谢谢',
    body: 'Q & A',
    bullets: [
      'github.com/anothersunset/zhixianyunshu',
      '一键 Demo: bash scripts/demo-walkthrough.sh',
      '双协议: MCP http://localhost:8001/mcp/rpc · A2A http://localhost:8080/.well-known/agent.json',
    ],
    notes: '不走预示, 看现场问题。压轴在 1m30s 以内。',
  },
]
</script>

<template>
  <SlideDeck :slides="slides" />
</template>
