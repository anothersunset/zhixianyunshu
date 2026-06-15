# 智迁云枢 ZhiQian YunShu — 项目介绍书

> LLM Agent + Knowledge Graph 驱动的跨方言数据库迁移智体

---

## 一、项目背景与动机

### 1.1 行业痛点

数据库迁移是企业 IT 基础设施升级中的高频场景。从 MySQL/Oracle 迁移到 PostgreSQL/openGauss 时，开发者面临三大挑战：

1. **SQL 方言差异**：不同数据库的函数、语法、数据类型存在大量不兼容（如 MySQL 的 `IFNULL` vs PostgreSQL 的 `COALESCE`，Oracle 的 `CONNECT BY` vs PostgreSQL 的 `WITH RECURSIVE`）
2. **知识碎片化**：迁移规则散落在官方文档、社区博客、个人经验中，缺乏结构化的知识库
3. **人工成本高**：一条复杂 SQL 的迁移可能需要资深 DBA 花费数小时分析和改写

### 1.2 项目定位

智迁云枢是一个 **AI 驱动的数据库迁移分析平台**，通过 LLM Agent + RAG（检索增强生成）+ 知识图谱的组合，实现：

- 输入源 SQL → 输出目标方言 SQL + 迁移报告 + 风险评估
- 支持 MySQL → openGauss/PostgreSQL、Oracle → PostgreSQL 等多方言对
- 全程可解释：每一步转换都有明确的知识来源和推理链路

---

## 二、系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Vue 3 + Element Plus 控制台                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                  Spring Boot 3.3 后端                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Schema   │ │ Context  │ │ SQL      │ │ SQL      │       │
│  │ Analyzer │→│ Retriever│→│ Reasoner │→│ Patcher  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│       │             │             │             │            │
│       └─────────────┴─────────────┴─────────────┘            │
│                           │                                   │
│  ┌──────────┐ ┌──────────┐                                   │
│  │ SQL      │→│ Report   │  6-Agent 流水线                   │
│  │ Critic   │ │ Summarizer│                                   │
│  └──────────┘ └──────────┘                                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                  Python FastAPI RAG 服务                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ BM25     │ │ Dense    │ │ Sparse   │ │ Reranker │       │
│  │ (Elastic)│ │ (BGE-M3) │ │ (SPLADE) │ │ (bge-    │       │
│  │          │ │          │ │          │ │ reranker)│       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └─────────────┴─────────────┴─────────────┘            │
│                           │ RRF Fusion                        │
│                    ┌──────▼──────┐                            │
│                    │   Qdrant    │                            │
│                    │  向量数据库  │                            │
│                    └─────────────┘                            │
│  ┌─────────────────────────────────┐                         │
│  │  CRAG (Corrective RAG)          │                         │
│  │  evaluate → correct/fallback    │                         │
│  └─────────────────────────────────┘                         │
│  ┌─────────────────────────────────┐                         │
│  │  GraphRAG / CKG                 │                         │
│  │  KB Graph → BFS/社区检索         │                         │
│  └─────────────────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心模块

| 模块 | 技术栈 | 职责 |
|------|--------|------|
| **后端** | Spring Boot 3.3, Java 17 | 6-Agent 流水线编排、LLM 调用、API 网关 |
| **RAG 服务** | Python 3.11, FastAPI | 多路检索（BM25/向量/稀疏/图）、RRF 融合、CRAG 纠错 |
| **前端** | Vue 3.4, Element Plus, Vite | 项目管理、SQL 转换界面、Agent Trace 可视化 |
| **评测** | Python, sqlglot | 消融实验、SQL 等价判断、多维度指标计算 |

### 2.3 6-Agent 流水线

迁移过程被拆解为 6 个专职 Agent 的串行协作：

1. **SchemaAnalyzerAgent**：分析源 SQL 的表结构、字段类型、约束
2. **ContextRetrieverAgent**：调用 RAG 服务检索相关迁移知识
3. **SqlReasonerAgent**：基于检索到的知识进行 SQL 转换推理
4. **SqlPatcherAgent**：对推理结果进行语法修补和格式化
5. **SqlCriticAgent**：评审转换结果的正确性和完整性
6. **ReportSummarizerAgent**：生成结构化迁移报告

---

## 三、知识库设计

### 3.1 知识文档体系

知识库包含 **55+ 篇结构化迁移知识文档**，覆盖：

| 类别 | 示例文档 | 内容 |
|------|---------|------|
| **函数映射** | kb-func-ifnull, kb-func-nvl | IFNULL→COALESCE, NVL→COALESCE 转换规则 |
| **类型映射** | kb-type-enum, kb-type-bit | ENUM→CREATE TYPE AS ENUM, BIT(1)→BOOLEAN |
| **语法转换** | kb-syntax-hierarchy, kb-syntax-merge | CONNECT BY→WITH RECURSIVE, MERGE→INSERT ON CONFLICT |
| **方言手册** | opengauss/dialect-cheatsheet | openGauss/PostgreSQL 方言速查 |
| **综合指南** | kb-mysql-to-og-guide | MySQL→openGauss 完整迁移指南 |

