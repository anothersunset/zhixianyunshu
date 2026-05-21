# scripts/

顶级一键脚本集, 用于 demo / 检查 / 运维。

| 脚本 | 用途 | 调用 |
| --- | --- | --- |
| `demo-walkthrough.sh` | 6 步一键拉起完整 demo | `bash scripts/demo-walkthrough.sh` |
| `healthcheck.sh` | 7 个 endpoint 状态检查 | `bash scripts/healthcheck.sh` |
| `smoke-test.sh` | 三路静态检 (不启服务) | `bash scripts/smoke-test.sh` |
| `install-supply-chain-workflow.sh` | 一键装供应链 CI | `bash scripts/install-supply-chain-workflow.sh` |

## demo 项的环境变量

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `ENABLE_CDC` | `0` | 是否拉 Debezium Kafka Connect (额增 ~600MB) |
| `MYSQL_PWD` | `zhiqian` | datasets MySQL root 密码 |
| `MYSQL_PORT` | `33306` | datasets MySQL 外部端口 |
| `OG_PORT` | `55432` | datasets openGauss 外部端口 |
| `SMOKE_SKIP_WEB` | `0` | smoke-test 跳 web |
| `SMOKE_SKIP_RAG` | `0` | smoke-test 跳 rag |
| `SMOKE_SKIP_BACKEND` | `0` | smoke-test 跳 backend |

## 推荐提交前顺序

```bash
bash scripts/smoke-test.sh           # 检编译
bash scripts/demo-walkthrough.sh     # 拉起
bash scripts/healthcheck.sh          # 验状态
```
