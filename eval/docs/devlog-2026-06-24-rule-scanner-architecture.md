# 开发日志：规则扫描器 P0/P1/P2 架构重构 + 三层复审

日期：2026-06-22 ~ 2026-06-24
项目：zhixianyunshu（智迁云枢）
模块：方言特征检测 + 评测复审

---

## 1. 背景

v11 版本 30/30 oracle-pg 通过后，架构存在两个核心问题：
- 注册表分裂：`FEATURE_MAP`（22 个）和 `RECIPES`（8 个）独立维护，新增特征需在两处添加
- 未知特征漏检：`REGEXP_REPLACE`、`TO_NUMBER` 等未注册函数零提示给 LLM
- 注释/字面量误检：`-- Use CONNECT BY` 被误判为 Oracle 特征

---

## 2. P0：统一注册表

**设计**：`TranslationRecipeRegistry.java` 重写为单一 `RegisteredFeature` record：

```java
public record RegisteredFeature(
    String sourceKeyword,       // 检测关键词
    String targetMapping,       // 简短映射
    String dialectGroup,        // "oracle" | "mysql"
    String constructName,       // null = simple entry
    String fewShotSource,       // null = simple entry（无 few-shot）
    String fewShotTarget,
    String stepByStepGuide,
    List<String> commonPitfalls
) {
    public boolean isRecipe() { return fewShotSource != null; }
}
```

- 37 个特征（22 Oracle + 15 MySQL）集中在单一 `ALL` 静态集合
- `isRecipe()` 区分 full recipe（含 few-shot）和 simple entry（仅关键词→映射）
- 新增特征只需添加一条 `RegisteredFeature`

---

## 3. P1：两阶段检测

**Phase 1**：遍历 `TranslationRecipeRegistry.allFor(dialect)` 做精确关键词匹配。

**Phase 2**：正则 `\b([A-Z][A-Z0-9_]{2,})\s*\(` 宽筛未注册大写函数，经 PG_STANDARD 白名单（60+ 条目）过滤后标记为 `"⚠ UNKNOWN: check PG equivalent"`。

PG_STANDARD 白名单设计原则：
- SQL 标准关键字（SELECT, WHERE, JOIN 等）
- PG 内置函数（ABS, TRIM, COALESCE 等）
- PG 类型（TEXT, JSONB, UUID 等）
- SQL:2003+ 子句关键词（FILTER, OVER, LATERAL, FETCH 等）
- PL/pgSQL 关键字（DECLARE, LOOP, RETURN 等）

**防止误检示例**：
- `COUNT(*) FILTER(WHERE ...)` → FILTER 不应标记为未知
- `ROW_NUMBER() OVER(...)` → OVER 不应标记为未知
- `... USING (id)` → USING 是 JOIN 子句，不是函数

---

## 4. P2：注释/字面量剥离

**问题**：关键字匹配是原始字符串扫描，注释和字面量导致误检：
```
-- Use CONNECT BY for hierarchy    → 误检 CONNECT BY
SELECT 'ROWNUM is not supported'   → 误检 ROWNUM
/* NVL() is deprecated */          → 误检 NVL(
```

**修复**：`stripCommentsAndStrings()` 纯 Java 状态机实现：
- 单行注释 `--` → 替换为空格
- 多行注释 `/* */` → 替换为空格
- 字符串字面量 `'...'`（含 `''` 转义） → 替换为空格

**关键设计**：用空格替换被剥离内容（而非直接删除），保留行列位置不变，避免合并相邻 token。

---

## 5. 规则扫描器版本演进

| 版本 | 结果 | 关键改动 |
|------|------|----------|
| v1-v5 | 24-27/30 | 基础 FEATURE_MAP + RECIPES |
| v6 | 28/30 | 规则扫描 + 跨模型 critic |
| v7 | 26/30 | 模型切换 mimo→deepseek-chat（引入回归） |
| v8 | 29/30 | fixupStubbornPatterns 增强 |
| v9 | 28/30 | deepseek-chat 行为不稳定 |
| v10 | 29/30 | "无特征→跳过 LLM" 优化 |
| v11 | **30/30** | fixup 完善 |
| v12 | **30/30** | P0+P1+P2 统一注册表 + 两阶段检测 |

### RAG-based vs Rule-based 对比

| 维度 | RAG-based | Rule-based (v12) |
|------|-----------|-------------------|
| oracle-pg 修复率 | 96-99% | 100% |
| 特征检测 | BM25/Vector/RRF 检索 | 零 LLM 关键词+正则 |
| 延迟 | RAG HTTP + LLM | 毫秒级内存扫描 |
| 稳定性 | 受 RAG 可用性影响 | 完全本地确定性 |
| 未知特征 | 依赖 KB 覆盖 | "⚠ UNKNOWN" 兜底 |

---

## 6. 三层复审体系

详见 `devlog-2026-06-24-review-system.md`。

| 层 | 方法 | 解决的问题 |
|----|------|-----------|
| Layer 1 | sqlglot 语法归一化（FETCH FIRST→LIMIT 等） | 写法差异 |
| Layer 2 | LLM Judge 语义复审 | 结构差异（ROW_NUMBER vs DISTINCT ON） |
| Layer 3 | 金标质量标记 | 区分"LLM 错了"还是"金标有问题" |

**效果**：PARROT 20-case 35% → 80%（调整后 90%）。

---

## 7. 涉及文件

| 文件 | 改动 |
|------|------|
| `TranslationRecipeRegistry.java` | P0 统一注册表 |
| `DialectFeatureScanner.java` | P1 两阶段 + P2 注释剥离 |
| `eval/metrics.py` | Layer 1 归一化 + Layer 3 金标检测 |
| `eval/run_eval.py` | 金标质量字段 + 调整修复率 |
| `MigrationEvalController.java` | 跨模型评审修复 |