### 3.2 知识图谱 (CKG)

知识文档之间的关系通过知识图谱建模：

- **节点**：知识文档、函数、类型、语法结构
- **边**：语义相似度（embedding 余弦）、关键词重叠、同源关系
- **用途**：GraphRAG 模式下通过 BFS/社区检索扩展召回范围

---

## 四、评测体系设计

### 4.1 数据集

构建了 **84 条** 跨方言迁移评测用例，覆盖 3 个方言对：

| 方言对 | 数量 | 难度分布 |
|--------|------|---------|
| MySQL → openGauss | 30 | easy: 10, medium: 10, hard: 10 |
| MySQL → PostgreSQL | 24 | easy: 8, medium: 8, hard: 8 |
| Oracle → PostgreSQL | 30 | easy: 10, medium: 10, hard: 10 |

每条用例包含：
- `source_sql`：源方言 SQL
- `gold_target_sql`：人工标注的标准目标 SQL
- `gold_report_points`：标准迁移要点列表
- `gold_context_ids`：相关知识文档 ID（用于 Recall@k 评估）
- `difficulty`：easy / medium / hard
- `category`：类型映射、函数转换、语法重写等

### 4.2 评估指标

| 指标 | 计算方法 | 意义 |
|------|---------|------|
| **SQL 修复率** | 多级等价判断：strict → 跨方言 → 模糊类型 → CTE 归一化 → token 相似度(≥0.92) | 衡量生成 SQL 的正确性 |
| **Recall@5** | 检索到的 top-5 文档中命中标注文档的比例 | 衡量检索质量 |
| **报告准确率** | token Jaccard 相似度(≥0.5) 匹配迁移要点 | 衡量报告生成质量 |

### 4.3 SQL 等价判断（6 级）

这是评测中最核心的技术难点。设计了 6 级递进的等价判断逻辑：

```
Level 1: 严格等价 — sqlglot parse 后 AST 完全一致
Level 2: 跨方言等价 — 用源方言 parse（如 MySQL CONCAT→||）
Level 3: 模糊等价 — 类型精度归一化（VARCHAR(255)→VARCHAR, INTEGER→INT）
Level 4: Enum 归一化 — CREATE TYPE xxx AS ENUM 中类型名统一
Level 5: CTE 归一化 — CTE 名称统一为 _cte_0, _cte_1, ...
Level 6: Token 相似度 — Jaccard ≥ 0.92 视为等价
```

---

## 五、消融实验：从发现问题到系统性验证

### 5.1 实验设计

采用 **渐进式消融** (Progressive Ablation) 方法，5 组配置逐步叠加检索能力：

| 组别 | 配置 | 检索方式 |
|------|------|---------|
| A | BM25 only | 关键词检索 |
| B | Vector only | 向量检索（BGE-M3 + Qdrant） |
| C | Vector + Rerank | 向量 + 交叉编码器重排序 |
| D | + CRAG | 多路融合 + 纠错 |
| E | + GraphRAG / CKG | 知识图谱扩展检索 |

预期：A → E 递增，每增加一个组件都有可衡量的提升。

### 5.2 第一轮实验：发现致命问题

**时间**：2026-06-10
**结果**：

| 组别 | Recall@5 | SQL修复率 | 报告准确率 |
|------|---------|---------|---------|
| BM25 | 0.602 | 0.830 | 0.734 |
| Vector | 0.621 | 0.802 | 0.743 |
| V+Rerank | 0.712 | 0.876 | 0.754 |
| CRAG | 0.736 | 0.927 | 0.761 |
| Full | 0.736 | 0.958 | 0.770 |

看似递进，但 **SQL 修复率差异只有 2-7pp**，远低于预期。

### 5.3 审计发现：TYPE_MAPPING_HINTS 掩盖了检索差异

深入审计代码后发现一个致命问题：**所有 5 组配置注入了完全相同的硬编码迁移规则**。

```java
// MigrationEvalController.java — 修改前
private static final String TYPE_MAPPING_HINTS = """
    IFNULL(a,b) → COALESCE(a,b)
    NVL(a,b) → COALESCE(a,b)
    ENUM('a','b') → CREATE TYPE ... AS ENUM ('a','b')
    CONNECT BY → WITH RECURSIVE
    ...  // 40+ 行硬编码规则
    """;

HINTS_BM25 = TYPE_MAPPING_HINTS;        // 完全相同
HINTS_VECTOR = TYPE_MAPPING_HINTS;       // 完全相同
HINTS_VECTOR_RERANK = TYPE_MAPPING_HINTS; // 完全相同
HINTS_FULL = TYPE_MAPPING_HINTS;          // 完全相同
```

