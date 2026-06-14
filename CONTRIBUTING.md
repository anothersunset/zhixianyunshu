# 贡献指南

欢迎 条拿开 PR 、 issue 、 文档、 demo case 贡献。

## 本地运行

```bash
git clone https://github.com/anothersunset/zhixianyunshu.git
cd zhixianyunshu
bash scripts/smoke-test.sh           # 三路冒烟检 (compile + lint + import + 单测)
bash scripts/demo-walkthrough.sh     # 一键拉 demo
```

### Pre-commit hooks (推荐)

提交前自动运行冒烟检，防止低级错误入库：

```bash
pip install pre-commit
pre-commit install          # 安装 git hooks
pre-commit run --all-files  # 手动跑一次
```

安装后 `git push` 时自动执行 `make smoke`。跳过: `git push --no-verify`。

## Commit message 规范

采 Conventional Commits + scope, 标题后带 *动机* / *影响*:

```
<type>(<scope>): <what> — <why> (<impact>)
```

| type | 意 | 示例 |
| --- | --- | --- |
| `feat` | 新功能 | `feat(rag): GraphRAG 索引 — 跨表表 PL/SQL 依赖可问` |
| `fix` | bug | `fix(web): LocalChat 模板改 v-text — 防 URL 压缩` |
| `refactor` | 重构 | `refactor(backend): MigrationTool 接口抽取` |
| `docs` | 文档 | `docs: TROUBLESHOOTING.md 12 条` |
| `chore` | 杂务 (依、脚本) | `chore(deps): vue-i18n@^9` |
| `test` | 测试 | `test(rag): RAGAS golden set 20` |
| `perf` | 性 | `perf(rag): RRF k=60 调 fusion ranking` |
| `build` | 构建 | `build(backend): Maven 上 JaCoCo 0.8.10` |
| `ci` | CI | `ci: supply-chain workflow template` |
| `security` | 安 | `security: cosign keyless OIDC 签 SBOM` |

scope 常用: `backend` `rag` `web` `deploy` `docs` `bonus` `ci` `security`。

## Branch 策略

- `main` — 发布分支, 只走 PR 进 (需 review)。
- `feat/*` `fix/*` `docs/*` — 特性分支。
- `v*` — tag, 触发完整 CI (supply-chain + image build + cosign sign + GitHub Release)。

### CI 自动化

PR 提交后自动触发：

| Job | 作用 | 阻断合并? |
| --- | --- | --- |
| `backend-test` | Maven compile + test | 是 |
| `frontend-build` | npm ci + build | 是 |
| `rag-lint` | ruff lint + compile + import chain | 是 |
| `labeler` | 按文件路径自动打 PR 标签 | 否 |
| `eval-smoke` | 轻量评测回归 (continue-on-error) | 否 |

### Dependabot

每周一自动检查依赖更新，PR 标签：`dependencies` + 组件名 (`backend`/`rag`/`web`/`ci`)。

## PR Checklist

- [ ] `bash scripts/smoke-test.sh` 本地通过
- [ ] commit message 遵上规范
- [ ] 动主题/架构 → 同步更 `UPGRADE_PLAN.md` 决策日志
- [ ] 动公共 API → 同步更 `README.md` quickstart 与 `docs/`
- [ ] 动依赖 → 重跑 `scripts/smoke-test.sh` 验装
- [ ] 动后端 DTO → web 类型同步 (`pnpm exec vue-tsc --noEmit`)

## DCO (Developer Certificate of Origin)

提交需带 Sign-off (git commit `-s`):

```
Signed-off-by: Your Name <you@example.com>
```

表明你有权提交该代码且同意 Apache-2.0 许可。

## Code style

- **Java**: 4-space, package `com.zhiqian.<scope>`, Spring Boot 3.x conventions。
- **Python**: ruff-clean (`ruff check app --select E,F,W --ignore E501`), type hint 优先, FastAPI v1。
- **TS/Vue**: vue-tsc 零错, `<script setup lang="ts">`, 模板防 URL 压缩不用二重括号 — 走 `v-text` / `v-bind` / `computed`。
- **YAML/K8s**: kustomize 不走 helm template, secret 走 sealed-secrets 或 External Secrets。

## 争议与 Issue

- 启发讨论 → Discussions tab。
- bug / 需求 → Issues tab, 务必附 `smoke-test` 输出与最小复现。
- 供应链 / 安全问题 → 不走公开 issue, 发邮 security@· (占位, 仓主可调)。
