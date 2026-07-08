# eval/ — 评测驱动开发（Eval-Driven Development）体系

垂直领域 Agent 的核心工程纪律：**每一次提示词、配方、检索策略的改动，都必须过同一套可复现的评测**。
本目录是这套纪律的载体，分四层 + 一个归档区。

```
eval/
├── 核心框架            run_eval.py / ablation.py / judge.py / metrics.py / noise_floor.py / ...
├── 失败学习闭环         failure_analyzer.py → kb_generator.py / recipe_suggester.py → validate_learning.py
├── 运行监控            backend_watchdog.py / rag_watchdog.py / realtime_monitor.py / ...
├── archive/            一次性重跑与修复验证脚本（历史快照，不再维护）
├── datasets/           分方言对的评测集（含 gold SQL 与报告要点）
├── results/            评测产出（per-case JSON、汇总、审计报告）
├── tests/              指标自检（metrics.py / judge.py / noise_floor.py 的单元测试）
└── docs/               评测方法说明
```

## 一、核心框架

| 文件 | 职责 |
| --- | --- |
| `run_eval.py` | 主入口。加载数据集 → 调后端迁移 → 算指标 →（可选）LLM judge。支持 `--mode bm25/vector/vector_rerank/crag/full` 五档消融 |
| `ablation.py` | 消融实验编排：同一数据集跑多档检索模式，对比各档贡献 |
| `judge.py` | LLM-as-a-Judge：对迁移解释质量打分；`cohen_kappa` 用于与人工评分校准一致性 |
| `human_review.py` | 人工复核抽样：从 judge 结果分层抽样，产出人工评分表 |
| `metrics.py` | 硬指标：`sql_equivalent`（AST 级等价）、`recall_at_k`/`mrr_at_k`、`report_point_hit_rate`、`discrimination_stats`（跨模式判别力）、gold 质检 |
| `noise_floor.py` | A/A 零假设基线：同一 mode 跑两次，量化纯噪声能造成多大差异，给 A/B 梯度提供"多大才算真信号"的参照 |
| `migration_client.py` | 后端 `/migration/eval` 客户端，带 cooldown 防过载 |
| `sql_validate.py` | 目标方言语法校验（sqlglot parse） |
| `preflight.py` | 跑评测前的环境自检（后端/RAG/数据集/judge key） |
| `parrot_adapter.py` | 外部数据集适配层 |
| `index_kb.py` | 把 KB 文档灌入 RAG 向量库 |
| `tests/` | 指标自检——见下方"消融梯度为什么会失真"一节的方法论 |

**指标设计原则**：客观层（SQL AST 等价、检索命中）先行，主观层（LLM judge）必须用
`human_review.py` + Cohen's κ 与人工校准后才可信。judge 从来不是唯一裁判。跑
`python -m pytest eval/tests/` 验证指标本身的判别力没有被回归破坏。

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

## 五、指标为什么会说谎 —— 五个隐藏陷阱与对应工具

垂直 Agent 评测最容易踩的坑：**实验跑完了、有数字、但梯度不单调甚至递减**。根因几乎从不是"模型不行"，而是**指标算出来了，但没人验证过指标本身在测量什么**。这不是一次性修复能解决的问题，是每次改动指标/加新消融维度都要重新过一遍的检查清单。

1. **能力静默降级**。`Embedder` 在 BGE-M3 不可用时降级为 SHA-256 hash 伪向量（纯噪声），`Reranker` 不可用时静默 noop。服务照常返回结果、实验照常跑完，但 `vector`/`vector_rerank`/`full` 各档全部退化成同一个噪声通道——梯度自然消失甚至反向。
   → **工具**：`preflight.py` 第 7 项**能力探针**读 `/retrieve` 的 `capabilities`，`dense`/`rerank`/`graphrag` 任一降级即 fail（除非 `--allow-degraded` 仅冒烟用）。

2. **检索降级污染实验组**。RAG 服务失联时后端 `ContextRetrieverAgent` 会降级到本地 mock 检索。个别 case 走 mock、其余走真实 RAG，混在一张表里对比，梯度就是噪声。
   → **工具**：后端在响应 meta 里透出 `retrieval_real`；`MigrationClient` 见到 `retrieval_real=False` 直接中止（除非 `ZHIQIAN_ALLOW_MOCK_RETRIEVAL=1`）；`summarize` 单列统计 `mock_retrieval_cases`，消融表出现即告警。

