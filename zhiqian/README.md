# zhiqian/ 代码目录

本目录包含三个可独立运行的模块与一个部署目录。推荐使用顶层 README 中的 `docker compose up` 统一拉起，以下说明面向需要单独调试的开发者。

## backend/  (Spring Boot 3)

```bash
cd backend
./mvnw -DskipTests spring-boot:run   # 需提前在 docker compose 中拉起 postgres 服务
```

环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `SPRING_DATASOURCE_URL` | `jdbc:postgresql://localhost:5432/zhiqian` | JDBC URL |
| `SPRING_DATASOURCE_USERNAME` | `zhiqian` | DB 账号 |
| `SPRING_DATASOURCE_PASSWORD` | `zhiqian123` | DB 密码 |
| `APP_JWT_SECRET` | `change-me-please-change-me-please-32bytes-min` | JWT 密钥，生产务必更换 |
| `APP_JWT_TTL_MINUTES` | `720` | JWT 存活（8 小时） |
| `APP_RAG_BASE_URL` | `http://localhost:8001` | 后端调用 RAG 的地址 |

启动后：

- 首次启动 Flyway 会运行 V1__init.sql 创建 8 张表；V2__seed.sql 插入演示项目/任务/建议。
- DataBootstrap 会检查是否存在 admin 账户，不存在则插入 admin / admin123。
- 提供接口：
  - `POST /api/auth/login`、`GET /api/users/me`
  - `GET /api/projects`、`GET /api/projects/{id}`
  - `GET /api/tasks`、`GET /api/tasks/{id}`
  - `GET /api/tasks/{id}/suggestions`
  - `GET /api/tasks/{id}/stream`  Server-Sent Events（8 个 Agent 步骤 + progress）

## rag/  (FastAPI)

```bash
cd rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

提供接口：

- `GET /health`
- `POST /query`  （参数 question / top_k / rewrite / critic / filters）
- `POST /validation/generate`  （依据 suggestion 生成 Jinja2 验证脚本）

Jinja2 使用**自定义分隔符**`<< var >>`以避开上游压缩 URL 占位符冲突，请勿改回 `218`。运行单测：

```bash
pytest -q
```

## web/  (Vue 3)

```bash
cd web
npm i              # 首次安装
npm run dev        # 启动 Vite dev server，默认 5173 端口
```

环境变量（`.env.development` 中）：

- `VITE_API_BASE`  后端基地址（默认 `/api`，由 Vite proxy 转发 → 8080）
- `VITE_RAG_BASE`  RAG 基地址（默认 `/rag`，由 Vite proxy 转发 → 8001）

生产构建：`npm run build` 输出到 `dist/`，该目录会被镜像打包到 nginx 容器。

## deploy/  (Docker Compose)

详见 `deploy/README.md`。
