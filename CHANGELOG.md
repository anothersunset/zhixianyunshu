# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🟡 Phase 2 进度 (5/6) — 2026-05-21

**Outlines 受约束解码 + Cytoscape.js CKG 可视化双落地**。剩 #17 Spring Boot Test ≥0.8 即 Phase 2 全部交付。

---

## [v2-step-16] 2026-05-21 — Cytoscape.js CKG 图谱可视化

**提交 SHA**: `c3374bf7` (batch 1 web 新文件 3) + `b31d20e6` (batch 2 wiring + backend controller)

### 动机
v1 有 CKG (Code Knowledge Graph) 分析结果, 却只能看 JSON, 拓扑关系 (表被哪些方法用 / 调用链路) 不可见。Cytoscape.js 是业界 SOTA 图可视化库 (11k⭐, Google/Mozilla 在用), fcose layout 对 100+ 节点也保持可读, 是答辩演示的关键加分项。

### 设计要点
- **CkgGraph.vue 独立组件**: props nodes/edges 走反序列化, 默认 fcose layout (力导向 + 避免重叠); 5 节点色调 (File=蓝 / Class=绿 / Method=橙 / Table=紫 / Column=灰); 3 边样式 (contains 实线 / calls 虚线 / reads 点线)。
- **不用 mustache 占位符**: 所有 Vue 模板走 v-text/v-bind, 避免上游工具压缩 URL 替换 (复发于 #1 #10)。
- **交互**: 节点点击 emit, 右侧面板展示属性 + 邻居; 顶部按 type 过滤 + label 搜索; fit-to-view 按钮。
- **后端**: GET /api/ckg/graph?projectId=X 当前返 demo 图 (13 节点 + 10 边: 1 file + 2 class + 4 method + 3 table + 3 column), 接入 CkgAnalyzerService 后切真实数据。
- **lazy import**: CKG 路由 lazy load, cytoscape + cytoscape-fcose 仅在该页面加载 (免主包 +200KB)。
- **仅增不改**: 不动现有路由与菜单项, 只追加。

### 变更项
新增 4 文件:
- `web/src/components/CkgGraph.vue` (cytoscape 包装 ~150 行)
- `web/src/api/ckg.ts` (axios 客户端)
- `web/src/views/CkgExplorer.vue` (主页: 项目选 + 过滤 + CkgGraph + 详情面板)
- `backend/src/main/java/com/zhiqian/ckg/CkgGraphController.java` (GET /api/ckg/graph, demo 图)

修改 3 文件:
- `web/package.json` (+cytoscape 3.30.2, +cytoscape-fcose 2.2.0, +@types/cytoscape; version 0.3.0 → 0.4.0)
- `web/src/router/index.ts` (+/ckg 路由)
- `web/src/layouts/MainLayout.vue` (+CKG 菜单项, Connection 图标)

### 验证
```bash
cd zhiqian/web && npm install && npm run dev
# 打开 http://localhost:5173/#/ckg
# 选 demo 项目 → 看到 13 节点 + 10 边 的力导向布局
# 点节点 → 右侧面板展属性 + 邻居 tag 列表
# 顶部过滤选 Table 只看表节点; 输入 order 高亮匹配

curl -s http://localhost:8080/api/ckg/graph?projectId=1 \
  -H 'Authorization: Bearer <JWT>' | jq '{nodes: (.data.nodes | length), edges: (.data.edges | length)}'
# => {nodes: 13, edges: 10}
```

### 回滚
`git revert b31d20e6 c3374bf7` → /ckg 页与 /api/ckg/* 接口消失, 其他不受影响。

---

## [v2-step-15] 2026-05-21 — Outlines 受约束解码 (强保证 JSON Schema)

**提交 SHA**: `8fcb13e3`

### 动机
LLM 生成结构化 JSON (转译解释 / schema 分析 / 迁移风险) 在生产里经常出 'JSON 末尾多一逗号' '字段名笔误' 这类问题, 重试 retry 也不收敛。Outlines (dottxt-ai) 是约束解码 SOTA, 直接在 logits 层强制走 schema, 但需要 transformers + 本地模型。DeepSeek API 自带 `response_format: json_object` 模式, 双轨可降级。

### 设计要点
- **双后端架构**: 默认 DeepSeek JSON mode (httpx POST + response_format), 可选 Outlines (`RAG_OUTLINES_ENABLED=true`, 需 transformers + outlines)。Outlines 不在场时静默降级。
- **pydantic v2 schema**: TranspileExplanation / SchemaAnalysisResult / MigrationRiskReport 三模型, Field 描述 + 校验。
- **retry + 错误反馈**: 解析失败时把 pydantic 错误回传给 LLM 重新生成, 最多 3 次。Langfuse trace 每次尝试。
- **3 REST 端点**:
  - POST /structured/transpile-explain (SQL 转译变动详解)
  - POST /structured/schema-analysis (DDL 表/字段结构 + 风险)
  - POST /structured/risk-report (迁移风险分级与建议)
- **轻量依赖**: 必装仅 jsonschema (~150KB), Outlines 留注释行可选启用。
- **6 测试**: schema 校验 / 无 key fallback / bad JSON retry / 3 端点 mock httpx 烟测。

### 变更项
新增 4 文件:
- `rag/app/core/schemas.py` (pydantic 模型)
- `rag/app/core/structured_output.py` (StructuredOutputClient 双后端)
- `rag/app/api/structured.py` (3 endpoint)
- `rag/tests/test_structured.py` (6 测试)

修改: `rag/app/main.py` (0.8.0 → 0.9.0, 注册 structured_router, +structured_output_enabled/structured_backend/outlines_available 三 health cap), `rag/requirements.txt` (+jsonschema==4.23.0, # outlines==0.0.46 可选注释行)。

### 验证
```bash
cd zhiqian/rag && pytest tests/test_structured.py -v
# 6 passed

curl -s http://localhost:8001/health | jq '.capabilities | {structured_output_enabled, structured_backend, outlines_available}'
# => {structured_output_enabled: true, structured_backend: "deepseek_json_mode", outlines_available: false}

curl -s -X POST http://localhost:8001/structured/transpile-explain \
  -H 'Content-Type: application/json' \
  -d '{"source_sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10","source_dialect":"mysql","target_dialect":"opengauss"}' | jq
# => { target_sql, changes: [...], risk_level, confidence }
```

### 回滚
`git revert 8fcb13e3` → /structured/* 端点消失; 主 /query /crag/* /graphrag/* 不受影响。

---

## 🟡 Phase 2 进度 (3/6) — 2026-05-21

**LangGraph CRAG + GraphRAG + Temporal worker 三大支柱已落地**。剩 Outlines 受约束解码、Cytoscape.js CKG 可视化、Spring Boot Test ≥0.8。

---

## [v2-step-14] 2026-05-21 — Temporal durable workflow worker

**提交 SHA**: `4692d68f` (batch 1 骨架 7 类) + `39ac14c6` (batch 2 pom+yml+compose+controller)

### 动机
6 Agent 流水线动辄 30 分钟, 进程崩溃或重启就要重跑, 是工程化最大短板。Temporal 是业界 durable workflow 事实标准 (Uber/Snap/Coinbase 重资产编排都走), 能把每个 Agent 节点的输入输出持久化, crash 后从断点续跑, 还提供可视化 UI、重试、超时、并发治理。

### 设计要点
- **完全可选**: `app.temporal.enabled=false` (默认) 时 `@ConditionalOnProperty` 不装载任何 Temporal bean, AgentRunner 路径毫无变化。SDK jar 仅占镜像 ~25MB。
- **复用现有 6 Agent**: `MigrationActivitiesImpl` (Spring `@Component`) 通过 `@Qualifier` 注入 6 个 AgentTool bean + AgentRunner, 不重写业务逻辑, 仅做 Temporal ↔ Spring 透传, 避免双护理。
- **6 stage workflow**: `MigrationWorkflowImpl` 顺序调 schema → retrieve → reason → patch → critic → report, 每节点 ActivityOptions startToClose 10min + heartbeat 2min + RetryOptions 指数退避 (maxAttempts=3, initial 2s, max 30s, ×2)。
- **QueryMethod 双轨**: SSE 适合活跃连接, `@QueryMethod currentStage()` 适合页面重打开后拉状态, 互补。
- **轻量 record 入参**: MigrationRequest/Result 全 record + Map, 不依赖重型领域类, 避免 Temporal payload 序列化反序列化问题。
- **TemporalWorkerStarter SmartLifecycle**: `start()` 注册 workflow impl class + activity bean, `workerFactory.start()`; `stop()` 优雅关闭。`getPhase()=100` 让 LLM/Langfuse 先就绪。
- **REST 入口**: `POST /api/temporal/start` 提交 workflow 返 wid/runId, `GET /api/temporal/status/{wid}` 走 QueryMethod。`ObjectProvider<WorkflowClient>` 让 controller 在 disabled 时返 503 而非 404。
- **docker compose profile=temporal**: 复用主 postgres (DBNAME=temporal + temporal_visibility, 通过 init-temporal-db.sql 预建), `temporalio/auto-setup:1.25.0` + UI `temporalio/ui:2.31.2` (8233 端口)。启动: `docker compose --profile temporal up -d`。

### 变更项
新增 10 个 Java 类 + 1 个 SQL + 1 个 controller:
- `com.zhiqian.temporal.TemporalProperties` (8 个 @ConfigurationProperties)
- `com.zhiqian.temporal.TemporalConfig` (@ConditionalOnProperty 3 bean: WorkflowServiceStubs + WorkflowClient + WorkerFactory)
- `com.zhiqian.temporal.workflow.MigrationRequest` / `MigrationResult` (record)
- `com.zhiqian.temporal.workflow.MigrationWorkflow` (@WorkflowInterface + QueryMethod)
- `com.zhiqian.temporal.workflow.MigrationWorkflowImpl`
- `com.zhiqian.temporal.workflow.MigrationActivities` (@ActivityInterface, 6 method)
- `com.zhiqian.temporal.workflow.MigrationActivitiesImpl` (@Component, 委托 AgentRunner)
- `com.zhiqian.temporal.TemporalWorkerStarter` (SmartLifecycle)
- `com.zhiqian.temporal.TemporalMigrationController` (POST /start, GET /status/{wid})
- `deploy/init-temporal-db.sql` (create database temporal + temporal_visibility)

修改: `backend/pom.xml` (+temporal-sdk 1.27.0 + temporal-testing test scope), `application.yml` (+app.temporal.* 八参数), `deploy/docker-compose.yml` (+temporal + temporal-ui, profile=temporal, 复用 postgres)。

### 验证
```bash
# 默认不启 — 完全不影响
docker compose up -d  # postgres + backend + rag + web

# 开启 Temporal
export TEMPORAL_ENABLED=true
docker compose --profile temporal up -d
open http://localhost:8233   # Temporal UI
curl http://localhost:8080/actuator/health  # 含 temporal up

# 跑 workflow
curl -X POST http://localhost:8080/api/temporal/start \
  -H 'Authorization: Bearer <JWT>' -H 'Content-Type: application/json' \
  -d '{"taskId":1,"projectId":1,"sourceDialect":"mysql","targetDialect":"opengauss"}'
# => {wid: 'migration-1-1747...', runId: '...', taskQueue: 'zhiqian-migration'}

curl http://localhost:8080/api/temporal/status/migration-1-1747...
# => {stage: 'REASON'}

# UI 上能看到 6 stage activity 顺序跑完, 重试可见, payload 可见
```

### 回滚
`git revert 39ac14c6 4692d68f` → controller / pom / yml / compose / SQL 全恢复; Java 类删除, 不影响 AgentRunner 路径。

---

## [v2-step-13] 2026-05-21 — GraphRAG 索引 CKG (Louvain-Lite 社区 + 局部/全局双查询)

**提交 SHA**: `e43729a6`

### 动机
纯向量检索对「这个表被哪些方法读? 调用链路上有什么影响?」这种需要图结构推理的问题答不好。GraphRAG (微软 2024) 把代码知识图谱按社区划分, 局部查询走实体 + 邻居, 全局查询走社区摘要, 是 SOTA 解法。

### 设计要点
- **CommunityDetector (Louvain-Lite)**: BFS 找连通分量, 大于 max_community_size=50 时按节点 type 二次拆分。简单可解释, 零外部依赖 (networkx 也不引)。
- **GraphRagIndex API**:
  - `.build(nodes, edges)` 返 `{n_nodes, n_edges, n_communities}`
  - `.stats()` 索引诊断
  - `.query_local(question, max_entities=3, hop=1)` 关键词命中实体 → 1 跳邻居 → 拼上下文
  - `.query_global(question, max_reports=3)` 跨社区找最相关报告 → 拼摘要上下文
- **CommunityReport dataclass**: id/title/summary/keywords/node_ids/type_breakdown — 五字段足以驱动 LLM 生成最终答案。
- **3 REST 端点**: `POST /graphrag/index` 入图, `POST /graphrag/query/local` + `POST /graphrag/query/global` 双轨, `GET /graphrag/stats`。未 index 时 409。
- **15 节点 + 18 边测试 fixture**: 模拟 order/payment/utils 三模块, 含 File/Class/Method/Table/Column 五种 type, contains/has_method/uses_table/has_column/reads/calls 六种边, 8 个测试覆盖 index_stats / local_hit / local_with_neighbors / local_no_hit / global / global_empty / community_reports_have_keywords / stats_method。

### 变更项
新增: `rag/app/graphs/community.py`, `rag/app/graphs/graphrag.py`, `rag/app/api/graphrag.py`, `rag/tests/test_graphrag.py`。
修改: `rag/app/main.py` (0.7.0 → 0.8.0, 注册 graphrag_router, +graphrag_enabled / graphrag_indexed_nodes / graphrag_communities 三个 health cap, 全局 `graphrag_index = GraphRagIndex()`)。

### 验证
```bash
cd zhiqian/rag && pytest tests/test_graphrag.py -v
# 8 passed in 0.3s

curl -s http://localhost:8001/health | jq '.capabilities | {graphrag_enabled, graphrag_indexed_nodes, graphrag_communities}'
# => {graphrag_enabled: true, graphrag_indexed_nodes: 0, graphrag_communities: 0}

# 入图 + 查询 see tests/test_graphrag.py fixture
```

### 回滚
`git revert <SHA>` → /graphrag/* 端点消失; HybridRetriever 不受影响。

---

## [v2-step-12] 2026-05-21 — LangGraph-style Self-RAG → CRAG

**提交 SHA**: `c881dc77` (batch 1 graphs 4 文件) + `2e76a1a6` (batch 2 web_search + crag runner + api + main + req)

### 动机
常规 RAG 检索质量差时直接生成幻觉。CRAG (Corrective RAG) 加一个 evaluator 给检索打分, 不够好时走 web_search 补救, 再 refine 问题重检索, 是 CRAG 论文的主架构。

### 设计要点
- **不引 langgraph 重依赖**: 自己写 mini StateGraph runner (graphs/crag.py), 200 行可读, 无 networkx/pydantic v1 兼容问题。
- **CragState 节点序列**: retrieve → evaluate → branch:
  - `correct`: refine → generate
  - `ambiguous`: web_search + refine → generate
  - `incorrect`: web_search → refine → generate
- **3 路评估**: evaluator 走 LLM (DeepSeek) 时如果 RAG_CRAG_USE_LLM_EVAL=1, 否则启发式 (top doc score 阈值)。
- **web_searcher.py**: 默认 duckduckgo-search (无需 key), 可选 SearXNG (RAG_SEARXNG_URL)。
- **refiner**: 把 question + 已检索证据丢给 LLM 重写 query, 提高第二轮召回。
- **generate**: DEEPSEEK_API_KEY 在场时走 LLM, 否则降级到 template fallback (拼证据 + 模板)。
- **CragRunner API**: `.run(question, top_k=5, use_web=True) -> CragState`。整 run 包 Langfuse trace, 每节点一个 span。
- **POST /crag/query**: 入参 question + top_k + use_web, 返 state.answer + state.path (走了哪些节点) + state.evaluations。

### 变更项
新增 batch 1: `rag/app/graphs/{__init__,state,evaluator,refiner}.py`。
新增 batch 2: `rag/app/graphs/web_search.py`, `rag/app/graphs/crag.py`, `rag/app/api/crag.py`。
修改: `rag/app/main.py` (0.6.0 → 0.7.0, +crag_router, +crag_enabled / langgraph_style_crag health cap), `rag/requirements.txt` (+duckduckgo-search==6.2.10)。

### 验证
```bash
curl -s -X POST http://localhost:8001/crag/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"openGauss 怎么模拟 mysql 的 ON UPDATE CURRENT_TIMESTAMP?","top_k":5,"use_web":true}'
# => { answer: "...", path: ["retrieve","evaluate","web_search","refine","generate"], evaluations: [...] }
```

### 回滚
`git revert 2e76a1a6 c881dc77` → /crag/* 端点 + graphs/ 目录消失; 主 /query 不受影响。

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21

**RAG 主链路可交付**。包括: DeepSeek LLM 接入 + 6 Agent 迁移流水线 + BGE-M3+重排 + Qdrant+RRF + Late/Semantic Chunking + Langfuse 双端 trace + sqlglot AST 转译 + Monaco SQL Diff Web + RAGAS+golden set 衡量。

下一阶段 (Phase 2): LangGraph CRAG, GraphRAG, Temporal worker, Outlines 约束解码, Cytoscape CKG 可视化, Spring Boot Test 覆盖率 ≥0.8。

---

## [v2-step-11] 2026-05-21 — RAGAS + 20 条 golden set 三层可衡量

**提交 SHA**: `4f17463c`

### 动机
以前「每步动 RAG 都不知道质量是提升还是退化」。进入后续优化循环前, 必须先钒上可重复的衡量手段。

### 设计要点
- **三层测试**: test_retrieval (recall@5 ≥ 0.80, p50 < 1s, 无 LLM) / test_transpile (8 条 sqlglot 输出断言, 无网络) / test_ragas (faithfulness+answer_relevancy, DeepSeek 判官)。
- **依赖隔离**: requirements-test.txt 独立, 不污染产品镜像。包含 ragas / langchain-openai / datasets。
- **20 条 golden set JSONL**: 8 transpile + 6 retrieve + 6 qa, 覆盖函数映射 / JDBC / 分页 / 类型 / JSON / 事务。
- **Skipif**: 本地无 DEEPSEEK_API_KEY 不报错, CI 可点。
- **Fallback**: test_keyword_faithfulness_fallback 不需 LLM, 50% 阈值下限。

### 变更项
新增: `rag/tests/{__init__,conftest,test_retrieval,test_transpile,test_ragas}.py`, `rag/tests/data/golden_set.jsonl`, `rag/requirements-test.txt`, `rag/Makefile`。

### 验证
```bash
cd zhiqian/rag && pip install -r requirements-test.txt
make test-fast      # 本地 ~5s, 跑三层中前两层
make test-ragas     # ~30s, 需 DEEPSEEK_API_KEY
make coverage       # htmlcov/
```

### 回滚
`git revert <SHA>` → tests/ 目录清空, 产品代码不受影响。

---

## [v2-step-10] 2026-05-21 — Monaco SQL Diff Web 页面

**提交 SHA**: `6b3d3dec` (创建) + `ce3cbb0f` (修复与接入)

### 动机
#9 上线 /transpile API 后, 需一个能在浏览器里看 SQL Diff 转译效果的页面。VSCode 同款 Monaco Editor 是广认场 SOTA。

### 设计要点
- monaco-editor 0.50.0 依赖, 动态 import 仅在 /sql-transpile 路由 lazy load。
- 关闭 worker 要求 (getWorkerUrl 返 data: URL), 避免 vite worker plugin 配置。
- /sql-transpile 页: 源/目标方言下拉 + 示例按钮 + diff 面板 + 变动说明表格。
- api/transpile.ts 直接打 rag service (default http://localhost:8001), CORS 走通。
- **Bug fix**: batch1 推送时 Vue 模板里的 ` var ` 被上游工具替换成了压缩 URL 占位, batch2 改成 v-text 修复。

### 变更项
新增: `web/src/components/SqlDiffEditor.vue`, `web/src/views/SqlTranspile.vue`, `web/src/api/transpile.ts`。
修改: `web/package.json` (+monaco-editor + version 0.3.0), `web/src/router/index.ts` (+/sql-transpile), `web/src/layouts/MainLayout.vue` (+SQL 转译 菜单)。

### 验证
```bash
cd zhiqian/web && npm install && npm run dev
# 打开 http://localhost:5173/#/sql-transpile
# 示例 -> 转译 -> diff 双栏出 COALESCE / TO_CHAR / LIMIT N OFFSET M
```

### 回滚
`git revert <两个 SHA>` → 菜单项与路由移除; rag /transpile 仍可 CLI 调用。

---

## [v2-step-09] 2026-05-21 — sqlglot AST 转译替代 Jinja2 字符串拼接

**提交 SHA**: `7bc3236e` (新增文件) + `4678b735` (接入主应用) + `bde6b9a1` (文档)

### 动机
v1 用 Jinja2 字符串拼接 'MySQL 函数 → openGauss 函数', 遇到 `DATE_FORMAT(t, '%Y-%m')` 含参数函数、嵌套 SELECT、别名 都会坏。

### 设计要点
- sqlglot 是 Tobiko Data 纯 Python AST 库, 6k⭐, 零依赖, ~2MB。
- openGauss = postgres 别名: normalize_dialect() alias 到 postgres (95% 同语法)。
- explain_transpile() 返原/后 SQL + 中文变动说明。
- 两个独立端点: POST /transpile + /transpile/batch, 都含 Langfuse trace。
- validation.py SQL_REWRITE/DIALECT 路径自动 transpile, 注入模板上下文。

### 变更项
新增: `rag/app/core/sql_transpiler.py`, `rag/app/api/transpile.py`。
修改: `rag/app/main.py` (0.6.0, 注册 router, /health 报 sqlglot_version), `rag/app/pipelines/validation.py`, `rag/requirements.txt` (+sqlglot==25.16.1)。

### 验证
```bash
curl -s http://localhost:8001/health | jq '.capabilities.sqlglot_version'  # 25.16.1
curl -s -X POST http://localhost:8001/transpile -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10","target":"opengauss"}' | jq '.target'
# => "SELECT COALESCE(a, b) FROM t LIMIT 10 OFFSET 5"
```

---

## [v2-step-08] 2026-05-21 — Langfuse Java 客户端 + backend 全链埋点

**提交 SHA**: `1ca293a2`

### 动机
#7 为 rag 端加了 trace, backend 迁移流水线(6 agents × 多次 LLM)才是核心路径。与 rag 端全面对称。

### 设计要点
- **零额外依赖**: Spring 6 原生 RestClient 直调 Public Ingestion API, 不引 SDK。
- **ThreadLocal trace context**: AgentRunner bind/unbind, DeepSeekLlmClient 自动 attach。
- **完全可选**: keys 留空 → TraceHandle.NOOP 零开销。
- **异步上报**: single-thread daemon executor, @PreDestroy 优雅关闭。

### 变更项
新增 4 个类: `LangfuseProperties` / `LangfuseConfig` / `LangfuseClient` / `TraceHandle`。
修改: `LlmClientFactory`, `DeepSeekLlmClient`, `AgentRunner`, `TaskExecutionService`, `application.yml`, `docker-compose.yml`。

### 验证
```bash
docker logs zhiqian-backend | grep '\[langfuse\]'
# disabled: [langfuse] disabled (set app.langfuse.public-key/secret-key to enable)
# enabled:  [langfuse] enabled host=https://cloud.langfuse.com (Public Ingestion API)
```

---

## [v2-step-07] 2026-05-21 — Langfuse rag 端全链 trace

**提交 SHA**: `ceb27034`

### 动机
6 路检索混合 + critique 黑箱化, 调试难。

### 设计要点
- Langfuse Python SDK 2.50.0。lazy init, keys 空 → disabled。
- /query trace 含 6 子 span: rewrite / bm25.search / bge.encode_query / qdrant.dense / qdrant.sparse / rrf.merge / rerank.cross_encoder / critique。
- /ingest + /retrieve_api 同样包 trace。
- /health.capabilities 报 langfuse_enabled + langfuse_host。

### 变更项
新增: `rag/app/core/observability.py`。修改: retriever.py, main.py, ingest.py, retrieve.py, requirements.txt, docker-compose.yml, .env.example。

---

## [v2-step-06] 2026-05-21 — Late Chunking + 语义分块

**提交 SHA**: `4670edd5`

### 动机
固定长 chunk 破坏上下文, 影响检索质量。

### 设计要点
- LateChunker (先 embed 全文再切) + SemanticChunker (相邻句余弦 < threshold)。
- pick_chunker(strategy) 工厂 → retriever / ingest 复用。
- env: `RAG_CHUNK_STRATEGY=semantic`, `RAG_CHUNK_SIM_THRESHOLD=0.62`。

---

## [v2-step-05] 2026-05-21 — Qdrant + 3 路 RRF 混合检索

**提交 SHA**: `104381a8`

### 动机
单路 BM25 召回低, 单路向量语义走偏。RRF 是业界公认 SOTA 融合。

### 设计要点
- Qdrant 1.11.3 (docker profile=ml), dense + sparse collection。
- RRF k=60。
- HybridRetriever 3 路: BM25 + Qdrant dense + Qdrant sparse → RRF → reranker。

---

## [v2-step-04] 2026-05-21 — BGE-M3 + bge-reranker-v2-m3 (中文 SOTA)

**提交 SHA**: `d6b4ac58`

### 动机
全凭 Jaccard + jieba 在中文代码机检索质量不够。

### 设计要点
- BGE-M3 多语言 + dense+sparse+colbert 三路。
- bge-reranker-v2-m3 跨编码器后出。
- requirements-ml.txt + docker build --build-arg BUILD_ML=1。
- HF_ENDPOINT=https://hf-mirror.com 默认走镜像。

---

## [v2-step-03] 2026-05-21 — LLM 驱动 6 Agent 迁移流水线

**提交 SHA**: `8d4fff1d`

### 动机
v1 主流程全是 mock 限制代码。

### 设计要点
- 6 Agent: SchemaAnalyzer / ContextRetriever / SqlReasoner / SqlPatcher / SqlCritic / ReportSummarizer。
- AgentGraph 串联, AgentRunner 逐节点, 输出 _model/_confidence/_real 元数据。
- TaskExecutionService SSE: step (JSON) + progress。
- Bug fix: LlmController Result.success → Result.ok。

---

## [v2-step-02] 2026-05-21 — DeepSeek LLM 客户端

**提交 SHA**: `790b10f2`

### 动机
DeepSeek-V3.1 / R1 (低成本中文优势 SOTA)。

### 设计要点
- LlmClient 接口 + DeepSeekLlmClient + MockLlmClient 降级。
- LlmClientFactory 按 api-key 是否空选 real/mock。
- /api/llm/{health,chat,reason} 三个端点。

---

## [v2-step-01] 2026-05-21 — v2 升级路线图基线

**提交 SHA**: `913006c0`

创建 UPGRADE_PLAN.md / CHANGELOG.md / docs/v2-overview.md, Phase 1/2/3 + 加分 共 32 提交路线。
