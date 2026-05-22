# 同类产品对比 · 顶层概览

> 详细表与选型决策看 [`zhiqian/docs/comparison.md`](../zhiqian/docs/comparison.md)。

## 6 维 × 5 商用产品

| 维度 | **智迁云枢** | AWS DMS / SCT | Oracle GoldenGate | Striim | Aiven Migrate | Fivetran |
| --- | --- | --- | --- | --- | --- | --- |
| LLM 语义迁移 | ✅ 6-Agent DAG | ❌ 规则 | ❌ 规则 | ⚠️ 部分 | ❌ | ❌ |
| GraphRAG 跨表推理 | ✅ Louvain-Lite | ❌ | ❌ | ❌ | ❌ | ❌ |
| CDC 增量 | ✅ Debezium 3.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 供应链闭环 | ✅ SBOM+Cosign | ⚠️ 仅于扫 | ❌ | ❌ | ⚠️ | ⚠️ |
| MCP / A2A | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 本地便携 (离线 demo) | ✅ WebGPU LLM | ❌ | ❌ | ❌ | ❌ | ❌ |
| 成本 (年) | 开源 Apache 2.0 | $0.018/hr | 商用高 | 商用 | 云费 | $/MAR |
| 适用场景 | 异构库+代码一体化 | AWS 内部 | 企业 Oracle | 流处理 | Aiven 内 | 数据仓 |

## 智迁云枢 不适用场景

- 只要动 dump-and-restore — 走 `pgloader` 更轻
- 业务 100% 走 AWS — 用 DMS 运维股菖小
- 生产走 Oracle→Oracle 仅主从 — GoldenGate 犹是业内金标

## 为什么 智迁云枢 在跨异构+代码场景里赢

1. **代码表全链跳** — 不仅迁 schema, 连业务表中的 SQL 跨方言译
2. **GraphRAG 预报危险** — 表改名 → 下游跨服务 N 表受影响, 事前出
3. **零调费** — DeepSeek-V3.1 / 本地 Phi-3.5 可选代 GPT-4
4. **带 demo** — 年度质评 / 赛事 / 照面都能跳 `/present` 走 10 幻片