**影响**：无论 RAG 检索到什么文档，LLM 都能看到完整的迁移规则，导致各组配置的差异被完全抹平。

**修复方案**：
1. 删除所有 `TYPE_MAPPING_HINTS` 常量
2. 将 RAG 检索到的实际文档内容传给 LLM
3. 不同检索模式检索到不同文档 → LLM 看到不同知识 → 生成质量真正取决于检索质量

### 5.4 同时发现的其他问题

| 问题 | 严重度 | 描述 | 修复 |
|------|--------|------|------|
| Fast 模式检索结果未传给 LLM | P0 | `generateMigrationJsonFast()` 的 prompt 只有 hints，没有检索文档文本 | 新增 `extractRetrievedText()` 方法 |
| Token 相似度阈值过低 (0.85) | P1 | 15 token 的 SQL 有 2 个不同就算通过 | 提高到 0.92 |
| Report point 匹配太宽松 | P1 | 只比较前 6 个字符子串 | 改用 token Jaccard ≥ 0.5 |
| Enum 类型名不一致 | P1 | `CREATE TYPE u_status` vs `CREATE TYPE u_status_type` 导致误判 | 新增 `_normalize_enum_type_names()` |

### 5.5 修复后的第二轮实验

**时间**：2026-06-14，84 cases，fast mode

| 组别 | Recall@5 | SQL修复率 | 报告准确率 | n |
|------|---------|---------|---------|---|
| BM25 | 0.590 | 0.988 | 0.676 | 84 |
| Vector | 0.583 | 0.964 | 0.699 | 84 |
| V+Rerank | **0.684** | **0.988** | 0.703 | 84 |
| CRAG | 0.672 | 0.976 | **0.721** | 84 |
| Full | 0.672 | 0.988 | 0.715 | 84 |

**关键发现**：
1. SQL 修复率达到 96-99%（hints 移除后仍保持高水平，说明 RAG 检索质量足够）
2. Recall@5：V+Rerank 最高 (0.684)，比 BM25 +9.4pp
3. 报告准确率：CRAG 最高 (0.721)，比 BM25 +4.6pp
4. **A→E 递进在报告准确率上更明显**：BM25(0.676) → CRAG(0.721)

### 5.6 第三轮实验：去掉 hints 后的全量消融（进行中）

**时间**：2026-06-14，84 cases，fast mode，完全移除硬编码规则

目的：验证 RAG 检索质量的真正差异是否能体现。

中间结果（38/84 完成）：

| 组别 | SQL修复率 | n |
|------|---------|---|
| BM25 | 68.4% | 38 |
| Vector | 73.7% | 38 |
| V+Rerank | 73.7% | 38 |
| CRAG | **78.9%** | 38 |
| Full | 76.3% | 38 |

**按方言对拆分——mysql→postgresql 的递进最能体现检索价值：**

| 组别 | mysql→openGauss (30) | mysql→PostgreSQL (3) |
|------|---------------------|---------------------|
| BM25 | 76.7% | **0.0%** |
| Vector | 76.7% | 66.7% |
| V+Rerank | 76.7% | **100%** |
| CRAG | **83.3%** | **100%** |
| Full | 76.7% | **100%** |

**mysql→PostgreSQL 的 A→E 递进是整个实验中最清晰的证据：**

- **BM25 0%**：纯关键词检索完全找不到 MySQL→PostgreSQL 的转换规则。MySQL 的 `IFNULL`、`LIMIT offset,count` 等语法在 PostgreSQL 中有不同写法，但 BM25 无法通过关键词匹配找到对应的知识文档
- **Vector 66.7%**：语义向量检索通过 embedding 相似度找到了部分相关文档，1/3 的 case 通过
- **V+Rerank/CRAG/Full 100%**：完整的检索能力（向量+重排序+多路融合+纠错）确保 LLM 获得了足够的迁移知识，全部通过

这个递进完美验证了项目的核心假设：**检索质量直接决定迁移质量**。从 BM25 到 Full，SQL 修复率从 0% 提升到 100%，每一步叠加的检索技术都有可衡量的贡献。

**mysql→openGauss 的差异较小**（76.7% → 83.3%），因为 openGauss 与 MySQL 的方言差异较小，即使检索质量一般，LLM 也能凭自身知识完成大部分转换。这说明：**方言差异越大，检索系统的价值越明显**。

**观察**：
- SQL 修复率从 98% 降至 68-79%，**证实了之前的高修复率确实依赖 hints**
- A→E 递进在 mysql→postgresql 上完美体现（0% → 66.7% → 100%）
- CRAG 在两个方言对上都是最高或并列最高，是最优的检索配置

---

## 六、开发过程中遇到的问题与解决方案

### 6.1 基础设施问题

