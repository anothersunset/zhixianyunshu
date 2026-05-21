# Troubleshooting

12 条常见问题。遇到时考备 issue 检查表。

## 1. `pnpm install` 报 vue-i18n peer warn

**现象**: `» peer vue@^3.0.0 not found from vue-i18n@9.x`。

**原因**: lockfile 还是 v0.4.0, vue-i18n 刚加。

**修**: `cd zhiqian/web && rm pnpm-lock.yaml && pnpm install`。

---

## 2. `vue-tsc` 报 `Cannot find module '@xenova/transformers'`

**原因**: 有意设为 optionalDeps, 本地未装。

**修**: 不需修 — `useLocalLlm.ts` 已 `// @ts-ignore` + dynamic import 处理。
若什么要本地玩端侧推理: `pnpm add @xenova/transformers`。

---

## 3. FastAPI 启动报 `ImportError: tts` 或 `reports`

**原因**: `app.api.tts` 或 `app.api.reports` 依未装 (typst CLI / edge-tts)。

**修**: 装 + 重启:

```bash
pip install edge-tts          # #26 TTS
brew install typst             # #27 PDF (或 cargo install typst-cli)
uvicorn app.main:app --reload
```

未装会 503 优雅返, 不会崩。

---

## 4. `/reports/generate` 返 503

**原因**: typst CLI 不在 PATH。

**验**: `typst --version` 能出版本。

**修**: `brew install typst` (macOS) / `cargo install --locked typst-cli` / [下载 release binary](https://github.com/typst/typst/releases)。

---

## 5. `/api/tts/speak` 返 503 "edge-tts CLI not in PATH"

**原因**: backend ProcessBuilder 调 `edge-tts` 不到。

**修**: 

```bash
pip install edge-tts
edge-tts --version              # 验证
SPRING_PROFILES_ACTIVE=tts ./mvnw spring-boot:run
```

前端优雅 fallback 到 `window.speechSynthesis`, 不装也能读。

---

## 6. WebGPU 不可用 / `/edge` 页加载卡住

**原因**: 浏览器不启 WebGPU。

**修**: 

- Chrome 113+ / Edge 113+ / Safari 17.4+ 默启。
- 旧版: `chrome://flags/#enable-unsafe-webgpu` 启。
- 未启会自动降 WASM, 首次加 ~ 600MB 较慢。

---

## 7. Cytoscape CKG 页闪白 / `fcose` 报错

**原因**: dynamic import 未完成。

**修**: 等 1-2s 或 hard reload (Cmd+Shift+R)。若报 `fcose extension not found`: `pnpm install` 重装 cytoscape-fcose。

---

## 8. ArgoCD `prod` Application out-of-sync

**原因**: ignoreDifferences 包 `replicas` 与 `Secret.data`, 是预期表现 (HPA 与 External Secrets 扣管)。

**修**: 不需修, 是设计。若误报: `kubectl describe app prod-zhiqian -n argocd` 看真原因。

---

## 9. Debezium connector 报 `database not in row format`

**原因**: MySQL 未启 binlog ROW 格式。

**修**: 

```sql
SET GLOBAL binlog_format = 'ROW';
SET GLOBAL binlog_row_image = 'FULL';
-- 或 my.cnf: binlog_format=ROW, binlog_row_image=FULL
```

---

## 10. Supply-chain workflow 装 后 仍报 `Unexpected token '<'`

**原因**: `install-supply-chain-workflow.sh` 未跳 sed, 原始占位符 `$ ctx ` 仍存。

**修**: 

```bash
grep -cE '\$ [a-z]' .github/workflows/supply-chain.yml
# 不为 0 说明 sed 未生效, 重跑:
bash scripts/install-supply-chain-workflow.sh
```

---

## 11. Backend `application-tts.yml` 没生效

**原因**: 未启 profile=tts。

**修**: `SPRING_PROFILES_ACTIVE=tts,dev ./mvnw spring-boot:run`。
验: `curl http://localhost:8080/api/tts/status` 返 `{"enabled":true}`。

---

## 12. `bash scripts/demo-walkthrough.sh` 拉 mysql 报 端口被占

**原因**: 主栈 mysql 已启, 与 datasets profile 33306 冲 (应不冲, 但某些机型错配)。

**修**: `MYSQL_PORT=43306 bash scripts/demo-walkthrough.sh` 或 `docker compose -f zhiqian/deploy/datasets/docker-compose.yml down`。

---

## 额外: Vue 模板二重大括号被吞

**原因**: Notion AI URL 压缩 / 某些 copy-paste 场景脱转义二重括号。

**修**: 所有动态 binding 走 `v-text`/`v-bind`/`computed`, 不在模板写二重括号。看 `LocalChat.vue` 为型。
