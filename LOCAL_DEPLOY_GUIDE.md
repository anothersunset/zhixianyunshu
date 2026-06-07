# 智迁云枢 本地 Docker 部署说明书

> 目标读者: AI 编程助手（如 Codex），用于理解本项目本地部署流程与常见踩坑点。
> 环境: Windows 11 + WSL2 + Docker Desktop，位于中国大陆网络环境。
> 版本: v1.0.4

---

## 1. 项目架构速览

```
zhixianyunshu/
├── zhiqian/backend/       # Spring Boot 3.2.5 + Java 21，端口 8080
├── zhiqian/rag/           # Python FastAPI + BGE-M3，端口 8001
├── zhiqian/web/           # Vue 3 + Vite + Element Plus，端口 5173
├── zhiqian/deploy/        # Docker Compose + Kustomize + ArgoCD 配置
├── .github/workflows/     # CI/CD（supply-chain.yml 等）
└── zhiqian/security/workflows-template/  # CI 模板
```

**核心服务（docker-compose 启动）:**
| 服务 | 端口 | 技术栈 |
|------|------|--------|
| backend | 8080 | Spring Boot + JWT + Flyway + PostgreSQL |
| rag | 8001 | FastAPI + Qdrant + BGE-M3 + Langfuse |
| postgres | 5432 | PostgreSQL 16 |
| qdrant | 6333 | 向量数据库 |
| web | 5173 | Vue 3 + Vite（开发模式） |

**健康检查端点（v1.0.4 修复后全绿）:**
| 端点 | 预期响应 |
|------|----------|
| `GET /actuator/health` (8080) | `{"status":"UP"}` |
| `GET /health` (8001) | `{"status":"ok"}` |
| `GET /mcp/manifest` (8001) | `{"name":"zhiqian-mcp",...}` |
| `GET /reports/status` (8001) | `{"typst_available":true}` |
| `GET /.well-known/agent.json` (8080) | `{"name":"sql.transpile",...}` |
| `GET /swagger-ui.html` (8080) | Swagger UI 页面 |
| `POST /api/auth/login` (8080) | `{"token":"..."}` |

---

## 2. 部署步骤

### 2.1 前置条件

```bash
# 必需工具
docker --version       # ≥ 24.0
docker compose version # ≥ 2.0
java --version         # JDK 21
node --version         # ≥ 18
python --version       # ≥ 3.11
```

### 2.2 克隆与启动

```bash
git clone https://github.com/anothersunset/zhixianyunshu.git
cd zhixianyunshu

# 创建 .env（可选，大多数场景用默认值）
cp zhiqian/deploy/.env.example zhiqian/deploy/.env

# 启动核心服务（backend + rag + postgres + qdrant）
docker compose -f zhiqian/deploy/docker-compose.yml up -d

# 等待所有服务就绪（约 60s）
docker compose -f zhiqian/deploy/docker-compose.yml ps
```

### 2.3 验证部署

```bash
# 健康检查
curl -s http://localhost:8080/actuator/health
curl -s http://localhost:8001/health

# MCP 清单
curl -s http://localhost:8001/mcp/manifest

# A2A Agent Card
curl -s http://localhost:8080/.well-known/agent.json

# Swagger UI
curl -s http://localhost:8080/swagger-ui.html -o /dev/null -w "%{http_code}"
```

---

## 3. 踩坑记录与修复方案

### 坑 #1: Docker 镜像构建网络失败

**现象:** `docker compose build` 超时，报 `error pulling from docker.io` 或 `dial tcp: lookup ... i/o timeout`。

**根因:** Docker Hub 在中国大陆直接被墙或极慢。尤其 `# syntax=docker/dockerfile:1.7` 指令需要从 Docker Hub 拉取 syntax 镜像。

**修复:**
```dockerfile
# 删除 Dockerfile 第一行
# syntax=docker/dockerfile:1.7   ← 删除这行
```

**影响文件:**
- `zhiqian/backend/Dockerfile`
- `zhiqian/rag/Dockerfile`

**通用建议:** 在中国大陆构建 Docker 镜像时，预先配置 Docker Hub 镜像加速器（阿里云/中科大），或避免使用 syntax 指令。

---

### 坑 #2: Maven 测试编译失败（-DskipTests vs -Dmaven.test.skip）

**现象:** Docker 构建 backend 镜像时 Maven 编译报错:
```
MockLlmClientTest.java: cannot find symbol: class ChatResponse
```

