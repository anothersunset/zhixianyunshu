# 开发日志：消融实验全流程

日期：2026-06-08 ~ 2026-06-14
项目：zhixianyunshu（智迁云枢）
模块：评测框架

---

## 1. 背景

需要验证 5 种 RAG 检索模式（BM25 / Vector / Vector+Rerank / CRAG / Full）对 SQL 迁移质量的影响，预期 A→E 递进（BM25 < Vector < V+Rerank < CRAG < Full）。

---

## 2. 问题发现

### 2.1 消融实验翻车（翻 3 次）

**第 1 次**：6-agent 流水线（非 fast 模式），C/D/E 因 API 限流全部归零。
**第 2 次**：1 小时跑完，SQL 修复率全组 83.33%，毫无区分度。
**第 3 次**：trace agent 间信息流后才发现根本原因。

### 2.2 根因：信息流断裂

通过 trace 发现 agent 流水线的信息传递问题：
1. `SchemaAnalyzer` 输出 100 字中文总结 → **原始 SQL 在此丢失**
2. `SqlReasoner/SqlPatcher/SqlCritic` 都只看到上一个 agent 的输出，从未见原始 SQL
3. `SqlPatcher` 硬编码 `"MySQL→openGauss"`，忽略了实际 dialect pair

### 2.3 根因：RRF 融合导致 Recall 下降

CRAG/Full 模式的 Recall@5 反而低于 BM25/Vector（0.52-0.58 vs 0.83-0.85）。

- RRF 公式 `score = Σ 1/(k+rank_i)`，k=60 时过于平滑
- 在 BM25 rank=2、Vector rank=1 但 Sparse rank=36 的文档，RRF 融合后反而被淘汰
- 某些在所有 channel 表现中等的文档，击败了在某些 channel 优秀但其他 channel 差的文档

**示例**（mysql-og-001: IFNULL → COALESCE）：
```
BM25: kb-func-ifnull rank 2 ✓
Vector: kb-func-ifnull rank 1 ✓
Sparse: kb-func-ifnull rank 36 ✗
RRF 融合后：kb-func-ifnull rank 6 ✗（被 kb-func-year 等超越）
```

---

## 3. 解决方案

### 3.1 放弃 6-agent → 用 fast 模式

结论：信息流修复成本太高，直接用 fast 模式（单 LLM 调用）更稳定可控。

### 3.2 预检流程制度化

从这次翻车提炼出 `preflight-check.md`：
1. 明确预期结果（A<B<C<D<E 递进）
2. 逆向审计关键路径（trace 信息流）
3. 识别潜在漏洞（agent 间信息丢失、硬编码值冲突）
4. 小范围验证后再全量（先 1-2 case）

### 3.3 RRF 加权融合

修改 `rrf.py` 添加 `weights` 参数支持加权 RRF：
```python
# 动态权重：提高 BM25/Vector 的权重，降低 Sparse 权重
weights = (0.5, 0.5, 0.0)  # 完全忽略 sparse
```

### 3.4 Checkpoint 增量保存修复

**问题**：消融实验中断后 checkpoint 文件为空或只有部分数据。
**根因**：`on_progress` 回调在 `evaluate()` 内部静默失败。
**修复**：改为直接在 `evaluate()` 内部每 case 写文件 + tmp+rename 原子替换。

### 3.5 反进程竞争机制

**问题**：多个 quick_ablation 实例同时运行，互相覆盖 checkpoint。
**修复**：PID-based 进程锁（`.ablation.lock`），支持 `--force` 强制覆盖。

---

## 4. 最终结果

### 全量消融 (2026-06-14, 84 cases)

| 组别 | Recall@5 | SQL修复率 | 报告准确率 |
|------|----------|----------|-----------|
| A - BM25 | 0.5899 | 0.9881 | 0.6756 |
| B - Vector | 0.5833 | 0.9643 | 0.6994 |
| C - Vector+Rerank | **0.6842** | **0.9881** | 0.7034 |
| D - CRAG | 0.6721 | 0.9762 | **0.7212** |
| E - Full (GraphRAG) | 0.6721 | 0.9881 | 0.7153 |

**关键发现**：
- C (Vector+Rerank) Recall@5 最高（+9.4pp vs BM25）
- D (CRAG) 报告准确率最高（+4.6pp vs BM25）
- **A→E 不单调**：GraphRAG 引入噪声，Full 低于 Vector+Rerank
- **最优配置：Vector+Rerank**（消融实验核心结论）

---

## 5. 经验教训

1. **跑实验前先 trace 信息流**：6-agent 流水线的问题完全可以在启动前发现
2. **不求全量求单调**：先跑 10-case 快速消融验证趋势，再全量
3. **Checkpoint 要原子写入**：tmp+rename 是必须的，回调模式不可靠
4. **RRF k 值敏感**：k=60 过于平滑，k=10-20 在 recall 和去噪间平衡更好
5. **GraphRAG 静态边构建收益有限**：边数 298→103(-65%) 仅 +1pp，需要 LLM 语义相关性判断
