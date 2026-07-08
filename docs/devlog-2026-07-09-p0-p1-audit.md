# P0/P1 遗留问题核实与修复 (2026-07-09)

## 背景

上一轮外部审查给出 10 项遗留问题清单（5 P0 + 5 P1）。逐条不轻信描述，对照真实代码
核实后再动手修复——3 处发现实际情况与描述不完全一致（见下表"核实结论"列）。

## 核实结论 + 修复结果

| # | 级别 | 问题 | 核实结论 | 修复 | Commit |
|---|------|------|----------|------|--------|
| 1 | P0 | CRAG 端点依赖注入缺失 (`crag._runner_dep`) | **属实** | `main.py` 补 `dependency_overrides[crag._runner_dep]` | `61e9f9d` |
| 2 | P0 | 结构化端点依赖注入缺失 (`structured._client_dep`) | **属实** | `main.py` 补 `dependency_overrides[structured._client_dep]` | `61e9f9d` |
| 3 | P0 | 路由冲突（crag 与 query 都注册 `POST /query`） | **属实** | `crag.py` 的 `APIRouter()` 加 `prefix="/crag"` | `61e9f9d` |
| 4 | P0 | `deploy/.env` 含真实 API 密钥明文 | **描述有出入**——密钥在**本地磁盘**属实存在，但 `git ls-files` 确认仅 `.env.example` 被跟踪，`.env` 从未进入任何提交，全历史搜不到该密钥前缀。**不是仓库/GitHub 泄漏**，是本地文件卫生问题 | 无法由 Claude 代为吊销；**需你在 DeepSeek 后台手动吊销并轮换** | 未修复（不可代办） |
| 5 | P0 | i18n + 暗色主题未接入 MainLayout | **属实** | `ThemeSwitcher.vue`/`LocaleSwitcher.vue` 组件早已存在且功能完整，从未被挂载；接入 `MainLayout.vue` 顶栏 | `3c27efd` |
| 6 | P1 | `SqlCriticAgent` LLM 失败时默认 `CORRECT` | **属实，且范围更大**——`MigrationEvalController` 的 critic 异常分支有同款谎报，一并修 | 改为 `STATUS: UNKNOWN` + `critic_status` 标记，不触发自纠正 | `20c82c5` |
| 7 | P1 | CORS `*` + credentials | **属实，但 API 描述有出入**——实际是 `setAllowedOriginPatterns("*")`（不是 `setAllowedOrigins`），配合 `allowCredentials(true)` 不会运行时抛异常，但仍反射任意 Origin 并放行凭证 | 改为 `app.cors.allowed-origins` 环境变量驱动的显式白名单，默认 localhost 开发端口 | `dda9c81` |
| 8 | P1 | `/migrate` `/chat` `/judge` `/a2a/**` 全 permitAll | **属实** | 收进 `app.security.eval-endpoints-open` 开关，默认 `true`（不破坏 eval 框架的无 token 调用），生产部署设 `false` 收紧 | `dda9c81` |
| 9 | P1 | Dockerfile 无 USER/HEALTHCHECK | **属实，且数量有出入**——是 **3 个**（rag/backend/web）不是 2 个 | rag/backend 加非 root 用户 + `HEALTHCHECK`；web(nginx) 只加 `HEALTHCHECK`，不加 `USER`（nginx master 需 root 绑 80，worker 已自动降权，盲目 `USER` 会导致启动失败） | `be6c24b` |
| 10 | P1 | `HybridRetriever.add()` 无锁 | **属实** | 加 `threading.RLock`，`add()` 全程持锁改写；`search()` 的 BM25 计算块持锁取 `(bm25, doc_ids)` 一致快照，避免 `zip()` 长度错位；Qdrant 写入(IO) 留在锁外 | `c1a0009` |

## 未修复项说明（#4）

`deploy/.env` 的密钥是真实凭证，本地磁盘明文存在。虽然核实后确认**从未进入 git 历史**（`.gitignore` 生效正常），谈不上代码泄漏，但：

- 密钥前缀在本次审查对话中被贴出过，出于最小化风险原则仍建议吊销轮换；
- 这是账号操作（登录服务商控制台吊销 key），Claude 无权限代为执行。

## 顺带产出

本轮核实/修复过程本身沉淀成了通用方法论 skill：
[`.claude/skills/diagnosing-silent-failures/SKILL.md`](../.claude/skills/diagnosing-silent-failures/SKILL.md) ——
诊断"能跑通但结果不对"类静默失败的心法与四步法（commit
`ce83761`）。#1/#2（依赖未注入直接 `NotImplementedError`）和 #6
（LLM 失败谎报 CORRECT）都是这类模式的典型案例。

## 验证方式

- 后端：`mvn test`（排除集成测试）79/79 通过
- RAG：改动文件 `ast.parse` 语法检查 + 导入符号解析（`crag._runner_dep`、
  `structured._client_dep`、`HybridRetriever._lock` 均可访问）通过
- 前端：`vue-tsc --noEmit` 通过
- Dockerfile：仅静态核对（本地无 docker 环境实测 build），建议合并后手动 build 一次确认