**根因:** `-DskipTests` 跳过测试执行但不跳过测试编译。测试文件 `MockLlmClientTest.java` 引用了运行时才存在的类，编译期失败。

**修复:**
```dockerfile
# 错误写法
RUN mvn package -DskipTests -q

# 正确写法（在 Docker 镜像构建场景）
RUN mvn package -Dmaven.test.skip=true -q
```

**说明:** 此修复仅在 Docker 镜像构建中适用。本地 IDE 中应正常编译和运行测试。

---

### 坑 #3: pom.xml Maven 依赖问题

#### 3a. flyway-database-postgresql 缺失版本号

**现象:** Maven 报 `Could not find artifact org.flywaydb:flyway-database-postgresql`。

**根因:** 依赖声明未指定 `<version>`，且父 POM 的 dependencyManagement 也未管理此依赖。

**修复:**
```xml
<dependency>
    <groupId>org.flywaydb</groupId>
    <artifactId>flyway-database-postgresql</artifactId>
    <version>10.15.2</version>  <!-- 补充此行 -->
</dependency>
```

#### 3b. mockito-inline 已废弃

**现象:** Maven 警告 `mockito-inline` 在 Mockito 5.x 中已废弃。

**根因:** Mockito 5.x 将 inline mock 功能内建到 `mockito-core`，不再需要独立 `mockito-inline` 依赖。

**修复:** 从 `pom.xml` 中删除以下依赖块：
```xml
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-inline</artifactId>
    <scope>test</scope>
</dependency>
```

#### 3c. 未集成 SpringDoc（Swagger UI 不可用）

**现象:** 访问 `http://localhost:8080/swagger-ui.html` 返回 403/404。

**根因:** 项目未引入 `springdoc-openapi` 依赖。虽然 Spring Boot 3.x 自动生成 OpenAPI 规范，但无 UI 展示层。

**修复:**
```xml
<!-- pom.xml 的 properties 区 -->
<springdoc.version>2.5.0</springdoc.version>

<!-- pom.xml 的 dependencies 区 -->
<dependency>
    <groupId>org.springdoc</groupId>
    <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
    <version>${springdoc.version}</version>
</dependency>
```

---

### 坑 #4: Spring Security 路径拦截导致 403/404

**现象:**
- `GET /.well-known/agent.json` → 403（A2A Agent Card）
- `GET /swagger-ui.html` → 403
- `GET /v3/api-docs/**` → 403

**根因:** `SecurityConfig.java` 中仅放行了 `/api/auth/**`、`/actuator/**` 等少数路径，其余全部需认证。

**修复:** 在 `SecurityConfig.java` 的 `authorizeHttpRequests` 链中添加:
```java
.authorizeHttpRequests(a -> a
    .requestMatchers("/api/auth/**").permitAll()
    .requestMatchers("/actuator/**").permitAll()
    .requestMatchers("/.well-known/**").permitAll()          // ← A2A Agent Card
    .requestMatchers("/swagger-ui/**", "/v3/api-docs/**").permitAll()  // ← Swagger
    .requestMatchers("/error").permitAll()
    .anyRequest().authenticated()
)
```

---

### 坑 #5: RAG FastAPI 路由冲突

**现象:** RAG 容器启动时崩溃:
```
AssertionError: Prefix and path cannot be both empty
```

**根因:** 部分 API router 文件用 `APIRouter()` 无参构造，FastAPI 不允许 prefix 和 path 同时为空。

**修复:** 为以下文件中的 router 添加 prefix:
```python
# zhiqian/rag/app/api/rerank.py
router = APIRouter(prefix="/rerank", tags=["rerank"])

# zhiqian/rag/app/api/retrieve.py
router = APIRouter(prefix="/retrieve", tags=["retrieve"])

# zhiqian/rag/app/api/ingest.py
router = APIRouter(prefix="/ingest", tags=["ingest"])

# zhiqian/rag/app/api/transpile.py
router = APIRouter(prefix="/transpile", tags=["transpile"])
```

---

### 坑 #6: RAG API 模块缺失

**现象:** 虽代码仓库中有对应文件，但 Docker 镜像中不存在。`GET /mcp/manifest` 和 `GET /reports/status` 返回 404。

**根因:** Docker 镜像构建时使用了旧版代码（未包含后续提交的 `mcp.py`、`reports.py`）。需确认本地 git 仓库代码完整，然后重新构建镜像。

