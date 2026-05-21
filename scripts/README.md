# scripts/ (v2-step-32)

- `demo-walkthrough.sh` 一键拉起演示栈 (MySQL + openGauss + RAG + Backend + Web)
- `healthcheck.sh` 一口检查三服务状态

## ENV 开关

- `ENABLE_CDC=1` 同时拉起 Debezium / Kafka Connect
- `MYSQL_PWD=zhiqian` (默)
- `MYSQL_PORT=33306` (默)
