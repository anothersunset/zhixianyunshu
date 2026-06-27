# 失败学习闭环 — 通用框架（从 SQL 方言迁移到数学建模）

## 概述

一个 **5 阶段自动化管道**，从评测中发现失败模式，用 LLM 生成针对性知识，注入回求解器，验证改进效果。

核心思想：**从真实失败中学习，而非从理论出发预设知识。**

已在 SQL 方言迁移项目中完整验证（38/38 失败 case 修复，100% 改善率）。

---

## 一、三层知识模型

任何求解问题都可以把领域知识拆成三层：

```
Layer 1: 通用知识文档 (KB Docs)
  作用: LLM 做背景参考，语义检索匹配
  精度: 粗 → 提供思路方向
  例子: "线性规划的标准形式"、"大M法的原理"、"约束松弛的常见方法"

Layer 2: 翻译配方 (Recipes)
  作用: 具体的转换步骤 + few-shot 示例 + 常见错误清单
  精度: 细 → 提供精确的"源→目标"映射
  例子: "绝对值目标函数 → 引入辅助变量线性化"、"分段函数 → 0-1变量转化"

Layer 3: 问题特征库 (Features)
  作用: 扫描器识别问题类型，触发对应配方
  精度: 触发器 → 决定注入哪些知识
  例子: "问题包含 max/min 函数"、"出现二次项"、"含0-1变量"
```

对应关系：

