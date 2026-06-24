# 开发日志：Phase 2 — 多方言扩展框架

日期：2026-06-24
项目：zhixianyunshu（智迁云枢）
模块：方言配置 + Java 数据驱动

---

## 1. 背景

项目仅支持 Oracle/MySQL→PG 两种方言，添加新方言需改 6-8 个文件：
- `TranslationRecipeRegistry.java` — 特征注册表（8 recipes + 22 simple = 30 oracle features）
- `DialectFeatureScanner.java` — PG_STANDARD 白名单（~100 硬编码）
- `MigrationEvalController.java` — 复杂度关键词（ORACLE_KEYWORDS + COMPLEX_KEYWORDS）
- `kb/active/kb-*.yaml` — KB 文档

**目标**：新方言只需添加 `kb/active/dialects/<name>.yaml`，不改任何 Java/Python 代码。

---

## 2. 方案设计

### 2.1 方言 YAML schema

```yaml
name: sqlserver
pairs: ["sqlserver->postgresql", "sqlserver->opengauss"]
complexity_keywords: ["top", "getdate(", ...]
standard_whitelist: ["ABS", "TRIM", ...]  # 方言特有的 PG 兼容函数
features:
  - keyword: TOP
    mapping: LIMIT
    category: syntax
    is_recipe: true
    construct_name: SELECT TOP → LIMIT
    few_shot_source: ...
    few_shot_target: ...
    step_by_step: ...
    pitfalls: [...]
```

### 2.2 Java 三组件改造

| 组件 | 原状态 | 改造后 |
|------|--------|--------|
| TranslationRecipeRegistry | `ALL` 硬编码 46 条 | YAML 加载→与硬编码合并（YAML 优先） |
| DialectFeatureScanner | `PG_STANDARD` 硬编码 ~100 条 | 基础白名单 + per-dialect `standard_whitelist` 扩展 |
| MigrationEvalController | `ORACLE_KEYWORDS` + `COMPLEX_KEYWORDS` 硬编码 | `DIALECT_COMPLEXITY` 从 YAML 加载，自动合并到 `COMPLEX_KEYWORDS` |

统一的目录解析逻辑（从 `ContextRetrieverAgent.java` 复用模式）：
```java
private static Path resolveDialectsDir() {
    // 1. 系统属性 kb.yaml.path
    // 2. 从 user.dir 向上 5 层查找 kb/active/dialects/
    // 3. 回退到 kb/active/dialects/
}
```

所有三处都保留硬编码回退，YAML 加载失败不影响系统可用性。

### 2.3 生成脚本

`kb/gen_dialects.py` 从现有 Java 硬编码数据生成 `oracle.yaml`（30 features）和 `mysql.yaml`（16 features）。可直接编辑 YAML 替代修改 Java 代码。

---

## 3. 涉及文件

| Action | File |
|--------|------|
| NEW | `kb/gen_dialects.py` |
| NEW | `kb/active/dialects/oracle.yaml`（30 features） |
| NEW | `kb/active/dialects/mysql.yaml`（16 features） |
| NEW | `kb/active/dialects/sqlserver.yaml`（12 features，验证用） |
| MODIFY | `TranslationRecipeRegistry.java` — 加 `loadFromYaml()` + `buildAll()` |
| MODIFY | `DialectFeatureScanner.java` — 加 `DIALECT_WHITELIST_ADDITIONS` |
| MODIFY | `MigrationEvalController.java` — 加 `DIALECT_COMPLEXITY` |

---

## 4. 验证结果

| 验证项 | 状态 | 结果 |
|--------|------|------|
| YAML 生成 | ✅ | oracle 30, mysql 16, sqlserver 12 features |
| kb_loader 加载 | ✅ | 3 方言均正确加载 |
| Java 编译 | ✅ | mvn compile 零错误 |
| 零代码验证 | ✅ | 仅添加 sqlserver.yaml，扫描器检测到 TOP/GETDATE/ISNULL |
| Python 模拟扫描 | ✅ | `SELECT TOP 10 ... GETDATE() ... ISNULL(...)` → 3 个特征检测 |

---

## 5. 经验教训

1. **YAML 是 Java/Python 的天然桥梁**。SnakeYAML 已在 classpath（SpringConfigScanner 使用），Python 用 PyYAML。无需额外依赖。
2. **回退是零风险的前提**。YAML 加载失败时所有 3 个组件回退到硬编码，不会因为文件路径/格式问题导致服务不可用。
3. **静态初始化顺序很重要**。Java static final 字段按声明顺序初始化，`YAML_FEATURES` 必须在 `ALL` 之前，`HARDCODED` 必须在 `YAML_FEATURES` 之前但可以引用更早定义的常量。
4. **复杂度关键词的合并策略**。`COMPLEX_KEYWORDS` = 通用标记（"with ", "recursive"）+ 所有方言的 `complexity_keywords` 并集。这样新方言的复杂度关键词自动流动到评分逻辑中。
