# deploy/ 部署包

## 一、docker compose 服务拓扑

| 服务 | 镜像 | 宿主端口 | 说明 |
| --- | --- | --- | --- |
| postgres | postgres:16-alpine | 未暴露（容器网络内 5432） | 数据库，初始化账号 zhiqian / `${POSTGRES_PASSWORD}` |
| qdrant | qdrant/qdrant:v1.11.3 | 6333 / 6334 | 向量库（RAG 检索），带 healthcheck |
| backend | 本地构建 | 8080 | Spring Boot 3，依赖 postgres healthcheck |
| rag | 本地构建 | 8001 | FastAPI 服务，依赖 qdrant |
| web | 本地构建 | 80 | Nginx + Vue SPA，负责转发 /api /rag |

另有一个可选的 temporal profile（`temporalio/auto-setup:1.25.0` + UI），默认不启动，
见 `docker-compose.yml` 内注释。

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

`docker-compose.yml` 强制要求以下三个变量（`${VAR:?}` 语法，缺失即报错退出）：

```
POSTGRES_PASSWORD=change-me-strong-db-password        # 数据库密码
JWT_SECRET=change-me-random-string-at-least-32-chars  # JWT 签名密钥，至少 32 字符
ADMIN_PASSWORD=change-me-admin-initial-password       # 内置管理员账号初始密码
```

其余均为可选变量（`LLM_*`、`TEMPORAL_*`、`LANGFUSE_*`、`RAG_*`、`HF_CACHE_DIR` 等），
compose 内置了默认值；完整清单与逐项中文注释见 [`.env.example`](./.env.example)。

两个历史遗留注意点：服务端口映射直接写在 `docker-compose.yml` 中（不存在
`*_HOST_PORT` 变量，postgres 未对宿主机暴露）；postgres 用户名/库名固定为
zhiqian，不从 `.env` 读取。

## 四、常见问题

### 1. 端口被占用

修改 `.env` 中的 `*_HOST_PORT`，例如将 `WEB_HOST_PORT=80` 改为 `8000`，重跑 `docker compose up -d`。

### 2. backend 启动报 connection refused

postgres 需要 5-10s 初始化。docker compose 已配置 healthcheck + depends_on condition: service_healthy，一般会自动重试。若仍失败请查看 `docker compose logs postgres`。

### 3. Flyway 报 migration checksum mismatch

清零数据卷重跑：`docker compose down -v && docker compose up -d --build`。生产环境请使用 `flyway repair`。

### 4. 前端出现 502 Bad Gateway

Nginx 转发失败。检查后端是否健康：`curl http://localhost:8080/actuator/health`；RAG：`curl http://localhost:8001/health`。

### 5. SSE 任务的鉴权方式

SSE 接口（`/api/tasks/*/stream`）只接受 `Authorization: Bearer <JWT>` 请求头。
更早版本支持的 query 参数 `?token=xxx` 已在提交 `01ad87d` 中从
`JwtAuthenticationFilter` 移除（URL 中的 token 会泄漏进访问日志、代理日志与浏览器
历史）；同一批提交把 `SecurityConfig` 里该端点的 `permitAll` 收紧为
`authenticated()`——未携带有效 JWT 的请求一律 401，不存在"默认游客可读"。
前端因 `EventSource` 无法自定义请求头，改用 `fetch` + Bearer 头消费 SSE 流
（见 `zhiqian/web/src/api/task.ts`）。
