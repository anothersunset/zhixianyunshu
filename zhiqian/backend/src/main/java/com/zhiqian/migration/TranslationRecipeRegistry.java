package com.zhiqian.migration;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * 统一注册表：方言特征的唯一注册源。
 * Full recipe（有 few-shot 的复杂构造）和 simple entry（仅关键词→目标映射）
 * 集中在同一个集合中。DialectFeatureScanner 从此派生特征检测列表。
 *
 * 新增特征时只需在此文件添加一条 RegisteredFeature。
 */
public class TranslationRecipeRegistry {

    public record RegisteredFeature(
        String sourceKeyword,       // 检测关键词，如 "MONTHS_BETWEEN("
        String targetMapping,       // 简短映射，如 "EXTRACT(YEAR FROM age(...))*12 + EXTRACT(MONTH FROM age(...))"
        String dialectGroup,        // "oracle" | "mysql"
        String constructName,       // null 表示 simple entry
        String fewShotSource,       // null 表示 simple entry
        String fewShotTarget,       // null 表示 simple entry
        String stepByStepGuide,     // null 表示 simple entry
        List<String> commonPitfalls // null 或空列表表示 simple entry
    ) {
        public boolean isRecipe() { return fewShotSource != null; }
    }

    // ── Oracle features ──

    private static final RegisteredFeature ORACLE_ROWNUM = new RegisteredFeature(
        "ROWNUM", "LIMIT (simple pagination) or ROW_NUMBER() OVER(ORDER BY ...) (complex)",
        "oracle",
        "ROWNUM Pagination",
        "SELECT * FROM (SELECT e.*, ROWNUM rn FROM emp e WHERE ROWNUM <= 20) WHERE rn > 10",
        "SELECT * FROM emp LIMIT 10 OFFSET 10",
        """
            1. 判断 ROWNUM 用途：如果仅做简单分页（ROWNUM <= N / rn > M），直接替换为 LIMIT/OFFSET。
            2. LIMIT = 外层条件值，OFFSET = 内层条件值；本例中 ROWNUM <= 20 表示上限为 20，rn > 10 表示跳过 10 行 → LIMIT 10 OFFSET 10。
            3. 仅当 ROWNUM 用于复杂表达式（如 WHERE ROWNUM < other_col 或与其他列比较）时，才使用 ROW_NUMBER() OVER(ORDER BY (SELECT NULL))。
            4. 绝对不要将 ROW_NUMBER() OVER() 与 LIMIT 组合在同一个子查询中。""",
        List.of(
            "NEVER combine ROW_NUMBER() OVER() with LIMIT — use simple LIMIT/OFFSET instead.",
            "Do NOT nest ROW_NUMBER() inside a subquery that already has LIMIT."
        )
    );

    private static final RegisteredFeature ORACLE_CONNECT_BY = new RegisteredFeature(
        "CONNECT BY", "WITH RECURSIVE",
        "oracle",
        "CONNECT BY Hierarchy",
        "SELECT CONNECT_BY_ISLEAF AS is_leaf, LEVEL AS lvl, name FROM emp START WITH manager_id IS NULL CONNECT BY PRIOR id = manager_id",
        "WITH RECURSIVE emp_tree AS (SELECT id, name, manager_id, 0 AS lvl, false AS is_leaf FROM emp WHERE manager_id IS NULL UNION ALL SELECT e.id, e.name, e.manager_id, t.lvl+1, NOT EXISTS(SELECT 1 FROM emp WHERE manager_id=e.id) FROM emp e JOIN emp_tree t ON e.manager_id = t.id) SELECT is_leaf, lvl, name FROM emp_tree",
        """
            1. 将 START WITH 条件提取为 CTE anchor member 的 WHERE 子句。
            2. 将 CONNECT BY PRIOR parent_col = child_col 转换为递归 JOIN 条件 (e.parent_col = t.child_col)。
            3. LEVEL 列：anchor 中设为 0，递归成员中设为 lvl+1。
            4. CONNECT_BY_ISLEAF 列：在 CTE 内部计算为 NOT EXISTS(SELECT 1 FROM table WHERE parent_col = current.id)，anchor 中设为 false。必须在 CTE 列列表中定义，不要放在外层 SELECT 中。
            5. 用 WITH RECURSIVE cte_name(col1, col2, ...) AS (anchor UNION ALL recursive) SELECT ... FROM cte_name 包装。""",
        List.of(
            "LEVEL must start at 0 in anchor (not 1).",
            "CONNECT_BY_ISLEAF must be computed INSIDE the CTE as boolean, not in outer SELECT.",
            "is_leaf must be boolean (true/false), not integer (1/0).",
            "Do NOT forget the parent_id column in CTE column list for recursive JOIN."
        )
    );