| 原项目（SQL迁移） | 数学建模 |
|------------------|---------|
| kb/active/kb-*.yaml | 通用建模知识库 |
| dialects/*.yaml features | 问题模式特征库 |
| recipe (few_shot + step_by_step + pitfalls) | 转换配方 |
| source_dialect → target_dialect | 自然语言 → 数学模型 / 非标准型 → 标准型 |

---

## 二、5 阶段管道

```
评测结果 checkpoint
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ Stage 1: 失败聚类器 (Failure Analyzer)                   │
│                                                         │
│ 输入: 评测结果 (case_id → mode → {ok, output, error})    │
│       + 问题数据集 (case_id → 原始问题描述)              │
│                                                         │
│ 核心算法:                                                │
│   for each failed case:                                 │
│     features = 从原始问题中提取特征(特征库)              │
│     for each (mode, result):                            │
│       if not result.ok:                                 │
│         每个特征都计为相关失败                           │
│         clusters[feature].fail_count++                  │
│         clusters[feature].modes.add(mode)               │
│         clusters[feature].samples.append(case_info)     │
│                                                         │
│ 排序: fail_rate DESC, fail_count DESC                   │
│ 分级:                                                    │
│   critical: fail_rate >= 80% AND 影响 >= 3 个求解模式   │
│   severe:   fail_rate >= 50%                            │
│   moderate: 其余                                        │
│                                                         │
│ 输出: failure_analysis.json                             │
│   - 每个聚类含: keyword, mapping, fail_rate,             │
│     fail_count, failing_modes, sample_cases (≤5个)      │
│   - summary: n_clusters, n_critical, suggested_actions  │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌─────────────────────┐   ┌──────────────────────────┐
│ Stage 2: KB 生成器  │   │ Stage 3: 配方生成器       │
│                     │   │                          │
│ 条件: fail_rate     │   │ 条件: fail_rate >= 0.8   │
│       >= 0.5        │   │       AND >= 3 modes     │
│                     │   │                          │
│ 生成: 通用知识条目  │   │ 生成: 精确转换配方       │
│  - 概念解释         │   │  - few_shot 输入→输出    │
│  - 常见错误         │   │  - step_by_step 步骤     │
│  - 正确做法         │   │  - pitfalls "不要做X"    │
│                     │   │                          │
│ LLM 调用:            │   │ LLM 调用:               │
│  优先 /chat 代理    │   │  优先 /chat 代理         │
│  回退 直连 API      │   │  回退 直连 API           │
│                     │   │                          │
│ 输出:               │   │ 输出:                    │
│  kb/pending/        │   │  kb/pending/recipes/     │
│  auto-<feature>.yaml│   │  recipe-<feature>.yaml   │
└─────────────────────┘   └──────────────────────────┘
          │                         │
          └──────────┬──────────────┘
                     │
┌────────────────────▼───────────────────────────────┐
│ Stage 4: 学习验证器 (Validate Learning)             │
│                                                     │
│ 职责: 人工闸门 + 一键部署 + 结果验证                 │
│                                                     │
│   python -m eval.validate_learning --preview        │
│     → 预览 LLM 生成的所有内容                       │
│                                                     │
│   python -m eval.validate_learning --approve --retest│
│     → ① 备份 active/ → backups/时间戳/              │
│     → ② KB文档 pending/ → active/                   │
│     → ③ 配方合并到 dialects/*.yaml                  │
│     → ④ 写部署日志 deploy_log.json                   │
│     → ⑤ 重新索引向量库                              │
│     → ⑥ 只重跑历史上失败的 case                      │
│     → ⑦ 对比 sql_ok 变化                            │
│                                                     │
│   python -m eval.validate_learning --rollback       │
│     → 从备份恢复，一键回退到部署前状态               │
│                                                     │
│ 安全闸门:                                            │
│   - LLM 只能写入 pending/，绝不自动写入 active/      │
│   - 部署必须显式传 --approve 标志                     │
│   - 每次部署前自动完整备份                           │
│   - retest 只跑失败 case，不浪费算力                 │
└────────────────────┬──────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────┐
│ Stage 5: 双通道知识注入                              │
│                                                     │
│ 通道 A — 离线直读 (不依赖外部服务):                   │
│   求解器启动时加载 active/ 和 dialects/ YAML        │
│   即使向量库/API 宕机，核心知识依然可用              │
│                                                     │
│ 通道 B — 在线 RAG 检索 (语义覆盖):                   │
│   知识库 → Embedding 向量化 → 向量数据库             │
│   BM25 + 向量 + Reranker 混合检索                    │
│   覆盖未显式注册为特征的模式                         │
└─────────────────────────────────────────────────────┘
```

---

## 三、迁移到数学建模的适配清单

### 零改动复用的模块

| 文件 | 职责 | 改动 |
|------|------|------|
| `kb/kb_loader.py` | 通用 YAML 加载器 | 零 |
| `eval/validate_learning.py` | 审核/部署/回退/重测 | 零 |
| `eval/failure_analyzer.py` | 聚类算法 + 排序 + 分级 | 零（仅改特征提取函数） |
| `eval/kb_generator.py` | LLM 调用 + YAML 输出 | 零（仅改 prompt） |
| `eval/recipe_suggester.py` | LLM 调用 + YAML 输出 | 零（仅改 prompt） |
| 安全闸门机制 | pending↔active 分离 | 零 |
| 备份/回退机制 | backups/ + deploy_log.json | 零 |

### 需要重写的模块（核心差异）

#### 1. 特征提取器

SQL 用关键词匹配，数学建模需要模式匹配：

```python
# 原: 精确关键词
def _matches(keyword: str, text: str) -> bool:
    if keyword == "connect by":
        return "connect by" in text
    if keyword.endswith("("):
        return keyword in text  # 函数名匹配

# 新: 数学模式正则
MATH_PATTERNS = {
    "nonlinear_obj": {
        "regex": r"(minimize|maximize).*?(x\d*\s*\*\s*x|quadratic|squared|²)",
        "mapping": "线性化或使用NLP求解器",
        "category": "objective",
    },
    "absolute_value": {
        "regex": r"\|.*\|",
        "mapping": "引入辅助变量: |x| → t, 约束 x≤t, -x≤t",
        "category": "constraint",
    },
    "piecewise_cost": {
        "regex": r"(if.*≤|分段|piecewise|tiered)",
        "mapping": "引入0-1变量 + big-M分段线性化",
        "category": "constraint",
    },
    "multi_objective": {
        "regex": r"(同时.*最小|同时.*最大|多目标|pareto)",
        "mapping": "加权和法 或 ε-约束法",
        "category": "objective",
    },
    "logical_or": {
        "regex": r"(或|x\s*=\s*0\s*或\s*\d+)",
        "mapping": "引入0-1变量: 每个条件一个指示变量",
        "category": "constraint",
    },
    "max_min_func": {
        "regex": r"\b(max|min)\s*\(",
        "mapping": "max/min → 引入辅助变量 + 不等式约束",
        "category": "function",
    },
    "integer_var": {
        "regex": r"(整数|integer|x_i\s*∈\s*Z|x_i\s*∈\s*\{0,1\})",
        "mapping": "MIP求解器(Gurobi/CPLEX等)",
        "category": "variable",
    },
    "stochastic": {
        "regex": r"(期望|E\[|方差|stochastic|scenario|不确定)",
        "mapping": "场景树 或 机会约束规划",
        "category": "structure",
    },
}
```

#### 2. 知识 YAML 结构

```yaml
# kb/active/features/linearization.yaml
name: 线性化
pairs: ["自然语言→数学规划标准型", "非标准型→标准型"]
complexity_keywords: ["绝对值", "分段", "max/min", "二次", "逻辑或"]
features:
  - keyword: "绝对值目标"
    mapping: "引入辅助变量t, 约束: x≤t, -x≤t, min t"
    category: objective
    is_recipe: true
    construct_name: "绝对值目标函数线性化"
    few_shot_source: |
      minimize |x - 5| + |y - 3|
    few_shot_target: |
      minimize t1 + t2
      subject to:
        x - 5 ≤ t1
        -(x - 5) ≤ t1
        y - 3 ≤ t2
        -(y - 3) ≤ t2
    step_by_step: |
      1. 对每个绝对值项引入辅助变量ti
      2. 目标函数用ti替代绝对值
      3. 添加两个不等式: 内部表达式 ≤ ti, -(内部表达式) ≤ ti
      4. 所有ti在目标中为非负(最小化保证)
    pitfalls:
      - "DO NOT 对最小化直接用x-5=t; 这等价于|x-5| 但要求等式约束"
      - "DO NOT 忘记ti≥0, 虽然最小化目标通常自动保证"
      - "DO NOT 在最大化问题中用同样方法, 辅助变量方向需反转"

  - keyword: "分段函数"
    mapping: "SOS2 或 big-M 0-1变量线性化"
    category: constraint
    is_recipe: true
    # ...
```

#### 3. LLM Prompt 模板

```python
SYSTEM_PROMPT = "You are a senior operations research and mathematical modeling expert."

KB_GENERATOR_PROMPT = """Generate a KB documentation entry for a recurring failure pattern in mathematical modeling.

PATTERN: {keyword} → {mapping}
FAILURE RATE: {fail_rate}
FAILED EXAMPLES:
{sample_text}

TASK: Write a concise KB document (200-400 words) that explains:
1. What the source formulation means
2. The correct standard form equivalent
3. Common pitfalls when converting
4. A correct source→target example
"""

RECIPE_PROMPT = """Generate a complete modeling recipe that will be injected as a few-shot example.

The recipe MUST include:
1. A clear few_shot_source (the original non-standard formulation)
2. A CORRECT few_shot_target (the correct standard form)
3. Step-by-step conversion guide (numbered, specific)
4. Common pitfalls that solvers/LLMs make when converting this

Pitfalls should describe the WRONG behavior and say DO NOT do it.
"""
```

### 建议的文件结构

```
project/
  kb/
    active/
      kb-linear-programming.yaml        # 线性规划知识
      kb-integer-programming.yaml       # 整数规划
      kb-convex-optimization.yaml       # 凸优化
      kb-robust-optimization.yaml       # 鲁棒优化
      features/
        linearization.yaml              # 线性化特征
        standardization.yaml            # 标准化特征
        decomposition.yaml              # 分解方法特征
    pending/                            # LLM生成, 待人工审核
      .gitkeep
      recipes/
        .gitkeep
    backups/                            # 部署前自动备份
    deploy_log.json                     # 部署审计日志
  eval/
    failure_analyzer.py                 # 聚类器（复用）
    kb_generator.py                     # KB生成器（复用，改prompt）
    recipe_suggester.py                 # 配方生成器（复用，改prompt）
    validate_learning.py               # 验证器（零改动复用）
    datasets/                           # 测试用例
    results/                            # 评测结果
```

---

## 四、闭环的六个核心原则

| 原则 | 说明 |
|------|------|
| **知识外化** | 领域知识从代码中剥离到 YAML，人与 LLM 均可读写 |
| **失败驱动** | 不从理论出发预设知识，从求解器真实失败中提炼 |
| **生成不部署** | LLM 输出永远进 pending/，人工确认后才进 active/ |
| **双通道冗余** | 离线通道（直读YAML）不依赖外部服务；在线通道（RAG）提供语义覆盖 |
| **可回退性** | 每次部署前完整备份，改进无效一键回退 |
| **只测失败者** | retest 只跑历史上失败的 case，不浪费算力 |

---

## 五、实际验证结果

SQL 方言迁移项目（84 cases × 5 modes = 420 个结果）：

```
failure_analyzer: 19 clusters → 3 critical + 5 severe + 11 moderate
kb_generator:     8 KB 文档 (fail_rate >= 50%)
recipe_suggester: 3 配方 (fail_rate >= 80% AND >= 3 modes)
validate_learning: --approve --retest
  → 38/38 previously-failed case×mode combinations IMPROVED (100%)
  → 覆盖: MONTHS_BETWEEN, CONNECT BY, START WITH, ENUM, BIT, REGEXP_SUBSTR 等全部失败模式
```

---

## 六、闭环运行节奏

```
[定期/每次实验后]
  python -m eval.failure_analyzer
    → 检查 failure_analysis.json 中的 critical clusters

[如果 critical > 0]
  python -m eval.kb_generator --min-fail-rate 0.5
  python -m eval.recipe_suggester
    → 生成 KB 文档 + 配方到 kb/pending/

[人工审核 kb/pending/ 内容]
  python -m eval.validate_learning --preview
    → 检查 LLM 生成质量

[审批通过]
  python -m eval.validate_learning --approve --retest
    → 部署 + 重测 + 验证改进

[改进无效则回退]
  python -m eval.validate_learning --rollback
    → 恢复部署前状态
```

---

## 七、关键设计约束

1. **特征提取必须与求解器内的一致**：analyzer 中提取特征的方法必须与求解器识别特征的方法完全一致，否则聚类得出的失败模式无法对准求解器的知识注入点。

2. **deploy_log.json 必须正确维护**：回退依赖部署日志，任何时候都不要手动删除或修改它。

3. **同一次部署只运行一个 validate_learning 进程**：多进程同时读写 active/ 和 deploy_log.json 会导致数据损坏。

4. **LLM 生成的配方质量需要人工把关**：critical cluster 的 3 个样本会注入 prompt 作为失败示例，LLM 生成的 pitfalls 通常准确，但 few_shot 示例需要人工验证数学正确性。