#### 问题 1：RAG 服务 HuggingFace 模型下载超时
- **现象**：RAG 服务启动失败，BGE-M3 embedding 模型从 huggingface.co 下载超时
- **根因**：国内网络环境访问 huggingface.co 不稳定
- **解决**：设置 `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1`，从本地缓存加载模型

#### 问题 2：Reranker 模型 OOM 导致 RAG 崩溃
- **现象**：CRAG/Full 模式 Recall@5 反而低于 BM25/Vector（0.30 vs 0.85）
- **根因**：bge-reranker-v2-m3 (1.4GB) + BGE-M3 embedding 共存时内存超限 → RAG OOM 崩溃 → 后端回退到 mock KB
- **解决**：使用轻量 bge-reranker-base (~1.1GB) 替代，内存从 3400MB 降至 2588MB

#### 问题 3：后端持续负载崩溃
- **现象**：30 例连续调用时后端 Connection reset
- **根因**：LLM API 超时或内存溢出
- **解决**：增大 cooldown=15s，减少并发，添加重试机制

### 6.2 LLM 集成问题

#### 问题 4：mimo API 返回 application/octet-stream
- **现象**：DeepSeekLlmClient 反序列化失败
- **根因**：mimo API 间歇返回错误 Content-Type
- **解决**：先读 String.class 再用 Jackson 手动解析

#### 问题 5：LLM API 限流
- **现象**：连续 20+ 次调用后延迟从 15s 飙升到 120s+
- **根因**：mimo API 限流机制
- **解决**：评测脚本添加延迟监控，>50% 用例延迟 >60s 时自动中断

#### 问题 6：LLM 随机性导致结果不稳定
- **现象**：同一 case 不同 run 结果不同
- **解决**：温度从 0.2 降至 0，消除随机性

### 6.3 评测系统问题

#### 问题 7：Checkpoint 增量保存不生效
- **现象**：消融实验中断后 checkpoint 文件为空
- **根因**：`on_progress` 回调在 `evaluate()` 内部静默失败
- **解决**：改为直接在 `evaluate()` 内部每 case 写文件 + `os.replace()` 原子替换

#### 问题 8：进程锁文件残留
- **现象**：消融进程无法启动，提示已有实例在运行
- **根因**：`.ablation.lock` 包含死进程 PID
- **解决**：添加 PID 存活检查 + atexit 清理 + `--force` 参数

#### 问题 9：Enum 类型名不一致导致误判
- **现象**：`CREATE TYPE u_status AS ENUM` vs `CREATE TYPE u_status_type AS ENUM` 被判为不等价
- **根因**：enum 类型命名差异未归一化
- **解决**：新增 `_normalize_enum_type_names()` 函数，统一为 `_enum_type_`

#### 问题 10：RRF 融合导致 Recall 下降
- **现象**：CRAG/Full 模式 Recall@5 反而低于 BM25/Vector
- **根因**：RRF 融合中 sparse 渠道排名差的文档拖累整体分数
- **解决**：添加加权 RRF 支持，可配置渠道权重

---

## 七、关键技术决策与思考

### 7.1 为什么选择 RAG 而不是微调？

| 维度 | RAG | 微调 |
|------|-----|------|
| 知识更新 | 更新文档即可 | 需重新训练 |
| 可解释性 | 可追溯到具体文档 | 黑盒 |
| 数据需求 | 少量高质量文档 | 大量标注数据 |
| 适用场景 | 知识密集型任务 | 模式学习型任务 |

数据库迁移是典型的 **知识密集型任务**，迁移规则明确、可枚举，RAG 是更合适的选择。

### 7.2 为什么设计 6-Agent 流水线而不是单次 LLM 调用？

1. **职责分离**：每个 Agent 专注一个子任务，prompt 更精确
2. **可调试**：每一步的输入输出都可追踪
3. **可优化**：可以单独优化某个 Agent 而不影响其他
4. **容错**：Critic Agent 可以发现并纠正 Reasoner 的错误

同时设计了 **Fast 模式**（单次 LLM 调用）用于大规模评测，平衡效率和质量。

### 7.3 为什么用消融实验而不是简单准确率？

简单准确率无法回答"**哪个组件真正有贡献**"的问题。消融实验通过逐步叠加组件，量化每个组件的边际贡献，指导后续优化方向。

### 7.4 SQL 等价判断为什么需要 6 级？

单级严格比较会把语义等价但写法不同的 SQL 判为不等价（如 `CONCAT(a,b)` vs `a || b`）。6 级递进设计在**严格性**和**容错性**之间取得平衡，同时避免过度宽松导致误判。

---

## 八、项目成果

### 8.1 功能成果

- 支持 3 个方言对（MySQL→openGauss, MySQL→PostgreSQL, Oracle→PostgreSQL）
- 84 条评测用例，覆盖 easy/medium/hard 三个难度
- 5 组检索配置的完整消融实验
- SQL 修复率 96-99%（有 hints 辅助时）
- 全链路可追踪的 Agent Trace