    private static final RegisteredFeature ORACLE_MERGE_INTO = new RegisteredFeature(
        "MERGE INTO", "INSERT ... ON CONFLICT",
        "oracle",
        "MERGE INTO Upsert",
        "MERGE INTO target t USING source s ON (t.id = s.id) WHEN MATCHED THEN UPDATE SET t.name = s.name WHEN NOT MATCHED THEN INSERT (id, name) VALUES (s.id, s.name)",
        "INSERT INTO target (id, name) SELECT id, name FROM source ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name",
        """
            1. 将 USING 子句的数据源（表或子查询）提取为 INSERT ... SELECT 的 FROM 子句。
            2. 将 ON 子句的匹配条件映射为 ON CONFLICT 的目标列（需有 UNIQUE 约束或主键）。
            3. 将 WHEN MATCHED THEN UPDATE SET 转换为 DO UPDATE SET，用 EXCLUDED 引用冲突行的值。
            4. 将 WHEN NOT MATCHED THEN INSERT 的列和值合并到初始 INSERT 的列列表和 SELECT 列表中。
            5. 移除所有 Oracle 表别名前缀（如 t.name → name），目标列名不带表前缀。""",
        List.of(
            "CONFLICT target column must have a UNIQUE constraint or be PRIMARY KEY.",
            "Use EXCLUDED.column_name to reference the conflicting row in DO UPDATE SET.",
            "WHEN NOT MATCHED INSERT columns go into the INSERT (...) and SELECT ... lists, not VALUES."
        )
    );

    private static final RegisteredFeature ORACLE_TRUNC = new RegisteredFeature(
        "TRUNC(", "TRUNC for numbers (same in PG), DATE_TRUNC for dates",
        "oracle",
        "TRUNC — distinguish numeric vs date",
        "SELECT TRUNC(salary) FROM emp",
        "SELECT TRUNC(salary) FROM emp",
        """
            1. 判断 TRUNC 的参数类型：如果参数是数字（如 salary, amount, price），TRUNC 在 PostgreSQL 中也支持，无需转换。
            2. 如果参数是日期（如 hire_date, SYSDATE），才需要转换为 DATE_TRUNC('day', date_column) 或相应的精度。
            3. 如果无法确定参数类型，保留 TRUNC 不变 — 它在 PG 中同时支持数字和日期。""",
        List.of(
            "Do NOT blindly convert TRUNC to DATE_TRUNC — TRUNC(number) works fine in PostgreSQL.",
            "Only convert TRUNC(date) to DATE_TRUNC. If unsure, keep TRUNC as-is."
        )
    );

    private static final RegisteredFeature ORACLE_MONTHS_BETWEEN = new RegisteredFeature(
        "MONTHS_BETWEEN(", "EXTRACT(YEAR FROM age(a,b))*12 + EXTRACT(MONTH FROM age(a,b))",
        "oracle",
        "MONTHS_BETWEEN — COPY THE OUTPUT EXACTLY",
        "SELECT MONTHS_BETWEEN(date1, date2) FROM t",
        "SELECT EXTRACT(YEAR FROM age(date1, date2)) * 12 + EXTRACT(MONTH FROM age(date1, date2)) FROM t",
        "COPY the Target example output character-by-character. Do NOT add EXTRACT(DAY ...) or any day fraction.",
        List.of("NEVER add + EXTRACT(DAY FROM ...) / N to the formula.")
    );

