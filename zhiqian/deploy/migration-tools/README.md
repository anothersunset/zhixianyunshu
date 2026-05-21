# 迁移工具适配层 (pgloader / Ora2Pg / ZhiQian Native)

> v2-step-22。让用户不被锁定在 ZhiQian 一个工具, 重流量/纯结构走 pgloader / Oracle走 Ora2Pg / 复杂转译走 ZhiQian。

## REST

```bash
curl http://localhost:8080/api/migration-tools | jq

# 推荐 MySQL → openGauss
curl -X POST http://localhost:8080/api/migration-tools/recommend \
  -H 'Content-Type: application/json' \
  -d '{"sourceDialect":"mysql","targetDialect":"opengauss"}' | jq
# => [{id:zhiqian-native, score:0.95}, {id:pgloader, score:0.90}, ...]

# Oracle → openGauss
curl -X POST http://localhost:8080/api/migration-tools/recommend \
  -H 'Content-Type: application/json' \
  -d '{"sourceDialect":"oracle","targetDialect":"opengauss"}' | jq
# => [{id:zhiqian-native, score:0.95}, {id:mtk-ora2pg, score:0.92}, ...]
```

## 起 docker

```bash
docker compose -f zhiqian/deploy/migration-tools/docker-compose.yml --profile migration-tools up -d

# pgloader
docker exec migration-tools-pgloader-1 pgloader /scripts/pgloader-mysql-to-opengauss.load

# ora2pg
docker exec migration-tools-ora2pg-1 ora2pg -c /scripts/ora2pg.conf -t TABLE -o /output/tables.sql
ls -la zhiqian/deploy/migration-tools/output/
```

## 设计考量

- ZhiQian 不是销售唯一选, 是 **smart layer**: 带上下文 + 可解释性 + 人机反馈
- pgloader: 高吞吐但 schema-only, 适底层结构 + 多表并发全量迁
- Ora2Pg: PL/SQL 主场, 企业资深 DBA 熟悉
- 未来可接入 AWS DMS / Alibaba DTS / DataX 为 additional adapters

## 选型决策树

```
不含过程/触发器, MySQL 起点, 要极高吞吐?  → pgloader
Oracle PL/SQL 为主, 需评估报告?               → Ora2Pg/SSMA + ZhiQian 补齐译难点
跨方言 + 需说明变动原因 + 可交互修复?        → ZhiQian Native
```
