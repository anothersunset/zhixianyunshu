# 开发日志：三层复审体系设计与实现

日期：2026-06-24

---

## 1. 背景

在之前的多轮评测中，`sql_equivalent()` 用 sqlglot 做 SQL 等价性比较。但存在两类明显的误判：

1. **语法等价但写法不同**：`FETCH FIRST n ROWS ONLY` vs `LIMIT n`（两者都是合法 PG 语法）
2. **金标本身有问题**：PARROT 数据集的部分金标保留了 Oracle 专有语法（`DBMS_LOB.SUBSTR`、`CONNECT BY`、`FROM dual`），因为它假设目标库预装了 Oracle 兼容 UDF

这两种情况导致 LLM 明明转换正确，却被判 FAIL。

---

## 2. 问题发现过程

### 2.1 第一轮：25-case 随机样本（基线 68%）

跑 `python -m eval.run_eval --retrieval full --pair oracle_postgresql_subset25 --dataset eval/datasets/parrot --mode fast`

结果 17/25 OK。分析 FAIL 的 8 个 case 发现：

| 失败模式 | 案例 | 说明 |
|---------|------|------|
| LLM 过度转换 | `COUNT(*) FILTER(...)` → `CASE WHEN` | FILTER 是合法 PG 语法，不应转换 |
| Eval 误判 | `FETCH FIRST n ROWS ONLY` vs `LIMIT n` | sqlglot 不归一化这俩 |
| 金标保留 Oracle | `DBMS_LOB.SUBSTR` 保留不动 | PARROT 假设 UDF 存在 |
| 漏检 | `TIMESTAMP_TRUNC`、`REGEXP_REPLACE` | 注册表未覆盖 |

### 2.2 第二轮：20-case 高价值样本（原始 35%）

从 217 个 PARROT case 中筛选出 84 个含真实 Oracle 特征的 case，取 20 个测试。结果仅 7/20 OK = 35%，远低于预期。

**逐一审查 13 个 FAIL**：

```
5 个 → PARROT 金标数据质量问题（金标保留 Oracle 专有语法，LLM 转换反而正确）
  27046: DBMS_LOB.SUBSTR → SUBSTRING（金标保留 Oracle 函数）
  27653: 同上
  27428: CONNECT BY → WITH RECURSIVE（金标保留 Oracle 层次查询）
  27599: FROM dual, NVL2 → 移除（金标保留 Oracle 语法）
  27874: STATS_MODE → MODE() WITHIN GROUP（金标保留 Oracle 聚合函数）

4 个 → Eval 误判（FETCH FIRST vs LIMIT，sqlglot 不归一化）
  23396, 22040, 21625, 21816

2 个 → 合法 PG 替代方案（eval 不够灵活）
  21581, 23017: ROW_NUMBER 去重 vs DISTINCT ON

1 个 → 轻微语法差异
  22773: CURRENT_DATE::date vs CAST(CURRENT_DATE AS DATE)
```

**核心发现**：35% 这个数字严重失真。实际 LLM 转换质量远高于数字显示。

---

## 3. 方案设计：三层复审体系

### 思路

评测链路中存在三类断层，需要分层解决：

```
LLM 输出 SQL ──→ sqlglot 等价比较 ──→ FAIL
                  ↑                    ↑
                  │                    │
         Layer 1: 语法归一化    Layer 2: LLM Judge 语义复审
         (解决写法差异)         (解决结构差异)
                                    │
                              Layer 3: 金标质量标记
                              (区分"LLM错了"还是"金标有问题")
```

### Layer 1：语法归一化（快速、确定性）

在 `sql_equivalent()` 比较前做纯文本正则归一化：

| 归一化规则 | 解决的问题 |
|-----------|-----------|
| `FETCH FIRST n ROWS ONLY` → `LIMIT n` | FETCH FIRST vs LIMIT |
| `CAST(CURRENT_DATE AS DATE)` → `CURRENT_DATE` | 冗余 CAST |
| `INTERVAL 'N DAYS'` → `INTERVAL 'N DAY'` | 单复数差异 |

设计原则：只归一化**确定语义等价但 sqlglot 不会处理**的语法差异。不碰可能有语义差异的转换。

### Layer 2：LLM Judge 语义复审（慢但精准）

已有基础架构（`eval/judge.py` + `--use-judge`），但之前没用。关键设计决策：

- **避免同模型自评**：chat-model（deepseek-chat）做 SQL 生成，reasoner-model（deepseek-reasoner）做 Judge 评审
- **通过后端代理调用**：设置 `ZHIQIAN_MIGRATE_URL=http://localhost:8080`，复用后端的 RestClient 连接池，避免 Python 直连 DeepSeek API 在大陆环境挂起

