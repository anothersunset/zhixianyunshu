# 开发日志：Phase 1 — KB 统一管理

日期：2026-06-24
项目：zhixianyunshu（智迁云枢）
模块：KB 基础设施

---

## 1. 背景

项目有 3 处独立维护的 KB 副本：
- `eval/index_kb.py` — 61 条（最完整）
- `zhiqian/rag/app/pipelines/retriever.py` — 28 条 `_DEMO_DOCS`
- `zhiqian/backend/.../ContextRetrieverAgent.java` — 17 条 mock 回退

新增一条 KB 需改 3 个文件，容易脱节。RAG 重启后 `/ingest` 添加的数据丢失（`_maybe_seed_qdrant` 直接覆盖）。

**目标**：单一真源（`kb/active/*.yaml`），三处消费者统一读取。

---

## 2. 方案设计

```
kb/
  active/
    kb-syntax.yaml         # 语法（17 条）
    kb-functions.yaml      # 函数（25 条）
    kb-types.yaml          # 类型映射（12 条）
    kb-ddl.yaml            # DDL（4 条）
    kb-dml.yaml            # DML（2 条）
    kb-plsql.yaml          # PL/SQL（1 条）
  pending/                 # 自动生成，待人工审核（Phase 3 使用）
  kb_loader.py             # 共享加载器
  cli.py                   # 一次性迁移脚本
```

YAML 格式选型原因：多行字符串原生支持、git diff 友好、Python( PyYAML )和 Java( SnakeYAML )都能读。

每个消费者都增加了回退：YAML 加载失败时使用硬编码的最小 KB 集。

---

## 3. 涉及文件

| Action | File |
|--------|------|
| NEW | `kb/__init__.py` |
| NEW | `kb/kb_loader.py` |
| NEW | `kb/cli.py` |
| NEW | `kb/active/kb-syntax.yaml` |
| NEW | `kb/active/kb-functions.yaml` |
| NEW | `kb/active/kb-types.yaml` |
| NEW | `kb/active/kb-ddl.yaml` |
| NEW | `kb/active/kb-dml.yaml` |
| NEW | `kb/active/kb-plsql.yaml` |
| MODIFY | `eval/index_kb.py` — 硬编码列表→ `from kb.kb_loader import load_all_docs` |
| MODIFY | `zhiqian/rag/app/pipelines/retriever.py` — `_DEMO_DOCS` → `_load_kb_docs()`, `_maybe_seed_qdrant()` 加计数检查 |
| MODIFY | `zhiqian/backend/.../ContextRetrieverAgent.java` — 硬编码 17 条 → 从 YAML 动态加载 + 硬编码回退 |

---

## 4. 验证结果

| 验证项 | 状态 | 结果 |
|--------|------|------|
| YAML 迁移 | ✅ | 61 docs, 6 categories, 2 source dialects |
| kb_loader 加载 | ✅ | 61 docs 一致 |
| index_kb.py 导入 | ✅ | KB_DOCS=61, DEMO_DOCS=0 |
| retriever.py 语法 | ✅ | ast.parse 通过 |
| Java 编译 | ✅ | mvn compile 零错误 |
| RAG 重启数据丢失修复 | ✅ | `_maybe_seed_qdrant()` 加 QdrantClient.count() 检查 |

---

## 5. 经验教训

1. **三处同步是常见的熵增源**。单一大文档（50+ 条）拆成 6 个 YAML 文件后，按 category 修改更方便，不需要在 800 行列表中翻找
2. **回退是必须的**。YAML 加载可能因为路径、权限、格式问题失败。每个消费者保留硬编码回退，确保不会因为 KB 问题导致服务不可用
3. **Java SnakeYAML 已是依赖**（`SpringConfigScanner` 使用），无需额外引入
4. **QdrantClient.count() 是单行修复**。RAG 重启数据丢失的问题，本质是 `_maybe_seed_qdrant` 没检查现有数据量
