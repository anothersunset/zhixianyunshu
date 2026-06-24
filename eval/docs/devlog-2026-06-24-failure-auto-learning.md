# 开发日志：Phase 3 — 失败模式自动学习

日期：2026-06-24
项目：zhixianyunshu（智迁云枢）
模块：知识积累回路

---

## 1. 背景

评测发现 LLM 反复在 MONTHS_BETWEEN/CONNECT BY 等模式失败，但无任何回写机制将失败模式转化为 KB 改进。Phase 1 统一了 KB YAML 体系，Phase 2 实现了多方言数据驱动，Phase 3 闭合反馈回路：评测失败 → 自动聚类 → LLM 生成 KB 补充 → 人工审批 → 部署验证。

**目标**：让每一次评测失败都转化为可积累的知识。

---

## 2. 方案设计

```
eval 全量消融
      ↓
failure_analyzer.py         ← 读取 checkpoint JSON + 数据集 JSONL
      ↓                      ← 提取方言特征（Python 版 DialectFeatureScanner Phase 1）
      ↓                      ← 按特征聚类 → 排序（fail_rate DESC, fail_count DESC）
failure_analysis.json
      ↓
      ├─→ kb_generator.py    ← 对 critical/severe 聚类 → LLM 生成 KB 文档
      │                       ← 输出到 kb/pending/kb-auto-*.yaml
      │
      └─→ recipe_suggester.py ← 对 fail_rate≥0.8 且 ≥3 modes → LLM 生成完整 Recipe
                                ← 输出到 kb/pending/recipes/recipe-*.yaml
      ↓
人工审核（mv kb/pending/*.yaml → kb/active/）
      ↓
validate_learning.py         ← --approve: 部署 + 备份 + RAG re-ingest
                             ← --retest: 仅重跑失败 case → 对比 sql_ok
                             ← --rollback: 回退到备份
```

### 安全闸门

| 阶段 | 闸门 | 说明 |
|------|------|------|
| 分析 | `kb/pending/` 只写不读 | 绝不自用自产 |
| 生成 | 仅 dry-run 预览 | 默认不调 LLM |
| 部署 | `--approve` 显式确认 | 部署前备份 kb/active/ 到 kb/backups/ |
| 验证 | 仅重跑失败 case | 不干扰已通过的 case |
| 回退 | `--rollback` | 从备份恢复，移回 pending |

---

## 3. 涉及文件

| Action | File | 说明 |
|--------|------|------|
| NEW | `eval/failure_analyzer.py` | 失败聚类器：checkpoint + dataset → 特征提取 → 聚类排序 |
| NEW | `eval/kb_generator.py` | KB 补充生成器：聚类 → LLM prompt → YAML doc |
| NEW | `eval/recipe_suggester.py` | Recipe 生成器：高失败聚类 → LLM → 完整 few-shot recipe |
| NEW | `eval/validate_learning.py` | 学习验证器：预览/部署/回退/RAG 索引/重测 |
| NEW | `kb/pending/.gitkeep` | 待审核目录 |
| NEW | `kb/pending/recipes/` | 待审核配方目录 |

### 依赖关系

```
failure_analyzer.py
  ├── 依赖 kb/kb_loader.py (load_dialect_config)
  ├── 读取 eval/results/per_case_all_fast.json
  └── 读取 eval/datasets/*.jsonl

kb_generator.py
  ├── 依赖 failure_analysis.json
  └── 需要 LLM_API_KEY + LLM_BASE_URL（生成时）

recipe_suggester.py
  ├── 依赖 failure_analysis.json
  └── 需要 LLM_API_KEY

validate_learning.py
  ├── 依赖 kb/kb_loader.py（re-ingest）
  ├── 需要 RAG 服务运行中（:8001）
  └── 需要迁移后端运行中（:8080，retest 时）
```

---

## 4. 验证结果

| 验证项 | 状态 | 结果 |
|--------|------|------|
| 语法检查 | ✅ | 4 个 .py 文件 ast.parse 通过 |
| failure_analyzer 运行 | ✅ | 19 clusters，3 critical（MONTHS_BETWEEN/CONNECT BY/START WITH 各 100% failure） |
| kb_generator dry-run | ✅ | 8/19 clusters eligible (fail_rate ≥ 50%) |
| recipe_suggester dry-run | ✅ | 3/19 clusters eligible (fail_rate ≥ 80% & ≥ 3 modes) |
| validate_learning preview | ✅ | `kb/pending/` 为空，就绪待用 |

### 聚类 Top 5

| 关键词 | fail_rate | fail_count | 影响 modes |
|--------|-----------|------------|------------|
| MONTHS_BETWEEN( | 100% | 5 | ALL 5 modes |
| CONNECT BY | 100% | 5 | ALL 5 modes |
| START WITH | 100% | 5 | ALL 5 modes |
| ENUM( | 67% | 10 | 4 modes |
| BIT( | 60% | 6 | 5 modes |

---

## 5. 使用流程

```bash
# Step 1: 跑完消融实验后分析失败模式
python -m eval.failure_analyzer \
    --checkpoint eval/results/per_case_all_fast.json \
    --dataset eval/datasets

# Step 2: 预览将要生成的文档（dry-run）
python -m eval.kb_generator --dry-run
python -m eval.recipe_suggester --dry-run

# Step 3: 设置 LLM API Key 后生成（写 kb/pending/）
export LLM_API_KEY=your-key
export LLM_BASE_URL=https://api.deepseek.com/v1
python -m eval.kb_generator
python -m eval.recipe_suggester

# Step 4: 人工审核 kb/pending/ 中的文件
# 审核通过后部署
python -m eval.validate_learning --preview
python -m eval.validate_learning --approve --retest

# 如果效果不好，回退
python -m eval.validate_learning --rollback
```

---

## 6. 经验教训

1. **Python 版特征提取必须与 Java 版保持一致**。`_matches()` 函数的每个分支都对照 `DialectFeatureScanner.matches()` 实现，特别是 "from dual" / "merge into" 需要 `re.sub(r'\s+', ' ', lower_sql)` 做空格归一化。
2. **fail_rate 计算要准确**。分母 = case × mode 中出现该特征的次数（不是 case 数），这样 CONNECT BY 一个 case 出现 5 次（5 个 mode），fail_rate 才正确等于 100%。
3. **样本数量限制**。每个特征聚类最多保留 10 个失败样本，避免 `failure_analysis.json` 过大。
4. **安全闸门是反馈回路的核心**。不设闸门的自动学习 = 自我退化。`kb/pending/` 分隔线确保人类始终在回路中。
5. **dry-run 是 LLM 调用前的必须步骤**。避免因 prompt 错误浪费 API 调用次数。
