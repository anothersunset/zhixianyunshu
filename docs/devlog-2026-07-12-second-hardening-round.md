# 第二轮 P0/P1 加固（2026-07-10 ~ 07-12）

## 方法论声明（先读这个）

本文是 **diff 复盘**，不是当时的开发实录。07-10 至 07-12 的 15 个提交
（`01ad87d` → `bacb026`）只有英文单行标题，没有提交正文，当时的会话记录
已不可考。本文逐个提交跑 `git show --stat` 确认改动面，再对关键提交抽查
核心 diff 反推"问题 → 修复"。写作规则：

- 标注 **diff 证实** 的内容：直接来自提交 diff，可信；
- 标注 **推断** 的内容：从改动面/状态文件反推的动机与问题背景，原修复决策
  过程不可考；
- 标注 **待核实** 的内容：本轮未重新运行验证、仅转述当时验收记录的结论。

主题清单来源：项目状态文件（`ZHIXIANYUNSHU-STATUS-2026-09-16.md` 第 5 节
"P0/P1 修复"）。该文件描述与实际 diff 逐条比对后基本吻合，个别出入在文中注明。

## 背景

07-09 完成第一轮 P0/P1 修复（见
[devlog-2026-07-09-p0-p1-audit.md](./devlog-2026-07-09-p0-p1-audit.md)）后，
随即对项目（及另一独立项目）做了一次更全面的第二轮审查，发现 8 个 P0，
制定 P0 → P1 修复计划并连续执行三天（07-10 ~ 07-12，共 15 个提交）。
第一轮修的多是"组件级"缺陷（依赖注入、CORS、Dockerfile）；这一轮动的是
**主链路级** 问题：六 Agent 链路三套实现并存、任务执行是硬编码的演示假流程、
SSE/eval/A2A 端点默认裸奔、JWT 走 URL 查询参数。

## 逐主题复盘（问题 → 修复 → 验证状态）

### 1. 六 Agent 主链路统一 + 任务真实加载（`01ad87d`，最大的一个提交）

- **问题**（推断，状态文件描述）：页面展示的"六 Agent"、SQL 转译页、评测
  链路是三套分离实现；`TaskExecutionService` 硬编码 `projectId=1`、不读任务
  自带的 SQL、LLM 不可用时回退内置示例 schema——任务跑完是"演给人看的"。
- **修复**（diff 证实，+1112/-270，31 个文件）：
  - 新增 `MigrationPipelineService`：唯一六 Agent 图
    `01-analyzer → 02-retriever → 03-reasoner → 04-patcher → 05-critic → 06-reporter`，
    任务执行与 `/migrate` 共用；
  - `TaskExecutionService` 重写（412 行改动）：按 taskId 加载真实任务与其 SQL，
    删除硬编码项目与演示用 `TaskSseDemoEmitter`；
  - 新增 `TaskAgentStep` 持久化（Flyway 迁移 `V3__task_agent_runtime.sql`），
    SSE 断线后可回放持久化步骤；
  - 同步补 `TaskWorkflowIntegrationTest`（130 行）。
- **验证状态**：集成测试随该提交入库；全量 `mvn clean verify` 通过为当时
  验收记录转述，本文未重跑（待核实）。

### 2. 认证边界：Bearer Header + owner 鉴权 + 有界线程池 + 409/429（`01ad87d`，测试压实在 `647c515`）

- **问题**（diff 证实）：`JwtAuthenticationFilter` 的 `extractToken()` 原样
  接受 `?token=xxx` URL 查询参数（token 进访问日志/浏览器历史）；SSE stream、
  `/a2a/**`、eval 端点默认 `permitAll`；线程池是 `Executors.newCachedThreadPool()`
  （无界）；`SseEmitter(0L)` 无超时。
- **修复**（diff 证实）：
  - `extractToken()` 只认 `Authorization: Bearer` Header，query token 返回
    `null`（**注意：query token 的移除发生在本提交，不是前端提交 `ca47bb5`**）；
  - `SecurityConfig`：eval 端点开关默认值 `true → false`；新增
    `app.security.integration-endpoints-open`（默认 false）控制 `/a2a/**`；
    移除 SSE stream 的 `permitAll`；显式 401/403 entry point；兜底
    `anyRequest().authenticated()`；
  - 新增 `TaskAccessService`：任务/项目按 owner 鉴权，ADMIN 放行全量；
  - `TaskExecutionService`：`cachedThreadPool` → 有界
    `ThreadPoolExecutor`（core 4 / max 8 / `ArrayBlockingQueue(100)` /
    `AbortPolicy`，均可经 `app.task-execution.*` 配置）；重复执行同一任务返回
    `409 CONFLICT`，队列饱和返回 `429 TOO_MANY_REQUESTS`；SSE 设有限超时；
  - `647c515`：集成测试把线程池压到 core 1 / max 1 / queue 1，断言饱和时
    返回 409/429 的契约不被静默吞掉。