Judge 解决了 sqlglot 无法判断的语义等价：
- `ROW_NUMBER() OVER(PARTITION BY ...)` vs `DISTINCT ON`（去重模式等价）
- `STATS_MODE(col)` vs `MODE() WITHIN GROUP (ORDER BY col)`（聚合函数等价）
- `DBMS_LOB.SUBSTR(col, n)` vs `SUBSTRING(col FROM 1 FOR n)`（如果假设 UDF 存在）

### Layer 3：金标质量标记（数据诊断）

在 `metrics.py` 中新增三个函数：

```python
is_valid_pg(sql)           # 金标能否被 PG 方言解析？
has_oracle_only_constructs(sql)  # 金标是否含 Oracle 专有语法？
gold_quality_check(sql)    # 返回 ok | oracle_residue | invalid_pg
```

在 `run_eval.py` 的 `summarize()` 中新增：

```python
adjusted_rate_excl_questionable_gold  # 排除可疑金标后的修复率
gold_quality: {ok, oracle_residue, invalid_pg}  # 金标质量分布
```

这样评测结果不再是单一数字，而是：
- 原始修复率（所有 case）
- 调整修复率（仅看金标 OK 的 case）
- 金标质量分布（诊断数据集本身的问题）

---

## 4. 迭代验证

### 4.1 逐个修复的效果

| 阶段 | 修复率 | 增益 | 说明 |
|------|--------|------|------|
| 原始 | 35% | - | FETCH FIRST、金标问题混在一起 |
| + Layer 1（归一化） | 60% | +25pp | 修复 5 个 FETCH FIRST 和 INTERVAL 差异 |
| + 排除可疑金标 | **90%** (9/10) | +30pp | 排除 10 个含 Oracle 残留的金标 |
| + Layer 2（Judge） | 80% (16/20) | +20pp | Judge 解决 5 个语义等价 case |

### 4.2 Judge 解决的 5 个 case

| Case | sqlglot | Judge | 争议点 |
|------|---------|-------|--------|
| 27874 | FAIL | → OK | `STATS_MODE` vs `MODE() WITHIN GROUP` + `DATE_TRUNC('IW')` vs `('week')` |
| **21581** | FAIL | → OK | **`ROW_NUMBER` 去重 vs `DISTINCT ON`** |
| 27653 | FAIL | → OK | `DBMS_LOB.SUBSTR` vs `SUBSTRING` |
| 22588 | FAIL | → OK | `CLOB/$$` vs `TEXT/$func$` |
| 22773 | FAIL | → OK | `CURRENT_DATE` vs `CAST(CURRENT_DATE AS DATE)` |

### 4.3 最终剩余 FAIL 分析

| Case | 金标质量 | 原因 |
|------|---------|------|
| 27046 | oracle_residue | 金标保留 `DBMS_LOB.SUBSTR`，LLM 转 `SUBSTRING`（LLM 正确） |
| 27428 | oracle_residue | 金标保留 `CONNECT BY`，LLM 转 `WITH RECURSIVE`（LLM 正确） |
| 27599 | oracle_residue | 金标保留 `FROM dual`/`NVL2`，LLM 移除（LLM 正确） |
| 23017 | **ok** | `ROW_NUMBER` 去重 vs `DISTINCT ON`，结构差异太大，Judge 也无法认定等价 |

---

## 5. 经验教训

### 5.1 金标质量是自动化评测的前提

PARROT 数据集设计时假设"目标库有 Oracle 兼容 UDF"，导致大量金标保留 Oracle 专有语法。这与 LLM 的"语法转换"目标冲突。Layer 3 通过标记金标质量，至少让这个问题可见、可量化。

### 5.2 评测数字需要拆分解读

单一修复率（80%）掩盖了三个不同层面的问题：
- 实际 LLM 质量（90% 调整后）
- Eval 工具链缺陷（FETCH FIRST 不归一化）
- 数据集质量问题（50% case 金标可疑）

### 5.3 Judge 不是银弹

Judge 能处理简单的语义等价（ROW_NUMBER vs DISTINCT ON），但遇到结构差异大的转换（23017 的 UNION + 多层嵌套 + 多语法点差异），Judge 也会 FAIL。

---

## 6. 涉及文件

| 文件 | 改动 |
|------|------|
| `eval/metrics.py` | `_normalize_fetch_first()`、`is_valid_pg()`、`has_oracle_only_constructs()`、`gold_quality_check()`、`_fuzzy_normalize` 增强 |
| `eval/run_eval.py` | `_eval_one()` 加 `gold_quality` 字段、`summarize()` 加调整修复率和金标分布 |
| `eval/judge.py` | 已有，通过 `ZHIQIAN_MIGRATE_URL` 使用后端代理模式 |
| `MigrationEvalController.java` | cross-model review 修复（chat-model 生成，reasoner 评审） |
