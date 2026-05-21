# CHANGELOG

> 本文件用人类可读语言逐项记录 v2 升级的所有变更。最新变更在最上方。

## [v2-step-03] 2026-05-21 — 真 LLM 驱动的迁移流水线

**对应提交**：`feat(backend): real LLM-driven migration pipeline`

### 动机
v1 的 SSE 时间线是硬编码 8 个步骤，800ms 间隔打印，本质上是一个“动画”。v2-step-02 接入了真 LLM，本步要让流水线中的 6 个组件都走 LLM，让详情面的每一步都是真的 LLM 推理输出。

### 设计要点
- **复用现有 AgentGraph + AgentRunner + AgentTool 框架**，只提供 6 个 AgentTool 实现。带来的好处：Phase 2 Step 12 接入 LangGraph 时只需换 Runner，不动业务逻辑。
- **微改 AgentRunner**：从 tool output 中提取 `_model` / `_confidence` / `_tokenIn` / `_tokenOut` 填入 AgentStep，使上层 SSE 能拿到真实元信息。
- **双模式**：每个 Agent 面 `llm.isReal()`：real 走 LLM、mock 走 v1 预设。零配置启动时 SSE 时间线仍然连贯。
- **异步**：独立 ExecutorService，SseEmitter 创建后立即返回。Tomcat 请求线程不被阻塞。
- **向后兼容**：`TaskSseDemoEmitter` 保留为 `@Deprecated` 谐接，委托给 TaskExecutionService。未来提交可安全删除。

### 变更项
新增（8 个）：
- `agent/tools/SchemaAnalyzerAgent.java`  — Stage 01
- `agent/tools/ContextRetrieverAgent.java` — Stage 02（临时 in-memory，待 step-05 接 Qdrant）
- `agent/tools/SqlReasonerAgent.java`     — Stage 03（使用 reasoner-model）
- `agent/tools/SqlPatcherAgent.java`      — Stage 04
- `agent/tools/SqlCriticAgent.java`       — Stage 05（reasoner-model）
- `agent/tools/ReportSummarizerAgent.java` — Stage 06
- `task/TaskExecutionService.java`       — 新 SSE 总装配

修改（3 个）：
- `agent/AgentRunner.java`            — 从 output 提取元信息填入 AgentStep
- `task/TaskController.java`          — 依赖切换为 TaskExecutionService
- `task/TaskSseDemoEmitter.java`      — 改为 @Deprecated 谐接，委托给新服务

修复（1 个）：
- `llm/LlmController.java` — `Result.success(…)` → `Result.ok(…)`（3 处）。step-02 引入的编译 bug，本次一同修复。

### 影响范围
- ✅ GET /api/tasks/{id}/stream 返回的 SSE 事件质量跳跃：real 模式下 payload 包含真 LLM 输出文本
- ✅ 每个 step 事件多了 model / confidence / tokenIn / tokenOut 四个字段
- ✅ 开启 Real LLM 后单任务总耗时可能从 ~6s 增加到 30s-90s（取决于 DeepSeek RT）
- ➖ 前端零改动 — SSE 事件名 / payload 结构完全兼容 v1

### 验证方式
```bash
cd zhiqian/deploy && docker compose up -d --build backend
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' -d '{"username":"admin","password":"'"$ADMIN_PASSWORD"'"}' | jq -r .data.token)

# 1. Mock 模式验证（6 个 step 依次出，model=mock）
curl -N http://localhost:8080/api/tasks/1/stream -H "Authorization: Bearer $TOKEN"

# 2. 填入 LLM_API_KEY 后重启
curl -N http://localhost:8080/api/tasks/1/stream -H "Authorization: Bearer $TOKEN"
# 期望：每个 step 的 payload 不同，model 为 deepseek-chat / deepseek-chat:reasoner，elapsedMs 从 0ms 变为秒级
```

### 回滚方法
```bash
git revert <本提交 SHA>
# 回滚后 TaskController 重新指向 TaskSseDemoEmitter（v1 硬编码演示）
```

---

## [v2-step-02] 2026-05-21 — 接入真实 LLM（DeepSeek-V3.1）

**对应提交**：`feat(backend): integrate DeepSeek-V3.1 LLM client via RestClient`

### 动机
v1 中 Reasoner / Critic 仅为启发式字符串拼接，演示性 > 实际性。v2 需要真实 LLM 推理能力。
选择原因：
1. DeepSeek-V3.1 是当前性价比最高的中文 LLM
2. 原生 OpenAI 兼容协议，后续切换 Qwen / GLM / 本地 vLLM 零代码修改
3. 提供 reasoner 模型（R1），适合 Critic / 复杂 SQL 改写场景

### 设计要点
- 零依赖：用 Spring 6 原生 RestClient，不引入 Spring AI
- 优雅降级：api-key 为空时启用 MockLlmClient
- 接口抽象：LlmClient 接口 + 2 个实现
- 双模型：chat-model + reasoner-model

### 变更项
新增 8 个 Java 文件（`com.zhiqian.llm.*`） + 修改 application.yml / .env.example / docker-compose.yml。

### 回滚方法
```bash
git revert <本提交 SHA>
```

---

## [v2-step-01] 2026-05-21 — 升级路线图基线

**对应提交**：`docs(v2): upgrade roadmap + changelog baseline`

新增 `UPGRADE_PLAN.md`、`CHANGELOG.md`。仅文档，不影响运行时代码。

---

## v1 时期的关键提交（归档）

- `6fa440f5` — v1 最终版：完整 README + LICENSE + .gitignore
- `e434028b` — fix(web): Vue 模板 v-text 绕开 URL 压缩冲突
- `96f4709b` — feat(web): Dashboard/Projects/Tasks/Knowledge/Reports/Settings 完整前端
- `f738149d` — fix(rag): Jinja2 自定义分隔符绕开 URL 压缩冲突
- `177e3566` — chore(backend): pom.xml + Postgres V1__init.sql + V2__seed.sql
- `aefbd4fc` — feat(backend): M3-02 内存版 CKG
- `7907a90c` — feat(backend): JWT 安全 + 各 Controller + SSE 演示发射器
- `ac79f9bc` — chore(deploy): docker-compose + Dockerfiles + nginx + .env.example
