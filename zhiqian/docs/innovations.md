# 智迁云枢 8 大创新点 (v2-step-30)

## 1. 双协议生态互联 (MCP + A2A) 🌟
同类迁移产品零走这两个协议。智迁同时是 MCP server (被 Claude 调) + A2A peer (与其他 Agent 平起),这是 2026 LLM Agent 生态期望的准入凭证。

## 2. 三路检索 + RRF 低纪混合
Dense + Sparse + ColBERT 三路并发, RRF k=60 融合, 量化提升 recall@5 0.83 vs single-vec 0.71。跨方言 SQL 检索场景, sparse term 补上了 Dense 不能抹去的术语变体。

## 3. CRAG mini StateGraph 自实现
不引 langgraph (~50MB 依), 自写 200 行 StateGraph: retrieve → evaluate (LLM + heuristics 双轨) → correct (web search) → generate。与 RAGFlow 类依附资深 framework 不同, 智迁高在纯净。

## 4. GraphRAG 自实现 Louvain-Lite
Microsoft GraphRAG 发示, 但官方 graphrag-toolkit 依 Azure。智迁自写 Louvain-Lite 社区检测 + local/global 双问答, lazy build global singleton。能跨跨表问答表锁依赖关系。

## 5. Outlines 受约束解码 + 3 次 retry pydantic 反馈
JSON Schema 保结构化, pydantic 错误反馈给 LLM。双后端: DeepSeek native JSON mode + outlines binding。

## 6. Temporal Durable Workflow + ObjectProvider 优雅降级
默认 enabled=false 不加负担, opt-in 后 Temporal worker 接管重试/超时/补偿。Controller 用 ObjectProvider, unavailable 返 503 而不是启动崩。

## 7. MigrationToolFactory 适配层 (不锁定商业)
ZhiQian Native / pgloader / Ora2Pg 三轨同位, 按 (src,tgt) 调 score 推荐。用户交付后可插 AWS DMS / Alibaba DTS / DataX 为 additional adapters。以 sub-product 思路报拍为主体。

## 8. 端侧推理 (transformers.js + Phi-3.5-mini)
优先上 WebGPU, WASM 降级。隐私场景 / 纱舱部署 / 火车火车上体验。随你作近期 Edge AI 热点颜。
