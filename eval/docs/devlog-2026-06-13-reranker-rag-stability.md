# 开发日志：Reranker OOM 与 RAG 稳定性修复

日期：2026-06-13
项目：zhixianyunshu（智迁云枢）
模块：RAG 检索 + 评测稳定性

---

## 1. 背景

消融实验 CRAG/Full 模式的 Recall@5 从正常值骤降至 0.30，而 BM25/Vector 正常。多次实验反复出现。

---

## 2. 问题发现

### 2.1 Recall@5 骤降 0.73→0.30

| 阶段 | CRAG/Full Recall@5 | BM25 Recall@5 |
|------|-------------------|---------------|
| 正常 | 0.73-0.81 | 0.85 |
| 异常 | 0.30-0.41 | 0.85 |

**排错过程**：
1. 最初怀疑 RRF 融合问题（进行了加权 RRF 修复，无效）
2. 发现异常时 RAG 服务返回的都是同样的 17 个 mock doc（关键词匹配），而非真实的 54+ 个 Qdrant KB doc

### 2.2 根因：Reranker 模型 OOM

真正的根因不是 RRF 融合算法，而是 **reranker 模型内存超限导致 RAG 服务崩溃**：

- `bge-reranker-v2-m3` (1.4GB) + `BGE-M3` embedding 模型共存
- 总内存超限 → RAG 进程 OOM → 自动回退到 mock KB（17 doc 关键词匹配）
- Mock KB 召回质量远低于真实 Qdrant → Recall 骤降

### 2.3 为什么之前没发现

异常被静默——RAG OOM 后不会 500，而是优雅回退到 mock KB。日志中的 OOM 被忽略。

---

## 3. 解决方案

### 3.1 轻量 Reranker 模型替换

```bash
# 从 1.4GB 降至 1.1GB
RAG_USE_RERANKER=true
RAG_RERANKER_MODEL=BAAI/bge-reranker-base  # 代替 bge-reranker-v2-m3
```

内存占用：3400MB → 2588MB (-812MB)。

### 3.2 RAG 看门狗

创建 `rag_watchdog.py`：
- 自动重启崩溃的 RAG 进程
- 内存监控（4500MB 限制 → 自动重启）
- 日志持久化到 `rag_service.log`

### 3.3 离线缓存配置

```bash
HF_HOME=/path/to/cache
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

防止 HuggingFace 在线下载超时导致启动失败。

### 3.4 Qdrant 本地模式

Docker 不可用时使用 qdrant-client 本地存储：
```python
RAG_QDRANT_LOCAL_PATH=./qdrant_local/
```

---

## 4. 效果验证

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| RAG 内存 | 3400MB | 2588MB (-24%) |
| CRAG Recall@5 | 0.30 | 0.73 (+143%) |
| Vector+Rerank Recall | 0.30 | 0.73 (+143%) |
| RAG 稳定性 | 间歇崩溃 | 看门狗自动恢复 |

全量消融验证效果：
- V+Rerank SQL 修复率：比纯 Vector +7.3pp
- V+Rerank Recall：比纯 Vector +10.7pp

---

## 5. 经验教训

1. **静默回退比崩溃更危险**：mock KB 回退让错误不可见
2. **OOM 排查要检查内存使用率，不只是日志**：日志可能没有显式的 OOM
3. **轻量模型是务实选择**：bge-reranker-base 在效果和内存间找到了平衡
4. **看门狗是长时间运行服务的必要配置**：评测跑数小时，RAG 必须能自愈
