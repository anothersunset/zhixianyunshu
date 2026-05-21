# RAG 检索架构

> v2-step-30. BGE-M3 三位一体 + RRF + reranker。

```mermaid
flowchart TB
  Q["查询问题"] --> EMB["BGE-M3 Encoder"]
  EMB --> D["Dense Vector\n(1024-d)"]
  EMB --> S["Sparse Lexical\n(token id→weight)"]
  EMB --> CB["ColBERT Multi-vec\n(token-level)"]

  D --> QD[("Qdrant Dense")]
  S --> SB[("Qdrant Sparse")]
  CB --> CBI[("ColBERT Index")]

  QD --> RRF["RRF 融合\nk=60"]
  SB --> RRF
  CBI --> RRF

  RRF --> RR["bge-reranker-v2-m3"]
  RR --> TOP["Top-k=8 上下文"]

  classDef store fill:#22c55e,stroke:#15803d,color:#fff
  class QD,SB,CBI store
```

## Late Chunking

```mermaid
flowchart LR
  DOC["全文"] --> TOK["全文 token 序列"]
  TOK --> EMB["全文 contextual embed"]
  EMB --> SPLIT["语义分块点\n(span detector)"]
  SPLIT --> POOL["块内 mean pooling"]
  POOL --> CHUNK["保留上下文的 chunk embed"]
```

## GraphRAG 口词

- 节点类型: Table / Column / Index / Procedure / View / FK
- 边类型: HAS_COLUMN / FK_REF / INDEXED_BY / CALLS / VIEW_OF
- 社区检测: Louvain-Lite 自实现(不依 graphrag-toolkit)
- 问答分双轨:
  - **local**: 错锈点 → 1-hop 邻居 → LLM
  - **global**: 跨社区 summary 聊天
