## 这个 PR 做什么
<!-- 一句话, 点明动机 + 影响 -->

## 变更类型
- [ ] feat (新功能)
- [ ] fix (bug)
- [ ] refactor (不改行为)
- [ ] perf (性)
- [ ] docs / test / chore / ci / security

## 检查单
- [ ] `bash scripts/smoke-test.sh` 本地通过
- [ ] 提交 message 遵 Conventional Commits (看 CONTRIBUTING.md)
- [ ] 动主题/架构 → 同步更 `UPGRADE_PLAN.md` 决策日志
- [ ] 动公共 API → 同步更 `README.md` quickstart / `docs/`
- [ ] 动依赖 → `package.json` / `pom.xml` / `requirements.txt` 同步
- [ ] 动后端 DTO → web 类型同步 (`pnpm exec vue-tsc --noEmit`)
- [ ] commit 带 `Signed-off-by` (DCO)

## 如有破坏性变更
<!-- 说明调用方需怎么改, 及迁移路径 -->

## 附截图 / 输出
<!-- 可选: 前端变贴图; 接口贴 curl 输出 -->

## 关联 issue
<!-- Closes #N / Refs #N -->
