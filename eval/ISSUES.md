# 消融实验问题记录

## 问题 1: sql_equivalent 对语义等价 SQL 判断过于严格

**发现时间**: 2026-06-10 17:48
**现象**: 消融实验 BM25 模式前 4 个 case 全部 FAIL
**根因**: `eval/metrics.py` 中的 `sql_equivalent()` 使用 sqlglot 解析后比较 AST，但对以下语义等价情况返回 False：
- `CONCAT(a,b)` vs `a || b` (OpenGauss 两种写法都支持)
- `IFNULL(a,b)` vs `COALESCE(a,b)` (语义完全等价)
- `NVL(a,b)` vs `COALESCE,a,b)` (Oracle → PostgreSQL 标准转换)

**示例**:
```python
gold = "SELECT first_name || ' ' || last_name AS full_name FROM emp"
pred = "SELECT CONCAT(first_name,chr(32),last_name) AS full_name FROM emp"
sql_equivalent(pred, gold, 'opengauss')  # False — 但语义完全等价
```

**影响**: 当前不使用 LLM judge 时，SQL 修复率被低估
**解决方案**: 运行消融时加 `--use-judge`，让 LLM judge 做二次语义判断

## 问题 2: LLM max_tokens=2048 导致 JSON 截断

**发现时间**: 2026-06-10 17:35
**现象**: LLM 返回的 JSON 在 `report_points` 数组中间被截断，导致 parse 失败
**根因**: `application-local.yml` 中 `max-tokens: 2048` 不够用，复杂 SQL 的 report_points 需要 3000+ tokens
**修复**: 改为 `max-tokens: ${LLM_MAX_TOKENS:4096}`，同时 `.env` 中已有 `LLM_MAX_TOKENS=4096`

## 问题 3: Java HttpClient → FastAPI 422 错误

**发现时间**: 2026-06-10 (之前 session)
**现象**: `ContextRetrieverAgent` 调用 RAG 服务返回 422 "Field required"
**根因**: `java.net.http.HttpClient` 默认发送 `Expect: 100-continue` header，FastAPI 不支持
**修复**: 改用 `java.net.HttpURLConnection`

## 问题 4: RAG vector 模式返回空结果

**发现时间**: 2026-06-10
**现象**: retrieval=vector 时 RAG 返回 bodyLen=313（空结果），fallback 到 mock
**影响**: vector/vector_rerank 模式的 Recall@5 可能不准确
**待查**: 需要检查 Qdrant 中 vector 索引是否正确构建

## 问题 5: 后端并发过载

**发现时间**: 2026-06-10
**现象**: parallel=2 时后端崩溃
**根因**: 每个 migration 调用 = 6 个 LLM 调用 × 30-60 秒
**修复**: 添加客户端节流机制（cooldown=5s），自适应退避

---

## 消融实验运行记录

### 2026-06-10 17:46 - BM25 模式（第 1 组，无 judge）
- 配置: fast=true, cooldown=5s, parallel=1
- 结果: 前 4 case 全部 FAIL（sql_equivalent 过于严格）
- 后续: 需要加 --use-judge 重跑

### 2026-06-10 17:52 - BM25 模式（第 1 组，有 judge）
- 配置: fast=true, cooldown=5s, parallel=1, --use-judge
- 进度: 27/96 case 完成 (28.1%)
- 中间结果:
  - SQL 修复率: 70.4% (19/27)
  - mysql→opengauss: 80.0% (16/20)
  - mysql→postgresql: 50.0% (1/2)
  - oracle→postgresql: 40.0% (2/5)
- 观察: oracle→postgresql 修复率较低，可能是 Oracle 特有语法转换难度大
- 预计: ~34 分钟完成 BM25 模式，全部 5 组约 3 小时

---

## 开发经验总结

### 1. 环境变量管理
- Windows 下 `export $(grep ...)` 方式加载 .env 文件不可靠
- 建议: 直接在命令行显式设置关键环境变量，或使用 Spring Boot 的 `spring.config.import`

### 2. LLM 输出截断
- 原因: max_tokens 设置过低（2048），复杂 SQL 的 report_points 需要 3000+ tokens
- 教训: 设置 max_tokens 时要考虑最坏情况（5 个 report_points + 完整 SQL）

### 3. Java HTTP 客户端兼容性
- `java.net.http.HttpClient` 的 `Expect: 100-continue` 与 FastAPI 不兼容
- 解决: 使用传统的 `HttpURLConnection` 更稳定

### 4. SQL 等价判断
- sqlglot 的 AST 比较无法处理语义等价但语法不同的 SQL
- 解决: 使用 LLM judge 做二次语义判断，成本约 +1 LLM 调用/case

### 5. 后端过载防护
- 原因: 每个 migration = 6 个 LLM 调用 × 30-60 秒
- 解决: 客户端节流（cooldown）+ 自适应退避 + 健康检查