- **验证状态**：`647c515` 的契约测试入库；待核实项同上。

### 3. critic 修正后复验 + `REVIEW_REQUIRED` 终态（`01ad87d`）

- **问题**（推断，状态文件描述）：SqlCriticAgent 给出修正 SQL 后直接采纳返回，
  修正版本身从不再过校验器。
- **修复**（diff 证实）：`SqlCriticAgent` 引入 `SqlSyntaxValidator` 对
  修正后 SQL 复验；`needs_correction` 改由确定性校验结果（而非仅 LLM 判断）
  决定；`MigrationPipelineService` 终态三分为 `DONE` / `FAILED` /
  `REVIEW_REQUIRED`（复验仍不过时不谎报 DONE）。
- **验证状态**：`TaskWorkflowIntegrationTest` 覆盖 `REVIEW_REQUIRED` 路径
  （状态文件记录的真实 HTTP 链路验收以 `REVIEW_REQUIRED` 收尾）。

### 4. A2A 任务契约加固（`ea1b423`）

- **修复**（diff 证实，+205/-63）：`A2ATaskController` / `A2ATaskExecutor`
  收紧请求解析与执行路径；`SqlSyntaxValidator` 两处实质修复：
  - `redirectErrorStream(true) → false`——sqlglot 把解析诊断写 stderr，此前
    stderr 混入 stdout 导致合法 SQL 被误报 validator error，现在 stdout 只吃
    JSON、stderr 单独解析；
  - 结果解析抽成可测的 `parseResult(stdout, stderr, exitCode)`。
- **验证状态**：新增 `A2ATaskExecutorTest`（73 行）+ `SqlSyntaxValidatorTest`
  （27 行）。

### 5. MCP FastAPI 契约校验（`e550d3c`）

- **问题**（diff 证实）：MCP server 声明的工具入参和 FastAPI 模型字段对不上
  （请求发 `source_sql`/`k`，FastAPI 模型要 `sql`/`top_k`），调用必然 422；
  `structured` 路由缺 `prefix` 导致整组 404。
- **修复**（diff 证实，+295/-47）：`mcp/server.py` 把两个 APIRouter 的入参
  schema 换成真实 Pydantic 约束（`minLength`、`top_k` 1~50 边界），调用侧做
  `source_sql → sql`、`k → top_k`（含 `k` 回退兼容）映射；
  `structured.py` 补 `prefix="/structured"`；`transpile.py`/`crag.py` 同步对齐。
- **验证状态**：`test_mcp.py` +207 行。

### 6. 显式 retrieval mode（`6af7e70`）

- **问题**（状态文件描述，与 diff 方向吻合）：此前宣称的 `crag`/`full` 模式
  实际都只是同一套 BM25+dense+sparse+rerank，模式名不副实。
- **修复**（diff 证实，+1015/-48）：新增 `pipelines/mode_retriever.py`（679 行），
  显式区分 `bm25 / dense / dense_rerank / hybrid / rerank / crag / full`
  七种模式，按模式门控各检索通道——只有 `full` 启用 graph 检索；`retrieve`
  API、CRAG/GraphRAG 图、rewriter、qdrant_store 同步改造；golden_set.jsonl 更新。
- **验证状态**：新增 `test_retrieval_modes.py`（188 行）。**遗留**（状态文件
  指出）：旧口径的消融实验数字（"CRAG 82.14% / Full 82.14%"）作废，修复后
  需用真实样本重跑对照实验，本文成稿时未见重跑记录（待核实）。

### 7. 复杂/未知 SQL 安全路由（`6f6b478`）

- **修复**（diff 证实）：`FeatureScannerAgent` 输出 `unknown_features` 及计数，
  未知方言特性时置信度归零；`SqlReasonerAgent` 按复杂度评分路由——
  `complexity_score >= 6` 走 reasoner 模型，否则走普通 chat，路由原因写入
  状态（`routing_reason`）。
- **验证状态**：新增 `FeatureScannerAgentTest`、`SqlReasonerAgentRoutingTest`，
  `TaskWorkflowIntegrationTest` 同步扩展。

### 8. eval 溯源（`12eae1c`）

- **修复**（diff 证实）：新增 `eval/provenance.py`——记录数据集 SHA256 指纹、
  git 信息、Python/平台环境，使 eval 结果可复现、可追溯；`run_eval.py` 接入，
  `test_provenance.py` 覆盖。

### 9. RAG 依赖锁定（`77e7741`）

- **修复**（diff 证实）：提交 `uv.lock`（2181 行）冻结 RAG 运行时依赖，
  `pyproject.toml` 规范化，`requirements.txt` 同步，`.gitignore` 补 uv 缓存目录。
