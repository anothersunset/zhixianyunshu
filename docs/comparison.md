# 同类产品对比 · 顶层概览

> 详细表与选型决策看 [`zhiqian/docs/comparison.md`](../zhiqian/docs/comparison.md)。

## 6 维 × 5 商用产品

| 维度 | **智迁云枢** | AWS DMS / SCT | Oracle GoldenGate | Striim | Aiven Migrate | Fivetran |
| --- | --- | --- | --- | --- | --- | --- |
| LLM 语义迁移 | ✅ 6-Agent DAG（待真实评测量化） | ❌ 规则 | ❌ 规则 | ⚠️ 部分 | ❌ | ❌ |
| GraphRAG / CKG 跨表推理 | ✅ 轻量图实现（待多跳评测） | ❌ | ❌ | ❌ | ❌ | ❌ |
| CDC 增量 | ✅ Debezium 3.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 供应链闭环 | ✅ SBOM+Cosign | ⚠️ 部分 | ❌ | ❌ | ⚠️ | ⚠️ |
| MCP / A2A | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 本地便携（离线 demo） | ✅ WebGPU LLM | ❌ | ❌ | ❌ | ❌ | ❌ |
| 成本（年） | 开源 Apache 2.0 | $0.018/hr | 商用高 | 商用 | 云费 | $/MAR |
| 适用场景 | 异构库+代码一体化 | AWS 内部 | 企业 Oracle | 流处理 | Aiven 内 | 数据仓 |

## 智迁云枢不适用场景

- 只要 dump-and-restore —— 走 `pgloader` 更轻。
- 业务 100% 走 AWS —— 用 DMS 运维成本更低。
- 生产走 Oracle→Oracle 仅主从 —— GoldenGate 仍是业内成熟方案。

## 智迁云枢的定位

1. **代码表全链路** —— 不仅迁 schema，也关注业务 SQL 的跨方言改写。
2. **GraphRAG / CKG 预警** —— 表改名、字段类型变化等可沿依赖边分析潜在影响。
3. **成本可控** —— DeepSeek / 本地小模型可选，降低对昂贵闭源模型的依赖。
4. **可展示** —— `/present`、Typst 报告、trace 链路适合赛事 / 答辩 / 作品集展示。

> 注意：以上是能力边界与产品定位对比，不把 demo seed 或启发式 baseline 当成最终效果证明。真实效果需要后续迁移样本集、人工复核和端到端评测支撑。
