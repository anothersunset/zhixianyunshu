# 智迁云枢 v2 升级路线图

> 本文件是 v2 全量升级的**导航图**与**决策记录**。每完成一个提交,`CHANGELOG.md` 会追加一条详细变更说明,本文件的 ✅ 状态也会同步勾选。

## 决策摘要 (2026-05-21)

| 维度 | 决策 | 备注 |
| --- | --- | --- |
| 升级范围 | Phase 1+2+3 + 加分彩蛋(全量) | 冲奖项 + 论文 |
| LLM Provider | DeepSeek-V3.1 (OpenAI 兼容协议) | 后续可一键切 Qwen3 / GLM-4.5 |
| API Key 策略 | `.env` 占位,用户自填 | 不进仓库,符合安全规范 |
| 部署主路径 | docker compose (本地一键) | 评委 / 用户 30 秒可跑 |
| 部署副路径 | Helm Chart + Kustomize(K3s 可单机) | 体现云原生能力 |
| 真实样本 | Sakila + Classic Models + Employees | MySQL 官方公开样本,合规免费 |
| 前端品牌化 | 完整(Logo / 主题 / 暗色 / i18n) | + 答辩演示模式(全屏 KPI 走马灯 + edge-tts 自动播报) |
| 交付节奏 | 多个小提交,每个独立可验证 | 强调可维护性、可追溯性 |
| 仓库分支 | 直接推 `main` | 用户偏好简单 |

## 提交规范(强制)

每个提交必须满足以下三条:

1. **标题格式**:`type(scope): 改了什么 — 为什么 (影响)`
   - type: `feat` / `fix` / `refactor` / `docs` / `chore` / `test` / `perf` / `build`
   - scope: `backend` / `rag` / `web` / `deploy` / `docs` / `bonus`
2. **正文必须包含**: 动机 / 变更项 / 影响 / 验证 / 回滚
3. **CHANGELOG.md 同步更新**

## 总进度表(32 提交)

### Phase 1 — 真 LLM + 真检索(P0)

| # | 提交 | 状态 | 影响 |
| --- | --- | --- | --- |
| 1 | docs(v2): 升级路线图 + 变更记录基线 | ✅ | 项目导航 |
| 2 | feat(backend): DeepSeek-V3.1 LLM 客户端 + 优雅降级 | ✅ | 后端获得真 LLM 能力 |
| 3 | feat(backend): LLMReasonerAgent 替换 TaskSseDemoEmitter | ⏳ | SSE 时间线变真 |
| 4 | feat(rag): BGE-M3 嵌入 + bge-reranker-v2-m3 重排 | ⏳ | 检索质量阶跃 |
| 5 | feat(rag): Qdrant 向量库 + 混合检索(BM25+Dense+Sparse) | ⏳ | 召回率提升 30%+ |
| 6 | feat(rag): Late Chunking + 语义分块 | ⏳ | 长文档不丢语义 |
| 7 | feat(rag): Langfuse trace 全链路埋点 | ⏳ | 可观测性补齐 |
| 8 | feat(backend): Langfuse Java SDK + traceId 贯通 | ⏳ | 跨服务追踪 |
| 9 | feat(rag): sqlglot 替换 Jinja2 — 真 SQL AST 转译 | ⏳ | 类型映射正确性飞跃 |
| 10 | feat(web): Monaco SQL Diff 编辑器 | ⏳ | 可视化改写前后对比 |
| 11 | test(rag): RAGAS 评测框架 + 20 条 golden set | ⏳ | 量化检索质量 |

### Phase 2 — Agent 编排 + GraphRAG(P1)

| # | 提交 | 状态 | 影响 |
| --- | --- | --- | --- |
| 12 | feat(rag): LangGraph 0.2 重构 Self-RAG → CRAG | ⏳ | 检索置信度低时自动纠错 |
| 13 | feat(rag): GraphRAG 索引 CKG 实体图谱 | ⏳ | 复杂跨表迁移决策能力 |
| 14 | feat(backend): Temporal worker + 持久化迁移工作流 | ⏳ | 长事务、断点续跑 |
| 15 | feat(rag): Outlines 受约束解码 | ⏳ | LLM 输出保证 SQL 合法 |
| 16 | feat(web): Cytoscape.js 渲染 CKG 图谱 | ⏳ | 可视化亮点 |
| 17 | test(backend): Spring Boot Test 覆盖率 ≥ 80% | ⏳ | 可维护性 |

