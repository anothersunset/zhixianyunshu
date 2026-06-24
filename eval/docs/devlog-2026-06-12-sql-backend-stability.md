# 开发日志：SQL 等价比较进化 + 后端稳定性修复

日期：2026-06-12 ~ 2026-06-22
项目：zhixianyunshu（智迁云枢）
模块：评测指标 + 后端韧性

---

## 1. SQL 等价比较进化

### 1.1 背景

评测时需要判断 LLM 输出的 SQL 和金标是否等价。初始使用 sqlglot 严格模式，大量语义等价但写法不同的 SQL 被判 FAIL。

### 1.2 迭代过程

| 阶段 | 方法 | SQL 修复率 |
|------|------|-----------|
| v1 | 严格 sqlglot 比较 | 0.3-0.5 |
| v2 | 4 级：strict → 跨方言 → 模糊类型 → token≥0.85 | 0.6-0.7 |
| v3 | 5 级：+ CTE 名称归一化 | 0.7-0.8 |
| v4 | + enum 类型名归一化 | 0.96-0.99 |
| v5 | + FETCH FIRST→LIMIT 归一化 + INTERVAL 归一化 | 0.80 (PARROT) |

### 1.3 5 级等价判断

```python
# Level 1: 严格 — 双方用目标方言 parse
# Level 2: 跨方言 — pred 用源方言 parse（CONCAT→||, NVL→COALESCE）
# Level 3: 模糊 — 类型精度、VARCHAR 长度归一化
# Level 4: CTE 归一化 — WITH name AS → _cte_0 AS
# Level 5: Token 相似度 ≥ 0.92
```

### 1.4 Enum 类型名归一化（关键修复）

**问题**：`CREATE TYPE u_status AS ENUM` vs `CREATE TYPE u_status_type AS ENUM` 导致误判。

**修复**：`_normalize_enum_type_names()` 将 enum 类型名统一为 `_enum_type_`。
```python
enum_names = re.findall(r"\bcreate\s+type\s+(\w+)\s+as\s+enum\b", s)
# 替换所有出现的类型名 → _enum_type_
```

**注意**：必须在多语句拆分前执行，否则 sqlglot 无法解析 `_enum_type_` 语法。

**效果**：SQL 修复率 +2.4pp（BM25: 0.964→0.988），修复 7 个 case。

---

## 2. 后端稳定性三层修复

### 2.1 问题

oracle-pg 跑评测时 500 错误率极高（10+ 次/30 case），严重影响结果可信度。

### 2.2 根因分析

| 层级 | 问题 | 表现 |
|------|------|------|
| ① LLM API | DNS 解析失败 (UnknownHostException) | `IllegalStateException` → 500 |
| ② RAG 连接 | Connection refused 无重试 | 一次失败即永久失败 |
| ③ RAG 超时 | 读超时 30s 过短 | 大文档检索时频繁超时 |

### 2.3 修复

| 问题 | 修复 |
|------|------|
| LLM API 失败 | `MigrationEvalController` 两个 `generateMigration*` 方法加 try-catch，失败返回 `parseFallback` |
| RAG 连接拒绝 | `ContextRetrieverAgent` Connection refused 加 3s 重试一次 |
| RAG 超时 | 读超时 30s→60s |

**效果**：零 500 错误。

---

## 3. Checkpoint 多进程覆盖事故

### 3.1 问题

配对跑脚本、补齐脚本、cron 监控同时读写 `per_case_all_fast.json`，后写覆盖先写，导致已完成 case 数据丢失。

### 3.2 根因

同一 checkpoint 文件被多个进程共享写入，无互斥机制。

### 3.3 修复

1. 同一 checkpoint 只允许一个写入进程
2. 启动新脚本前检查残留进程
3. 跑完后立即验证 checkpoint 完整性
4. 写入用 tmp+rename 原子操作

详见 `process-guardrails.md` 第 5 条和第 7 条。

---

## 4. 经验教训

1. **SQL 比较不是简单的字符串匹配**：需要从严格→跨方言→模糊→CTE→token 五级退化
2. **Enum 类型名是最隐蔽的误判源**：不同的命名习惯导致的 FAIL 和模型质量无关
3. **LLM API 不可靠是常态**：必须 try-catch 降级，不能让它传播异常到 500
4. **Checkpoint 是评测的生命线**：多进程覆盖可以无声地毁掉数小时的实验结果