**缺失模块清单:**
- `zhiqian/rag/app/api/query.py` — `/query` 端点（POST）
- `zhiqian/rag/app/api/validation.py` — `/validation/generate` 端点（POST）

**临时修复（容器已运行）:**
```bash
docker cp zhiqian/rag/app/api/query.py <container>:/app/app/api/
docker cp zhiqian/rag/app/api/validation.py <container>:/app/app/api/
docker restart <container>
```

**永久修复:** 重新 `docker compose build --no-cache rag`。

---

### 坑 #7: Temporal 工作流 Bean 注入失败

**上下文:** Temporal 工作流默认禁用（`app.temporal.enabled=false`），但相关 Controller 和 Activity Bean 仍尝试注入不存在的依赖。

#### 7a. TemporalMigrationController

**现象:** Spring 启动报 `NoSuchBeanDefinitionException: No qualifying bean of type 'TemporalProperties'`。

**根因:** 使用 `@RequiredArgsConstructor` 直接注入 `TemporalProperties`，该 bean 在 Temporal 禁用时不存在。

**修复:**
```java
// 错误写法
@RequiredArgsConstructor
public class TemporalMigrationController {
    private final TemporalProperties props;
}

// 正确写法
public class TemporalMigrationController {
    private final TemporalProperties props;

    public TemporalMigrationController(ObjectProvider<TemporalProperties> propsProvider) {
        this.props = propsProvider.getIfAvailable();  // null-safe
    }
}
```

#### 7b. MigrationActivitiesImpl

**现象:** Spring 启动报 `NoSuchBeanDefinitionException: No qualifying bean of type 'AgentTool'`（6 个 AgentTool bean 均不可用）。

**根因:** 所有 `AgentTool` bean 仅在 Temporal 启用时才注册，但 `MigrationActivitiesImpl` 无条件尝试注入它们。

**修复（两处修改）:**
```java
// 1. 类级别：仅在 Temporal 启用时注册此 Bean
@Component
@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")
public class MigrationActivitiesImpl implements MigrationActivities {

    // 2. 字段级别：全部改用 ObjectProvider
    private final ObjectProvider<AgentTool> schemaAnalyzer;
    private final ObjectProvider<AgentTool> typeMapper;
    // ... (6 个字段均为 ObjectProvider)

    public MigrationActivitiesImpl(
        @Qualifier("schemaAnalyzer") ObjectProvider<AgentTool> schemaAnalyzer,
        @Qualifier("typeMapper") ObjectProvider<AgentTool> typeMapper,
        // ...
    ) {
        this.schemaAnalyzer = schemaAnalyzer;
        this.typeMapper = typeMapper;
        // ...
    }
}
```

---

### 坑 #8: GitHub Actions trivy-action 版本被删

**现象:** CI workflow 运行时报:
```
Unable to resolve action aquasecurity/trivy-action@0.24.0
```

**根因:** 2026 年 3 月 Aqua Security 发生供应链攻击（CVE-2026-33634），攻击者删除了 `trivy-action` 中 76/77 个版本标签。`0.24.0` 已永久不可用。

**修复:**
```yaml
# 错误
uses: aquasecurity/trivy-action@0.24.0

# 正确（v0.35.0 为首个修复后安全版本）
uses: aquasecurity/trivy-action@v0.35.0
```

**影响文件:**
- `.github/workflows/supply-chain.yml`（2 处）
- `zhiqian/security/workflows-template/supply-chain.yml`（2 处）

---

### 坑 #9: Docker Compose 配置文件路径与 .env 关系

**易错点:** `docker compose` 默认读取当前目录下的 `.env`。由于配置文件在 `zhiqian/deploy/` 子目录，需注意路径。

```bash
# 错误：如果从项目根目录直接运行，会读根目录的 .env
cd zhixianyunshu && docker compose up

# 正确：指定配置文件路径
docker compose -f zhiqian/deploy/docker-compose.yml up -d

# 或者先切到配置目录
cd zhiqian/deploy && docker compose up -d
```

**关键环境变量（在 `zhiqian/deploy/docker-compose.yml` 中引用）:**
| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEMPORAL_ENABLED` | `false` | 设为 true 会尝试启动 Temporal，需更多依赖 |
| `DEEPSEEK_API_KEY` | 空 | 空值会优雅降级到本地模型 |
| `POSTGRES_PASSWORD` | `zhiqian123` | 数据库密码 |

---

### 坑 #10: Docker 构建缓存与 --no-cache

**场景区分:**
- **首次构建或依赖变更:** 使用 `--no-cache` 确保全新构建
- **代码小幅修改:** 不使用 `--no-cache`，利用 Docker 层缓存加速
- **中国大陆网络:** 优先利用缓存，避免反复从 Docker Hub 拉取

```bash
# 依赖变更时（pom.xml / requirements.txt 等）
docker compose -f zhiqian/deploy/docker-compose.yml build --no-cache backend

