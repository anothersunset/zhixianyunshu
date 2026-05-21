# ZhiQian MCP Server

> v2-step-23。让 ZhiQian 作为 [MCP](https://modelcontextprotocol.io) 工具被 Claude Desktop / Cursor / 任意 MCP 客户端调用。

## endpoint

| 路由 | 说明 |
| --- | --- |
| `GET  /mcp/manifest` | 返服务能力与 protocolVersion |
| `GET  /mcp/tools` | 便捷获取工具清单 (非标准) |
| `POST /mcp/rpc` | JSON-RPC 2.0 endpoint, 支 initialize / tools/list / tools/call |
| `POST /mcp/call` | tools/call 别名 |

## 工具清单 (6)

| name | 作用 | 底层 |
| --- | --- | --- |
| sql_transpile | SQL 转译 (mysql/oracle/sqlserver → opengauss/postgres) | /transpile (sqlglot) |
| sql_explain | 转译变动结构化说明 | /structured/transpile-explain (Outlines) |
| schema_analysis | DDL 表结构分析 + 迁移风险 | /structured/schema-analysis |
| risk_report | 一组 SQL 迁移风险报告 | /structured/risk-report |
| retrieve | BGE-M3 + RRF 检索迁移知识 | /retrieve |
| migrate_query | CRAG 增强问答 | /crag/query |

## Claude Desktop 使用

```jsonc
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "zhiqian": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/inspector", "--cli",
               "--url", "http://localhost:8001/mcp/rpc"]
    }
  }
}
```

## 手测

```bash
# initialize
curl -s -X POST http://localhost:8001/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"1","method":"initialize"}' | jq

# tools/list
curl -s -X POST http://localhost:8001/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"2","method":"tools/list"}' | jq

# tools/call sql_transpile
curl -s -X POST http://localhost:8001/mcp/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"3","method":"tools/call",
       "params":{"name":"sql_transpile","arguments":{
         "source_sql":"SELECT IFNULL(a,b) FROM t LIMIT 5,10",
         "source_dialect":"mysql","target_dialect":"opengauss"}}}' | jq
```
