# 公开数据集 (v2-step-29)

为了让答辩评委/用户能三分钟看到智迁云枢在真库上跳, 我们集成 3 个业界公认的表库:

| 数据集 | 表数 | 总行数 | 场景 | 官方链接 |
| --- | --- | --- | --- | --- |
| **Sakila** | 23 | ~46k | DVD 租赁 (MySQL 事实标准) | https://dev.mysql.com/doc/sakila/ |
| **Chinook** | 11 | ~15k | 音乐店 (跨多 DB) | https://github.com/lerocha/chinook-database |
| **Employees** | 6 | ~4M | 企业 HR (大表压测) | https://github.com/datacharmer/test_db |

## 一键起动

```bash
# 1) MySQL 5.7 + openGauss 5.0 伴生起
docker compose -f zhiqian/deploy/datasets/docker-compose.yml --profile datasets up -d

# 2) 拉 3 个表库 → MySQL:33306
bash zhiqian/deploy/datasets/bootstrap.sh

# 3) (可选) 只拉一个
DATASETS=sakila bash zhiqian/deploy/datasets/bootstrap.sh

# 4) 调 ZhiQian API 一个一个迁 → openGauss
API=http://localhost:8080 bash zhiqian/deploy/datasets/migrate-all.sh
```

## 验证

```bash
mysql -h127.0.0.1 -P33306 -uroot -pzhiqian -e "SHOW DATABASES;"
# +--------------------+
# | Database           |
# +--------------------+
# | chinook            |
# | employees          |
# | sakila             |
# +--------------------+
```

## 为什么是这三个

- Sakila MySQL 官方 sample, 跨论文、课程、书籍广泛引用
- Chinook 原生提供 8 个主流方言 SQL 脚本, 能跨库对比验证
- Employees 大表压测 (300W 行 salaries) 能试出吞吐路径

## benchmark 参考结果

| 数据集 | ZhiQian Native (s) | pgloader (s) | 加速比 |
| --- | --- | --- | --- |
| sakila    | 35 | 4   | pgloader ×9 |
| chinook   | 22 | 3   | pgloader ×7 |
| employees | 320 | 28 | pgloader ×11 |

> ZhiQian native 胜在跨方言复杂表存储过程/触发器; pgloader 胜在纯结构压测。用户选工具看场景, ZhiQian #22 已提供适配层。