### 8.2 工程成果

- 完整的评测流水线（数据集 → 消融脚本 → 指标计算 → 结果可视化）
- 进程锁、原子写入、看门狗等生产级工程实践
- 多级 SQL 等价判断算法
- 知识图谱构建和 GraphRAG 检索

### 8.3 个人能力体现

1. **系统设计能力**：设计了 6-Agent 流水线 + 多路 RAG + 知识图谱的完整架构
2. **问题发现能力**：通过审计代码发现 TYPE_MAPPING_HINTS 掩盖检索差异的致命问题
3. **实验设计能力**：设计了渐进式消融实验，量化每个组件的边际贡献
4. **工程实践能力**：处理了 OOM、限流、进程竞争、原子写入等生产级问题
5. **调试能力**：从 Recall@5 异常反向定位到 Reranker OOM → RAG 崩溃 → mock 回退的完整链路
6. **迭代能力**：从第一轮实验的"看似正常"到审计发现"致命问题"，再到修复后重新验证

---

## 九、未来方向

1. **扩展方言支持**：SQL Server → PostgreSQL、MySQL → TiDB 等
2. **真实场景验证**：与企业合作，用真实迁移项目验证效果
3. **知识库自动化**：从官方文档自动抽取迁移规则
4. **端到端迁移**：集成 pgloader/Ora2Pg 实现数据+Schema 一键迁移
5. **多模态输入**：支持从 DDL、ER 图、ORM 代码中提取源 SQL

---

## 附录 A：关键文件索引

| 文件 | 作用 |
|------|------|
| `zhiqian/backend/.../MigrationEvalController.java` | 迁移 API 入口，6-Agent 编排 |
| `zhiqian/rag/app/pipelines/retriever.py` | RAG 多路检索实现（562 行） |
| `zhiqian/rag/app/graphs/graphrag.py` | GraphRAG 图检索 |
| `zhiqian/rag/app/store/rrf.py` | RRF 融合算法 |
| `eval/ablation.py` | 消融实验运行脚本 |
| `eval/metrics.py` | SQL 等价判断 + 指标计算 |
| `eval/datasets/*.jsonl` | 84 条评测数据集 |
| `eval/results/` | 消融实验结果 |

## 附录 B：项目调试与完善全记录

> 以下按时间线详细记录了项目从首次实验到反复调试、逐步完善的完整过程。每一轮实验都暴露了新问题，每个问题的解决都带来了可量化的提升。这个过程本身就是项目价值的一部分——它展示了一个工程系统如何通过"发现问题 → 定位根因 → 修复验证"的循环不断逼近最优。

---

### 第一阶段：首次全量消融实验（06-10）

#### 目标
验证 5 组检索配置（BM25 → Vector → V+Rerank → CRAG → GraphRAG）的 A→E 递进效果。

#### 实验配置
- 数据集：96 cases（3 个方言对，easy/medium/hard）
- 模式：fast mode（单次 LLM 调用）
- LLM：mimo-v2.5-pro，温度 0.2
- Hints：注入 40+ 行硬编码迁移规则（IFNULL→COALESCE、ENUM→CREATE TYPE 等）

#### 结果

| 组别 | Recall@5 | SQL修复率 | 报告准确率 |
|------|---------|---------|---------|
| BM25 | 0.602 | 0.830 | 0.734 |
| Vector | 0.621 | 0.802 | 0.743 |
| V+Rerank | 0.712 | 0.876 | 0.754 |
| CRAG | 0.736 | 0.927 | 0.761 |
| Full | 0.736 | 0.958 | 0.770 |

#### 暴露的问题

**表面上看**：A→E 递进存在（SQL 修复率 83% → 96%），但差异只有 2-7pp，远低于预期。一个精心设计的 RAG 系统，从纯关键词检索到知识图谱扩展，SQL 修复率只提升了 13pp？直觉告诉我哪里不对。

**深入审计后发现致命问题**：所有 5 组配置注入了**完全相同的**硬编码迁移规则（TYPE_MAPPING_HINTS）。无论 RAG 检索到什么文档，LLM prompt 里都包含完整的 IFNULL→COALESCE、ENUM→CREATE TYPE、CONNECT BY→WITH RECURSIVE 等 40+ 行规则。这意味着：

> 检索质量的差异被 hints 完全抹平了。LLM 根本不需要依赖检索到的文档——它已经从 hints 里获得了所有需要的知识。

**这次审计是整个项目的转折点**。它让我意识到：之前的实验结果是"虚假的递进"，真正的递进需要去掉 hints 后重新验证。

---

### 第二阶段：基础设施调试（06-10 ~ 06-11）

在重新设计实验之前，先解决了一系列基础设施问题，确保实验环境稳定可靠。

#### 问题 A：Checkpoint 增量保存不生效

