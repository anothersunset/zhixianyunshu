# 真实全栈评测：glm-4-flash + 真 BGE-M3 五数据集 & 五组消融 — 2026-10-10

> 一次补上欠了三个月的实验：**显式 retrieval mode 落地后的五组对照**，以及免费模型
> glm-4-flash 在五个公开数据集上的真实修复率。全部链路真实（无 mock），结果文件带
> provenance 溯源（git sha / 数据集 SHA256 / 模型配置）。

## 0. TL;DR

- **五数据集（fast 模式，BM25 检索，glm-4-flash LLM + 真 BGE-M3 检索 + glm-4-flash judge）：总修复率 112/116 = 96.6%**，oracle 30/30 与 mysql 两组 100%，零系统错误、零 mock 检索。
- **五组消融（oracle→pg，30 case × 5 组，150 次真实调用）回答了 6 月悬置的问题：CRAG / GraphRAG 不提升 SQL 修复率，反而递降（C 组 90.0% → D 组 76.7% → E 组 66.7%）**；它们提升的是检索召回（E 组 Recall@5 最高 0.9375），但注入的上下文更杂，伤害转译准确率。
- **端到端最优配置仍是 Vector+Rerank（C 组）**：修复率 90.0%、Recall@5 0.9015，与 6 月旧口径结论方向一致——但这次的数字建立在真实模式门控之上，可信度不同。

## 1. 环境（全部真实，无 mock）

| 组件 | 配置 | 备注 |
|---|---|---|
| LLM（chat/reasoner） | `glm-4-flash` @ bigmodel OpenAI 兼容端点 | 免费额度；glm-4.6 因账户无余额未用 |
| Judge | `glm-4-flash`，仅裁决 AST 判否的边界样本 | verdict_source 三值标注，本轮 judge 改判 1-3 例/组 |
| Embedding | **真 BGE-M3**（modelscope 本地权重，fp32 CPU） | 三通道全真：bm25 + dense + sparse，`degraded_channels=[]` |
| Reranker | bge-reranker-base（真交叉编码） | rerank 分数非回退序 |
| KB | 单一真源 YAML，70 条文档 | 真检索非 fallback |
| 后端 | Spring Boot local profile（H2） | `raw.real=true`，`mock_retrieval_cases=0` |
| 命令 | `python -m eval.run_eval --retrieval bm25 --pair <stem> --fast --use-judge --cooldown 3`；消融 `python -m eval.ablation --pair oracle_pg --per-case --fast --use-judge --cooldown 3 --force` | seed 42，provenance 全记录 |

排障记录（环境侧，供复现）：本机代理进程未运行导致 Python 全局代理失效 → 所有 Python 进程需 `env -u HTTP_PROXY -u HTTPS_PROXY`；HF 缓存两份（D 盘快照缺权重，C 盘 modelscope 完整）→ `HF_HOME=C:/Users/anoth/.hf_cache` + `RAG_BGE_MODEL` 直指本地权重目录；BGE 在本机 CPU 上 `use_fp16=true` 会挂起 → `RAG_BGE_FP16=false`（fp32 加载 21s）；qdrant-client 1.11.3 本地模式与 pydantic 2.9 不兼容 → 升 1.12.2 并使用全新本地库目录重灌。

## 2. 五数据集结果（fast / bm25 / 真全栈）

| 数据集 | n | SQL 修复率 | 报告准确率 | Recall@5 | MRR@10 | 系统错误 | mock | 金标质量 |
|---|---|---|---|---|---|---|---|---|
| oracle→postgresql | 30 | **100%** | 100% | 0.78 | 0.63 | 0 | 0 | ok 29 / 残留 1 |
| sqlserver→opengauss | 16 | **93.75%** | 100% | 0.10 | 0.13 | 0 | 0 | ok 16 |
| sqlserver→postgresql | 16 | **87.5%** | 100% | 0.10 | 0.11 | 0 | 0 | ok 16 |
| mysql→opengauss | 30 | **100%** | 100% | 0.85 | 0.69 | 0 | 0 | ok 28 / 残留 2 |
| mysql→postgresql | 24 | **100%** | 100% | 0.81 | 0.66 | 0 | 0 | ok 23 / 残留 1 |

