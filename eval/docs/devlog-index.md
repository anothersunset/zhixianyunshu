# 开发日志索引

> 按项目分类，记录完整的开发过程：问题发现 → 方案设计 → 迭代验证 → 经验教训
> **中央索引**（跨所有项目）：`~/.claude/projects/C--Users-anoth/memory/devlog-index.md`

---

## zhixianyunshu（智迁云枢）— SQL 方言迁移工具

### 评测框架

| 文件 | 日期 | 主题 | 关键结果 |
|------|------|------|----------|
| [消融实验全流程](devlog-2026-06-10-ablation-experiments.md) | 06-08~14 | 5 组×84 case 消融实验 | 最优配置: Vector+Rerank (SQL 修复率 98.8%) |
| [GraphRAG Copilot 优化](devlog-2026-06-11-graphrag-copilot-optimization.md) | 06-10~11 | Faithfulness/CRAG/跨文档 | jieba 分词修复: faithfulness +62pp |
| [SQL 比较 + 后端稳定性](devlog-2026-06-12-sql-backend-stability.md) | 06-12~22 | 5 级等价比较 + 3 层后端修复 | Enum 归一化 +2.4pp, 零 500 错误 |
| [Reranker OOM + RAG 稳定性](devlog-2026-06-13-reranker-rag-stability.md) | 06-13 | Reranker 内存超限 + 看门狗 | Recall@5: 0.30→0.73 (+143%) |
| [规则扫描器 P0/P1/P2](devlog-2026-06-24-rule-scanner-architecture.md) | 06-22~24 | 统一注册表 + 两阶段 + 注释剥离 | v12: 30/30 oracle-pg |
| [三层复审体系](devlog-2026-06-24-review-system.md) | 06-24 | FETCH FIRST 归一化 + Judge + 金标检测 | PARROT: 35%→80% (adjusted 90%) |

### 关键里程碑

```
v1-v5: 基础 FEATURE_MAP + RECIPES        → 24-27/30
v6:    规则扫描 + 跨模型 critic            → 28/30
v11:   fixupStubbornPatterns 完善         → 30/30 ★
v12:   P0+P1+P2 架构重构                 → 30/30 (零回归)
       三层复审体系                        → 80%/90% PARROT
```

### 核心教训（跨文件提炼）

1. **中文分词是隐蔽杀手**（`str.split()` 对中文无效 → +62pp 单一修复）
2. **静默回退比崩溃更危险**（mock KB 回退让 Recall 骤降不可见）
3. **金标质量决定评测上限**（PARROT 50% case 金标含 Oracle 残留）
4. **单一根因 > 多因修补**（漏浮力一项解释全部 4 个偏差）
5. **评测数字需要拆分解读**（原始率 / 调整率 / 金标质量分布）

---

## GraphRAG Copilot — 独立项目

| 文件 | 日期 | 主题 | 关键结果 |
|------|------|------|----------|
| [v3.2 本地验证](../../../Graphrag-copilot/docs/devlog-2026-05-22-v3.2-validation.md) | 05-22 | 5 修复 + 哨兵测试 | 20/20 PASS |
| [50 题 Benchmark 评测](../../../Graphrag-copilot/docs/devlog-2026-06-11-benchmark-evaluation.md) | 06-10~11 | Faithfulness/CRAG/跨文档/GraphRAG 边 | faithfulness 0.18→0.83 (+65pp) |
| `memory/graphrag-copilot-v3.2-validation.md` | 05-22 | v3.2 本地验证（原始记录） | - |

### 关键修复
- **jieba 中文分词**：`str.split()` 对中文无效 → +62pp faithfulness（最大单一改进）
- **CRAG LLM Judge**：加入 LLM 语义评估，精准触发 rewrite/fallback
- **跨文档推理**：10 个模块文档 + 来源多样性选择 + crossdoc prompt → +17pp
- **GraphRAG 边优化三连击**：修复 unhashable dict + BFS 权重感知 + 边降低 65%
- JSON 解析：括号深度匹配替代贪婪正则
- 同步阻塞 FastAPI：用 asyncio.to_thread() 包装
- BM25 sigmoid 归一化替代 max_score 膨胀

---

## 数学建模 — AI 辅助求解

| 文件 | 日期 | 主题 |
|------|------|------|
| [AI Loop 方法论](devlog-2026-06-math-modeling-ai-loop.md) | 06-?? | CUMCM2016-A 系泊系统踩坑→纠错全流程 |
| `memory/math-modeling-ai-loop.md` | - | 五轮闭环方法论详细版（Round 0-4） |

### 核心贡献
- **五轮闭环**：Round 0(解构) → Round 1(基准验证·闸门) → Round 2(模型增强) → Round 3(单一根因) → Round 4(诚实表述)
- **单一根因诊断法**：一个原因解释全部偏差的方向和量级
- **诚实表述三分法**：定性一致 / 数值吻合 / 仍有偏差，禁"完全吻合"

---

## Notion 自动化 — 开发工具

| 文件 | 日期 | 主题 |
|------|------|------|
| `memory/notion-automation.md` | 06-22~23 | Notion→代码提取→Maven→PDF 一键构建 |

### 核心脚本
- `notion-agent.sh` — 智能监听 Agent
- `notion-build.sh` — 一键构建（抓取→拆分→附件→运行→PDF）
- `notion-detect.sh` — UserPromptSubmit hook 检测

---

## 跨项目通用 — Trace 失败模式

| 文件 | 日期 | 主题 |
|------|------|------|
| `memory/trace-failure-patterns.md` | 06-08 | 66 个 session trace → 7 类失败模式 |
| `memory/process-guardrails.md` | 06-14 | 七条铁律 + 执行模板 |
| `memory/preflight-check.md` | 06-08 | 工作前预检流程（消融实验翻车教训） |

### 7 类失败模式
1. API 认证失败（2,111 次） — 密钥/端点检查
2. Ripgrep 超时（3,397 次） — 先 Glob 再 Grep
3. 非 Git 目录执行 Git（101 次） — 先 rev-parse 检查
4. 命令未找到（887 次） — 先 which 确认
5. 不可达资源循环重试 — 2 次失败即停
6. 未审计流水线（3 次翻车） — 先 trace 信息流
7. SSL 证书错误（39 次） — 不使用有问题端点

---

## 记忆文件一览

```
memory/
├── MEMORY.md                              # 总索引
├── devlog-rule.md                         # 开发日志规则（2026-06-24 新增）
├── ablation-results.md                    # 消融实验详细数据
├── graphrag-eval-issues.md                # GraphRAG 评测问题
├── graphrag-copilot-v3.2-validation.md    # GraphRAG v3.2 验证
├── zhiqian-vault.md                       # 项目结构（Obsidian）
├── trace-failure-patterns.md              # 7 类失败模式
├── preflight-check.md                     # 预检流程
├── process-guardrails.md                  # 七条铁律
├── math-modeling-ai-loop.md               # AI Loop 方法论
├── notion-automation.md                   # Notion 自动化
├── model-switching.md                     # 模型切换
└── auto-task-flow.md                      # 自动任务流
```