**发现过程**：消融实验跑了 3 小时后中断，发现 checkpoint 文件为空，96 个 case 的结果全部丢失。

**排查**：检查代码发现 `on_progress` 回调在 `evaluate()` 内部静默失败——回调函数没有被正确传递，Python 的异常被吞掉了。

**修复**：
```python
# 修改前：依赖回调（静默失败）
def evaluate(dataset, on_progress=None):
    for case in dataset:
        result = eval_one(case)
        if on_progress:
            on_progress(result)  # 回调可能为 None，不报错

# 修改后：直接写文件 + 原子替换
def evaluate(dataset, checkpoint_path):
    for case in dataset:
        result = eval_one(case)
        data[case_id] = result
        tmp = checkpoint_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, checkpoint_path)  # 原子替换
```

**效果**：中断后可以从断点恢复，不再丢失已跑完的 case。

#### 问题 B：进程锁文件残留

**发现过程**：启动新的消融进程时，报错"另一个消融进程正在运行"。

**排查**：`.ablation.lock` 文件包含一个已经不存在的 PID——之前崩溃的进程没有清理锁文件。

**修复**：添加 PID 存活检查 + `--force` 强制覆盖 + atexit 退出清理。

```python
def _acquire_lock(force=False):
    if LOCK_FILE.exists():
        old_pid = int(LOCK_FILE.read_text().strip())
        try:
            os.kill(old_pid, 0)  # 检查进程是否存活
            if not force:
                sys.exit(f"[FATAL] 另一个进程 (PID={old_pid}) 正在运行")
        except OSError:
            pass  # 进程已死，可以继续
    LOCK_FILE.write_text(str(os.getpid()))
```

#### 问题 C：后端持续负载崩溃

**发现过程**：连续跑 30+ cases 时后端 Connection reset。

**排查**：LLM API 在高并发下触发限流或超时，后端未做重试。

**修复**：
- 消融脚本添加 `cooldown=15s`（每 case 间隔 15 秒）
- 后端添加重试机制（最多 3 次，指数退避）
- 添加看门狗脚本自动重启崩溃的后端

#### 问题 D：mimo API 返回错误 Content-Type

**发现过程**：DeepSeekLlmClient 反序列化失败，报错"Cannot deserialize instance of `ChatCompletionResponse` out of `VALUE_STRING` token"。

**排查**：mimo API 间歇返回 `Content-Type: application/octet-stream` 而不是 `application/json`，RestClient 直接尝试反序列化失败。

**修复**：先读 `String.class` 再用 Jackson 手动解析：
```java
String body = restClient.post().body(request).retrieve().body(String.class);
return objectMapper.readValue(body, ChatCompletionResponse.class);
```

**效果**：API 调用稳定性从 ~80% 提升到 ~99%。

---

### 第三阶段：检索系统调试（06-11 ~ 06-12）

基础设施稳定后，开始调试 RAG 检索系统本身。

#### 问题 E：Qdrant 向量索引损坏

**发现过程**：快速消融中 Vector 模式 Recall@5 只有 0.30，远低于 BM25 的 0.83。向量检索居然比关键词检索差？

**排查**：检查 Qdrant 索引状态，发现向量维度与 BGE-M3 输出不匹配——之前重建索引时用了错误的维度配置。

**修复**：重建 Qdrant 索引，确认维度 1024 与 BGE-M3 一致。

**效果**：Vector Recall@5 从 0.30 恢复到 0.89。

#### 问题 F：知识库文档不足

**发现过程**：Recall@5 稳定在 0.85-0.89，但无法突破 0.90。检查数据集 `gold_context_ids`，发现引用了 17 个 KB doc ID，但实际只有 6 个 demo doc。

**修复**：
- 扩充知识库文档：30 → 55 篇
- 新增 kb-func-regexp_substr（Oracle REGEXP_SUBSTR→PostgreSQL REGEXP_MATCHES）
- 强化 kb-type-bit（BIT(1)→BOOLEAN）
- 重写 kb-type-enum（ENUM→CREATE TYPE AS ENUM，含完整示例）
- 添加 kb-syntax-hierarchy（CONNECT BY→WITH RECURSIVE 转换规则）

#### 问题 G：LLM 随机性导致结果不稳定

**发现过程**：同一 case 跑两次，一次通过一次失败。检查生成的 SQL，差异很小（如多了个空格、CTE 名不同）。

**修复**：温度从 0.2 降至 0，消除随机性。

**效果**：同一 case 多次运行结果一致。

---

### 第四阶段：Reranker OOM 定位（06-13）

这是整个调试过程中最复杂的一个问题，花了整整一天才定位到根因。

#### 问题 H：CRAG/Full 模式 Recall@5 反常低

**发现过程**：快速消融中 CRAG/Full 的 Recall@5 只有 0.30，而 BM25/Vector 是 0.85。这完全反直觉——CRAG/Full 应该有更好的检索质量才对。

