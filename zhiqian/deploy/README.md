# deploy/ 部署包

## 一、docker compose 服务拓扑

| 服务 | 镜像 | 宿主端口 | 说明 |
| --- | --- | --- | --- |
| postgres | postgres:16-alpine | 5432 | 数据库，初始化账号 zhiqian / `${POSTGRES_PASSWORD}` |
| backend | 本地构建 | 8080 | Spring Boot 3，依赖 postgres healthcheck |
| rag | 本地构建 | 8001 | FastAPI 服务 |
| web | 本地构建 | 80 | Nginx + Vue SPA，负责转发 /api /rag |

## 二、启动与停止

```bash
cp .env.example .env             # 首次运行。可修改 JWT_SECRET、数据库密码等
docker compose up -d --build     # 拉起全栈
docker compose ps                # 查看状态
docker compose logs -f backend   # 跟踪后端日志
docker compose down              # 停止但保留数据
docker compose down -v           # 完全清零（包括数据卷）
```

## 三、环境变量（.env）

```
POSTGRES_USER=zhiqian
POSTGRES_PASSWORD=zhiqian123
POSTGRES_DB=zhiqian
JWT_SECRET=change-me-please-change-me-please-32bytes-min
JWT_TTL_MINUTES=720
WEB_HOST_PORT=80
BACKEND_HOST_PORT=8080
RAG_HOST_PORT=8001
POSTGRES_HOST_PORT=5432
```

## 四、常见问题

### 1. 端口被占用

修改 `.env` 中的 `*_HOST_PORT`，例如将 `WEB_HOST_PORT=80` 改为 `8000`，重跑 `docker compose up -d`。

### 2. backend 启动报 connection refused

postgres 需要 5-10s 初始化。docker compose 已配置 healthcheck + depends_on condition: service_healthy，一般会自动重试。若仍失败请查看 `docker compose logs postgres`。

### 3. Flyway 报 migration checksum mismatch

清零数据卷重跑：`docker compose down -v && docker compose up -d --build`。生产环境请使用 `flyway repair`。

### 4. 前端出现 502 Bad Gateway

Nginx 转发失败。检查后端是否健康：`curl http://localhost:8080/actuator/health`；RAG：`curl http://localhost:8001/health`。

### 5. 需要在 SSE 上使用 token

本平台 SSE 接口接受两种鉴权方式：`Authorization: Bearer xxx` 或 query 参数 `?token=xxx`。`SecurityConfig` 对 `/api/tasks/*/stream` 默认允许游客，生产环境请收紧。
