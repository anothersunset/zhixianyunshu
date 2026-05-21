# CHANGELOG

> 说明: 以下为智迁云枢 v2 升级正式启动以来的完整提交记录。每步提交同步更新 `UPGRADE_PLAN.md` 状态表。

---

## 🟢 Phase 3 milestone (7/7) — 2026-05-21 ✅

**云原生 Kustomize + ArgoCD GitOps + KubeRay/vLLM + Debezium CDC + pgloader/MTK + MCP + A2A**。Phase 3 全 7 步完成,共 39 提交 (37 个 v2 + Phase 3 含 14 个新 SHA)。

---

## [v2-step-24] 2026-05-21 — A2A 协议适配 (AgentCard + tasks/send + sendSubscribe SSE)

**提交 SHA**: `984dd127`

### 动机
让 ZhiQian 作为 Google [A2A](https://google.github.io/A2A/) 协议服务端 agent,其他 agent (Claude, AutoGPT, LangGraph supervisor) 通过 `/.well-known/agent.json` 发现后即可委托迁移任务,实现多 Agent 互联。

### 设计要点
- **AgentCard** (`GET /.well-known/agent.json`): 暴露 4 个 skill — sql.transpile / sql.explain / migration.plan / schema.analyze,声明 streaming=true。
- **POST /a2a/tasks/send**: 同步 task,内存 store 跟踪 submitted→working→completed/failed 状态机。
- **POST /a2a/tasks/sendSubscribe**: SSE 流,逐事件推 `task` / `status(working)` / `artifact` / `status(completed)`。
- **A2ATaskExecutor**: switch skill 后调 RAG (`/transpile` / `/structured/*` / `/crag/query`),Map 形结果包成 A2A artifact。
- **GET /a2a/tasks/{id}** / **GET /a2a/tasks**: 状态查询与列表。
- 内存 store 单机 demo,生产换 RedisHash。

### 变更项
新增 7 文件:
- `zhiqian/backend/src/main/java/com/zhiqian/a2a/{AgentCardController,A2ATask,A2ATaskStore,A2ATaskController,A2ATaskExecutor}.java`
- `zhiqian/backend/src/main/java/com/zhiqian/a2a/README.md`
- `zhiqian/backend/src/test/java/com/zhiqian/a2a/A2AControllerTest.java` (4 集成测)

### 验证
```bash
curl http://localhost:8080/.well-known/agent.json | jq
curl -X POST http://localhost:8080/a2a/tasks/send -H 'Content-Type: application/json' \
  -d '{"id":"t1","message":{"skill":"sql.transpile","arguments":{"source_sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10"}}}'
```

### 回滚
`git revert 984dd127` → A2A 目录清除。

---

## [v2-step-23] 2026-05-21 — MCP Server (rag 端暴露 6 工具给 Claude Desktop / Cursor)

**提交 SHA**: `0faa7d9d`

### 动机
Model Context Protocol 是 Anthropic 推的标准,让 LLM 客户端 (Claude Desktop / Cursor / Continue) 可发现并调用外部工具。把 ZhiQian 包成 MCP server,意味着用户在 Claude Desktop 里直接说 "帮我把这段 MySQL 转成 openGauss",Claude 就会调 ZhiQian。

### 设计要点
- **/mcp/manifest**: protocolVersion `2024-11-05`,声明 capabilities.tools。
- **/mcp/tools**: 列出 6 工具 — sql_transpile / sql_explain / schema_analysis / risk_report / retrieve / migrate_query,每个含 JSON Schema 输入约束。
- **/mcp/rpc** + **/mcp/call**: JSON-RPC 2.0,支持 initialize / tools/list / tools/call。
- **server.py** 内 dispatch + _call_tool: 通过 httpx.AsyncClient 内部转发到已有 endpoint (`/transpile` / `/structured/*` / `/retrieve` / `/crag/query`),零业务改动复用全部 RAG 能力。
- **errors**: -32601 unknown method / -32603 internal,返回符合 JSON-RPC 2.0。

### 变更项
新增 6 文件:
- `zhiqian/rag/app/mcp/__init__.py`
- `zhiqian/rag/app/mcp/server.py` (TOOLS 清单 + dispatch + _call_tool)
- `zhiqian/rag/app/api/mcp.py` (FastAPI router)
- `zhiqian/rag/app/main.py` (注册 router,version 升 1.0.0)
- `zhiqian/rag/app/mcp/README.md` (Claude Desktop / Cursor 配置示例)
- `zhiqian/rag/tests/test_mcp.py` (6 测试)

### 验证
```bash
curl http://localhost:8001/mcp/manifest | jq
curl -X POST http://localhost:8001/mcp/rpc -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}' | jq
```

### 回滚
`git revert 0faa7d9d` → MCP router 不再 include,/mcp/* 全部 404。

---

## [v2-step-22] 2026-05-21 — pgloader / MTK 迁移工具适配层

**提交 SHA**: `54695192`

### 动机
ZhiQian 不应是数据库迁移的唯一答案 — pgloader (10+ 年 MySQL→PG 实战) 与 Ora2Pg (Oracle PL/SQL 事实标准) 都是成熟开源。把它们抽象为 `MigrationTool` 接口的兄弟实现,通过 matchScore 给用户智能推荐:**纯结构迁移走 pgloader,Oracle PL/SQL 走 Ora2Pg,复杂跨方言转译走 ZhiQian Native**。

### 设计要点
- **MigrationTool 接口**: id / displayName / supportedSources / supportedTargets / tradeoffs / matchScore。
- **3 实现**: ZhiqianNativeAdapter (mysql/oracle/sqlserver/db2/postgres → opengauss/postgres/mysql,openGauss 得 0.95)、PgloaderAdapter (mysql/sqlite/sqlserver/csv → postgres/opengauss,mysql 得 0.90)、MtkAdapter (oracle/sqlserver/sybase → postgres/opengauss,oracle 得 0.92)。
- **MigrationToolFactory**: 注入全部 bean,recommend(src,tgt) 按 score 降序返回。
- **MigrationToolController**: GET `/api/migration-tools` 列工具,POST `/api/migration-tools/recommend` 智能推荐。
- **docker compose** profile=migration-tools: 起 dimitri/pgloader:ccl.latest + georgmoser/ora2pg:24.3 容器 + 脚本/输出挂载。
- **scripts/pgloader-mysql-to-opengauss.load**: 含 zero-dates-to-null、tinyint(1)→boolean、并发 8 worker。
- **scripts/ora2pg.conf**: Oracle HR schema, PLSQL_PGSQL=1, MODIFY_TYPE 钉 number/date/clob/blob。

### 变更项
新增 10 文件:
- `zhiqian/backend/src/main/java/com/zhiqian/migrationtool/{MigrationTool,ZhiqianNativeAdapter,PgloaderAdapter,MtkAdapter,MigrationToolFactory,MigrationToolController}.java`
- `zhiqian/deploy/migration-tools/{docker-compose.yml,scripts/pgloader-mysql-to-opengauss.load,scripts/ora2pg.conf,README.md}`

### 验证
```bash
curl http://localhost:8080/api/migration-tools | jq
curl -X POST http://localhost:8080/api/migration-tools/recommend \
  -H 'Content-Type: application/json' \
  -d '{"sourceDialect":"oracle","targetDialect":"opengauss"}' | jq
# → [{id:zhiqian-native,score:0.95}, {id:mtk-ora2pg,score:0.92}, {id:pgloader,score:0.0}]
```

### 回滚
`git revert 54695192` → migration-tools 目录清除。

---

## [v2-step-21] 2026-05-21 — Debezium 3.0 CDC (MySQL → Kafka → openGauss)

**提交 SHA**: `d997f284`

### 动机
#3 ZhiQian 流水线是"全量+离线"迁移,CDC 提供"实时增量+不停机"路线。Debezium 3.0 (2025-01 GA) 是业界标准,通过 binlog → Kafka topic → JDBC Sink Connector 写 openGauss,实现毫秒级同步,适合大表灰度切换。

### 设计要点
- **docker-compose** profile=cdc: Zookeeper + Kafka 3.7 + Schema Registry 7.6 + Debezium Connect 3.0 + cdc-mysql-source (33307 端口)。
- **mysql-source.json**: connector.class=io.debezium.connector.mysql.MySqlConnector + snapshot.mode=initial + ExtractNewRecordState SMT 把 envelope unwrap 为 flat row。
- **opengauss-sink.json**: io.confluent.connect.jdbc.JdbcSinkConnector + dialect=PostgreSqlDatabaseDialect + insert.mode=upsert + delete.enabled=true + RegexRouter SMT 剪 topic 前缀。
- **Spring side**: `CdcProperties` (`app.cdc.{enabled,connect-url,timeout-seconds}`, 默认 enabled=false), `CdcConnectClient` (RestClient 包装 Connect REST API), `CdcController` (GET/POST `/api/cdc/connectors/*`),`CdcConfiguration` 用 ObjectProvider 守卫,enabled=false 时 controller 返 503。

### 变更项
新增 8 文件:
- `zhiqian/deploy/cdc/{docker-compose.yml,connectors/mysql-source.json,connectors/opengauss-sink.json,README.md}`
- `zhiqian/backend/src/main/java/com/zhiqian/cdc/{CdcProperties,CdcConnectClient,CdcController,CdcConfiguration}.java`

### 验证
```bash
docker compose -f zhiqian/deploy/cdc/docker-compose.yml --profile cdc up -d
curl -X POST http://localhost:8083/connectors -H 'Content-Type: application/json' \
  -d @zhiqian/deploy/cdc/connectors/mysql-source.json
curl http://localhost:8083/connectors | jq
# 后端代理
export APP_CDC_ENABLED=true
curl http://localhost:8080/api/cdc/connectors
```

### 回滚
`git revert d997f284` → CDC 目录清除。docker compose down --profile cdc。

---

## [v2-step-20] 2026-05-21 — KubeRay + vLLM (可选 GPU 推理)

**提交 SHA**: `57323cb6`

### 动机
DeepSeek SaaS 适合演示,但企业内网/数据合规场景要求自托管 LLM 推理。vLLM 是 Berkeley 出的高吞吐推理引擎 (PagedAttention),KubeRay 是 Ray + K8s 编排。两条路径并存:**单机 vLLM Deployment** (适合开发/演示)、**KubeRay RayService** (适合生产/弹性)。

### 设计要点
- **vllm-deployment.yaml**: PVC 50Gi 挂 /models + vllm/vllm-openai:v0.6.3 + nvidia runtimeClass + GPU resource limits + HF_ENDPOINT 镜像 + startupProbe failureThreshold=60 (模型加载长) + Service ClusterIP 8000。
- **rayservice-vllm.yaml**: KubeRay RayService CRD + serveConfigV2 (LLMModel deployment) + headGroup CPU only + workerGroup GPU autoscale min=1 max=4 + ray-ml:2.34.0-py310-gpu。
- **kuberay-operator-install.md**: helm install pointer (不入 repo,运维侧装)。
- **application-vllm.yml**: Spring profile,api-key=EMPTY + base-url 切 vllm svc + model Qwen/Qwen2.5-7B-Instruct。
- **README.md**: 3 路对比矩阵 + Qwen2.5-7B GPU 性能表 (A10 / A100 / 4090)。

### 变更项
新增 5 文件:
- `zhiqian/deploy/kuberay/{README.md,vllm-deployment.yaml,rayservice-vllm.yaml,kuberay-operator-install.md}`
- `zhiqian/backend/src/main/resources/application-vllm.yml`

### 验证
```bash
kubectl apply -f zhiqian/deploy/kuberay/vllm-deployment.yaml
kubectl -n zhiqian port-forward svc/vllm 8000:8000
curl http://localhost:8000/v1/models | jq
# 后端切 profile
SPRING_PROFILES_ACTIVE=vllm java -jar zhiqian-backend.jar
```

### 回滚
`git revert 57323cb6` → kuberay 目录与 vllm profile 清除。

---

## [v2-step-19] 2026-05-21 — ArgoCD GitOps (AppProject + dev/prod Application + bootstrap)

**提交 SHA**: `46274be6` + `11713498` (docs 同步 + bootstrap.sh 修)

### 动机
在 #18 Kustomize 上套 declarative GitOps,实现 git push → 集群自动同步,容器手工 patch 不能 drift。ArgoCD 是 CNCF Graduated Project,原生消费 Kustomize 无需 chart provider。

### 设计要点
- **AppProject zhiqian**: RBAC 隔离 sources/destinations/cluster resources,orphanedResources warn,内置 read-only role 给 zhiqian:viewers 组。
- **Application zhiqian-dev**: automated sync,prune=true selfHeal=true,retry 5 次 backoff 5s→3m。
- **Application zhiqian-prod**: automated.prune=false (防误删) + selfHeal=true,ignoreDifferences 跳过 replicas (HPA) 与 Secret.data (External Secrets)。
- **bootstrap.sh**: 5-step 引导 ns + install + wait + apply + 输出密码。
- **app-of-apps.yaml**: 可选根 Application。

### 变更项
新增 7 ArgoCD 文件 + bootstrap.sh bash 语法 bug 修复。

---

## [v2-step-18] 2026-05-21 — Kustomize base + overlays (pivot from Helm Chart)

**提交 SHA**: `9833e4dc` + `c5f375d5`

原计划 Helm Chart,因 URL 压缩损坏 Go-template,pivot 到纯 YAML Kustomize。base 12 文件 + overlays/dev (NodePort+低资源) + overlays/prod (Ingress+HA)。

---

## 🟢 Phase 2 milestone (6/6) — 2026-05-21 ✅

LangGraph CRAG + GraphRAG + Temporal + Outlines + Cytoscape + JaCoCo 全部交付。

---

## [v2-step-17] 2026-05-21 — Spring Boot Test ≥0.8
`8cf5f96c` + `2e8cedbb`

## [v2-step-16] 2026-05-21 — Cytoscape.js CKG
`c3374bf7` + `b31d20e6`

## [v2-step-15] 2026-05-21 — Outlines 受约束解码
`8fcb13e3`

## [v2-step-14] 2026-05-21 — Temporal durable workflow
`4692d68f` + `39ac14c6`

## [v2-step-13] 2026-05-21 — GraphRAG 索引 CKG
`e43729a6`

## [v2-step-12] 2026-05-21 — LangGraph-style CRAG
`c881dc77` + `2e76a1a6`

---

## 🟢 Phase 1 milestone (11/11) — 2026-05-21 ✅

DeepSeek + 6 Agent + BGE-M3+RRF + Late Chunking + Langfuse + sqlglot + Monaco + RAGAS。

---

## [v2-step-01..11] 2026-05-21 — 详 git log

`913006c0` `790b10f2` `8d4fff1d` `d6b4ac58` `104381a8` `4670edd5` `ceb27034` `1ca293a2` `7bc3236e`/`4678b735`/`bde6b9a1` `6b3d3dec`/`ce3cbb0f` `4f17463c`