    private static final RegisteredFeature ORACLE_ADD_MONTHS = new RegisteredFeature(
        "ADD_MONTHS(", "date + INTERVAL 'n months'",
        "oracle",
        "ADD_MONTHS — COPY THE OUTPUT EXACTLY",
        "SELECT ADD_MONTHS(hire_date, 6) FROM emp",
        "SELECT hire_date + INTERVAL '6 months' FROM emp",
        "1. Replace ADD_MONTHS(date_col, N) with date_col + INTERVAL 'N months'.\n2. If N is negative, use - INTERVAL 'N months'.\n3. Do NOT use MAKE_INTERVAL or DATE_PLUS.",
        List.of(
            "NEVER use DATEADD() or DATE_ADD() — PostgreSQL does not have these.",
            "NEVER use MAKE_INTERVAL(months => N) — use the simpler INTERVAL syntax."
        )
    );

    private static final RegisteredFeature ORACLE_LISTAGG = new RegisteredFeature(
        "LISTAGG(", "STRING_AGG(col, delim ORDER BY col)",
        "oracle",
        "LISTAGG — COPY THE OUTPUT EXACTLY",
        "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM emp GROUP BY dept",
        "SELECT STRING_AGG(name, ',' ORDER BY name) FROM emp GROUP BY dept",
        "1. Replace LISTAGG(col, delim) WITHIN GROUP (ORDER BY col) with STRING_AGG(col, delim ORDER BY col).\n2. The delimiter is the second argument to both functions.\n3. WITHIN GROUP (ORDER BY ...) becomes the ORDER BY clause inside STRING_AGG.",
        List.of(
            "NEVER use GROUP_CONCAT — that is MySQL syntax.",
            "The ORDER BY goes INSIDE STRING_AGG, not in a separate clause."
        )
    );

    private static final RegisteredFeature ORACLE_REGEXP_SUBSTR = new RegisteredFeature(
        "REGEXP_SUBSTR(", "(REGEXP_MATCHES(str,pattern))[1]",
        "oracle",
        "REGEXP_SUBSTR — COPY THE OUTPUT EXACTLY",
        "SELECT REGEXP_SUBSTR(email, '[^@]+') FROM users",
        "SELECT (REGEXP_MATCHES(email, '[^@]+'))[1] FROM users",
        "COPY the Target example output character-by-character. Do NOT invent shortcuts like split_part. Use REGEXP_MATCHES (with S). Do NOT use SUBSTRING, regexp_match, or split_part.",
        List.of(
            "NEVER use SUBSTRING() for regex extraction.",
            "NEVER use regexp_match (singular, without S). Use REGEXP_MATCHES (plural).",
            "NEVER use split_part() as a shortcut for REGEXP_SUBSTR — it is not equivalent for general regex patterns."
        )
    );

    // ── Oracle simple entries ──

