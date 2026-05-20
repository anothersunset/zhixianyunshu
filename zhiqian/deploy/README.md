# 智迁云枢 · 部署

本目录用于放置 Docker Compose 编排脚本与 Grafana 大盘配置(已规划于 M7,后续补全)。

## 一键启动(规划版)

```bash
docker compose up -d
```

- 后端 zhiqian-backend:8080
- RAG  zhiqian-rag:8001
- 前端 zhiqian-web:5173
- MySQL 8.0:3306
- ChromaDB 持久化卷:/data/chroma
- Prometheus + Grafana:9090 / 3000

## 信创版本对应
- 统信 UOS / 麒麟 V10
- 毕昇 JDK 17
- 达梦 DM8 或人大金仓 KingbaseES V9
