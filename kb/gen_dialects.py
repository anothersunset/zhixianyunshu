"""生成 kb/active/dialects/*.yaml 从现有的 Java 硬编码数据。"""
import sys, yaml
from pathlib import Path

ACTIVE = Path(__file__).resolve().parent / "active"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def feature(keyword, mapping, category, is_recipe=False, **kwargs):
    d = {"keyword": keyword, "mapping": mapping, "category": category, "is_recipe": is_recipe}
    d.update(kwargs)
    return d


oracle_features = [
    feature("ROWNUM", "LIMIT / ROW_NUMBER() OVER()", "pseudo-column", True,
        construct_name="ROWNUM Pagination",
        few_shot_source="SELECT * FROM (SELECT e.*, ROWNUM rn FROM emp e WHERE ROWNUM <= 20) WHERE rn > 10",
        few_shot_target="SELECT * FROM emp LIMIT 10 OFFSET 10",
        step_by_step="1. 判断 ROWNUM 用途。2. LIMIT = 外层条件值, OFFSET = 内层条件值。3. 绝对不要将 ROW_NUMBER() OVER() 与 LIMIT 组合。",
        pitfalls=["NEVER combine ROW_NUMBER() OVER() with LIMIT", "Do NOT nest ROW_NUMBER() inside a subquery that already has LIMIT"],
    ),
    feature("CONNECT BY", "WITH RECURSIVE", "syntax", True,
        construct_name="CONNECT BY Hierarchy",
        few_shot_source="SELECT CONNECT_BY_ISLEAF AS is_leaf, LEVEL AS lvl, name FROM emp START WITH manager_id IS NULL CONNECT BY PRIOR id = manager_id",
        few_shot_target="WITH RECURSIVE emp_tree AS (SELECT id, name, manager_id, 0 AS lvl, false AS is_leaf FROM emp WHERE manager_id IS NULL UNION ALL SELECT e.id, e.name, e.manager_id, t.lvl+1, NOT EXISTS(SELECT 1 FROM emp WHERE manager_id=e.id) FROM emp e JOIN emp_tree t ON e.manager_id = t.id) SELECT is_leaf, lvl, name FROM emp_tree",
        step_by_step="1. START WITH -> CTE anchor WHERE。2. CONNECT BY PRIOR -> 递归 JOIN。3. LEVEL 从 0 开始。4. CONNECT_BY_ISLEAF 在 CTE 内计算为 boolean。5. 用 WITH RECURSIVE 包装。",
        pitfalls=["LEVEL must start at 0 in anchor", "CONNECT_BY_ISLEAF must be computed INSIDE CTE as boolean", "Do NOT forget parent_id column in CTE column list"],
    ),
    feature("MERGE INTO", "INSERT ... ON CONFLICT", "syntax", True,
        construct_name="MERGE INTO Upsert",
        few_shot_source="MERGE INTO target t USING source s ON (t.id = s.id) WHEN MATCHED THEN UPDATE SET t.name = s.name WHEN NOT MATCHED THEN INSERT (id, name) VALUES (s.id, s.name)",
        few_shot_target="INSERT INTO target (id, name) SELECT id, name FROM source ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name",
        step_by_step="1. USING 数据源 -> INSERT ... SELECT FROM。2. ON 条件 -> ON CONFLICT 目标列。3. WHEN MATCHED UPDATE -> DO UPDATE SET, 用 EXCLUDED。4. WHEN NOT MATCHED INSERT -> INSERT/SELECT 列表。5. 移除 Oracle 表别名前缀。",
        pitfalls=["CONFLICT target must have UNIQUE constraint", "Use EXCLUDED.column_name", "WHEN NOT MATCHED INSERT columns go into INSERT/SELECT, not VALUES"],
    ),
    feature("TRUNC(", "TRUNC (numbers same) / DATE_TRUNC (dates)", "function", True,
        construct_name="TRUNC distinguish numeric vs date",
        few_shot_source="SELECT TRUNC(salary) FROM emp",
        few_shot_target="SELECT TRUNC(salary) FROM emp",
        step_by_step="1. 判断 TRUNC 参数类型：数字则 PG 中 TRUNC 也支持。2. 日期则转为 DATE_TRUNC('day', col)。3. 不确定则保留 TRUNC。",
        pitfalls=["Do NOT blindly convert TRUNC to DATE_TRUNC", "Only convert TRUNC(date) to DATE_TRUNC"],
    ),
    feature("MONTHS_BETWEEN(", "EXTRACT(YEAR FROM age(a,b))*12 + EXTRACT(MONTH FROM age(a,b))", "function", True,
        construct_name="MONTHS_BETWEEN",
        few_shot_source="SELECT MONTHS_BETWEEN(date1, date2) FROM t",
        few_shot_target="SELECT EXTRACT(YEAR FROM age(date1, date2)) * 12 + EXTRACT(MONTH FROM age(date1, date2)) FROM t",
        step_by_step="COPY the Target example output character-by-character. Do NOT add EXTRACT(DAY ...) fraction.",
        pitfalls=["NEVER add + EXTRACT(DAY FROM ...) / N to the formula"],
    ),
    feature("ADD_MONTHS(", "date + INTERVAL 'n months'", "function", True,
        construct_name="ADD_MONTHS",
        few_shot_source="SELECT ADD_MONTHS(hire_date, 6) FROM emp",
        few_shot_target="SELECT hire_date + INTERVAL '6 months' FROM emp",
        step_by_step="1. ADD_MONTHS(date_col, N) -> date_col + INTERVAL 'N months'。2. N 为负时用 - INTERVAL。",
        pitfalls=["NEVER use DATEADD() or DATE_ADD()", "NEVER use MAKE_INTERVAL"],
    ),
    feature("LISTAGG(", "STRING_AGG(col, delim ORDER BY col)", "function", True,
        construct_name="LISTAGG",
        few_shot_source="SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM emp GROUP BY dept",
        few_shot_target="SELECT STRING_AGG(name, ',' ORDER BY name) FROM emp GROUP BY dept",
        step_by_step="1. LISTAGG(col, delim) WITHIN GROUP (ORDER BY col) -> STRING_AGG(col, delim ORDER BY col)。2. 分隔符是第二个参数。3. WITHIN GROUP ORDER BY -> STRING_AGG 内的 ORDER BY。",
        pitfalls=["NEVER use GROUP_CONCAT (MySQL syntax)", "ORDER BY goes INSIDE STRING_AGG"],
    ),
    feature("REGEXP_SUBSTR(", "(REGEXP_MATCHES(str,pattern))[1]", "function", True,
        construct_name="REGEXP_SUBSTR",
        few_shot_source="SELECT REGEXP_SUBSTR(email, '[^@]+') FROM users",
        few_shot_target="SELECT (REGEXP_MATCHES(email, '[^@]+'))[1] FROM users",
        step_by_step="COPY the Target example output character-by-character. Use REGEXP_MATCHES (with S). Do NOT use SUBSTRING, regexp_match, or split_part.",
        pitfalls=["NEVER use SUBSTRING() for regex extraction", "NEVER use regexp_match (singular)", "NEVER use split_part() as shortcut"],
    ),
    # Oracle simple entries
    feature("DECODE(", "CASE WHEN", "function"),
    feature("NVL(", "COALESCE", "function"),
    feature("NVL2(", "CASE WHEN ... THEN ... ELSE", "function"),
    feature("FROM DUAL", "omit DUAL", "syntax"),
    feature("(+)", "standard LEFT/RIGHT JOIN", "operator"),
    feature("START WITH", "WITH RECURSIVE anchor clause", "syntax"),
    feature("TO_CHAR(", "TO_CHAR (format review needed)", "function"),
    feature("TO_DATE(", "TO_DATE (format review needed)", "function"),
    feature("INSTR(", "POSITION / STRPOS", "function"),
    feature("SYSDATE", "CURRENT_TIMESTAMP", "function"),
    feature("USER", "CURRENT_USER", "function"),
    feature("UID", "CURRENT_USER", "function"),
    feature("INITCAP(", "INITCAP (pg compatible, verify)", "function"),
    feature("PIVOT(", "CROSSTAB / conditional aggregation", "syntax"),
    feature("UNPIVOT(", "UNNEST / lateral join", "syntax"),
    feature("REGEXP_LIKE(", "col ~ pattern or REGEXP_MATCHES(col, pattern)", "function"),
    feature("TO_NUMBER(", "col::numeric or CAST(col AS numeric)", "function"),
    feature("SUBSTR(", "SUBSTRING(col FROM start FOR len)", "function"),
    feature("SYSTIMESTAMP", "CURRENT_TIMESTAMP or clock_timestamp()", "function"),
    feature("TO_TIMESTAMP(", "col::timestamp or to_timestamp(col, fmt)", "function"),
    feature("REGEXP_REPLACE(", "REGEXP_REPLACE (PG compatible, verify)", "function"),
    feature("TIMESTAMP_TRUNC(", "DATE_TRUNC('day', col)", "function"),
]