    private static final RegisteredFeature ORACLE_DECODE   = simple("DECODE(", "CASE WHEN", "oracle");
    private static final RegisteredFeature ORACLE_NVL      = simple("NVL(", "COALESCE", "oracle");
    private static final RegisteredFeature ORACLE_NVL2     = simple("NVL2(", "CASE WHEN ... THEN ... ELSE", "oracle");
    private static final RegisteredFeature ORACLE_FROM_DUAL = simple("FROM DUAL", "omit DUAL", "oracle");
    private static final RegisteredFeature ORACLE_OUTER_JOIN = simple("(+)", "standard LEFT/RIGHT JOIN", "oracle");
    private static final RegisteredFeature ORACLE_START_WITH = simple("START WITH", "WITH RECURSIVE anchor clause", "oracle");
    private static final RegisteredFeature ORACLE_TO_CHAR  = simple("TO_CHAR(", "TO_CHAR (format review needed)", "oracle");
    private static final RegisteredFeature ORACLE_TO_DATE  = simple("TO_DATE(", "TO_DATE (format review needed)", "oracle");
    private static final RegisteredFeature ORACLE_INSTR    = simple("INSTR(", "POSITION / STRPOS", "oracle");
    private static final RegisteredFeature ORACLE_SYSDATE  = simple("SYSDATE", "CURRENT_TIMESTAMP", "oracle");
    private static final RegisteredFeature ORACLE_USER     = simple("USER", "CURRENT_USER", "oracle");
    private static final RegisteredFeature ORACLE_UID      = simple("UID", "CURRENT_USER", "oracle");
    private static final RegisteredFeature ORACLE_INITCAP  = simple("INITCAP(", "INITCAP (pg compatible, verify)", "oracle");
    private static final RegisteredFeature ORACLE_PIVOT    = simple("PIVOT(", "CROSSTAB / conditional aggregation", "oracle");
    private static final RegisteredFeature ORACLE_UNPIVOT  = simple("UNPIVOT(", "UNNEST / lateral join", "oracle");
    // PARROT 分析新增：Oracle 函数在 PARROT 数据中出现频率高但未注册
    private static final RegisteredFeature ORACLE_REGEXP_LIKE = simple("REGEXP_LIKE(", "col ~ pattern or REGEXP_MATCHES(col, pattern)", "oracle");
    private static final RegisteredFeature ORACLE_TO_NUMBER = simple("TO_NUMBER(", "col::numeric or CAST(col AS numeric)", "oracle");
    private static final RegisteredFeature ORACLE_SUBSTR = simple("SUBSTR(", "SUBSTRING(col FROM start FOR len)", "oracle");
    private static final RegisteredFeature ORACLE_SYSTIMESTAMP = simple("SYSTIMESTAMP", "CURRENT_TIMESTAMP or clock_timestamp()", "oracle");
    private static final RegisteredFeature ORACLE_TO_TIMESTAMP = simple("TO_TIMESTAMP(", "col::timestamp or to_timestamp(col, fmt)", "oracle");
    private static final RegisteredFeature ORACLE_REGEXP_REPLACE = simple("REGEXP_REPLACE(", "REGEXP_REPLACE(col, pattern, repl, flags) — PG compatible, verify", "oracle");

    // ── MySQL features ──

    private static final RegisteredFeature MYSQL_IFNULL    = simple("IFNULL(", "COALESCE", "mysql");
    private static final RegisteredFeature MYSQL_DATE_FORMAT = simple("DATE_FORMAT(", "TO_CHAR", "mysql");
    private static final RegisteredFeature MYSQL_GROUP_CONCAT = simple("GROUP_CONCAT(", "STRING_AGG", "mysql");
    private static final RegisteredFeature MYSQL_AUTO_INC  = simple("AUTO_INCREMENT", "SERIAL / SEQUENCE", "mysql");
    private static final RegisteredFeature MYSQL_ENUM      = simple("ENUM(", "VARCHAR + CHECK or CREATE TYPE", "mysql");
    private static final RegisteredFeature MYSQL_DUP_KEY   = simple("ON DUPLICATE KEY", "ON CONFLICT ... DO UPDATE", "mysql");
    private static final RegisteredFeature MYSQL_REGEXP    = simple("REGEXP", "~ (or SIMILAR TO / regexp_matches)", "mysql");
    private static final RegisteredFeature MYSQL_NOW       = simple("NOW()", "CURRENT_TIMESTAMP", "mysql");
    private static final RegisteredFeature MYSQL_TINYINT   = simple("TINYINT", "SMALLINT", "mysql");
    private static final RegisteredFeature MYSQL_BIT       = simple("BIT(", "BOOLEAN", "mysql");
    private static final RegisteredFeature MYSQL_BACKTICK  = simple("`", "remove backticks (use \" or unquoted)", "mysql");
    private static final RegisteredFeature MYSQL_ENGINE    = simple("ENGINE=", "omit ENGINE clause", "mysql");
    private static final RegisteredFeature MYSQL_CHARSET   = simple("CHARACTER SET", "omit or adjust charset", "mysql");
    private static final RegisteredFeature MYSQL_COLLATE   = simple("COLLATE", "omit collation", "mysql");
    private static final RegisteredFeature MYSQL_UNSIGNED  = simple("UNSIGNED", "use CHECK constraint instead", "mysql");
    private static final RegisteredFeature MYSQL_ZEROFILL  = simple("ZEROFILL", "LPAD or format", "mysql");

    // ── Master list ──

