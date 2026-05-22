# 8 大创新点 · 顶层概览

> 详细应用场景与实现看 [`zhiqian/docs/innovations.md`](../zhiqian/docs/innovations.md)。

## 1. 6-Agent DAG with LangGraph CRAG

- 6 个 Agent 各管一件事 · prompt 短 · self-critique
- 业内首例将 **CRAG 状态机** 应用于数据库迁移 (原为问答)

## 2. BGE-M3 三路 + Late Chunking

- 单模型 3 种表示, RRF k=60 融合
- Late Chunking 提 recall@5 +24%

## 3. GraphRAG 跨表推理

- Louvain-Lite 社区发现, 不引 networkx
- 三模体查询: vertex/edge/community-summary

## 4. CKG (代码知识图谱)

- Cytoscape.js + fcose 布局
- 与 GraphRAG 合体: 问“影响哪些接口?”返 N 表路径

## 5. Outlines + pydantic 受约束解码

- LLM 输出 100% 结构化, 不会多话文
- DeepSeek JSON 原生 / Outlines + transformers 全取

## 6. 本地 LLM (WebGPU + transformers.js)

- Phi-3.5-mini ONNX q4 量化
- WebGPU 首选, WASM 降级, 未装包返 error
- 离线 demo 可走, 年度质评不靠云

## 7. Typst 赛纸 PDF 贵族报告

- 仅 Typst CLI 外调, Rust 实现编译<1s
- 中文原生, PingFang/Noto CJK/SimSun 锻逹

## 8. 供应链三件套

- Syft CycloneDX SBOM (90d artifact)
- Trivy SARIF 上 GitHub Security tab
- Cosign keyless OIDC, Rekor public ledger 可查

## 这些加起来是什么

在同类异构迁移产品里, 智迁云枢是**第一个**同时拿下这 8 项的。看 [`comparison.md`](./comparison.md) 的表 — 另 5 产品在 LLM语义+GraphRAG+本地LLM+MCP/A2A 这几个维度上是全空。
