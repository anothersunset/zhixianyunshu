# CHANGELOG

> 本文件用人类可读语言逐项记录 v2 升级的所有变更。最新变更在最上方。
>
> 配套 `UPGRADE_PLAN.md` 是路线图("将做什么"),本文件是执行日志("已做了什么")。

## [v2-step-02] 2026-05-21 — 接入真实 LLM（DeepSeek-V3.1）

**对应提交**：`feat(backend): integrate DeepSeek-V3.1 LLM client via RestClient`

### 动机
v1 中 Reasoner / Critic 仅为启发式字符串拼接，演示性 > 实际性。v2 需要真实 LLM 推理能力。
选择原因：
1. DeepSeek-V3.1 是当前性价比最高的中文 LLM（缓存命中 $0.07/M tokens）
2. 原生 OpenAI 兼容协议，事实上的行业标准，后续切换 Qwen / GLM / 本地 vLLM 零代码修改
3. 提供 reasoner 模型（R1），适合 Critic / 复杂 SQL 改写场景

### 设计要点
- **零依赖**：用 Spring 6 原生 RestClient，不引入 Spring AI（避免 Boot 3.2→3.4 升级风险）
- **优雅降级**：api-key 为空时启用 MockLlmClient，docker compose 零配置也能启动
- **接口抽象**：LlmClient 接口 + DeepSeek / Mock 两个实现，后续增加 Qwen / GLM 只需新增 impl
- **双模型**：chat-model（V3）用于一般生成；reasoner-model（R1）用于复杂推理

### 变更项
新增代码（8 个文件，隶属包 `com.zhiqian.llm`）：
- `LlmProperties.java` — @ConfigurationProperties 绑定 `app.llm.*`
- `LlmClient.java` — 接口：chat / reason / isReal / providerName
- `DeepSeekLlmClient.java` — RestClient 实现，POST /chat/completions
- `MockLlmClient.java` — 占位实现，明示告知未配置
- `LlmClientFactory.java` — @Bean 工厂，根据 api-key 是否为空选择 impl
- `LlmController.java` — GET /api/llm/health 、POST /api/llm/chat 、POST /api/llm/reason
- `dto/ChatMessage.java`、`dto/ChatRequestPayload.java`、`dto/ChatCompletionResponse.java`

修改现有：
- `application.yml` — 新增 `app.llm.*` 配置块（8 项）
- `deploy/.env.example` — 新增 LLM_* 环境变量说明，含 Qwen/GLM 切换示例
- `deploy/docker-compose.yml` — backend 服务透传 8 个 LLM_* 变量

### 影响范围
- ✅ 新增 3 个 HTTP 端点（需 JWT）
- ✅ Spring 容器多 1 个 Bean：LlmClient
- ✅ docker compose 多 8 个环境变量（都有默认值，不强制填）
- ➖ 不影响任何现有模块（JWT / Project / Task / SSE / CKG / RAG / Web 零改动）
- ⚠️ Step 3 会让 TaskSseDemoEmitter 调用 LlmClient，那是下一个提交的事

### 验证方式
代码拉取后：
```bash
cd zhiqian/deploy
cp .env.example .env
# 编辑 .env：填入 POSTGRES_PASSWORD / JWT_SECRET / ADMIN_PASSWORD（LLM_API_KEY 可以先不填）
docker compose up -d --build backend postgres

# 1. 拿 JWT
TOKEN=$(curl -s -X POST http://localhost:8080/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"'"$ADMIN_PASSWORD"'"}' | jq -r .data.token)

# 2. 检查 LLM 状态（未填 key 应返回 provider=mock, real=false）
curl http://localhost:8080/api/llm/health -H "Authorization: Bearer $TOKEN"

# 3. Mock 聊天验证
curl -X POST http://localhost:8080/api/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"hello"}'

# 4. 填入 DEEPSEEK API Key 后重启 backend
sed -i 's|LLM_API_KEY=|LLM_API_KEY=sk-xxxxxx|' .env
docker compose restart backend

# 5. 真 LLM 验证（应返回 provider=deepseek, real=true）
curl http://localhost:8080/api/llm/health -H "Authorization: Bearer $TOKEN"
curl -X POST http://localhost:8080/api/llm/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"用一句话解释 MySQL 到 openGauss 迁移的最大挑战"}'
```

### 回滚方法
```bash
git revert <本提交 SHA>
cd zhiqian/deploy && docker compose up -d --build backend
```
回滚后 LlmController 端点消失，其他模块零影响（零耦合设计的好处）。

---

## [v2-step-01] 2026-05-21 — 升级路线图基线

**对应提交**：`docs(v2): upgrade roadmap + changelog baseline`

### 动机
用户将整个 v2 升级交由 AI 负责人统筹,需要一份对外可见、可追溯的总路线图与变更日志。

### 变更项
- 新增 `UPGRADE_PLAN.md`、`CHANGELOG.md`

### 影响范围
- 仅文档，不影响运行时代码

### 回滚方法
```bash
git revert <本提交 SHA>
```

---

## v1 时期的关键提交（归档）

- `6fa440f5` — v1 最终版：完整 README + LICENSE + .gitignore
- `e434028b` — fix(web): Vue 模板 ` ` 改用 v-text 绕开 URL 压缩冲突
- `96f4709b` — feat(web): Dashboard/Projects/Tasks/Knowledge/Reports/Settings 完整前端
- `f738149d` — fix(rag): Jinja2 自定义分隔符 `<<...>>` 绕开 URL 压缩冲突
- `177e3566` — chore(backend): pom.xml + Postgres V1__init.sql + V2__seed.sql
- `aefbd4fc` — feat(backend): M3-02 内存版 CKG
- `7907a90c` — feat(backend): JWT 安全 + 各 Controller + SSE 演示发射器
- `ac79f9bc` — chore(deploy): docker-compose + Dockerfiles + nginx + .env.example
