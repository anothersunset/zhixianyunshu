# eval/ — 评测驱动开发（Eval-Driven Development）体系

垂直领域 Agent 的核心工程纪律：**每一次提示词、配方、检索策略的改动，都必须过同一套可复现的评测**。
本目录是这套纪律的载体，分四层 + 一个归档区。

```
eval/
├── 核心框架            run_eval.py / ablation.py / judge.py / metrics.py / ...
├── 失败学习闭环         failure_analyzer.py → kb_generator.py / recipe_suggester.py → validate_learning.py
├── 运行监控            backend_watchdog.py / rag_watchdog.py / realtime_monitor.py / ...
├── archive/            一次性重跑与修复验证脚本（历史快照，不再维护）
├── datasets/           分方言对的评测集（含 gold SQL 与报告要点）
├── results/            评测产出（per-case JSON、汇总、审计报告）
└── docs/               评测方法说明
```

## 一、核心框架

| 文件 | 职责 |
| --- | --- |
| `run_eval.py` | 主入口。加载数据集 → 调后端迁移 → 算指标 →（可选）LLM judge。支持 `--mode bm25/vector/vector_rerank/crag/full` 五档消融 |
| `ablation.py` | 消融实验编排：同一数据集跑多档检索模式，对比各档贡献 |
| `judge.py` | LLM-as-a-Judge：对迁移解释质量打分；`cohen_kappa` 用于与人工评分校准一致性 |
| `human_review.py` | 人工复核抽样：从 judge 结果分层抽样，产出人工评分表 |
| `metrics.py` | 硬指标：`sql_equivalent`（AST 级等价）、`recall_at_k`、`report_point_hit_rate`、gold 质检 |
| `migration_client.py` | 后端 `/migration/eval` 客户端，带 cooldown 防过载 |
| `sql_validate.py` | 目标方言语法校验（sqlglot parse） |
| `preflight.py` | 跑评测前的环境自检（后端/RAG/数据集/judge key） |
| `parrot_adapter.py` | 外部数据集适配层 |
| `index_kb.py` | 把 KB 文档灌入 RAG 向量库 |

**指标设计原则**：客观层（SQL AST 等价、检索命中）先行，主观层（LLM judge）必须用
`human_review.py` + Cohen's κ 与人工校准后才可信。judge 从来不是唯一裁判。

## 二、失败学习闭环（5 阶段）

从评测失败中自动生成领域知识，回注到 KB，再验证改进 — 详见
[docs/devlog-2026-06-24-failure-learning-loop.md](../docs/devlog-2026-06-24-failure-learning-loop.md)。

```
① run_eval.py 发现失败 case
② failure_analyzer.py   聚类失败模式（按特征/方言对/错误类型）
③ kb_generator.py       LLM 生成 KB 文档草稿  ┐
   recipe_suggester.py  LLM 生成转换配方草稿  ┘ → 写入 kb/pending/
④ validate_learning.py --approve   人工审批门禁 → kb/active/ + deploy_log.json
⑤ 重跑失败 case 验证改进（历史脚本见 archive/）
```

知识只进不淘汰会腐化：所有生成的知识先进 `kb/pending/`，经 `--approve` 审批后才部署，
且 `kb/backups/` + `deploy_log.json` 保证可回滚、可审计。

## 三、运行监控

长时评测（100+ case × 5 模式 × LLM 调用）经常跑数小时，监控与自愈是刚需：

- `backend_watchdog.py` / `rag_watchdog.py` — 探活 + 自动重启挂掉的服务
- `realtime_monitor.py` / `case_monitor.py` / `monitor.sh` — 实时进度与中间指标

## 四、archive/ — 历史一次性脚本

修某一批失败 case、验证某次配方部署时写的重跑脚本（`rerun_*`、`retest_*`、
`half_ablation` 等）。保留它们是因为 results/ 里的历史数据由它们产出，删了就无法复现；
但它们**不再维护**，运行必须在仓库根目录（依赖 `sys.path` 或 `PYTHONPATH` 指向根目录）：

```bash
python -m eval.archive.rerun_full        # 推荐 -m 方式
```

## 五、消融梯度为什么会失真 —— 三个隐藏陷阱

垂直 Agent 评测最容易踩的坑：**实验跑完了、有数字、但梯度不单调甚至递减**。根因几乎从不是"模型不行"，而是实验条件被污染。本项目踩过并已加固三处：

1. **能力静默降级**。`Embedder` 在 BGE-M3 不可用时降级为 SHA-256 hash 伪向量（纯噪声），`Reranker` 不可用时静默 noop。服务照常返回结果、实验照常跑完，但 `vector`/`vector_rerank`/`full` 各档全部退化成同一个噪声通道——梯度自然消失甚至反向。
   → 修复：`preflight.py` 第 7 项**能力探针**读 `/retrieve` 的 `capabilities`，`dense`/`rerank`/`graphrag` 任一降级即 fail（除非 `--allow-degraded` 仅冒烟用）。

2. **检索降级污染实验组**。RAG 服务失联时后端 `ContextRetrieverAgent` 会降级到本地 mock 检索。个别 case 走 mock、其余走真实 RAG，混在一张表里对比，梯度就是噪声。
   → 修复：后端在响应 meta 里透出 `retrieval_real`；`MigrationClient` 见到 `retrieval_real=False` 直接中止（除非 `ZHIQIAN_ALLOW_MOCK_RETRIEVAL=1`）；`summarize` 单列统计 `mock_retrieval_cases`，消融表出现即告警。

3. **指标饱和**。文档池小时，各检索模式的 top-k **集合**往往相同，集合型 `Recall@5` 全部饱和到同一个值——而 rerank/CRAG 改变的恰恰是**排序**，不是集合。用饱和指标当然测不出它们的贡献。
   → 修复：新增排序敏感的 **MRR@10**（`metrics.mrr_at_k`），消融表与 summary 并列输出。同一命中集合下，命中排在第 1 位 MRR=1.0、第 5 位 MRR=0.2，梯度立刻显形。

此外 `summarize` 现在单列 `system_errors` 与 `sql_repair_rate_excl_system_errors`：超时等系统错误不该被计入"修复失败"稀释真实修复率——把系统噪声和模型能力分开看，是让梯度可信的最后一步。

**方法论要点**：评测的可信度不在跑了多少 case，而在**每一档的实验条件是否真的只差你要消融的那一个变量**。能力探针 + 降级守卫 + 排序敏感指标，三者缺一，梯度都可能是假的。

## 常用命令

```bash
python -m eval.preflight                                  # 环境自检
python -m eval.run_eval --pair oracle->postgresql --fast  # 单方言对快跑
python -m eval.ablation --per-case --fast --pair all      # 全量消融（另见根目录 run_ablation.bat）
python -m eval.human_review --sample 20                   # judge 校准抽样
```
