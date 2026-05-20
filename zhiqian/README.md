# 🛰️ 智迁云枢 · ZhiQian Agent

> **信创软件迁移的可信智能 Agent 平台 · 中国软件杯参赛作品**

## 一句话
智迁云枢 = **信创软件迁移** × **AI Agent 落地** × **可信工程**。

## 8 个必背数字
1. **90s** · 从 ZIP 上传到出 PDF 报告的端到端延迟
2. **0.891** · RAG 综合评分(v3 基准)
3. **38** · 示例项目产出 patches 数
4. **7** · 业务 Agent 数(Planner / CodeAnalyzer / SQLCompat / KnowledgeRetriever / SolutionGen / Evaluator / Auditor)
5. **0** · 万条审计链中断裂 hash 数
6. **≤ 30min** · 复核 SLA
7. **≤ 50ms** · 接口 P99 延迟
8. **≥ 1万** · KB chunks 总量

## 系统架构(5 层 + 7 Agent)

```text
┌────────────────────────────────────────────────────────┐
│ L5 治理层  Hash 链审计 · 复核 · RBAC · Grafana 5 大盘 │
├────────────────────────────────────────────────────────┤
│ L4 业务层  PatchGenerator · Validation · Report      │
├────────────────────────────────────────────────────────┤
│ L3 编排层  Planner + 7 业务 Agent + 状态机           │
├────────────────────────────────────────────────────────┤
│ L2 知识层  BGE-M3 · GraphRAG · CKG · 三类记忆        │
├────────────────────────────────────────────────────────┤
│ L1 感知层  AST · SQL Parser · 依赖扫描 · 配置扫描    │
└────────────────────────────────────────────────────────┘
```

## 子模块

| 目录 | 模块 | 技术栈 |
|---|---|---|
| [`backend/`](./backend) | Spring Boot 主服务 + Agent 编排 + 治理审计 + 代码分析 | Spring Boot 3 · JWT · MyBatis · Flyway · JavaParser · JSqlParser |
| [`rag/`](./rag) | Python AgenticRAG + 信创知识库 + GraphRAG | FastAPI · BGE-M3 · ChromaDB · NetworkX |
| [`web/`](./web) | Vue 3 控制台 | Vue 3 · Element Plus · Pinia · ECharts · SSE |
| [`deploy/`](./deploy) | Docker Compose 一键部署 + Grafana 大盘 | Docker · Prometheus · Grafana |
| [`docs/`](./docs) | 架构 / 概要设计 / API | Markdown · Mermaid |

## License
Apache-2.0
