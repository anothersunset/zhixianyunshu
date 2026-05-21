# 智迁云枢总体架构

> v2-step-30. 反映本仓库 v2.0 状态(32 提交 + 7 加分)。

```mermaid
flowchart TB
  subgraph Client["客户端"]
    B["Web Console<br/>Vue3 + Element Plus"]
    M["Claude Desktop / Cursor<br/>(MCP 客户端)"]
    O["其他 Agent<br/>(A2A 客户端)"]
  end

  subgraph Edge["端侧"]
    T["transformers.js<br/>Phi-3.5-mini ONNX/WebGPU"]
  end

  subgraph Backend["Spring Boot 主服务"]
    A["Auth + RBAC"]
    P["Project / Task / Suggestion"]
    AG["6 Agent 流水线<br/>(AgentGraph)"]
    L["DeepSeek RestClient"]
    LF["Langfuse SDK"]
    TM["Temporal Activities (opt-in)"]
    CD["CDC Connect Client"]
    MT["Migration Tool Factory"]
    A2A["A2A Server"]
    RP["Report Client"]
  end

  subgraph RAG["Python FastAPI RAG"]
    R1["BGE-M3 三路混合"]
    R2["Late Chunking"]
    R3["CRAG / GraphRAG"]
    R4["Outlines 受约束解码"]
    R5["sqlglot 转译"]
    R6["MCP Server"]
    R7["TTS / Typst Report"]
  end

  subgraph Data["数据与推理"]
    PG["openGauss / PostgreSQL"]
    QD["Qdrant"]
    KF["Kafka + Debezium 3.0"]
    MQ["MySQL (源)"]
    LM["DeepSeek SaaS / vLLM"]
  end

  subgraph Infra["云原生"]
    K["Kubernetes"]
    KU["Kustomize base+overlays"]
    AR["ArgoCD GitOps"]
    KR["KubeRay"]
  end

  B --> A
  B --> P
  P --> AG
  AG --> L
  AG --> LF
  AG -->|durable| TM
  AG --> RAG
  L --> LM
  CD --> KF
  KF --> PG
  MQ -.binlog.-> KF
  MT -.dispatch.-> AG
  M -->|JSON-RPC 2.0| R6
  O -->|/.well-known/agent.json| A2A
  A2A --> RAG
  R3 --> QD
  R5 --> PG
  T -.端侧.-> B
  KU --> K
  AR --> K
  KR --> K
```

## 设计原则

1. **三层清晰**。Web / Backend / RAG 独立升级,Backend 面向业务 + Java 依赖;RAG 面向 LLM + Python 生态。
2. **双协议入口**。MCP 让 ZhiQian 被外部调(serve),A2A 让 ZhiQian 与其他 Agent 互联(peer)。
3. **迁移不锁定一条路**。ZhiQian Native / pgloader / Ora2Pg / Debezium 四轨并行,MigrationToolFactory 推荐。
4. **云原生**。Kustomize 原生 + ArgoCD GitOps + 可选 KubeRay (生产型 GPU 推理)。
5. **端侧零推理成本**。transformers.js Phi-3.5-mini 走浏览器,隐私高的场景可脱后端。
6. **可观测**。Langfuse + JaCoCo 门禁 + Temporal 事件 = 全链追踪 + 结算 + 重试。
