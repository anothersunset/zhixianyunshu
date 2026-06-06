# 8 大创新点 · 顶层概览

> 详细应用场景与实现看 [`zhiqian/docs/innovations.md`](../zhiqian/docs/innovations.md)。

## 口径说明

以下创新点描述的是当前工程骨架和设计能力。CRAG / GraphRAG / Late Chunking 的真实语义增益仍需通过真实迁移样本和对照实验验证，不把 demo seed 或启发式 baseline 包装成最终效果证明。

## 1. 6-Agent DAG with CRAG

- 6 个 Agent 各管一件事，prompt 短，stage 可观测。
- 将 **CRAG 状态机** 引入数据库迁移检索链路：retrieve → evaluate → correct / fallback → generate。

## 2. BGE-M3 三路 + Late Chunking

- 单模型 3 种表示，RRF k=60 融合。
- Late Chunking 作为提升长文档语义保留的工程策略；真实收益以后续评测集为准。

## 3. GraphRAG / CKG 跨表推理

- 当前口径为 CKG / GraphRAG 轻量图实现，围绕表、列、索引、外键、视图等对象建立依赖关系。
- 支持 local / global 图检索思路，真实多跳收益待补对照实验。

## 4. CKG（代码 / 数据库知识图谱）

- Cytoscape.js + fcose 布局用于可视化。
- 与 GraphRAG 合体：问“影响哪些接口 / 下游表？”时返回依赖路径。

## 5. Outlines + pydantic 受约束解码

- LLM 输出结构化，减少自由文本漂移。
- DeepSeek JSON 原生 / Outlines + transformers 双后端。

## 6. 本地 LLM（WebGPU + transformers.js）

- Phi-3.5-mini ONNX q4 量化。
- WebGPU 首选，WASM 降级，未装包返 error。
- 离线 demo 可走，隐私场景可降低云端依赖。

## 7. Typst PDF 报告

- 通过 Typst CLI 渲染迁移报告。
- 中文字体按 PingFang / Noto CJK / SimSun 逐级 fallback。

## 8. 供应链三件套

- Syft CycloneDX SBOM。
- Trivy SARIF 上 GitHub Security tab。
- Cosign keyless OIDC，Rekor public ledger 可查。

## 这些加起来是什么

智迁云枢的特点不是单点替代传统迁移工具，而是在传统工具之上叠加 **Agent 编排、RAG / GraphRAG 辅助分析、报告生成、协议互联和供应链治理**。下一步重点是用真实迁移任务证明这些能力带来的效果增益。