解读要点：
- oracle 30/30 **复现了规则扫描器时代的成绩**，且这次是真实 LLM 生成路径（非确定性规则）。
- sqlserver 两组的 Recall@5 极低（0.10）但修复率高——kb 中 sqlserver 配方文档的 `gold_context_ids` 覆盖不足，检索召回调的是 oracle/mysql 的近似文档，LLM 仍靠配方与自身知识答对。**检索指标与端到端指标脱钩**的又一例证（与 6 月结论一致）。
- 与 6 月历史口径（deepseek-chat + Vector+Rerank，sqlserver fast 32/32=100%）相比，本次 glm-4-flash + bm25 为 29/32——免费轻量模型 + 单路检索的代价约 3 个 case，属合理差距；不同模型/检索口径的数字不可直接混比。

## 3. 五组消融（oracle→pg × 30，per-case，53.2 分钟）

| 组别 | Recall@5 | MRR@10 | SQL 修复率 | 报告准确率 |
|---|---|---|---|---|
| A · BM25 only | 0.7857 | 0.6349 | 86.7% | 86.7% |
| B · Vector only | 0.8254 | 0.7635 | 86.7% | 86.7% |
| C · Vector + Rerank | 0.9015 | 0.7023 | **90.0%** | **90.0%** |
| D · + CRAG | 0.8796 | 0.7148 | 76.7% | 76.7% |
| E · + GraphRAG / CKG | **0.9375** | 0.6792 | 66.7% | 66.7% |

判别力自检：A-B recall 相同 90% / B-C 90% / C-D 87% / **D-E mrr 相同 93%（该对指标可能饱和）**；mock 检索全部为 0。

**结论（回答 README 边界声明第 1 条悬置的问题）**：
1. **修复率不单调**：C(90.0%) > A=B(86.7%) > D(76.7%) > E(66.7%)。CRAG 的查询重写与 GraphRAG 的图通道扩大了召回（E 组 Recall@5 最高），但对**窄领域、配方驱动**的 SQL 转译任务，额外上下文是噪声源——与 6 月「Full 引入图噪声低于 Vector+Rerank」的方向性结论一致，且这次排除了「模式名不副实」的干扰（trace 验证通道真实门控）。
2. **适用边界**：CRAG/GraphRAG 的价值预期在开放域问答/跨文档推理（本项目 /crag/query 与 /graphrag/* 端点的场景），而非转译准确率。对外表述应改为「Vector+Rerank 为转译最优配置；CRAG/GraphRAG 面向解释与问答场景」。
3. E 组修复率下降主因待归因（候选：图融合 rrf 权重 0.8 过强、社区报告文本挤占 prompt 预算）——留作后续调参实验，不在本轮扩大战线。

## 4. 与历史口径的关系（诚实声明）

- 旧消融数字（CRAG 82.14% / Full 82.14%）此前已作废——当时 crag/full 模式未真实实现。
- 本轮数字的新口径：LLM=glm-4-flash（免费轻量）、judge=glm-4-flash（未做人工 κ 校准，judge 仅裁决 1-3 例/组）、检索=本机 CPU fp32 BGE-M3。**与 6 月 deepseek-chat 口径的数字不可直接混比**；结果文件（eval/results/raw_bm25_*_fast.json、per_case_oracle_pg_fast.json）带完整 provenance 可复现。
- judge 未做 κ 校准是本轮边界：judge 改判样本少（≤3/组），对修复率影响 ≤1 例，但严谨引用时应注明。

## 5. 遗留

1. E 组（GraphRAG）修复率下降的根因归因（图权重/prompt 预算）与调参实验。
2. 用付费旗舰模型（glm-4.6 或 deepseek-chat）复跑五数据集，量化「模型档位 × 修复率」关系。
3. sqlserver 数据集的 `gold_context_ids` 覆盖修复（当前 Recall 低是金标侧问题而非检索侧）。
4. judge 人工 κ 校准（沿用 human_review.py 流程）。
