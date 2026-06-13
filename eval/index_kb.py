"""将 KB 文档索引到 RAG 服务 (Qdrant + BGE-M3)。

Usage:
    python -m eval.index_kb [--rag-url http://localhost:8001]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import httpx

RAG_URL_DEFAULT = "http://localhost:8001"
COLLECTION = "zhiqian-default"

# ── 17 条 KB 文档 (来自 ContextRetrieverAgent.java) ──
KB_DOCS: List[Dict[str, Any]] = [
    {
        "id": "kb-syntax-identifier",
        "text": (
            "Identifier quoting: MySQL uses backticks (`) to quote identifiers (table names, column names). "
            "openGauss and PostgreSQL use double quotes (\"). When migrating SQL, replace backticks with double quotes. "
            "Example: SELECT `order_id` FROM `orders` → SELECT \"order_id\" FROM \"orders\". "
            "Reserved keywords that need quoting: ORDER, GROUP, SELECT, TABLE, etc."
        ),
        "source": "kb/syntax/identifier-quoting",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-ifnull",
        "text": (
            "IFNULL / NVL to COALESCE: MySQL IFNULL(x, y) and Oracle NVL(x, y) should be replaced with "
            "COALESCE(x, y) in openGauss/PostgreSQL. COALESCE is SQL standard and supports multiple arguments: "
            "COALESCE(a, b, c) returns the first non-null value. "
            "Example: SELECT IFNULL(name, 'unknown') → SELECT COALESCE(name, 'unknown'). "
            "Note: NVL2(x, y, z) in Oracle maps to CASE WHEN x IS NOT NULL THEN y ELSE z END."
        ),
        "source": "kb/functions/null-handling",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-autoincrement",
        "text": (
            "Auto increment mapping: MySQL AUTO_INCREMENT maps to different strategies in openGauss/PostgreSQL. "
            "For new tables, use GENERATED ALWAYS AS IDENTITY (SQL standard) or SERIAL/BIGSERIAL (legacy). "
            "For existing data migration, use sequences: CREATE SEQUENCE seq_name; then set column default to nextval('seq_name'). "
            "Example: id INT AUTO_INCREMENT → id INTEGER GENERATED ALWAYS AS IDENTITY. "
            "Important: When using SERIAL, the sequence is automatically created but not tied to the column identity."
        ),
        "source": "kb/types/auto-increment",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-enum",
        "text": (
            "Enum type mapping: MySQL ENUM('val1', 'val2') has no direct equivalent in PostgreSQL/openGauss. "
            "Options: 1) Create a custom type: CREATE TYPE mood AS ENUM ('happy', 'sad'); "
            "2) Use VARCHAR with CHECK constraint: status VARCHAR(20) CHECK (status IN ('active', 'inactive')); "
            "3) Use smallint with lookup table for better performance. "
            "Recommendation: Use CHECK constraint for simple cases, custom ENUM type for complex cases."
        ),
        "source": "kb/types/enum-mapping",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-decimal",
        "text": (
            "Decimal/NUMERIC mapping: MySQL DECIMAL(p, s) maps directly to NUMERIC(p, s) or DECIMAL(p, s) in openGauss. "
            "Both are equivalent in PostgreSQL/openGauss. For monetary values, use NUMERIC(20, 4) to avoid floating-point errors. "
            "MySQL NUMBER (Oracle) maps to NUMERIC. Oracle NUMBER(p, s) → NUMERIC(p, s). "
            "Important: MySQL FLOAT/DOUBLE are approximate types; consider NUMERIC for exact precision requirements."
        ),
        "source": "kb/types/decimal-numeric",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-dateformat",
        "text": (
            "Date formatting functions: MySQL DATE_FORMAT(date, format) maps to TO_CHAR(date, format) in openGauss/PostgreSQL. "
            "Format specifiers differ: MySQL %Y-%m-%d → PostgreSQL YYYY-MM-DD. "
            "Common mappings: %Y→YYYY, %m→MM, %d→DD, %H→HH24, %i→MI, %s→SS. "
            "Example: DATE_FORMAT(created_at, '%Y-%m') → TO_CHAR(created_at, 'YYYY-MM'). "
            "Also: MySQL STR_TO_DATE(str, format) → TO_DATE(str, format) in PostgreSQL."
        ),
        "source": "kb/functions/date-format",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-syntax-limit",
        "text": (
            "LIMIT offset syntax: MySQL LIMIT offset, count and PostgreSQL LIMIT count OFFSET offset have reversed order. "
            "MySQL: SELECT * FROM t LIMIT 10, 20 (skip 10, take 20). "
            "PostgreSQL: SELECT * FROM t LIMIT 20 OFFSET 10 (take 20, skip 10). "
            "Oracle uses ROWNUM or ROW_NUMBER() OVER() for pagination. "
            "openGauss supports PostgreSQL-style LIMIT/OFFSET syntax."
        ),
        "source": "kb/syntax/limit-offset",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-groupconcat",
        "text": (
            "GROUP_CONCAT to STRING_AGG: MySQL GROUP_CONCAT(expr SEPARATOR sep) maps to "
            "STRING_AGG(expr::text, sep) in PostgreSQL/openGauss. "
            "Example: GROUP_CONCAT(name SEPARATOR ', ') → STRING_AGG(name, ', '). "
            "Note: STRING_AGG requires explicit type cast (::text) if the expression is not already text. "
            "ORDER BY inside GROUP_CONCAT: GROUP_CONCAT(name ORDER BY name) → STRING_AGG(name, ',' ORDER BY name)."
        ),
        "source": "kb/functions/group-concat",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-syntax-upsert",
        "text": (
            "Upsert syntax: MySQL INSERT ... ON DUPLICATE KEY UPDATE maps to "
            "INSERT ... ON CONFLICT (key) DO UPDATE SET ... in PostgreSQL/openGauss. "
            "Example: INSERT INTO t (id, val) VALUES (1, 'x') ON DUPLICATE KEY UPDATE val='x' "
            "→ INSERT INTO t (id, val) VALUES (1, 'x') ON CONFLICT (id) DO UPDATE SET val='x'. "
            "The ON CONFLICT clause requires specifying the conflict target (unique constraint columns). "
            "DO NOTHING is also supported to silently skip conflicts."
        ),
        "source": "kb/syntax/upsert",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-regexp",
        "text": (
            "Regular expression operator: MySQL REGEXP/RLIKE maps to ~ (case-sensitive) or ~* (case-insensitive) "
            "in PostgreSQL/openGauss. "
            "Example: WHERE name REGEXP '^test' → WHERE name ~ '^test'. "
            "MySQL REGEXP_REPLACE(str, pattern, repl) → regexp_replace(str, pattern, repl) in PostgreSQL. "
            "POSIX regex syntax in PostgreSQL is slightly different from MySQL's regex syntax."
        ),
        "source": "kb/functions/regexp",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-nvl",
        "text": (
            "Oracle NVL mapping: NVL(expr1, expr2) returns expr2 if expr1 is null, otherwise returns expr1. "
            "Direct replacement: NVL(x, y) → COALESCE(x, y). "
            "NVL2(expr1, expr2, expr3): returns expr2 if expr1 is NOT null, else expr3. "
            "NVL2 equivalent: CASE WHEN x IS NOT NULL THEN y ELSE z END, or COALESCE(y, z) if x determines nullability. "
            "openGauss supports COALESCE (SQL standard) but not NVL/NVL2 (Oracle proprietary)."
        ),
        "source": "kb/functions/oracle-nvl",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-sysdate",
        "text": (
            "Oracle SYSDATE mapping: Oracle SYSDATE returns current date and time. "
            "In PostgreSQL/openGauss: CURRENT_TIMESTAMP (with timezone) or LOCALTIMESTAMP (without timezone). "
            "Also: NOW() is equivalent to CURRENT_TIMESTAMP in PostgreSQL. "
            "Example: SELECT SYSDATE FROM dual → SELECT CURRENT_TIMESTAMP; "
            "For date-only: TRUNC(SYSDATE) → CURRENT_DATE or DATE_TRUNC('day', CURRENT_TIMESTAMP)."
        ),
        "source": "kb/functions/oracle-sysdate",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-syntax-dual",
        "text": (
            "Oracle DUAL table: Oracle requires SELECT ... FROM DUAL for expressions without a table. "
            "PostgreSQL/openGauss do not need DUAL; just use SELECT expr directly. "
            "Example: SELECT SYSDATE FROM DUAL → SELECT CURRENT_TIMESTAMP. "
            "If SQL must be compatible with both, create a DUAL view: CREATE VIEW dual AS SELECT 1;"
        ),
        "source": "kb/syntax/oracle-dual",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-syntax-rownum",
        "text": (
            "Oracle ROWNUM mapping: Oracle ROWNUM pseudo-column for row numbering. "
            "For pagination: WHERE ROWNUM <= 10 → LIMIT 10 in PostgreSQL. "
            "For ranked results: Use ROW_NUMBER() OVER (ORDER BY ...) window function. "
            "Example: SELECT * FROM (SELECT t.*, ROWNUM rn FROM t WHERE ROWNUM <= 20) WHERE rn > 10 "
            "→ SELECT * FROM t LIMIT 10 OFFSET 10."
        ),
        "source": "kb/syntax/oracle-rownum",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-decode",
        "text": (
            "Oracle DECODE mapping: DECODE(expr, search1, result1, search2, result2, default) is Oracle's conditional function. "
            "Maps to CASE WHEN in standard SQL: "
            "DECODE(status, 'A', 'Active', 'I', 'Inactive', 'Unknown') "
            "→ CASE status WHEN 'A' THEN 'Active' WHEN 'I' THEN 'Inactive' ELSE 'Unknown' END. "
            "openGauss supports CASE WHEN (SQL standard) but not DECODE (Oracle proprietary)."
        ),
        "source": "kb/functions/oracle-decode",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-join-outer",
        "text": (
            "Oracle outer join: Oracle uses (+) operator for outer joins: WHERE a.id = b.id(+). "
            "Standard SQL LEFT JOIN: FROM a LEFT JOIN b ON a.id = b.id. "
            "The (+) is placed on the side that should have NULLs when no match. "
            "a.id = b.id(+) → LEFT JOIN (b rows can be null). "
            "a.id(+) = b.id → RIGHT JOIN (a rows can be null). "
            "Always convert to explicit JOIN syntax for clarity and portability."
        ),
        "source": "kb/joins/oracle-outer-join",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-substr",
        "text": (
            "SUBSTR/SUBSTRING mapping: MySQL SUBSTR(str, start, length) and SUBSTRING(str, start, length) are interchangeable. "
            "PostgreSQL/openGauss use SUBSTRING(str, start, length) or SUBSTR(str, start, length) — both work. "
            "Key difference: MySQL uses 1-based indexing with negative values counting from end. "
            "Oracle SUBSTR is the same. All are compatible across databases. "
            "Example: SUBSTR('hello', 2, 3) → 'ell' (works the same in all databases)."
        ),
        "source": "kb/functions/substr",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
]

# ── RAG demo 文档 (来自 retriever.py) ──
DEMO_DOCS: List[Dict[str, Any]] = [
    {
        "id": "doc-1",
        "text": (
            "openGauss 不支持 MySQL 的 DATE_FORMAT 函数,需要使用 TO_CHAR 进行格式化。"
            "例如 TO_CHAR(t.created_at, 'YYYY-MM')。格式说明符也不同：%Y→YYYY, %m→MM, %d→DD。"
        ),
        "source": "opengauss/dialect-cheatsheet.md#date-format",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-2",
        "text": (
            "MySQL IFNULL(x, y) 在 openGauss 中可以等价替换为 COALESCE(x, y),两者语义一致。"
            "COALESCE 是 SQL 标准函数,支持多个参数: COALESCE(a, b, c) 返回第一个非 NULL 值。"
        ),
        "source": "opengauss/dialect-cheatsheet.md#null-handling",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-3",
        "text": (
            "从 MySQL 迁移到 openGauss 时,JDBC URL 需从 jdbc:mysql:// 改为 jdbc:opengauss://,"
            "默认端口从 3306 变为 5432。驱动类从 com.mysql.cj.jdbc.Driver 改为 org.opengauss.Driver。"
        ),
        "source": "opengauss/migration-guide.md#jdbc",
        "meta": {"dialect": "openGauss", "category": "CONFIG"},
    },
    {
        "id": "doc-4",
        "text": (
            "openGauss 驱动 GA 版本仅提供 opengauss-jdbc artifact,在 Maven 中需替换 mysql-connector-java。"
            "Maven 坐标: org.opengauss:opengauss-jdbc:版本号。Gradle 也需同步更新依赖。"
        ),
        "source": "opengauss/migration-guide.md#dependency",
        "meta": {"dialect": "openGauss", "category": "DEPENDENCY"},
    },
    {
        "id": "doc-5",
        "text": (
            "建议使用 LIMIT ... OFFSET ... 并明确指定 ORDER BY,openGauss 与 MySQL 在分页语法上兼容,"
            "但顺序需明确。MySQL LIMIT 10, 20 需改写为 LIMIT 20 OFFSET 10 (注意参数顺序反转)。"
        ),
        "source": "opengauss/dialect-cheatsheet.md#pagination",
        "meta": {"dialect": "openGauss", "category": "SQL_REWRITE"},
    },
    {
        "id": "doc-6",
        "text": (
            "BigDecimal 推荐映射为 openGauss 的 NUMERIC(p, s),例如金额使用 NUMERIC(20, 4),避免精度丢失。"
            "MySQL FLOAT/DOUBLE 是近似类型,迁移时应改为 NUMERIC 以保证精确计算。"
        ),
        "source": "opengauss/type-mapping.md#numeric",
        "meta": {"dialect": "openGauss", "category": "TYPE_MAPPING"},
    },
]


def index_docs(rag_url: str, docs: List[Dict[str, Any]], strategy: str = "none") -> dict:
    """调用 RAG /ingest 端点索引文档。"""
    payload = {
        "collection": COLLECTION,
        "docs": docs,
        "strategy": strategy,
    }
    resp = httpx.post(f"{rag_url}/ingest", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Index KB docs to RAG service")
    parser.add_argument("--rag-url", default=RAG_URL_DEFAULT, help="RAG service URL")
    parser.add_argument("--strategy", default="none", help="Chunking strategy: none/semantic/late")
    args = parser.parse_args()

    all_docs = KB_DOCS + DEMO_DOCS
    print(f"Indexing {len(all_docs)} docs ({len(KB_DOCS)} KB + {len(DEMO_DOCS)} demo) to {args.rag_url}...")

    result = index_docs(args.rag_url, all_docs, strategy=args.strategy)
    print(f"OK: docs_received={result['docs_received']}, chunks_inserted={result['chunks_inserted']}, "
          f"strategy={result['strategy_used']}")
    print(f"Capabilities: {json.dumps(result['capabilities'], indent=2)}")


if __name__ == "__main__":
    main()
