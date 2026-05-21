#!/usr/bin/env bash
# v2-step-29: 一键拉 Sakila / Chinook / Employees 三个公开数据集到 MySQL。
#
# Usage:
#   bash zhiqian/deploy/datasets/bootstrap.sh           # 拉 + 入 mysql:33306
#   DATASETS=sakila,chinook bash bootstrap.sh           # 只拉两个
set -euo pipefail

MYSQL_HOST="${MYSQL_HOST:-127.0.0.1}"
MYSQL_PORT="${MYSQL_PORT:-33306}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_PWD="${MYSQL_PWD:-zhiqian}"
DATASETS="${DATASETS:-sakila,chinook,employees}"
SEED_DIR="$(dirname "$0")/seed"
mkdir -p "$SEED_DIR"

echo "==> [1/4] 检查 mysql client"
command -v mysql >/dev/null 2>&1 || { echo "mysql client not found, brew install mysql-client / apt install mysql-client"; exit 1; }

fetch() {  # fetch <url> <out>
  local url="$1" out="$2"
  if [ -f "$out" ]; then echo "  cached: $out"; return; fi
  echo "  download: $url"
  curl -fL "$url" -o "$out"
}

IFS=',' read -ra DS <<< "$DATASETS"
for d in "${DS[@]}"; do
  case "$d" in
    sakila)
      echo "==> [2/4] sakila"
      fetch "https://downloads.mysql.com/docs/sakila-db.tar.gz" "$SEED_DIR/sakila.tar.gz"
      tar -xzf "$SEED_DIR/sakila.tar.gz" -C "$SEED_DIR"
      mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PWD" < "$SEED_DIR/sakila-db/sakila-schema.sql"
      mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PWD" < "$SEED_DIR/sakila-db/sakila-data.sql"
      ;;
    chinook)
      echo "==> [3/4] chinook"
      fetch "https://github.com/lerocha/chinook-database/raw/master/ChinookDatabase/DataSources/Chinook_MySql.sql" "$SEED_DIR/chinook.sql"
      mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PWD" < "$SEED_DIR/chinook.sql"
      ;;
    employees)
      echo "==> [4/4] employees"
      fetch "https://github.com/datacharmer/test_db/raw/master/employees.sql" "$SEED_DIR/employees.sql"
      mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PWD" < "$SEED_DIR/employees.sql"
      ;;
    *) echo "unknown dataset: $d"; ;;
  esac
done

echo "==> done. 表库列表:"
mysql -h"$MYSQL_HOST" -P"$MYSQL_PORT" -u"$MYSQL_USER" -p"$MYSQL_PWD" -e "SHOW DATABASES;"