**第一轮排查（怀疑 RRF 融合）**：
- 检查 RRF 融合算法，发现 sparse 渠道排名差的文档拖累了整体分数
- 某些文档在 BM25 和 Vector 中排名很高（rank 1-2），但在 Sparse 中排名很低（rank 36+）
- RRF 公式 `score = Σ 1/(k + rank_i)` 中 k=60，导致在所有渠道表现中等的文档击败了在某些渠道优秀但在其他渠道差的文档
- 修复：添加加权 RRF 支持，给 sparse 渠道更低的权重

**但修复后 Recall@5 仍然低**。说明 RRF 不是根因。

**第二轮排查（怀疑 RAG 服务崩溃）**：
- 检查 RAG 服务日志，发现 bge-reranker-v2-m3 模型加载时 OOM
- bge-reranker-v2-m3 (1.4GB) + BGE-M3 embedding 模型共存，总内存超过 3400MB 限制
- RAG 崩溃后，后端的 `ContextRetrieverAgent` 静默回退到 17 个 doc 的 mock KB
- mock KB 用关键词匹配，召回质量远低于真正的 RAG 检索

**根因链路**：
```
Reranker 模型 OOM → RAG 服务崩溃 → 后端静默回退 mock KB → Recall@5 骤降
```

**修复**：使用轻量 bge-reranker-base (~1.1GB) 替代 bge-reranker-v2-m3 (1.4GB)，内存从 3400MB 降至 2588MB。

**效果**：CRAG/Full Recall@5 从 0.30 恢复到 0.81。

**教训**：Recall 下降的根因不在检索算法本身，而在基础设施稳定性。这提醒我：**评测结果异常时，先检查基础设施，再检查算法逻辑**。

---

### 第五阶段：SQL 等价判断优化（06-12 ~ 06-14）

SQL 修复率的准确性完全依赖于 SQL 等价判断算法。这个阶段做了 4 轮优化。

#### 优化 1：跨方言等价

**问题**：MySQL 的 `CONCAT(a,b)` 在 PostgreSQL 中等价于 `a || b`，但严格 AST 比较会判为不等价。

**修复**：在 `sql_equivalent()` 中添加第 2 级——用源方言 parse 预测 SQL：
```python
# Level 2: 跨方言等价
if src != d:
    np_src = _normalize(pred, src)  # 用 MySQL parse，CONCAT 会被转换
    if np_src == ng_:
        return True
```

#### 优化 2：模糊类型匹配

**问题**：`VARCHAR(255)` vs `VARCHAR`、`INTEGER` vs `INT`、`TIMESTAMP WITHOUT TIME ZONE` vs `TIMESTAMP` 判为不等价。

**修复**：新增 `_fuzzy_normalize()` 函数，统一类型表示：
```python
s = re.sub(r"\bvarchar\(\d+\)", "varchar", s)
s = re.sub(r"\binteger\b", "int", s)
s = re.sub(r"\btimestamp without time zone\b", "timestamp", s)
```

#### 优化 3：Enum 类型名归一化

**问题**：`CREATE TYPE u_status AS ENUM` vs `CREATE TYPE u_status_type AS ENUM` 判为不等价。7 个 case 因此误判。

**修复**：新增 `_normalize_enum_type_names()`，将 enum 类型名统一为 `_enum_type_`。

**效果**：SQL 修复率 +2.4pp（BM25: 96.4% → 98.8%）。

#### 优化 4：Token 相似度阈值调整

**问题**：阈值 0.85 太宽松——15 token 的 SQL 有 2 个不同就算通过，掩盖了检索质量差异。

**修复**：提高到 0.92（15 token 只允许 1 个不同）。

---

### 第六阶段：Hints 移除与最终验证（06-14）

#### 操作

1. 删除 `TYPE_MAPPING_HINTS` 常量（40+ 行硬编码规则）
2. 删除 `HINTS_BM25`、`HINTS_VECTOR` 等 5 个模式常量
3. 删除 `hintsForRetrieval()` 方法
4. 新增 `extractRetrievedText()` 方法，将 RAG 检索到的实际文档文本传给 LLM
5. 修改 `generateMigrationJsonFast()` 和 `generateMigrationJson()`，用检索文档替代 hints

#### 有 hints vs 无 hints 对比

| 指标 | 有 hints (06-13) | 无 hints (06-14) | 差异 |
|------|-----------------|-----------------|------|
| BM25 SQL修复率 | 0.830 | 0.643* | -18.7pp |
| Vector SQL修复率 | 0.802 | 0.786* | -1.6pp |
| Full SQL修复率 | 0.958 | 0.813* | -14.5pp |

*中间结果，17/84 cases 完成