3. **指标饱和**。文档池小时，各检索模式的 top-k **集合**往往相同，集合型 `Recall@5` 全部饱和到同一个值——而 rerank/CRAG 改变的恰恰是**排序**，不是集合。用饱和指标当然测不出它们的贡献。
   → **工具**：排序敏感的 **MRR@10**（`metrics.mrr_at_k`），消融表与 summary 并列输出。同一命中集合下，命中排在第 1 位 MRR=1.0、第 5 位 MRR=0.2，梯度立刻显形。
   → **工具**：光加新指标不够，还要能*看见*旧指标在哪些 case 上失去了区分度。`metrics.discrimination_stats(rows_a, rows_b, key)` 计算两组之间该指标完全相同的 case 占比；`ablation.py` 的 `_print_interim` 每轮都打印相邻模式对的判别力，占比 >85% 直接标红——均值上的一点差异，如果背后 85%+ 的 case 该指标根本没变，那这点差异更可能是少数 case 在拉动，不是真实梯度。

4. **人工校准抽样本身会说谎**。`human_review.py` 靠人工标注和 Cohen's κ 校准 LLM judge，但如果抽样是**纯随机**的，judge 大概率在"简单、明显对/错"的 case 上和人类一致，真正容易分歧的边界样本会被稀释进大多数一致样本里——κ 照样能算得很好看，却根本没验证到 judge 真正可能出错的地方。
   → **工具**：`run_eval.py` 的 `_eval_one` 现在给每行结果标 `verdict_source`：`"judge"` 表示 sqlglot AST 比对判否、但 LLM judge 判语义等价而把结论翻转为通过——这正是 judge 意见真正改变结论、最该被人工验证的边界样本。`judge.sample_for_human_review` 改为分层抽样：`verdict_source == "judge"` 的样本优先全部纳入，剩余配额才随机抽做基线覆盖。

5. **没有零假设/安慰剂基线，分不清信号和噪声**。"CRAG 比 BM25 高 8 个百分点"——这 8% 是真信号还是 LLM 采样噪声？没有对照组回答不了。
   → **工具**：`noise_floor.py` 的 A/A 测试——把同一个 mode 在同一批 case 上独立跑两次（不同时间、独立 LLM 调用），`compare_runs()` 算出两次之间的 `flip_rate`（个案层面翻转率）和 `rate_delta`/`mean_delta`（汇总层面噪声地板）。你的 A/B 差异必须显著超过这个噪声地板，才配被称为"梯度"：
   ```bash
   python -m eval.run_eval --retrieval full --pair mysql_opengauss --out eval/results/aa_run1
   python -m eval.run_eval --retrieval full --pair mysql_opengauss --out eval/results/aa_run2
   python -m eval.noise_floor --a eval/results/aa_run1/raw_full_mysql_opengauss.json \
                               --b eval/results/aa_run2/raw_full_mysql_opengauss.json
   ```

此外 `summarize` 单列 `system_errors`、`sql_repair_rate_excl_system_errors`、`judge_decided_cases`：超时等系统错误不该被计入"修复失败"稀释真实修复率，judge 裁决样本数则是分层抽样配额是否够用的直接依据。

**方法论要点**：评测的可信度不在跑了多少 case，而在**每一档的实验条件是否真的只差你要消融的那一个变量、指标本身是否真的能分辨这个变量、以及你有没有一个"什么都没变"的参照系去校准"多大的差异才算真"**。能力探针、降级守卫、排序敏感指标、判别力检查、分层校准抽样、零假设基线——六件事缺一，梯度都可能是假的。`eval/tests/` 把这几条判别力断言固化成了单元测试，防止未来改动 `metrics.py` 时无声地退化回同样的坑。

## 常用命令

```bash
python -m eval.preflight                                  # 环境自检
python -m eval.run_eval --pair oracle->postgresql --fast  # 单方言对快跑
python -m eval.ablation --per-case --fast --pair all      # 全量消融（另见根目录 run_ablation.bat）
python -m eval.human_review --sample 20                   # judge 校准抽样
```
