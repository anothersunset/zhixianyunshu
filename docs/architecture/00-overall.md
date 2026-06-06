# 总架构 · 顶层概览

> 本页为项目顶层架构概览。深入实现看 [`zhiqian/docs/architecture/`](../../zhiqian/docs/)（下面小节里链了具体文件）。

## 一句话

智迁云枢 = **6-Agent DAG** 驱动的 **MySQL/Oracle/SQLServer → openGauss/PostgreSQL** 跨方言数据库迁移平台，背靠 **BGE-M3 三路检索 + GraphRAG + CRAG** 提高迁移建议准确率，并通过云原生部署与供应链安全形成工程闭环。

## 6 层架构（top-down）

```mermaid
flowchart TB
  subgraph L1["接入层 · Vue 3 控制台"]
    UI["Element Plus + Monaco + Cytoscape"]
    LL["本地 LLM (transformers.js + WebGPU)"]
    SLIDES["PresentationView + edge-tts"]
  end
  subgraph L2["网关层 · Spring Boot 8080"]
    AUTH["鉴权 + RestClient"]
    AGENT["6-Agent DAG:<br/>SchemaAnalyzer / ContextRetriever / SqlReasoner / SqlPatcher / SqlCritic / ReportSummarizer"]
    MIG["MigrationToolFactory:<br/>ZhiQian Native / pgloader / Ora2Pg / Debezium"]
  end
  subgraph L3["智能层 · Python FastAPI 8001"]
    RAG["BGE-M3 三路 + RRF + Late Chunking"]
    GRAPH["GraphRAG (CKG / Louvain-Lite)"]
    CRAG["CRAG mini StateGraph"]
    OUT["Outlines JSON 受约束解码"]
  end
  subgraph L4["协议层"]
    MCP["MCP Server (JSON-RPC 2.0)"]
    A2A["A2A AgentCard + SSE"]
  end
  subgraph L5["数据层"]
    MYSQL["MySQL 5.7/8.0"]
    OG["openGauss / PostgreSQL"]
    QD["Qdrant"]
    KAFKA["Kafka + Debezium 3.0 CDC"]
    TEMP["Temporal"]
  end
  subgraph L6["云原生"]
    K8S["Kustomize base + dev/prod overlays"]
    ARGO["ArgoCD GitOps"]
    RAY["KubeRay + vLLM"]
    SEC["Syft SBOM + Trivy + Cosign keyless"]
  end

  L1 --> L2 --> L3
  L2 --> L4
  L3 --> L4
  L2 --> L5
  L3 --> L5
  L5 -.-> L6
```

## 关键详情文档

| 架构跳转 | 详细位置 |
| --- | --- |
| 6-Agent DAG | [`01-agent-pipeline.md`](./01-agent-pipeline.md) |
| RAG 三路检索 | [`02-rag-retrieval.md`](./02-rag-retrieval.md) |
| 实现级架构（full mermaid） | [`zhiqian/docs/architecture/00-overall.md`](../../zhiqian/docs/architecture/00-overall.md) |
| Agent 细粒度 pipeline | [`zhiqian/docs/architecture/01-agent-pipeline.md`](../../zhiqian/docs/architecture/01-agent-pipeline.md) |
| RAG 详细检索面 | [`zhiqian/docs/architecture/02-rag-retrieval.md`](../../zhiqian/docs/architecture/02-rag-retrieval.md) |

## 部署拓扑

### 本地演示（最小）
```
[浏览器 5173]
    → [web Vite dev server]
    → [backend Spring Boot :8080]
         → [RAG FastAPI :8001]
              → [Qdrant :6333] [DeepSeek API]
         → [MySQL :3306] [openGauss :5432]
```

### 生产（Kubernetes）
```
[Ingress] → [web nginx] [backend HPA 2-8] [RAG HPA 2-4]
           → [vLLM via KubeRay autoscale 1-4] [Qdrant cluster]
           → [MySQL + openGauss + Kafka + Debezium + Temporal]
[ArgoCD] — GitOps → kustomize/overlays/prod
[Sealed Secrets] — 加密 secret 可进 Git
```

## 设计原则

1. **默认优雅降级** — 未装 typst / edge-tts / transformers.js / Temporal / CDC 都返 503，不崩服务。
2. **依赖可选** — ML 依赖走 `requirements-ml.txt + BUILD_ML=1`。
3. **供应链透明** — 每个 artifact 都有 SBOM + Cosign 签名 + Rekor 公开可查。
4. **GitOps 可反复** — 一切部署状态都在 Git，dev=auto，prod=manual+selfHeal。
