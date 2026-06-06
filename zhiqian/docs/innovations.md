# 智迁云枢 8 大创新点 (v2-step-30)

> 说明：本页描述当前工程能力和创新设计。涉及 CRAG / GraphRAG / Late Chunking 的效果表述均以“已实现控制流 / baseline”为准，真实语义增益需通过后续对照实验验证。

## 1. 双协议生态互联 (MCP + A2A) 🌟
同类迁移产品通常不接这两个协议。智迁同时是 MCP server（被 Claude / Cursor 调）+ A2A peer（与其他 Agent 互联），更贴近 2026 LLM Agent 生态。

## 2. 三路检索 + RRF 低成本混合
Dense + Sparse + ColBERT 三路并发，RRF k=60 融合。跨方言 SQL 检索场景中，sparse term 可补 Dense 容易忽略的术语变体；真实收益需在迁移样本集上补 Recall@5 / Top-5 precision 对照。

## 3. CRAG mini StateGraph 自实现
不引 langgraph 重依赖，自写轻量 StateGraph：retrieve → evaluate（LLM + heuristics 双轨）→ correct / fallback → generate。价值在于控制流清晰、可降级、可插 LLM judge；默认启发式结果不直接等同真实模型效果。

## 4. GraphRAG / CKG 轻量图实现
以 CKG / Louvain-Lite 思路组织表、列、索引、外键、视图等依赖关系，支持 local / global 双检索。当前重点是工程骨架与展示链路，跨表推理收益需要多跳问题集验证。

## 5. Outlines 受约束解码 + 3 次 retry pydantic 反馈
JSON Schema 保结构化，pydantic 错误反馈给 LLM。双后端：DeepSeek native JSON mode + outlines binding。

## 6. Temporal Durable Workflow + ObjectProvider 优雅降级
默认 enabled=false 不加负担，opt-in 后 Temporal worker 接管重试 / 超时 / 补偿。Controller 用 ObjectProvider，unavailable 返 503 而不是启动崩。

## 7. MigrationToolFactory 适配层（不锁定商业）
ZhiQian Native / pgloader / Ora2Pg / Debezium 多轨同位，按 (src,tgt) 调 score 推荐。后续可插 AWS DMS / Alibaba DTS / DataX 作为 additional adapters。

## 8. 端侧推理 (transformers.js + Phi-3.5-mini)
优先上 WebGPU，WASM 降级。适合隐私场景、演示场景和弱网环境。
