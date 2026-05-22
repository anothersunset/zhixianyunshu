# 快速上手

5 分钟从 zero 到 demo 跑起来。心急可跳到§3。

## 1. 检依赖

```bash
java -version    # 要 21+
mvn -v           # 要 3.9+ (或用项目自带 ./mvnw)
python3 -V       # 要 3.11+
node -v          # 要 20+
pnpm -v          # 要 9+ (npm install -g pnpm)
docker -v        # 要 24+
docker compose version
```

一键装 (macOS):
```bash
make install-tools
```

所有版本要求看 [`TOOLS.md`](./TOOLS.md)。

## 2. clone + 静态检

```bash
git clone https://github.com/anothersunset/zhixianyunshu.git
cd zhixianyunshu
make smoke       # 走 web vue-tsc + rag compileall + backend mvn compile
```

smoke 没错说明三路代码都过静态检验。

## 3. 跑 demo

### 3.1 最小集 (不含公开数据集 · 3 个服务)

开 3 个终端:

```bash
# 终端 1 — backend (8080)
make backend

# 终端 2 — RAG (8001)
cd zhiqian/rag
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# 终端 3 — web (5173)
make web
```

验:
```bash
make health      # 7 endpoint 验状态
```
访 [`http://localhost:5173`](http://localhost:5173)。

### 3.2 完整 demo (含 sakila/chinook/sales/CDC · 6 步)

```bash
make demo
# 等同于 bash scripts/demo-walkthrough.sh
# 会拉 mysql:5.7 + openGauss-lite + 入数据 + 启 backend/RAG/web
```

### 3.3 只要看演示幻灯片

启 web 后访 [`http://localhost:5173/#/present`](http://localhost:5173/#/present)。
10 张幻灯, 键盘 `←`/`→` 翻页, `R` 读稿。

## 4. 遇块了

看 [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) — 12 条常见问题 + 定位/修复。

## 5. 有本地修改想提

看 [`CONTRIBUTING.md`](../CONTRIBUTING.md) — 提交规范 + smoke gate + DCO。

## 6. 下一步

- 架构 → [`architecture/00-overall.md`](./architecture/00-overall.md)
- 8 大创新点 → [`innovations.md`](./innovations.md)
- 同类产品对比 → [`comparison.md`](./comparison.md)
- CLI 依赖 → [`TOOLS.md`](./TOOLS.md)
- 决策史 → [`../UPGRADE_PLAN.md`](../UPGRADE_PLAN.md) (70 项决策日志)
- 提交史 → [`../CHANGELOG.md`](../CHANGELOG.md) (50+ 提交明细)
