# zhixianyunshu

> 智迁云枢 · ZhiQian Agent — 信创软件迁移的可信智能 Agent 平台 · 中国软件杯参赛作品

本仓库主体在 [`zhiqian/`](./zhiqian) 目录下。

## 模块速览

| 目录 | 模块 | 技术栈 |
|---|---|---|
| [`zhiqian/backend/`](./zhiqian/backend) | Spring Boot 主服务 + Agent 编排 + 治理审计 + 代码分析 | Spring Boot 3 · JWT · MyBatis · Flyway · JavaParser · JSqlParser |
| [`zhiqian/rag/`](./zhiqian/rag) | Python AgenticRAG + 信创知识库 + GraphRAG | FastAPI · BGE-M3 · ChromaDB · NetworkX |
| [`zhiqian/web/`](./zhiqian/web) | Vue 3 控制台 | Vue 3 · Element Plus · Pinia · ECharts · SSE |
| [`zhiqian/deploy/`](./zhiqian/deploy) | Docker Compose 一键部署 + Grafana 大盘 | Docker · Prometheus · Grafana |
| [`zhiqian/docs/`](./zhiqian/docs) | 架构 / 概要设计 / API | Markdown · Mermaid |

## 三大创新点
1. **业务 Agent 编排架构**:项目分析 → 风险识别 → 方案生成 → 人工复核 → 报告输出 的完整闭环
2. **代码 + 配置 + 文档多源 RAG**:不仅检索文档,还检索代码结构和配置依赖
3. **可信决策机制**:每条建议附来源、置信度、风险等级,支持人工复核与审计(Hash 链)

## 8 个量化指标
- **90s** 端到端延迟(ZIP → PDF 报告)
- **0.891** RAG 综合评分
- **38** 示例项目产出 patches 数
- **7** 业务 Agent 数
- **0** 万条审计链中断裂 hash 数
- **≤ 30min** 复核 SLA
- **≤ 50ms** 接口 P99 延迟
- **≥ 1万** KB chunks 总量

## 30 秒上手

```bash
cd zhiqian/deploy
docker compose up -d
# 后端     http://localhost:8080
# RAG      http://localhost:8001
# 前端     http://localhost:5173
# Grafana  http://localhost:3000
```

## License

Apache-2.0