- **验证状态**：当时记录 `uv lock --check` 123 包一致（待核实）。

### 10. 核心 70% 覆盖率门禁（`63940f1`）

- **修复**（diff 证实）：`pom.xml` JaCoCo check 绑定 `mvn verify`，按 include
  清单只圈定生产迁移运行时核心包（agent/task/security/auth/project/report/a2a/
  common 及三个指定 migration 类）——注释明确说明 legacy 分析器、CDC/Temporal/
  TTS 适配器不稀释该信号。
- **验证状态**：当时记录 57 个核心类行覆盖率 76.08%（门禁 70%，待核实）。

### 11. 前端：认证 SSE 消费 + 响应式工作台（`ca47bb5`、`97709af`）

- `ca47bb5`（diff 证实）：`EventSource` 无法自定义 Header，`api/task.ts` 改用
  `fetch` + `Authorization: Bearer` + `Accept: text/event-stream` 消费 SSE——
  与主题 2 的后端收紧配套（老 EventSource 路径在后端已 401）；store 与
  `TaskDetail.vue`（+440 行）重写步骤回放展示。
- `97709af`（diff 证实，+524/-95）：`MainLayout`（+240 行）、`Dashboard`、
  `TaskList`、`AgentTimeline`、`style.css` 响应式打磨。
- **待核实**：状态文件明确记录 **TaskDetail 三档截图 QA（1440/900/390）未做**
  ——浏览器实页验收当时因工具缺失没有执行，且**没有伪造完成**。这是本轮
  最明确的遗留项。

### 12. CI 门禁与版本声明对齐（`f55f472`）

- **修复**（diff 证实）：后端 CI `mvn test → mvn verify`（覆盖率门禁进 CI）；
  RAG CI 从 `pip install -r requirements.txt` 切到 `uv sync --frozen`（锁文件
  生效）；README/pom/package.json/docs 中版本号与宣称口径统一到 2.0.0。
- **待核实**：状态文件第 6 节记录 `VERSION` 文件当时仍漏在 `1.0.4`——该问题
  到 2026-09-23 的 `c4d9095` 才修复，不在本轮 15 提交范围内。

### 13. 认证任务产物测试补链（`7307b76`）

- **修复**（diff 证实）：`ProjectController` 补 `POST /api/projects` 创建端点
  （owner 归属当前用户、201 返回、参数校验）——推断是为集成测试补齐
  "认证用户 → 建项目 → 建任务 → 验产物"全链路的缺口；`TaskWorkflowIntegrationTest`
  同步扩展。

### 14. 离线 SQL fallback input-aware（`dda4a3d`）

- **问题**（diff 证实）：`SqlPatcherAgent` LLM 不可用时的 fallback 是**写死的
  示例 SQL**（无论输入什么，输出都是同一段 orders 表演示转换）。
- **修复**（diff 证实）：改为 `deterministicFallback()` 对真实输入做规则转换
  （`IFNULL/NVL → COALESCE`、反引号 → 双引号、`DATETIME → TIMESTAMP`、
  `AUTO_INCREMENT → IDENTITY`、`LIMIT x,y → LIMIT y OFFSET x`），输入不变时
  patches 计 0，诚实标记 `_real: false`。

### 15. 离线验收边界文档（`bacb026`）

- **修复**（diff 证实）：根 README 增补一段声明——CI 默认验收完全离线
  （`mvn clean verify` + 确定性 pytest + 前端构建）；真实 Qdrant/外部 LLM/
  Langfuse 是凭据齐备后的可选 smoke，不把 mock 结果报告为在线质量成绩。

## 验收数字（转述，本文未重新运行）

据状态文件记录的当时子线程自报：Maven `clean verify` 91 tests 0 failures
（1 skipped）；JaCoCo 57 核心类行覆盖 76.08%；RAG pytest 50 passed / 3 skipped；
eval pytest 28 passed；`uv lock --check` 123 包一致；Vue typecheck + build 通过；
真实 HTTP 链路（创建项目 → 任务 → execute → 409 → Bearer SSE 回放 →
`REVIEW_REQUIRED` → Markdown 下载 200）走通。**以上均为转述，本文成稿时未
复跑任何测试套件。**

## 遗留

1. **TaskDetail 三档截图 QA 未做**（1440/900/390 登录后受保护页面）——当时
   工具缺失，未伪造完成；本文成稿时仍未补。
2. **消融实验未用新 retrieval mode 重跑**——旧数字不能证明 CRAG/GraphRAG
   语义增益。
3. **在线 smoke 未跑**——真实 Qdrant / 外部 LLM / Langfuse 边界只验证了
   显式降级与契约，未验证在线质量。
4. 15 个提交长期未推送未合并（本 devlog 成稿时仍在本地分支
   `codex/p0-p1-repair` 上）。
