# CHANGELOG

> 本文件用人类可读语言逐项记录 v2 升级的所有变更。最新变更在最上方。
>
> 配套 `UPGRADE_PLAN.md` 是路线图("将做什么"),本文件是执行日志("已做了什么")。

## [v2-step-01] 2026-05-21 — 升级路线图基线

**对应提交**:`docs(v2): upgrade roadmap + changelog baseline`

### 动机
用户将整个 v2 升级交由 AI 负责人统筹,需要一份对外可见、可追溯的总路线图与变更日志,确保"每一处改动都讲清楚改了什么、为什么改、影响是什么"。

### 变更项
- 新增 `UPGRADE_PLAN.md`(根目录):决策摘要、提交规范、32 提交总进度表、风险登记册、决策日志
- 新增 `CHANGELOG.md`(根目录,本文件):逐项实施日志

### 影响范围
- 仅文档,不影响任何运行时代码
- 后续每个代码提交都会回写本文件

### 验证方式
- 在 GitHub 仓库根目录查看两个 MD 文件
- `cat UPGRADE_PLAN.md | grep -c '⏳'` 应等于 31(31 个待办)

### 回滚方法
```bash
git revert <本提交 SHA>
```
回滚后路线图丢失,不影响功能。

---

## v1 时期的关键提交(归档)

- `6fa440f5` — v1 最终版:完整 README + LICENSE + .gitignore
- `e434028b` — fix(web): Vue 模板 ` ` 改用 v-text 绕开 URL 压缩冲突
- `96f4709b` — feat(web): Dashboard/Projects/Tasks/Knowledge/Reports/Settings 完整前端
- `f738149d` — fix(rag): Jinja2 自定义分隔符 `<<...>>` 绕开 URL 压缩冲突
- `177e3566` — chore(backend): pom.xml + Postgres V1__init.sql + V2__seed.sql
- `aefbd4fc` — feat(backend): M3-02 内存版 CKG
- `7907a90c` — feat(backend): JWT 安全 + 各 Controller + SSE 演示发射器
- `ac79f9bc` — chore(deploy): docker-compose + Dockerfiles + nginx + .env.example