# 仅代码修改时（利用缓存）
docker compose -f zhiqian/deploy/docker-compose.yml build backend

# 强制完全重建所有服务
docker compose -f zhiqian/deploy/docker-compose.yml build --no-cache
```

---

## 4. 故障排查速查表

| 症状 | 可能原因 | 检查命令 | 参考坑位 |
|------|----------|----------|----------|
| Docker build 超时 | 网络墙 / syntax 指令 | `docker build --pull=false` | #1 |
| Backend 起不来 (Bean 注入) | Temporal 禁用但 Bean 缺失 | `docker logs <backend>` 搜 `NoSuchBean` | #7a, #7b |
| RAG 起不来 (路由冲突) | APIRouter 缺 prefix | `docker logs <rag>` 搜 `Prefix and path` | #5 |
| `/mcp/manifest` 404 | RAG 镜像缺 mcp.py | `docker exec <rag> ls /app/app/api/` | #6 |
| `/swagger-ui.html` 403 | 缺 springdoc 依赖或 Security 未放行 | 检查 pom.xml + SecurityConfig.java | #3c, #4 |
| `/.well-known/agent.json` 403 | SecurityConfig 未放行 | 检查 SecurityConfig.java | #4 |
| Maven 测试编译失败 | -DskipTests 不跳过编译 | 改用 `-Dmaven.test.skip=true` | #2 |
| CI trivy-action 找不到 | 版本标签被删除 | 升级到 v0.35.0+ | #8 |

---

## 5. 快速修复检查单（新部署时逐项确认）

- [ ] 检查 Dockerfile 无 `# syntax=docker/dockerfile:1.7`（坑 #1）
- [ ] 检查 backend Dockerfile 用 `-Dmaven.test.skip=true`（坑 #2）
- [ ] 检查 `pom.xml` 中 flyway-database-postgresql 有版本号（坑 #3a）
- [ ] 检查 `pom.xml` 中无 mockito-inline 依赖（坑 #3b）
- [ ] 检查 `pom.xml` 中有 springdoc-openapi 依赖（坑 #3c）
- [ ] 检查 `SecurityConfig.java` 放行 `/.well-known/**` 和 `/swagger-ui/**`（坑 #4）
- [ ] 检查 `rag/app/api/*.py` 所有 router 均有 prefix（坑 #5）
- [ ] 检查 `rag/app/api/` 下有 `query.py` 和 `validation.py`（坑 #6）
- [ ] 检查 `TemporalMigrationController` 用 ObjectProvider（坑 #7a）
- [ ] 检查 `MigrationActivitiesImpl` 有 `@ConditionalOnProperty`（坑 #7b）
- [ ] 检查 `supply-chain.yml` 中 trivy-action 版本 ≥ v0.35.0（坑 #8）
- [ ] `curl http://localhost:8080/actuator/health` → UP
- [ ] `curl http://localhost:8001/health` → ok
- [ ] `curl http://localhost:8001/mcp/manifest` → zhiqian-mcp
- [ ] `curl http://localhost:8080/.well-known/agent.json` → sql.transpile
- [ ] `curl http://localhost:8080/swagger-ui.html` → 200

---

## 6. 项目特有约定

- **Temporal 默认不启用:** `app.temporal.enabled=false`，所有相关组件需用 ObjectProvider + Conditional 守卫
- **DeepSeek API Key 为空优雅降级:** 不配 API key 时使用本地模型，不报错
- **CI 模板机制:** `.github/workflows/` 下真正生效的 workflow 由 `scripts/install-supply-chain-workflow.sh` 从 `zhiqian/security/workflows-template/` 模板生成
- **GitHub Actions 表达式易被压缩破坏:** 模板中使用 `$ name `（单 $ + 空格）占位，安装脚本 sed 还原为 `${{ name }}`
- **Docker Compose 可选 Profile:**
  - `--profile ml` 启动 ML 相关（Qdrant 等）
  - `--profile temporal` 启动 Temporal 全家桶
  - `--profile cdc` 启动 Debezium CDC
  - `--profile datasets` 启动公开数据集容器