    private static final List<RegisteredFeature> ALL = List.of(
        // Oracle recipes
        ORACLE_ROWNUM, ORACLE_CONNECT_BY, ORACLE_MERGE_INTO, ORACLE_TRUNC,
        ORACLE_MONTHS_BETWEEN, ORACLE_ADD_MONTHS, ORACLE_LISTAGG, ORACLE_REGEXP_SUBSTR,
        // Oracle simple
        ORACLE_DECODE, ORACLE_NVL, ORACLE_NVL2, ORACLE_FROM_DUAL, ORACLE_OUTER_JOIN,
        ORACLE_START_WITH, ORACLE_TO_CHAR, ORACLE_TO_DATE, ORACLE_INSTR,
        ORACLE_SYSDATE, ORACLE_USER, ORACLE_UID, ORACLE_INITCAP, ORACLE_PIVOT, ORACLE_UNPIVOT,
        ORACLE_REGEXP_LIKE, ORACLE_TO_NUMBER, ORACLE_SUBSTR, ORACLE_SYSTIMESTAMP,
        ORACLE_TO_TIMESTAMP, ORACLE_REGEXP_REPLACE,
        // MySQL
        MYSQL_IFNULL, MYSQL_DATE_FORMAT, MYSQL_GROUP_CONCAT, MYSQL_AUTO_INC,
        MYSQL_ENUM, MYSQL_DUP_KEY, MYSQL_REGEXP, MYSQL_NOW,
        MYSQL_TINYINT, MYSQL_BIT, MYSQL_BACKTICK, MYSQL_ENGINE,
        MYSQL_CHARSET, MYSQL_COLLATE, MYSQL_UNSIGNED, MYSQL_ZEROFILL
    );

    private static RegisteredFeature simple(String keyword, String mapping, String dialect) {
        return new RegisteredFeature(keyword, mapping, dialect, null, null, null, null, null);
    }

    // ── Public API ──

    /** 返回某方言的所有注册特征。 */
    public static List<RegisteredFeature> allFor(String dialect) {
        if (dialect == null || dialect.isBlank()) return List.of();
        String d = dialect.toLowerCase(Locale.ROOT);
        return ALL.stream()
            .filter(f -> f.dialectGroup().equals(d))
            .toList();
    }

    /** 根据关键词查找已注册特征（含 recipe 和 simple）。 */
    public static RegisteredFeature get(String sourceFeatureKeyword, String dialect) {
        if (sourceFeatureKeyword == null || dialect == null) return null;
        String kw = sourceFeatureKeyword.toUpperCase(Locale.ROOT);
        String d = dialect.toLowerCase(Locale.ROOT);
        return ALL.stream()
            .filter(f -> f.sourceKeyword().toUpperCase(Locale.ROOT).equals(kw) && f.dialectGroup().equals(d))
            .findFirst().orElse(null);
    }

    /** 仅返回含 few-shot 的 recipe 条目（用于格式化注入 prompt）。 */
    public static List<RegisteredFeature> recipesOnly(List<RegisteredFeature> features) {
        if (features == null || features.isEmpty()) return List.of();
        return features.stream().filter(RegisteredFeature::isRecipe).toList();
    }

    /** 检查某方言中某关键词是否已注册。 */
    public static boolean isRegistered(String keyword, String dialect) {
        return get(keyword, dialect) != null;
    }

    /** 将 Recipe 列表格式化为 prompt-ready 文本块。非 recipe 条目跳过。 */
    public static String formatRecipesForPrompt(List<RegisteredFeature> features) {
        if (features == null || features.isEmpty()) return "";
        List<RegisteredFeature> recipes = recipesOnly(features);
        if (recipes.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        sb.append("\n=== Detailed Conversion Recipes (MUST FOLLOW step-by-step) ===\n");
        for (RegisteredFeature r : recipes) {
            sb.append("\n--- Recipe: ").append(r.constructName()).append(" ---\n");
            sb.append("Source example:\n  ").append(r.fewShotSource()).append("\n");
            sb.append("Target example:\n  ").append(r.fewShotTarget()).append("\n");
            sb.append("Steps:\n").append(r.stepByStepGuide()).append("\n");
            sb.append("Pitfalls to AVOID:\n");
            for (String pitfall : r.commonPitfalls()) {
                sb.append("  - ").append(pitfall).append("\n");
            }
        }
        return sb.toString();
    }
}
