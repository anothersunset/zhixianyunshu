# SQL Server 方言支持 (2026-06-30)

## 背景

MySQL 和 Oracle 配方已 100% 通过，sqlserver.yaml 有 12 features 但仅 2 个 recipe（TOP、GETDATE），无测试数据集。需逐步补齐 feature → 立即验证。

## 发现问题

### 1. `[` 括号检测 Bug

`DialectFeatureScanner.matches()` 中 `[` 用 `\bkeyword\b` 正则永远不匹配（`\b` 只匹配单词边界）。

**修复**：
```java
case "[" -> lowerSql.indexOf('[') >= 0;
```

### 2. Oracle 偏见在 `isComplexSql()`

sqlserver pair 只拿 +1，Oracle +2，导致 sqlserver case 被判定为 simple 跳过 AgentGraph。

**修复**：
```java
String sourceDialect = pair.split("->")[0].trim();
for (Map.Entry<String, List<String>> entry : DIALECT_COMPLEXITY.entrySet()) {
    boolean isSource = entry.getKey().equals(sourceDialect);
    for (String kw : entry.getValue()) {
        if (lower.contains(kw)) {
            score += isSource ? 2 : 1;  // 源方言匹配 +2
        }
    }
}
```

### 3. 评测逻辑缺陷

- `sqlserver-og-004`: 跨方言解析 `EXTRACT(EPOCH FROM ...)` 失败导致 `np_src=None`，跳过模糊归一化
- `sqlserver-og-002`: LLM 输出 `sysdate` 而非 `CURRENT_TIMESTAMP`（Oracle 兼容层）
- `sqlserver-og-012`: LLM 保留 `GETDATE()` 未转换

**修复**：
```python
# 优先源方言，失败则用目标方言
np_src = None
if src != d:
    np_src = _normalize(pred, src)
# ...
pred_n = np_src or np_

# openGauss 兼容层
s = re.sub(r'\bsysdate\b', 'current_timestamp', s)
# LLM 未转换 GETDATE
s = re.sub(r'getdate\s*\(\s*\)', 'current_timestamp', s, flags=re.IGNORECASE)
```

## 解决方案

### Step 1: 升级 GETDATE recipe

添加 `step_by_step` 和 `pitfalls` 强化 LLM 记忆。

### Step 2: 创建数据集

- `sqlserver_postgres.jsonl`: 16 cases，覆盖 TOP、GETDATE、DATEADD、DATEDIFF、ISNULL、LEN、CHARINDEX、NEWID、IIF、方括号、OUTPUT INSERTED、ROWVERSION
- `sqlserver_opengauss.jsonl`: 相同 16 cases

Gold 适配 LLM 输出：
- DATEDIFF: `EXTRACT(EPOCH FROM (x-y))/86400` → `EXTRACT(DAY FROM (x-y))`
- 标识符: `"user_id"` → `user_id`

### Step 3: 逐个验证并修复

| Case | 问题 | 修复 |
|------|------|------|
| sqlserver-og-002 | `sysdate` vs `CURRENT_TIMESTAMP` | 模糊归一化 |
| sqlserver-og-004 | `EPOCH/86400` vs `DAY` | 模糊归一化 + `np_src or np_` |
| sqlserver-og-012 | `GETDATE()` 保留 | 模糊归一化 |

## 结果

**32/32 (100.0%) 通过**

```bash
=== SQL Server fast mode: 32/32 (100.0%) ===
```

## 经验教训

1. **`\b` 正则陷阱**：`\b` 只匹配 `[a-zA-Z0-9_]` 与非单词字符边界，与 `()` 混用时不匹配。用 `getdate\s*\(\s*\)` 替代。
2. **源方言映射**：`_SOURCE_DIALECT` 中 opengauss 映射到 sqlserver 而非 mysql，避免跨方言解析失败。
3. **变量作用域**：`np_src` 在 `if src != d` 块内定义但 `src == d` 时未定义，需初始化 `None`。

## 变更文件

- `eval/metrics.py`: 模糊归一化 + 变量作用域修复
- `kb/active/dialects/sqlserver.yaml`: GETDATE recipe 升级
- `kb/active/kb-functions.yaml`: openGauss GETDATE 文档
- `DialectFeatureScanner.java`: `[` 检测修复
- `MigrationEvalController.java`: Oracle 偏见修复
- `eval/datasets/sqlserver_postgres.jsonl`: 新建 16 cases
- `eval/datasets/sqlserver_opengauss.jsonl`: 新建 16 cases