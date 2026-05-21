# A2A (Agent-to-Agent) 适配

> v2-step-24。让 ZhiQian 作为 Google [A2A](https://google.github.io/A2A/) 协议的服务端 agent,
> 其他 agent 发现 + 开任务 + 订阅状态流。

## endpoint

| 路由 | 说明 |
| --- | --- |
| `GET  /.well-known/agent.json` | AgentCard, 商业发现用 |
| `POST /a2a/tasks/send` | 同步 task, body={id, message:{skill, arguments}} |
| `POST /a2a/tasks/sendSubscribe` | SSE 流, 推 submitted/working/artifact/completed |
| `GET  /a2a/tasks/{id}` | 查任务状态 + history + artifacts |
| `GET  /a2a/tasks` | 列代看任务 |

## 支持的 skills

| skill id | 作用 | RAG endpoint |
| --- | --- | --- |
| sql.transpile | SQL 转译 | `/transpile` |
| sql.explain | 转译化变动说明 | `/structured/transpile-explain` |
| schema.analyze | DDL 表结构分析 | `/structured/schema-analysis` |
| migration.plan | 迁移计划 (CRAG) | `/crag/query` |

## 发起一个 task

```bash
curl -s -X POST http://localhost:8080/a2a/tasks/send \
  -H 'Content-Type: application/json' \
  -d '{
        "id": "task-001",
        "sessionId": "sess-1",
        "message": {
          "skill": "sql.transpile",
          "arguments": {
            "source_sql": "SELECT IFNULL(a,b) FROM t LIMIT 5,10",
            "source_dialect": "mysql",
            "target_dialect": "opengauss"
          }
        }
      }' | jq
```

## SSE 流式订阅

```bash
curl -N -X POST http://localhost:8080/a2a/tasks/sendSubscribe \
  -H 'Content-Type: application/json' \
  -d '{"id":"task-002",
        "message":{"skill":"migration.plan",
          "arguments":{"question":"怎么把 Oracle 19c HR 迁到 openGauss?"}}}'
# 会依次收: event=task / event=status(working) / event=artifact / event=status(completed)
```

## 跨 agent 互操场景

- Claude Desktop 加上 A2A bridge 后可直接调 ZhiQian 转译 SQL
- LangGraph supervisor 可启动 multiple A2A agents, 让他们使用不同专长协作
- AutoGPT-型 agent 可发现 ZhiQian 后委托迁移任务