oracle = {
    "name": "oracle",
    "pairs": ["oracle->postgresql", "oracle->opengauss"],
    "complexity_keywords": ["decode(", "rownum", "(+)", "from dual", "sysdate", "nvl(", "nvl2(", "connect by", "start with", "merge into", "pivot(", "unpivot("],
    "standard_whitelist": [],
    "features": oracle_features,
}

mysql_features = [
    feature("IFNULL(", "COALESCE", "function"),
    feature("DATE_FORMAT(", "TO_CHAR", "function"),
    feature("GROUP_CONCAT(", "STRING_AGG", "function"),
    feature("AUTO_INCREMENT", "SERIAL / SEQUENCE", "type"),
    feature("ENUM(", "VARCHAR + CHECK or CREATE TYPE", "type"),
    feature("ON DUPLICATE KEY", "ON CONFLICT ... DO UPDATE", "syntax"),
    feature("REGEXP", "~ (or SIMILAR TO / regexp_matches)", "function"),
    feature("NOW()", "CURRENT_TIMESTAMP", "function"),
    feature("TINYINT", "SMALLINT", "type"),
    feature("BIT(", "BOOLEAN", "type"),
    feature("`", "remove backticks", "syntax"),
    feature("ENGINE=", "omit ENGINE clause", "ddl"),
    feature("CHARACTER SET", "omit or adjust charset", "ddl"),
    feature("COLLATE", "omit collation", "ddl"),
    feature("UNSIGNED", "use CHECK constraint instead", "type"),
    feature("ZEROFILL", "LPAD or format", "type"),
]

mysql = {
    "name": "mysql",
    "pairs": ["mysql->postgresql", "mysql->opengauss"],
    "complexity_keywords": ["on duplicate key", "group_concat(", "auto_increment", "enum("],
    "standard_whitelist": [],
    "features": mysql_features,
}

for dialect_data, filename in [(oracle, "oracle.yaml"), (mysql, "mysql.yaml")]:
    path = ACTIVE / "dialects" / filename
    path.write_text(
        yaml.dump(dialect_data, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"Written {path}: {len(dialect_data['features'])} features")

# Verify
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from kb.kb_loader import load_dialect_config
for name in ["oracle", "mysql"]:
    cfg = load_dialect_config(name)
    if cfg:
        print(f"  {name}: {len(cfg['features'])} features, {len(cfg['complexity_keywords'])} complexity keywords")
    else:
        print(f"  {name}: FAILED to load!")
