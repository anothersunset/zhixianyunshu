# 同类产品对比 (v2-step-30)

## 商业/社区迁移工具

| 维度 | **智迁云枢** | AWS DMS | Alibaba DTS | Ora2Pg | pgloader | DataX |
| --- | --- | --- | --- | --- | --- | --- |
| LLM 增强 | ✅ 6 Agent | ❌ | ❌ | ❌ | ❌ | ❌ |
| 实时 CDC | ✅ (Debezium 3.0) | ✅ | ✅ | ❌ | ❌ | 部分 |
| openGauss | ✅ 锐化 | 中 | ❌ | ✅ | ✅ | 中 |
| 跨方言复杂 SQL 转 | ✅ | 中 | 中 | 仅 Oracle | ❌ | ❌ |
| 可解释报告 | ✅ (Typst) | 部分 | 部分 | ✅ | ❌ | ❌ |
| MCP / A2A | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 本地部署 | ✅ (Kustomize) | ❌ (cloud) | ❌ (cloud) | ✅ | ✅ | ✅ |
| 价格 | 开源 | 按小时 | 按小时 | 开源 | 开源 | 开源 |
| 独特优势 | 生态互联 | AWS 资高 | 阿里资高 | PL/SQL 深 | 吞吐高 | DataWorks 走 |

## RAG 架构对比

| 特性 | **智迁云枢** | LangChain Naive | LlamaIndex Default | RAGFlow | Verba |
| --- | --- | --- | --- | --- | --- |
| 检索路数 | 3 (Dense+Sparse+ColBERT) | 1 | 2 | 2 | 1 |
| 融合 | RRF k=60 | none | weighted | RRF | none |
| Late Chunking | ✅ | ❌ | 部分 | ❌ | ❌ |
| CRAG | ✅ mini StateGraph | ❌ | ❌ | 部分 | ❌ |
| GraphRAG | ✅ 自实现 Louvain-Lite | ❌ | 部分 | 部分 | ❌ |
| 受约束生成 | Outlines + JSON Schema | ❌ | ❌ | ❌ | ❌ |
| trace | Langfuse 全链 | 部分 | 部分 | 中 | ❌ |

## 云原生部署对比

| | **智迁云枢** | Helm Chart | 原生 kubectl |
| --- | --- | --- | --- |
| 资源组装 | Kustomize base+overlays | Helm Go-template | YAML 累鱼 |
| GitOps | ArgoCD AppProject + Dev/Prod | Helmfile / FluxCD | 手动 sync |
| Secret | secretGenerator + External Secrets | template | base64 |
| LLM 推理 | vLLM Deployment / KubeRay RayService | 需设 values | 手动 |
| GPU 弹性 | KubeRay autoscale 1-4 | 需附加 chart | 手动 |

## CDC 对比

| | **Debezium 3.0 (智迁)** | AWS DMS CDC | Maxwell | Canal | Striim |
| --- | --- | --- | --- | --- | --- |
| 源 | MySQL/Postgres/Oracle/SQLServer/MongoDB | 众多 | 仅 MySQL | 仅 MySQL | 众多 |
| sink | Kafka Connect JDBC sink 泛型 | DMS 端点 | Kafka/Redis | RocketMQ/Kafka | 商业 |
| 本地部署 | ✅ docker | ❌ | ✅ | ✅ | ❌ |
| openGauss sink | ✅ (PostgreSqlDatabaseDialect) | 部分 | ❌ | ❌ | 部分 |

## 结论

- **智迁云枢 不是取代 pgloader/DataX**, 是**智能层 + 适配层 + 生态层**:
  - 智能层: 6 Agent + CRAG + GraphRAG 解决复杂跨方言转译。
  - 适配层: MigrationToolFactory 作为调度,让 pgloader/Ora2Pg/Debezium 作为同类调下。
  - 生态层: MCP + A2A 双协议让 ZhiQian 与 LLM 生态互联。
- 同类产品都是**点**, ZhiQian 是**面** —— 这是本作品的论文赵象老子。
