# CHANGELOG

## [v2-step-08] 2026-05-21 — Langfuse Java 客户端 + backend 全链埋点

**对应提交**: `feat(backend): Langfuse Java 客户端 — task.migration root trace 贯穿 6 个 Agent 与每次 LLM 调用`

### 动机
#7 为 rag 端加了 trace,但 backend 的迁移流水线才是核心用户路径(6 agents,每个 agent 多次 LLM 调用)。以前用户只能从 SSE 事件看 stage 概要,看不到 prompt/completion/token 详情。本步为 backend 加上 Java Langfuse 轻量客户端,与 rag 端全面对称。

### 设计要点
- **零额外依赖**: Langfuse Java SDK 不存在,官方推荐 OTel-GenAI 但集成重。本步采用轻量的 'Public Ingestion API 直调' 方案:Spring 6 原生 RestClient + Base64 Basic Auth,POST `/api/public/ingestion {batch:[…]}`。
- **完全可选**: keys 留空时 `TraceHandle.NOOP` 路径零开销;`LlmClientFactory` 输出 langfuse=enabled@host 或 disabled 状态。
- **异步上报**: single-thread daemon executor,业务线程零等待。
- **ThreadLocal trace context**: `AgentRunner` 在每个 stage 前 bind/unbind,`DeepSeekLlmClient.attachToCurrentTrace()` 调 `LangfuseClient.current()` 拿到当前 trace,自动把 chat/reason 作为 generation 挑 attach——业务代码不需传 traceId。
- **secret 不入日志**: 仅初始化时 INFO 提示 host,从不打印 keys。
- **trace 树结构**:
  ```
  task.migration (root)
  ├── 01-analyzer:schema_analyzer (span)
  │   └── llm.chat (generation, model=deepseek-chat, prompt+completion tokens)
  ├── 02-retriever:context_retriever (span)
  │   └── llm.chat (generation)
  ├── … (03-reasoner / 04-patcher / 05-critic / 06-reporter)
  └── trace.finish (output: status, stages_executed)
  ```
- **traceId 回吹前端**: SSE step 事件额外携 `traceId` 字段,Web 可点按钮跳转 Langfuse UI 定位本次任务。

### 变更项
新增(4 个类):
- `backend/.../observability/LangfuseProperties.java` — @ConfigurationProperties(prefix="app.langfuse")。4 个字段。
- `backend/.../observability/LangfuseConfig.java` — @EnableConfigurationProperties 挂接点。
- `backend/.../observability/LangfuseClient.java` — @Component。包含 lazy init / async flush / ThreadLocal context / @PreDestroy 优雅关闭。
- `backend/.../observability/TraceHandle.java` — trace 上下文句柄。NOOP 单例零开销。

修改:
- `backend/.../llm/LlmClientFactory.java` — @Bean llmClient 新增 LangfuseClient 参数。
- `backend/.../llm/DeepSeekLlmClient.java` — 构造函数新增 LangfuseClient;callModel(…, genName) 重载;调用前后记 Instant,成功/失败都 attachToCurrentTrace。
- `backend/.../agent/AgentRunner.java` — run() 新增重载接受 parentTrace;每个 stage 前 bind 后 unbind,同时上报 stage 作为 span。
- `backend/.../task/TaskExecutionService.java` — 构造函数新增 LangfuseClient;runPipeline 起 'task.migration' root trace,传给 runner.run;成功/失败路径都调 trace.finish;SSE step 事件额外携 traceId。
- `backend/.../resources/application.yml` — 新增 app.langfuse 配置项。
- `deploy/docker-compose.yml` — backend 服务 env 透传 3 个 LANGFUSE_*。

### 影响范围
- ✅ 不配 keys: 行为完全不变,启动多 1 条 INFO 'langfuse disabled'。
- ✅ 配 keys: Langfuse UI 可看到 `task.migration` trace,括展看 6 stage span + 6+ generation (含原始 prompt/completion + token 用量 + 每调耗时)。
- ✅ Mock 路径不受影响: MockLlmClient 不注入 LangfuseClient,不上报 generation,只上报 span。
- ✅ 向后兼容: AgentRunner.run() 保留原 3 参重载。
- ➖ 启动 +0.1s。
- ➖ 每次 LLM 调用 +<1ms overhead。
- ➖ 镜像不增大(零新依赖)。

### 验证方式
```bash
# 1. 不开 Langfuse:
docker compose up -d --build backend
docker logs zhiqian-backend | grep -E '\[langfuse\]|\[TaskExecution\]'
# 期望:
#   [langfuse] disabled (set app.langfuse.public-key/secret-key to enable)
#   [TaskExecution] 初始化完成。LLM provider=deepseek, real=true, langfuse=disabled

# 2. 开 Langfuse (云 cloud):
# 注册 https://cloud.langfuse.com -> Settings -> API Keys
# 在 deploy/.env 加:
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
docker compose restart backend
docker logs zhiqian-backend | grep -E '\[langfuse\]|\[TaskExecution\]'
# 期望:
#   [langfuse] enabled host=https://cloud.langfuse.com (Public Ingestion API)
#   [TaskExecution] 初始化完成。LLM provider=deepseek, real=true, langfuse=enabled@https://cloud.langfuse.com

# 3. 跑任务看 trace:
export JWT_TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.data.token')
curl -s -N -H "Authorization: Bearer $JWT_TOKEN" http://localhost:8080/api/tasks/1/stream | head -200
# Langfuse UI 中 Traces -> task.migration 点开看到完整树。
```

### 回滚
```bash
git revert <本 SHA>
```
回滚后 LangfuseClient bean 被移除 -> DeepSeekLlmClient / AgentRunner / TaskExecutionService 依赖注入失败。如需仅