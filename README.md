# 智迁云枢 · ZhiQian YunShu

> 中国软件杯参赛作品 · 面向 MySQL → openGauss 的多 Agent 数据库智能迁移平台

本仓库是**可本地 30 秒起走**的演示版：包含 Spring Boot 3 后端、FastAPI RAG 服务、Vue 3 前端、PostgreSQL 与 Nginx，一条 `docker compose up` 命令即可拉起全栈。

## 一、架构总览

```
╔═════════════════╗      ╔════════════════╗      ╔══════════════╗
║ zhiqian-web      ║ -- Nginx → ║ zhiqian-backend║ -- HTTP → ║ PostgreSQL ║
║ Vue 3 + Element  ║      ║ Spring Boot 3  ║      ║  (openGauss兼)║
╠═════════════════╣      ╠════════════════╣      ╠══════════════╣
║       SSE        ║ ←────────── ║ SSE · JWT     ║      ║ Flyway 迁移 ║
╚═════════════════╝      ╠════════════════╣      ╚══════════════╝
                          ║     │          ║
                          ╚═══ HTTP ═══════╝
                                │
                       ╔════════════════╗
                       ║ zhiqian-rag    ║
                       ║ FastAPI + BM25 ║
                       ╚════════════════╝
```

十 个 Agent 节点与完整理论架构请参阅同名设计文档。

## 二、本地 30 秒启动

```bash
git clone https://github.com/anothersunset/zhixianyunshu.git
cd zhixianyunshu/zhiqian/deploy
cp .env.example .env
docker compose up -d --build
```

启动完成后访问：http://localhost （默认占用的端口：80 / 8080 / 8001 / 5432，冲突请改 `.env`）。

首次启动后记录下面三个地址：

| 服务 | URL | 说明 |
| --- | --- | --- |
| 前端 | http://localhost | Vue 3 SPA + Element Plus |
| 后端 | http://localhost:8080/actuator/health | Spring Boot 3 + JWT |
| RAG  | http://localhost:8001/health | FastAPI + BM25 + Self-RAG critic |

默认管理员账户：**admin / admin123**，首次登录请及时修改。

## 三、可访问页面

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/` | 仪表盘 | 4 个 KPI 卡、趋势/风险 ECharts、最近任务表 |
| `/projects` | 项目列表 | 从 `GET /api/projects` 读取 1 个演示项目 |
| `/projects/:id` | 项目详情 | 项目属性 + 本项目下任务列表 |
| `/tasks` | 任务列表 | 2 个演示任务（1 个 DONE、1 个 RUNNING） |
| `/tasks/:id` | 任务详情 | 点击 “开始演示” 观看 8 步 SSE 实时时间线 |
| `/knowledge` | 知识库 | RAG 检索 + Self-RAG critic 评估面板 |
| `/reports` | 报告中心 | 演示报告入口 |
| `/settings` | 设置 | 当前账户、服务地址 |

## 四、演示状态与已知限制

> 本版本为 **本地可跑动的演示版**，以下能力以 mock / 虚拟数据方式提供，生产版本需接入真实服务：
>
> - **嵌入检索**：未接入 BGE-M3 与 Faiss，仅启用 BM25 作为主检索。
> - **LLM 推理**：未接入 GLM-4-Plus 等 LLM provider，Reasoner / Critic 为启发式打分。
> - **K8s 部署**：仅提供 docker compose ，生产需复制为 Helm Chart。
> - **权限模型**：仅提供 ADMIN / USER 两角色，未接入 RBAC 细粒度权限。
> - **报告渲染**：Reporter Agent 为提示占位，未生成真实 PDF。

## 五、常用命令

```bash
# 查看服务状态
docker compose ps

# 查看某个服务日志
docker compose logs -f backend
docker compose logs -f rag

# 重启某个服务
docker compose restart web

# 完全重置 (清除数据卷)
docker compose down -v
```

## 六、项目结构

```
zhiqian/
├─ backend/      Spring Boot 3 + Spring Data JDBC + Spring Security + JWT
│   ├─ src/main/java/com/zhiqian/    · controllers · agents · ckg · analyzer
│   └─ src/main/resources/db/migration/  Flyway V1__init.sql · V2__seed.sql
├─ rag/          FastAPI + BM25 + Self-RAG critic + Jinja2 validation 脚本模板
│   ├─ app/pipelines/ retriever · critic · rewriter · validation
│   └─ app/templates/ 验证脚本 (自定义分隔符 << >>)
├─ web/          Vue 3 + Vite + Element Plus + ECharts + Pinia + vue-router
│   └─ src/{views,components,api,stores,layouts,router,mock}
└─ deploy/       docker-compose.yml · nginx.conf · .env.example · init-db.sql
```

## 七、License

MIT © 2026 ZhiQian YunShu Team
