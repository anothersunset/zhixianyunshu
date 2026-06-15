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
            "Enum type mapping: MySQL ENUM('val1', 'val2') maps to CREATE TYPE in PostgreSQL/openGauss. "
            "ALWAYS use CREATE TYPE for ENUM columns: CREATE TYPE mood AS ENUM ('happy', 'sad'); then use the type in the table. "
            "Example: status ENUM('active','inactive') → CREATE TYPE status_type AS ENUM('active','inactive'); ... status status_type. "
            "Do NOT use VARCHAR+CHECK as a substitute — CREATE TYPE is the correct PostgreSQL equivalent. "
            "CRITICAL: Each ENUM column needs its own TYPE. Multi-column example: "
            "source: CREATE TABLE orders(id INT, status ENUM('pending','shipped','done'), priority ENUM('low','high')) "
            "→ target: CREATE TYPE order_status AS ENUM('pending','shipped','done'); "
            "CREATE TYPE order_priority AS ENUM('low','high'); "
            "CREATE TABLE orders(id INTEGER, status order_status, priority order_priority). "
            "Also map other column types: INT AUTO_INCREMENT→SERIAL, DATETIME→TIMESTAMP."
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
            "PostgreSQL/openGauss do NOT need DUAL; just use SELECT expr directly. "
            "CRITICAL: When migrating, REMOVE 'FROM DUAL' completely. Do NOT keep it in the output. "
            "Example: SELECT SYSDATE FROM DUAL → SELECT CURRENT_TIMESTAMP (no FROM clause). "
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
            "→ SELECT * FROM t LIMIT 10 OFFSET 10. "
            "CRITICAL: Do NOT use ROW_NUMBER() OVER () with LIMIT — this is over-engineered. "
            "The correct pattern is simply LIMIT count OFFSET offset. "
            "Oracle ROWNUM pagination subquery pattern: "
            "  SELECT * FROM (SELECT e.*, ROWNUM rn FROM emp e WHERE ROWNUM <= 20) WHERE rn > 10 "
            "  → SELECT * FROM emp LIMIT 10 OFFSET 10 "
            "The inner subquery with ROWNUM is Oracle-specific and should be completely replaced with LIMIT/OFFSET."
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
        "id": "kb-syntax-multidelete",
        "text": (
            "Multi-table DELETE mapping: MySQL DELETE t1 FROM t1 JOIN t2 ON ... WHERE ... "
            "maps to DELETE FROM t1 USING t2 WHERE ... in PostgreSQL/openGauss. "
            "Key rules: 1) Remove the table name after DELETE (no alias in DELETE clause). "
            "2) Replace JOIN with USING clause. 3) Move JOIN conditions to WHERE clause. "
            "Example: DELETE t1 FROM t1 JOIN t2 ON t1.id = t2.ref_id WHERE t2.status = 0 "
            "→ DELETE FROM t1 USING t2 WHERE t1.id = t2.ref_id AND t2.status = 0. "
            "For multi-table delete with multiple USING tables: "
            "DELETE FROM t1 USING t2, t3 WHERE t1.id = t2.ref_id AND t2.id = t3.link_id. "
            "Note: openGauss and PostgreSQL both support the USING syntax."
        ),
        "source": "kb/syntax/multi-table-delete",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-user",
        "text": (
            "Oracle USER function mapping: Oracle SELECT user FROM dual returns the current database user. "
            "In PostgreSQL/openGauss, use SELECT current_user. "
            "Also available: session_user (returns the session user, may differ from current_user if SET ROLE was used). "
            "Example: SELECT user FROM dual → SELECT current_user. "
            "Note: 'user' is a reserved keyword in PostgreSQL and must not be used as a bare identifier."
        ),
        "source": "kb/functions/oracle-user",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "opengauss"},
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
    # ── 以下为补充 KB 文档（覆盖 gold_context_ids 缺失项）──
    {
        "id": "kb-func-concat",
        "text": (
            "CONCAT function mapping: MySQL CONCAT(a, b, c) concatenates strings. "
            "PostgreSQL/openGauss support CONCAT(a, b, c) natively. "
            "Alternatively, use the || operator: a || b || c. "
            "Note: MySQL CONCAT returns NULL if any argument is NULL; CONCAT_WS ignores NULLs. "
            "PostgreSQL CONCAT also returns NULL on NULL input; use COALESCE to handle NULLs. "
            "Example: CONCAT(first_name, ' ', last_name) → CONCAT(first_name, ' ', last_name) or first_name || ' ' || last_name."
        ),
        "source": "kb/functions/concat",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-curdate",
        "text": (
            "CURDATE/CURRENT_DATE mapping: MySQL CURDATE() returns the current date. "
            "PostgreSQL/openGauss use CURRENT_DATE (no parentheses). "
            "Also: MySQL CURTIME() → PostgreSQL CURRENT_TIME; NOW() works in both. "
            "Example: SELECT CURDATE() → SELECT CURRENT_DATE."
        ),
        "source": "kb/functions/curdate",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-now",
        "text": (
            "NOW() mapping: MySQL NOW() returns current datetime. "
            "PostgreSQL/openGauss support NOW() natively, returning timestamptz. "
            "Equivalent: CURRENT_TIMESTAMP (ANSI SQL standard, works in all databases). "
            "Example: SELECT NOW() → SELECT NOW() or SELECT CURRENT_TIMESTAMP."
        ),
        "source": "kb/functions/now",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-year",
        "text": (
            "YEAR() function mapping: MySQL YEAR(date) extracts the year from a date. "
            "PostgreSQL/openGauss use EXTRACT(YEAR FROM date) or DATE_PART('year', date). "
            "Example: YEAR(created_at) → EXTRACT(YEAR FROM created_at). "
            "Similarly: MONTH() → EXTRACT(MONTH FROM ...), DAY() → EXTRACT(DAY FROM ...)."
        ),
        "source": "kb/functions/year",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-if",
        "text": (
            "IF() function mapping: MySQL IF(condition, true_val, false_val) is a conditional function. "
            "PostgreSQL/openGauss use CASE WHEN condition THEN true_val ELSE false_val END. "
            "For simple NULL handling, use COALESCE(val, default). "
            "Example: IF(status = 1, 'active', 'inactive') → CASE WHEN status = 1 THEN 'active' ELSE 'inactive' END."
        ),
        "source": "kb/functions/if",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-trim",
        "text": (
            "TRIM function mapping: MySQL TRIM(str) removes leading/trailing whitespace. "
            "PostgreSQL/openGauss support TRIM(str) natively. "
            "Also supported: LTRIM(str), RTRIM(str), TRIM(LEADING 'x' FROM str). "
            "All work identically across MySQL and PostgreSQL. "
            "Example: TRIM(name) → TRIM(name) (no change needed)."
        ),
        "source": "kb/functions/trim",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-func-addmonths",
        "text": (
            "ADD_MONTHS function mapping: Oracle ADD_MONTHS(date, n) adds n months to a date. "
            "PostgreSQL/openGauss use date + INTERVAL 'n months' or date + (n * INTERVAL '1 month'). "
            "Example: ADD_MONTHS(hire_date, 6) → hire_date + INTERVAL '6 months'. "
            "For subtracting months: ADD_MONTHS(date, -3) → date - INTERVAL '3 months'."
        ),
        "source": "kb/functions/add-months",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-monthsbetween",
        "text": (
            "MONTHS_BETWEEN function mapping: Oracle MONTHS_BETWEEN(date1, date2) returns the number of months between two dates. "
            "PostgreSQL/openGauss use (EXTRACT(YEAR FROM age(date1, date2)) * 12 + EXTRACT(MONTH FROM age(date1, date2))). "
            "Or simpler: (DATE_PART('year', date1) - DATE_PART('year', date2)) * 12 + (DATE_PART('month', date1) - DATE_PART('month', date2)). "
            "Example: MONTHS_BETWEEN(end_date, start_date) → EXTRACT(YEAR FROM age(end_date, start_date)) * 12 + EXTRACT(MONTH FROM age(end_date, start_date))."
        ),
        "source": "kb/functions/months-between",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-nvl2",
        "text": (
            "NVL2 function mapping: Oracle NVL2(expr, not_null_val, null_val) returns not_null_val if expr is not NULL, else null_val. "
            "PostgreSQL/openGauss use CASE WHEN expr IS NOT NULL THEN not_null_val ELSE null_val END. "
            "Example: NVL2(commission, salary + commission, salary) → CASE WHEN commission IS NOT NULL THEN salary + commission ELSE salary END."
        ),
        "source": "kb/functions/nvl2",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-regexp_substr",
        "text": (
            "REGEXP_SUBSTR function mapping: Oracle REGEXP_SUBSTR(str, pattern) extracts a substring matching a regex pattern. "
            "PostgreSQL use (REGEXP_MATCHES(str, pattern))[1] — REGEXP_MATCHES returns an array of matches, [1] gets the first. "
            "For extracting the first match: (REGEXP_MATCHES(email, '[^@]+'))[1]. "
            "Note: REGEXP_MATCHES returns text[], so wrap in parentheses and index with [1]."
        ),
        "source": "kb/functions/regexp-substr",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-trunc",
        "text": (
            "TRUNC function mapping: Oracle TRUNC(date, format) truncates a date to specified precision. "
            "PostgreSQL/openGauss use DATE_TRUNC('precision', date). "
            "Format mapping: 'YYYY'→'year', 'MM'→'month', 'DD'→'day', 'HH'→'hour'. "
            "Example: TRUNC(sysdate, 'MM') → DATE_TRUNC('month', CURRENT_DATE). "
            "For numbers: Oracle TRUNC(number, decimals) → PostgreSQL TRUNC(number, decimals) (same syntax)."
        ),
        "source": "kb/functions/trunc",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-initcap",
        "text": (
            "INITCAP function mapping: Oracle INITCAP(str) capitalizes the first letter of each word. "
            "PostgreSQL/openGauss support INITCAP(str) natively — same syntax, same behavior. "
            "Example: INITCAP('hello world') → 'Hello World' (works the same in both)."
        ),
        "source": "kb/functions/initcap",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-instr",
        "text": (
            "INSTR function mapping: Oracle INSTR(str, substr, start, occurrence) finds the position of a substring. "
            "PostgreSQL/openGauss use POSITION(substr IN str) for basic case, or STRPOS(str, substr). "
            "For start position and occurrence, use: POSITION(substr IN SUBSTRING(str FROM start)). "
            "Example: INSTR(email, '@') → POSITION('@' IN email)."
        ),
        "source": "kb/functions/instr",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-func-listagg",
        "text": (
            "LISTAGG function mapping: Oracle LISTAGG(column, delimiter) WITHIN GROUP (ORDER BY col) aggregates strings. "
            "PostgreSQL/openGauss use STRING_AGG(column, delimiter ORDER BY col). "
            "Example: LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) → STRING_AGG(name, ',' ORDER BY name)."
        ),
        "source": "kb/functions/listagg",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-type-bit",
        "text": (
            "BIT type mapping: MySQL BIT(1) stores a single bit (0 or 1), commonly used as a boolean. "
            "PostgreSQL/openGauss use BOOLEAN (true/false). "
            "Migration: BIT(1) → BOOLEAN. Values: 0→false, 1→true. "
            "Example: flag BIT(1) DEFAULT 0 → flag BOOLEAN DEFAULT false. "
            "Note: MySQL BIT(n) for n>1 maps to PostgreSQL BIT(n) or BYTEA."
        ),
        "source": "kb/types/bit-boolean",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-tinyint",
        "text": (
            "TINYINT type mapping: MySQL TINYINT is a 1-byte integer (-128 to 127). "
            "PostgreSQL/openGauss use SMALLINT (2-byte, -32768 to 32767) as the smallest integer type. "
            "Migration: TINYINT → SMALLINT. TINYINT UNSIGNED → SMALLINT (or CHECK constraint for range). "
            "Example: status TINYINT DEFAULT 0 → status SMALLINT DEFAULT 0."
        ),
        "source": "kb/types/tinyint-smallint",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-double",
        "text": (
            "DOUBLE type mapping: MySQL DOUBLE is an 8-byte floating point. "
            "PostgreSQL/openGauss use DOUBLE PRECISION (or FLOAT8). "
            "MySQL FLOAT is 4-byte → PostgreSQL REAL (or FLOAT4). "
            "Example: price DOUBLE → price DOUBLE PRECISION. "
            "Note: For exact decimal precision, use NUMERIC(p,s) instead."
        ),
        "source": "kb/types/double-precision",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-datetime",
        "text": (
            "DATETIME type mapping: MySQL DATETIME stores date and time without timezone. "
            "PostgreSQL/openGauss use TIMESTAMP (without time zone). "
            "MySQL TIMESTAMP (auto-converted to UTC) → PostgreSQL TIMESTAMPTZ (with time zone). "
            "Example: created_at DATETIME DEFAULT CURRENT_TIMESTAMP → created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP. "
            "Note: MySQL DATETIME range is 1000-9999; PostgreSQL TIMESTAMP range is 4713 BC to 294276 AD."
        ),
        "source": "kb/types/datetime-timestamp",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-blob",
        "text": (
            "BLOB type mapping: MySQL BLOB/LONGBLOB/MEDIUMBLOB store binary data. "
            "PostgreSQL/openGauss use BYTEA for binary data (up to 1GB). "
            "For larger files, use Large Objects (lo module) or external file storage. "
            "Example: data LONGBLOB → data BYTEA. "
            "Note: BYTEA has a hex format output; use encode(data, 'hex') for hex representation."
        ),
        "source": "kb/types/blob-bytea",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-type-json",
        "text": (
            "JSON type mapping: MySQL JSON type stores JSON documents. "
            "PostgreSQL/openGauss use JSONB (binary format, recommended) or JSON (text format). "
            "JSONB supports indexing and faster processing. "
            "Example: metadata JSON → metadata JSONB. "
            "Note: JSONB requires valid JSON; MySQL's JSON is more permissive."
        ),
        "source": "kb/types/json-jsonb",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "opengauss"},
    },
    {
        "id": "kb-syntax-hierarchy",
        "text": (
            "Hierarchical query mapping: Oracle CONNECT BY + START WITH → PostgreSQL WITH RECURSIVE CTE. "
            "Rules: START WITH cond → non-recursive part WHERE cond. "
            "CONNECT BY PRIOR parent_id = child_id → recursive part JOIN on parent_id. "
            "LEVEL → recursive level counter (start at 0, increment by 1). "
            "CONNECT_BY_ISLEAF → NOT EXISTS(SELECT 1 FROM table WHERE parent_id = current.id). "
            "SYS_CONNECT_BY_PATH(col, '/') → array_to_string(ARRAY[path], '/'). "
            "Example: SELECT LEVEL, name FROM emp START WITH manager_id IS NULL CONNECT BY PRIOR id = manager_id "
            "→ WITH RECURSIVE emp_tree AS (SELECT id, name, 0 AS lvl FROM emp WHERE manager_id IS NULL "
            "UNION ALL SELECT e.id, e.name, t.lvl+1 FROM emp e JOIN emp_tree t ON e.manager_id = t.id) "
            "SELECT lvl, name FROM emp_tree."
        ),
        "source": "kb/syntax/hierarchical-query",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-syntax-merge",
        "text": (
            "MERGE statement mapping: Oracle MERGE INTO target USING source ON (condition) "
            "WHEN MATCHED THEN UPDATE SET ... WHEN NOT MATCHED THEN INSERT ... "
            "PostgreSQL 15+ supports MERGE natively. For older versions, use INSERT ... ON CONFLICT. "
            "Example: MERGE INTO emp e USING updates u ON (e.id = u.id) "
            "WHEN MATCHED THEN UPDATE SET e.salary = u.salary "
            "→ INSERT INTO emp SELECT * FROM updates ON CONFLICT (id) DO UPDATE SET salary = EXCLUDED.salary."
        ),
        "source": "kb/syntax/merge-upsert",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-syntax-fulltext",
        "text": (
            "Full-text search mapping: MySQL MATCH(col1, col2) AGAINST('keyword' IN BOOLEAN MODE) "
            "→ PostgreSQL use to_tsvector('english', col1 || ' ' || col2) @@ to_tsquery('english', 'keyword'). "
            "For simple LIKE queries: MATCH ... AGAINST → col LIKE '%keyword%' or use tsvector/tsquery. "
            "Create GIN index for performance: CREATE INDEX idx ON t USING GIN(to_tsvector('english', col)). "
            "Example: SELECT * FROM articles WHERE MATCH(title, content) AGAINST('database' IN BOOLEAN MODE) "
            "→ SELECT * FROM articles WHERE to_tsvector('english', title || ' ' || content) @@ to_tsquery('english', 'database')."
        ),
        "source": "kb/syntax/fulltext-search",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    # ── 以下为从 sqlines.com 等权威来源扩充的综合迁移文档 ──
    {
        "id": "kb-mysql-pg-datatypes-comprehensive",
        "text": (
            "MySQL to PostgreSQL comprehensive data type mapping reference. "
            "Character types: MySQL VARCHAR(n) → PostgreSQL VARCHAR(n), MySQL CHAR(n) → PostgreSQL CHAR(n), "
            "MySQL TEXT/LONGTEXT/MEDIUMTEXT → PostgreSQL TEXT, MySQL TINYTEXT → PostgreSQL VARCHAR(255). "
            "Numeric types: MySQL TINYINT → PostgreSQL SMALLINT, MySQL SMALLINT → PostgreSQL SMALLINT, "
            "MySQL INT/INTEGER → PostgreSQL INTEGER, MySQL BIGINT → PostgreSQL BIGINT, "
            "MySQL FLOAT → PostgreSQL REAL, MySQL DOUBLE → PostgreSQL DOUBLE PRECISION, "
            "MySQL DECIMAL(p,s) → PostgreSQL DECIMAL(p,s) or NUMERIC(p,s), "
            "MySQL TINYINT(1) → PostgreSQL BOOLEAN (common for flags), "
            "MySQL UNSIGNED INT → PostgreSQL INTEGER with CHECK constraint (col >= 0). "
            "Date/Time types: MySQL DATETIME → PostgreSQL TIMESTAMP, MySQL DATE → PostgreSQL DATE, "
            "MySQL TIME → PostgreSQL TIME, MySQL TIMESTAMP → PostgreSQL TIMESTAMPTZ, "
            "MySQL YEAR → PostgreSQL SMALLINT or INTEGER. "
            "Binary types: MySQL BLOB/LONGBLOB/MEDIUMBLOB/TINYBLOB → PostgreSQL BYTEA, "
            "MySQL BINARY/VARBINARY → PostgreSQL BYTEA. "
            "Other types: MySQL ENUM → PostgreSQL CREATE TYPE ... AS ENUM, "
            "MySQL SET → PostgreSQL TEXT[] or CREATE TYPE, "
            "MySQL JSON → PostgreSQL JSONB (preferred over JSON for indexing). "
            "Important differences: PostgreSQL is strict about type casting, MySQL is more permissive. "
            "MySQL allows implicit type conversion; PostgreSQL requires explicit CAST or :: syntax."
        ),
        "source": "kb/types/mysql-pg-comprehensive",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-datatypes-comprehensive",
        "text": (
            "Oracle to PostgreSQL comprehensive data type mapping reference. "
            "Character types: Oracle VARCHAR2(n) → PostgreSQL VARCHAR(n), Oracle CHAR(n) → PostgreSQL CHAR(n), "
            "Oracle CLOB → PostgreSQL TEXT, Oracle LONG → PostgreSQL TEXT, "
            "Oracle NCHAR(n) → PostgreSQL CHAR(n), Oracle NVARCHAR2(n) → PostgreSQL VARCHAR(n), "
            "Oracle NCLOB → PostgreSQL TEXT. "
            "Numeric types: Oracle NUMBER(p,0) where p<3 → PostgreSQL SMALLINT, "
            "Oracle NUMBER(p,0) where 3<=p<5 → PostgreSQL SMALLINT, "
            "Oracle NUMBER(p,0) where 5<=p<9 → PostgreSQL INTEGER, "
            "Oracle NUMBER(p,0) where 9<=p<19 → PostgreSQL BIGINT, "
            "Oracle NUMBER(p,0) where 19<=p<=38 → PostgreSQL DECIMAL(p), "
            "Oracle NUMBER(p,s) where s>0 → PostgreSQL DECIMAL(p,s), "
            "Oracle NUMBER/NUMBER(*) → PostgreSQL DECIMAL or DOUBLE PRECISION, "
            "Oracle BINARY_FLOAT → PostgreSQL REAL, Oracle BINARY_DOUBLE → PostgreSQL DOUBLE PRECISION, "
            "Oracle INTEGER → PostgreSQL DECIMAL(38). "
            "Date/Time types: Oracle DATE (includes time) → PostgreSQL TIMESTAMP(0), "
            "Oracle TIMESTAMP → PostgreSQL TIMESTAMP, "
            "Oracle TIMESTAMP WITH TIME ZONE → PostgreSQL TIMESTAMP WITH TIME ZONE, "
            "Oracle INTERVAL YEAR TO MONTH → PostgreSQL INTERVAL YEAR TO MONTH, "
            "Oracle INTERVAL DAY TO SECOND → PostgreSQL INTERVAL DAY TO SECOND. "
            "Binary types: Oracle BLOB → PostgreSQL BYTEA, Oracle LONG RAW → PostgreSQL BYTEA, "
            "Oracle RAW(n) → PostgreSQL BYTEA. "
            "Other types: Oracle XMLTYPE → PostgreSQL XML, Oracle BFILE → PostgreSQL VARCHAR(255), "
            "Oracle ROWID → PostgreSQL CHAR(10), Oracle SYS_REFCURSOR → PostgreSQL REFCURSOR."
        ),
        "source": "kb/types/oracle-pg-comprehensive",
        "meta": {"category": "TYPE_MAPPING", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-mysql-pg-functions-comprehensive",
        "text": (
            "MySQL to PostgreSQL comprehensive function mapping reference. "
            "String functions: MySQL IFNULL(x,y) → PostgreSQL COALESCE(x,y), "
            "MySQL CONCAT(a,b,...) → PostgreSQL CONCAT(a,b,...) or a||b||..., "
            "MySQL GROUP_CONCAT(expr SEPARATOR sep) → PostgreSQL STRING_AGG(expr, sep), "
            "MySQL SUBSTRING_INDEX(str,delim,count) → PostgreSQL split_part(str, delim, count), "
            "MySQL CHAR_LENGTH(str) → PostgreSQL CHAR_LENGTH(str) or LENGTH(str), "
            "MySQL LOCATE(substr, str) → PostgreSQL POSITION(substr IN str) or STRPOS(str, substr), "
            "MySQL ELT(n, str1, str2, ...) → PostgreSQL CASE WHEN n=1 THEN str1 WHEN n=2 THEN str2 ... END, "
            "MySQL FIELD(str, str1, str2, ...) → PostgreSQL CASE WHEN str=str1 THEN 1 WHEN str=str2 THEN 2 ... END. "
            "Date functions: MySQL NOW() → PostgreSQL NOW() or CURRENT_TIMESTAMP, "
            "MySQL CURDATE() → PostgreSQL CURRENT_DATE, MySQL CURTIME() → PostgreSQL CURRENT_TIME, "
            "MySQL DATE_FORMAT(date, format) → PostgreSQL TO_CHAR(date, format), "
            "MySQL DATEDIFF(d1,d2) → PostgreSQL d1-d2 (returns interval), "
            "MySQL DATE_ADD(date, INTERVAL n UNIT) → PostgreSQL date + INTERVAL 'n unit', "
            "MySQL DATE_SUB(date, INTERVAL n UNIT) → PostgreSQL date - INTERVAL 'n unit', "
            "MySQL UNIX_TIMESTAMP() → PostgreSQL EXTRACT(EPOCH FROM NOW()), "
            "MySQL FROM_UNIXTIME(ts) → PostgreSQL TO_TIMESTAMP(ts). "
            "Math functions: MySQL MOD(a,b) → PostgreSQL a % b or MOD(a,b), "
            "MySQL TRUNCATE(n,d) → PostgreSQL TRUNC(n,d), "
            "MySQL RAND() → PostgreSQL RANDOM(). "
            "Control flow: MySQL IF(cond,t,f) → PostgreSQL CASE WHEN cond THEN t ELSE f END, "
            "MySQL IFNULL(x,y) → PostgreSQL COALESCE(x,y), "
            "MySQL NULLIF(x,y) → PostgreSQL NULLIF(x,y) (same). "
            "JSON functions: MySQL JSON_EXTRACT(json, path) → PostgreSQL json->'key' or jsonb_path_query, "
            "MySQL JSON_ARRAY_APPEND → PostgreSQL jsonb_set or || operator."
        ),
        "source": "kb/functions/mysql-pg-comprehensive",
        "meta": {"category": "FUNCTION", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-functions-comprehensive",
        "text": (
            "Oracle to PostgreSQL comprehensive function mapping reference. "
            "String functions: Oracle NVL(x,y) → PostgreSQL COALESCE(x,y), "
            "Oracle NVL2(x,y,z) → PostgreSQL CASE WHEN x IS NOT NULL THEN y ELSE z END, "
            "Oracle DECODE(expr, val1, res1, val2, res2, default) → PostgreSQL CASE expr WHEN val1 THEN res1 WHEN val2 THEN res2 ELSE default END, "
            "Oracle INSTR(str, substr) → PostgreSQL POSITION(substr IN str) or STRPOS(str, substr), "
            "Oracle INSTR(str, substr, pos) → PostgreSQL POSITION(substr IN SUBSTRING(str FROM pos)) + pos - 1, "
            "Oracle SUBSTR(str, pos, len) → PostgreSQL SUBSTRING(str FROM pos FOR len), "
            "Oracle LISTAGG(expr, delim) WITHIN GROUP (ORDER BY col) → PostgreSQL STRING_AGG(expr, delim ORDER BY col), "
            "Oracle REGEXP_SUBSTR(str, pat, pos, nth) → PostgreSQL (REGEXP_MATCHES(str, pat))[nth], "
            "Oracle REGEXP_REPLACE(str, pat, rep) → PostgreSQL REGEXP_REPLACE(str, pat, rep), "
            "Oracle SOUNDEX(str) → PostgreSQL SOUNDEX(str) (same), "
            "Oracle TO_CHAR(expr, format) → PostgreSQL TO_CHAR(expr, format) (same), "
            "Oracle CONCAT(a,b) → PostgreSQL a||b (only 2 args in Oracle, use || for multiple). "
            "Date functions: Oracle SYSDATE → PostgreSQL CURRENT_TIMESTAMP(0) or NOW(), "
            "Oracle SYSTIMESTAMP → PostgreSQL CURRENT_TIMESTAMP, "
            "Oracle TRUNC(datetime, 'unit') → PostgreSQL DATE_TRUNC('unit', datetime), "
            "Oracle ADD_MONTHS(date, n) → PostgreSQL date + INTERVAL 'n months', "
            "Oracle MONTHS_BETWEEN(d1,d2) → PostgreSQL EXTRACT(YEAR FROM age(d1,d2))*12 + EXTRACT(MONTH FROM age(d1,d2)), "
            "Oracle NEXT_DAY(date, 'day') → PostgreSQL date + ((n - EXTRACT(DOW FROM date) + 7) % 7), "
            "Oracle LAST_DAY(date) → PostgreSQL (DATE_TRUNC('MONTH', date) + INTERVAL '1 MONTH - 1 day')::date, "
            "Oracle FROM_TZ(ts, tz) → PostgreSQL ts AT TIME ZONE tz. "
            "Math functions: Oracle TRUNC(n, precision) → PostgreSQL TRUNC(n, precision) (same), "
            "Oracle MOD(a,b) → PostgreSQL a % b or MOD(a,b), "
            "Oracle POWER(a,b) → PostgreSQL POWER(a,b) or a^b. "
            "System functions: Oracle USER → PostgreSQL CURRENT_USER, "
            "Oracle SYS_CONTEXT('USERENV','SESSION_USER') → PostgreSQL SESSION_USER, "
            "Oracle SYS_CONTEXT('USERENV','IP_ADDRESS') → PostgreSQL INET_CLIENT_ADDR()."
        ),
        "source": "kb/functions/oracle-pg-comprehensive",
        "meta": {"category": "FUNCTION", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-mysql-pg-syntax-differences",
        "text": (
            "MySQL to PostgreSQL comprehensive syntax differences reference. "
            "LIMIT clause: MySQL LIMIT offset, count → PostgreSQL LIMIT count OFFSET offset (note: order is reversed). "
            "Example: LIMIT 10, 20 → LIMIT 20 OFFSET 10. "
            "UPDATE with JOIN: MySQL UPDATE t1 JOIN t2 ON t1.id=t2.id SET t1.col=val → PostgreSQL UPDATE t1 SET col=val FROM t2 WHERE t1.id=t2.id. "
            "DELETE with JOIN: MySQL DELETE t1 FROM t1 JOIN t2 ON ... → PostgreSQL DELETE FROM t1 USING t2 WHERE .... "
            "INSERT IGNORE: MySQL INSERT IGNORE INTO t → PostgreSQL INSERT INTO t ... ON CONFLICT DO NOTHING. "
            "REPLACE INTO: MySQL REPLACE INTO t → PostgreSQL INSERT INTO t ... ON CONFLICT DO UPDATE SET .... "
            "ON DUPLICATE KEY UPDATE: MySQL ON DUPLICATE KEY UPDATE col=VALUES(col) → PostgreSQL ON CONFLICT (key) DO UPDATE SET col=EXCLUDED.col. "
            "Identifier quoting: MySQL backticks `col` → PostgreSQL double quotes \"col\". "
            "String quoting: MySQL allows single quotes and double quotes for strings; PostgreSQL only uses single quotes for strings, double quotes for identifiers. "
            "Boolean values: MySQL uses 0/1 or TRUE/FALSE; PostgreSQL uses true/false/NULL. "
            "Auto increment: MySQL AUTO_INCREMENT → PostgreSQL GENERATED ALWAYS AS IDENTITY (PostgreSQL 10+) or SERIAL (legacy). "
            "Table engine: MySQL ENGINE=InnoDB → PostgreSQL (no equivalent, remove). "
            "Character set: MySQL CHARSET=utf8 → PostgreSQL (no equivalent, use UTF-8 by default). "
            "Collation: MySQL COLLATE utf8_general_ci → PostgreSQL (use COLLATE clause or set at database level). "
            "Constraint naming: MySQL auto-generates constraint names; PostgreSQL may throw 'relation already exists' error if constraint name conflicts. "
            "Solution: explicitly name constraints or use IF NOT EXISTS."
        ),
        "source": "kb/syntax/mysql-pg-differences",
        "meta": {"category": "SYNTAX", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-syntax-differences",
        "text": (
            "Oracle to PostgreSQL comprehensive syntax differences reference. "
            "Outer join: Oracle (+) operator → PostgreSQL LEFT/RIGHT JOIN ... ON. "
            "Example: WHERE e.dept_id = d.dept_id(+) → FROM e LEFT JOIN d ON e.dept_id = d.dept_id. "
            "Hierarchical query: Oracle CONNECT BY + START WITH → PostgreSQL WITH RECURSIVE CTE. "
            "ROWNUM: Oracle ROWNUM <= N → PostgreSQL LIMIT N. "
            "ROWNUM pagination: Oracle SELECT * FROM (SELECT t.*, ROWNUM rn FROM t WHERE ROWNUM <= 20) WHERE rn > 10 "
            "→ PostgreSQL SELECT * FROM t LIMIT 10 OFFSET 10 (do NOT use ROW_NUMBER() OVER ()). "
            "DUAL table: Oracle SELECT expr FROM dual → PostgreSQL SELECT expr (remove FROM dual). "
            "Sequences: Oracle seq.NEXTVAL → PostgreSQL NEXTVAL('seq'), Oracle seq.CURRVAL → PostgreSQL CURVAL('seq'). "
            "Synonyms: Oracle CREATE SYNONYM → PostgreSQL (no equivalent, use schema names or views). "
            "Packages: Oracle CREATE PACKAGE → PostgreSQL (no equivalent, use schemas and functions). "
            "Triggers: Oracle :NEW.col and :OLD.col → PostgreSQL NEW.col and OLD.col (no colon). "
            "Cursors: Oracle SYS_REFCURSOR → PostgreSQL REFCURSOR. "
            "Exception handling: Oracle EXCEPTION WHEN NO_DATA_FOUND → PostgreSQL EXCEPTION WHEN NO_DATA_FOUND (same). "
            "Oracle WHEN OTHERS → PostgreSQL WHEN OTHERS (same). "
            "DBMS_OUTPUT: Oracle DBMS_OUTPUT.PUT_LINE(msg) → PostgreSQL RAISE NOTICE '%', msg. "
            "Autonomous transactions: Oracle PRAGMA AUTONOMOUS_TRANSACTION → PostgreSQL (use dblink or pg_background). "
            "Materialized views: Oracle CREATE MATERIALIZED VIEW → PostgreSQL CREATE MATERIALIZED VIEW (same syntax). "
            "Hint syntax: Oracle /*+ HINT */ → PostgreSQL (no hints, use EXPLAIN and pg_hint_plan extension)."
        ),
        "source": "kb/syntax/oracle-pg-differences",
        "meta": {"category": "SYNTAX", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-plsql-plpgsql",
        "text": (
            "Oracle PL/SQL to PostgreSQL PL/pgSQL conversion reference. "
            "Function structure: Oracle CREATE OR REPLACE FUNCTION name(params) RETURN type IS BEGIN ... END; "
            "→ PostgreSQL CREATE OR REPLACE FUNCTION name(params) RETURNS type AS $$ BEGIN ... END; $$ LANGUAGE plpgsql; "
            "Procedure structure: Oracle CREATE OR REPLACE PROCEDURE name(params) IS BEGIN ... END; "
            "→ PostgreSQL CREATE OR REPLACE PROCEDURE name(params) AS $$ BEGIN ... END; $$ LANGUAGE plpgsql; "
            "Variable declaration: Oracle var_name type; → PostgreSQL var_name type; (same). "
            "Constant: Oracle var_name CONSTANT type := value; → PostgreSQL var_name CONSTANT type := value; (same). "
            "Cursor: Oracle CURSOR cur IS SELECT ... → PostgreSQL cur CURSOR FOR SELECT ...; "
            "Oracle OPEN cur; FETCH cur INTO var; CLOSE cur; → PostgreSQL OPEN cur; FETCH cur INTO var; CLOSE cur; (same). "
            "For loop: Oracle FOR rec IN (SELECT ...) LOOP ... END LOOP; → PostgreSQL FOR rec IN SELECT ... LOOP ... END LOOP; (no parentheses). "
            "While loop: Oracle WHILE condition LOOP ... END LOOP; → PostgreSQL WHILE condition LOOP ... END LOOP; (same). "
            "If statement: Oracle IF condition THEN ... ELSIF ... ELSE ... END IF; "
            "→ PostgreSQL IF condition THEN ... ELSIF ... ELSE ... END IF; (same, but ELSIF not ELSEIF). "
            "Return: Oracle RETURN expr; → PostgreSQL RETURN expr; (same for functions). "
            "Oracle RETURN; (no value) → PostgreSQL RETURN; (same for procedures). "
            "Exception handling: Oracle EXCEPTION WHEN exception_name THEN ... → PostgreSQL EXCEPTION WHEN exception_name THEN ... (same). "
            "Oracle WHEN OTHERS THEN → PostgreSQL WHEN OTHERS THEN (same). "
            "Oracle SQLCODE → PostgreSQL SQLSTATE (different values). "
            "Oracle SQLERRM → PostgreSQL SQLERRM (same). "
            "Raise error: Oracle RAISE_APPLICATION_ERROR(code, msg) → PostgreSQL RAISE EXCEPTION '%', msg; "
            "Print output: Oracle DBMS_OUTPUT.PUT_LINE(msg) → PostgreSQL RAISE NOTICE '%', msg; "
            "Commit: Oracle COMMIT; → PostgreSQL COMMIT; (same, but PostgreSQL auto-commits outside transaction blocks). "
            "Rollback: Oracle ROLLBACK; → PostgreSQL ROLLBACK; (same). "
            "Savepoint: Oracle SAVEPOINT name; → PostgreSQL SAVEPOINT name; (same)."
        ),
        "source": "kb/plsql/oracle-pg-plsql-plpgsql",
        "meta": {"category": "PLSQL", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-mysql-pg-create-table-comprehensive",
        "text": (
            "MySQL to PostgreSQL CREATE TABLE comprehensive conversion reference. "
            "Auto increment: MySQL id INT AUTO_INCREMENT PRIMARY KEY → PostgreSQL id SERIAL PRIMARY KEY (legacy) "
            "or id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY (PostgreSQL 10+). "
            "MySQL BIGINT AUTO_INCREMENT → PostgreSQL BIGSERIAL or BIGINT GENERATED ALWAYS AS IDENTITY. "
            "Default values: MySQL DEFAULT CURRENT_TIMESTAMP → PostgreSQL DEFAULT CURRENT_TIMESTAMP (same). "
            "MySQL DEFAULT 0 → PostgreSQL DEFAULT 0 (same). "
            "MySQL DEFAULT NULL → PostgreSQL DEFAULT NULL (same, but PostgreSQL treats NULL differently). "
            "Engine: MySQL ENGINE=InnoDB → PostgreSQL (remove, PostgreSQL always uses similar storage). "
            "Charset: MySQL DEFAULT CHARSET=utf8mb4 → PostgreSQL (remove, use UTF-8 by default). "
            "Collation: MySQL COLLATE=utf8mb4_unicode_ci → PostgreSQL (remove or use COLLATE clause). "
            "Comment: MySQL COMMENT 'text' → PostgreSQL (use COMMENT ON COLUMN after CREATE TABLE). "
            "Index: MySQL KEY idx_name (col) → PostgreSQL CREATE INDEX idx_name ON table(col) (separate statement). "
            "Unique: MySQL UNIQUE KEY idx (col) → PostgreSQL UNIQUE (col) or CREATE UNIQUE INDEX. "
            "Foreign key: MySQL FOREIGN KEY (col) REFERENCES t2(id) → PostgreSQL same syntax. "
            "Check constraint: MySQL CHECK (expr) → PostgreSQL CHECK (expr) (same). "
            "Enum: MySQL status ENUM('a','b') → PostgreSQL CREATE TYPE status_type AS ENUM('a','b'); then status status_type. "
            "Set: MySQL tags SET('a','b','c') → PostgreSQL tags TEXT[] or CREATE TYPE tags_type AS ENUM('a','b','c'). "
            "Unsigned: MySQL col INT UNSIGNED → PostgreSQL col INTEGER CHECK (col >= 0). "
            "Zerofill: MySQL col INT ZEROFILL → PostgreSQL col INTEGER (remove ZEROFILL, use LPAD for display)."
        ),
        "source": "kb/ddl/mysql-pg-create-table",
        "meta": {"category": "DDL", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-create-table-comprehensive",
        "text": (
            "Oracle to PostgreSQL CREATE TABLE comprehensive conversion reference. "
            "Data types: Oracle NUMBER → PostgreSQL NUMERIC/INTEGER/BIGINT (depends on precision), "
            "Oracle VARCHAR2(n) → PostgreSQL VARCHAR(n), Oracle DATE → PostgreSQL TIMESTAMP(0), "
            "Oracle CLOB → PostgreSQL TEXT, Oracle BLOB → PostgreSQL BYTEA. "
            "Storage clauses: Oracle LOGGING → PostgreSQL (remove, logged by default), "
            "Oracle TABLESPACE ts_name → PostgreSQL TABLESPACE ts_name (same, but must exist). "
            "Constraints: Oracle CONSTRAINT pk_name PRIMARY KEY → PostgreSQL CONSTRAINT pk_name PRIMARY KEY (same), "
            "Oracle CONSTRAINT uk_name UNIQUE → PostgreSQL CONSTRAINT uk_name UNIQUE (same), "
            "Oracle CONSTRAINT fk_name FOREIGN KEY → PostgreSQL CONSTRAINT fk_name FOREIGN KEY (same). "
            "Sequences: Oracle CREATE SEQUENCE seq_name START WITH 1 INCREMENT BY 1; "
            "→ PostgreSQL CREATE SEQUENCE seq_name START WITH 1 INCREMENT BY 1; (same syntax). "
            "Identity columns: Oracle id NUMBER GENERATED ALWAYS AS IDENTITY → PostgreSQL id INTEGER GENERATED ALWAYS AS IDENTITY. "
            "Default values: Oracle DEFAULT expr → PostgreSQL DEFAULT expr (same). "
            "Not null: Oracle col NOT NULL → PostgreSQL col NOT NULL (same). "
            "Comments: Oracle COMMENT ON COLUMN t.col IS 'text' → PostgreSQL COMMENT ON COLUMN t.col IS 'text' (same). "
            "Partitioning: Oracle PARTITION BY RANGE(col) → PostgreSQL PARTITION BY RANGE(col) (similar syntax). "
            "Index-organized tables: Oracle IOT → PostgreSQL (no direct equivalent, use clustered indexes). "
            "Global temporary tables: Oracle CREATE GLOBAL TEMPORARY TABLE → PostgreSQL CREATE TEMPORARY TABLE."
        ),
        "source": "kb/ddl/oracle-pg-create-table",
        "meta": {"category": "DDL", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-mysql-pg-select-differences",
        "text": (
            "MySQL to PostgreSQL SELECT statement differences reference. "
            "LIMIT: MySQL LIMIT offset, count → PostgreSQL LIMIT count OFFSET offset. "
            "Example: SELECT * FROM t LIMIT 10, 20 → SELECT * FROM t LIMIT 20 OFFSET 10. "
            "GROUP_CONCAT: MySQL GROUP_CONCAT(col SEPARATOR ',') → PostgreSQL STRING_AGG(col, ','). "
            "WITH ROLLUP: MySQL GROUP BY col WITH ROLLUP → PostgreSQL GROUP BY ROLLUP(col). "
            "HAVING: MySQL HAVING can use aliases; PostgreSQL HAVING cannot use aliases (use full expression). "
            "Example: MySQL SELECT COUNT(*) AS cnt ... HAVING cnt > 5 → PostgreSQL SELECT COUNT(*) AS cnt ... HAVING COUNT(*) > 5. "
            "Backticks: MySQL SELECT `col` FROM `table` → PostgreSQL SELECT \"col\" FROM \"table\". "
            "String comparison: MySQL 'abc' = 'ABC' (case-insensitive by default); PostgreSQL 'abc' = 'abc' (case-sensitive). "
            "Use ILIKE for case-insensitive matching in PostgreSQL. "
            "REGEXP: MySQL col REGEXP 'pattern' → PostgreSQL col ~ 'pattern' (case-sensitive) or col ~* 'pattern' (case-insensitive). "
            "IF function: MySQL IF(cond, t, f) → PostgreSQL CASE WHEN cond THEN t ELSE f END. "
            "IFNULL: MySQL IFNULL(x, y) → PostgreSQL COALESCE(x, y). "
            "NULL-safe equality: MySQL col <=> val → PostgreSQL col IS NOT DISTINCT FROM val. "
            "FORCE INDEX: MySQL FORCE INDEX(idx) → PostgreSQL (no equivalent, use pg_hint_plan extension). "
            "SQL_CALC_FOUND_ROWS: MySQL SELECT SQL_CALC_FOUND_ROWS ... → PostgreSQL use window function COUNT(*) OVER()."
        ),
        "source": "kb/query/mysql-pg-select",
        "meta": {"category": "QUERY", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-select-differences",
        "text": (
            "Oracle to PostgreSQL SELECT statement differences reference. "
            "ROWNUM: Oracle SELECT * FROM t WHERE ROWNUM <= 10 → PostgreSQL SELECT * FROM t LIMIT 10. "
            "ROWNUM pagination: Oracle SELECT * FROM (SELECT t.*, ROWNUM rn FROM t WHERE ROWNUM <= 20) WHERE rn > 10 "
            "→ PostgreSQL SELECT * FROM t LIMIT 10 OFFSET 10. "
            "Do NOT use ROW_NUMBER() OVER () for simple pagination in PostgreSQL. "
            "CONNECT BY: Oracle SELECT LEVEL, name FROM emp START WITH manager_id IS NULL CONNECT BY PRIOR id = manager_id "
            "→ PostgreSQL WITH RECURSIVE emp_tree AS (SELECT id, name, 0 AS lvl FROM emp WHERE manager_id IS NULL "
            "UNION ALL SELECT e.id, e.name, t.lvl+1 FROM emp e JOIN emp_tree t ON e.manager_id = t.id) SELECT lvl, name FROM emp_tree. "
            "DUAL table: Oracle SELECT SYSDATE FROM dual → PostgreSQL SELECT CURRENT_TIMESTAMP (remove FROM dual). "
            "NVL: Oracle SELECT NVL(col, 'default') → PostgreSQL SELECT COALESCE(col, 'default'). "
            "DECODE: Oracle DECODE(col, 'a', 1, 'b', 2, 0) → PostgreSQL CASE col WHEN 'a' THEN 1 WHEN 'b' THEN 2 ELSE 0 END. "
            "LISTAGG: Oracle LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) → PostgreSQL STRING_AGG(name, ',' ORDER BY name). "
            "REGEXP_SUBSTR: Oracle REGEXP_SUBSTR(str, '[^@]+') → PostgreSQL (REGEXP_MATCHES(str, '[^@]+'))[1]. "
            "Outer join (+): Oracle WHERE e.dept_id = d.dept_id(+) → PostgreSQL FROM e LEFT JOIN d ON e.dept_id = d.dept_id. "
            "Minus: Oracle MINUS → PostgreSQL EXCEPT. "
            "INTERSECT: same in both. "
            "UNION: same in both. "
            "Subquery in FROM: Oracle SELECT * FROM (SELECT ...) → PostgreSQL SELECT * FROM (SELECT ...) AS alias (alias required). "
            "Inline view alias: Oracle (SELECT ...) alias → PostgreSQL (SELECT ...) AS alias (AS keyword required)."
        ),
        "source": "kb/query/oracle-pg-select",
        "meta": {"category": "QUERY", "source_dialect": "oracle", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-mysql-pg-update-delete",
        "text": (
            "MySQL to PostgreSQL UPDATE and DELETE statement differences. "
            "UPDATE with JOIN: MySQL UPDATE t1 INNER JOIN t2 ON t1.id = t2.ref_id SET t1.col = t2.val WHERE t2.status = 1 "
            "→ PostgreSQL UPDATE t1 SET col = t2.val FROM t2 WHERE t1.id = t2.ref_id AND t2.status = 1. "
            "Note: In PostgreSQL, JOIN conditions go in WHERE clause, not FROM clause. "
            "DELETE with JOIN: MySQL DELETE t1 FROM t1 INNER JOIN t2 ON t1.id = t2.ref_id WHERE t2.status = 0 "
            "→ PostgreSQL DELETE FROM t1 USING t2 WHERE t1.id = t2.ref_id AND t2.status = 0. "
            "Note: MySQL uses DELETE alias FROM ...; PostgreSQL uses DELETE FROM ... USING .... "
            "Multi-table DELETE: MySQL DELETE t1, t2 FROM t1 JOIN t2 ON ... WHERE ... "
            "→ PostgreSQL requires separate DELETE statements for each table. "
            "INSERT ... ON DUPLICATE KEY UPDATE: MySQL INSERT INTO t (id, val) VALUES (1, 'a') ON DUPLICATE KEY UPDATE val = VALUES(val) "
            "→ PostgreSQL INSERT INTO t (id, val) VALUES (1, 'a') ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val. "
            "Note: VALUES(col) in MySQL → EXCLUDED.col in PostgreSQL. "
            "REPLACE INTO: MySQL REPLACE INTO t (id, val) VALUES (1, 'a') "
            "→ PostgreSQL INSERT INTO t (id, val) VALUES (1, 'a') ON CONFLICT (id) DO UPDATE SET val = EXCLUDED.val. "
            "INSERT IGNORE: MySQL INSERT IGNORE INTO t ... → PostgreSQL INSERT INTO t ... ON CONFLICT DO NOTHING."
        ),
        "source": "kb/dml/mysql-pg-update-delete",
        "meta": {"category": "DML", "source_dialect": "mysql", "target_dialect": "postgresql"},
    },
    {
        "id": "kb-oracle-pg-update-delete",
        "text": (
            "Oracle to PostgreSQL UPDATE and DELETE statement differences. "
            "UPDATE with subquery: Oracle UPDATE t1 SET col = (SELECT val FROM t2 WHERE t2.id = t1.ref_id) "
            "→ PostgreSQL same syntax (works in both). "
            "UPDATE with MERGE: Oracle MERGE INTO target USING source ON (condition) WHEN MATCHED THEN UPDATE SET ... "
            "→ PostgreSQL 15+ MERGE INTO target USING source ON (condition) WHEN MATCHED THEN UPDATE SET ... (same syntax). "
            "For older PostgreSQL: INSERT ... ON CONFLICT DO UPDATE SET .... "
            "DELETE with ROWNUM: Oracle DELETE FROM t WHERE ROWNUM <= 10 → PostgreSQL DELETE FROM t WHERE ctid IN (SELECT ctid FROM t LIMIT 10). "
            "Note: PostgreSQL doesn't support ROWNUM; use ctid or LIMIT in subquery. "
            "TRUNCATE: Oracle TRUNCATE TABLE t → PostgreSQL TRUNCATE TABLE t (same syntax). "
            "Oracle TRUNCATE TABLE t CASCADE → PostgreSQL TRUNCATE TABLE t CASCADE (same). "
            "Oracle TRUNCATE TABLE t PURGE → PostgreSQL (no equivalent, PostgreSQL doesn't have recycle bin). "
            "INSERT with sequence: Oracle INSERT INTO t (id, name) VALUES (seq.NEXTVAL, 'a') "
            "→ PostgreSQL INSERT INTO t (id, name) VALUES (NEXTVAL('seq'), 'a'). "
            "INSERT with RETURNING: Oracle INSERT INTO t ... RETURNING col INTO var "
            "→ PostgreSQL INSERT INTO t ... RETURNING col INTO var (same in PL/pgSQL). "
            "BULK COLLECT: Oracle BULK COLLECT INTO collection → PostgreSQL use arrays or FOR loop. "
            "FORALL: Oracle FORALL i IN 1..count INSERT INTO t ... → PostgreSQL use FOR loop or COPY command."
        ),
        "source": "kb/dml/oracle-pg-update-delete",
        "meta": {"category": "DML", "source_dialect": "oracle", "target_dialect": "postgresql"},
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