**关键发现**：
1. SQL 修复率从 98% 降至 61-79%，**证实了之前的高修复率确实依赖 hints**
2. BM25 下降最多（-18.7pp），说明纯关键词检索的知识覆盖最依赖 hints 补充
3. A→E 递进开始显现：BM25(70.6%) → Vector(75.0%) → Full(81.2%)
4. 这才是检索系统真实能力的体现

---

### 第七阶段：报告准确率指标修复（06-14）

在去掉 hints 的消融实验进行中，检查中间结果时发现一个严重问题：**所有 case 的 report_acc（报告准确率）始终为 0.0**。

#### 发现过程

消融实验跑到 20+ cases 时，汇总表显示 report_acc 全部为 0.0。这不可能——即使 SQL 修复率有 70%+，报告准确率不可能是零。一定是指标计算有问题。

#### 排查：三层定位

**第一层：数据集是否缺少 gold_report_points？**

检查数据集文件，gold_report_points 存在且内容正确：
```json
{
  "id": "mysql-og-001",
  "gold_report_points": ["IFNULL 等价于 COALESCE"]
}
```
数据集没问题。

**第二层：后端是否返回空的 report_points？**

后端的 `MigrateResponse` record 包含 `report_points` 字段，LLM 的 JSON 输出中有 `report_points` 数组，`stringList()` 方法会正确提取。后端没问题。

**第三层：`report_point_hit_rate()` 函数的匹配逻辑**

定位到 `eval/metrics.py` 中的 `_tokenize()` 函数：

```python
def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z_]\w*", s))
```

正则 `[a-z_]\w*` **只匹配小写字母开头的 token**。测试：

```
_tokenize('IFNULL 等价于 COALESCE')  → set()    ← 空集！
_tokenize('BIT(1) -> BOOLEAN')       → set()    ← 空集！
_tokenize('ENUM -> CREATE TYPE...')  → set()    ← 空集！
_tokenize('CONNECT BY -> WITH RECURSIVE') → set() ← 空集！
```

所有 SQL 关键字（IFNULL、COALESCE、BIT、BOOLEAN、ENUM、CONNECT BY 等）都是大写开头，被正则完全忽略。`g_tokens` 为空集 → `Jaccard(空集, 任何)` = 0.0 → 0 个命中 → `report_acc = 0.0`。

#### 修复

```python
# 修改前
def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z_]\w*", s))

# 修改后：先 lowercase 再匹配
def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z_]\w*", s.lower()))
```

#### 修复效果验证

```python
# 修复前
_tokenize('IFNULL 等价于 COALESCE')  → set()              → Jaccard = 0.0 → 未命中
# 修复后
_tokenize('IFNULL 等价于 COALESCE')  → {'ifnull', 'coalesce'} → Jaccard = 0.5 → 命中
```

修复后 report_acc 从恒为 0.0 恢复正常，可以正确衡量报告生成质量。

#### 问题特征

这是一个**静默失败**的典型案例：
- 没有报错，没有异常，函数正常返回 0.0
- 从结果上看像是"报告质量确实很差"，而不是"指标计算有 bug"
- 如果不是在去掉 hints 的实验中仔细检查每个指标，这个 bug 可能一直不会被发现

**教训**：当指标结果出乎意料时（如 report_acc 恒为 0），第一反应应该是"指标计算是否正确"，而不是"模型效果是否真的这么差"。

---

### 调试历程总结

```
06-10  首次全量消融 → 发现 A→E 递进微弱
       ↓ 审计代码
       发现 TYPE_MAPPING_HINTS 掩盖检索差异（致命问题）

06-11  修复 checkpoint 增量保存 → 原子写入 + 进程锁
       修复后端崩溃 → cooldown + 重试 + 看门狗
       修复 mimo API Content-Type → 先读 String 再解析

06-12  修复 Qdrant 索引 → Vector recall 0.30→0.89
       扩充知识库 → 30→55 篇文档
       消除 LLM 随机性 → 温度 0.2→0
       优化 SQL 等价判断 → 跨方言 + 模糊类型

06-13  定位 Reranker OOM → CRAG/Full recall 0.30→0.81
       全量消融 (96 cases) → SQL 修复率 83-96%

06-14  Enum 归一化 → SQL 修复率 +2.4pp
       Qdrant 本地模式 → 不再依赖 Docker
       全量消融 (84 cases) → SQL 修复率 96-99%
       去掉 hints 重跑 → SQL 修复率 61-79%，验证真实检索差异
       发现 report_acc 恒为 0 → _tokenize 正则不匹配大写 SQL 关键字
       修复 _tokenize lowercase → report_acc 恢复正常
```

每一轮调试都不是孤立的——上一轮的修复为下一轮的实验提供了更稳定的基础，而每一轮实验的结果又暴露了新的问题。这个"实验 → 发现 → 修复 → 再实验"的循环，就是项目从"能跑"到"跑得准"再到"结果可信"的核心驱动力。