### Phase 3 — 云原生 + 真库 + 开放协议(P2)

| # | 提交 | 状态 | 影响 |
| --- | --- | --- | --- |
| 18 | feat(deploy): Helm Chart 完整版 | ⏳ | K8s 一键部署 |
| 19 | feat(deploy): ArgoCD Application + Kustomize overlays | ⏳ | GitOps |
| 20 | feat(deploy): KubeRay + vLLM 可选自托管路径 | ⏳ | GPU 推理可水平扩展 |
| 21 | feat(backend): Debezium 3.0 + Kafka Connect CDC | ⏳ | 增量迁移能力 |
| 22 | feat(backend): pgloader / openGauss MTK 工具适配器 | ⏳ | 接入工业级工具链 |
| 23 | feat(rag): MCP Server 暴露 CKG + 检索能力 | ⏳ | 外部 Agent 可调用 |
| 24 | feat(backend): A2A 协议(Google 2025.4)端点 | ⏳ | 与他人 Agent 互通 |

### 加分彩蛋(P3)

| # | 提交 | 状态 | 影响 |
| --- | --- | --- | --- |
| 25 | feat(web): 暗色模式 + vue-i18n(中/英) | ⏳ | 评委友好 |
| 26 | feat(web): 答辩演示模式 + edge-tts 自动播报 | ⏳ | 现场加分 |
| 27 | feat(reports): Typst PDF 报告生成器 | ⏳ | 替代占位 Reporter |
| 28 | feat(web): transformers.js + Phi-3.5-mini 端侧 SQL 预览 | ⏳ | 浏览器内 AI,黑科技感 |
| 29 | feat(deploy): Sakila/Classic Models/Employees 一键导入 | ⏳ | 真实样本演示 |
| 30 | docs: 论文级架构图 + 性能对比表 + 答辩讲稿 | ⏳ | 论文/答辩材料 |
| 31 | chore: SBOM + Cosign 镜像签名 + Trivy 扫描 | ⏳ | 安全合规 |
| 32 | docs: 最终 README 总修订 + 演示视频脚本 | ⏳ | 交付收尾 |

## 风险登记册

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| DeepSeek API 限流 | 中 | LLM 调用变慢 | 实现指数退避 + 切换 Qwen/GLM 路由 |
| BGE-M3 模型下载慢 | 中 | 首次启动慢 | Dockerfile 预拉取 + ModelScope 镜像源 |
| Temporal 学习曲线 | 中 | 工期延后 | 提供回退到 Spring `@Async` 的实现 |
| 公开 MySQL 样本与 openGauss 兼容性 | 低 | 演示卡 | sqlglot 自动转 + 验证报告 |
| K8s 部署对评委演示意义不大 | 低 | 加分有限 | 用 K3s + 录屏演示 |

## 决策日志

| 日期 | 决策 | 决策人 | 理由 |
| --- | --- | --- | --- |
| 2026-05-21 | 全量升级 + 彩蛋 | lee fanwei | 冲奖项 + 论文 |
| 2026-05-21 | LLM 选 DeepSeek-V3.1 | lee fanwei | 性价比 + 中文 SOTA |
| 2026-05-21 | docker compose 为主路径 | lee fanwei | 本地拉取直接可跑 |
| 2026-05-21 | 使用公开数据集 Sakila/CM/Employees | lee fanwei | 合规 + 免运维 |
| 2026-05-21 | LLM 接入不引 Spring AI，用 RestClient 零依赖 | AI 负责人 | 避免 Boot 3.2→3.4 升级连锁风险 |
| 2026-05-21 | api-key 为空时优雅降级为 Mock | AI 负责人 | docker compose 零配置可启动 |
