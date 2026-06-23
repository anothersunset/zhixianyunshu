package com.zhiqian.migration;

import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * 翻译配方注册表：为复杂 SQL 构造提供完整 few-shot 示例和分步指南。
 * 当 DialectFeatureScanner 检测到这些构造时，将配方注入生成 prompt，
 * 替代原来仅一行的模糊提示。
 */
public class TranslationRecipeRegistry {

    public record TranslationRecipe(
        String constructName,
        String detectionKeyword,
        String fewShotSource,
        String fewShotTarget,
        String stepByStepGuide,
        List<String> commonPitfalls
    ) {}

    private static final Map<String, TranslationRecipe> RECIPES = Map.of(
        "ROWNUM", new TranslationRecipe(
            "ROWNUM Pagination",
            "ROWNUM",
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
        ),
        "CONNECT BY", new TranslationRecipe(
            "CONNECT BY Hierarchy",
            "CONNECT BY",
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
        ),
        "MERGE INTO", new TranslationRecipe(
            "MERGE INTO Upsert",
            "MERGE INTO",
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
        ),
        "TRUNC(", new TranslationRecipe(
            "TRUNC — distinguish numeric vs date",
            "TRUNC(",
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
        ),
        "MONTHS_BETWEEN(", new TranslationRecipe(
            "MONTHS_BETWEEN — COPY THE OUTPUT EXACTLY",
            "MONTHS_BETWEEN(",
            "SELECT MONTHS_BETWEEN(date1, date2) FROM t",
            "SELECT EXTRACT(YEAR FROM age(date1, date2)) * 12 + EXTRACT(MONTH FROM age(date1, date2)) FROM t",
            "COPY the Target example output character-by-character. Do NOT add EXTRACT(DAY ...) or any day fraction.",
            List.of(
                "NEVER add + EXTRACT(DAY FROM ...) / N to the formula."
            )
        ),
        "ADD_MONTHS(", new TranslationRecipe(
            "ADD_MONTHS — COPY THE OUTPUT EXACTLY",
            "ADD_MONTHS(",
            "SELECT ADD_MONTHS(hire_date, 6) FROM emp",
            "SELECT hire_date + INTERVAL '6 months' FROM emp",
            "1. Replace ADD_MONTHS(date_col, N) with date_col + INTERVAL 'N months'.\n2. If N is negative, use - INTERVAL 'N months'.\n3. Do NOT use MAKE_INTERVAL or DATE_PLUS.",
            List.of(
                "NEVER use DATEADD() or DATE_ADD() — PostgreSQL does not have these.",
                "NEVER use MAKE_INTERVAL(months => N) — use the simpler INTERVAL syntax."
            )
        ),
        "LISTAGG(", new TranslationRecipe(
            "LISTAGG — COPY THE OUTPUT EXACTLY",
            "LISTAGG(",
            "SELECT LISTAGG(name, ',') WITHIN GROUP (ORDER BY name) FROM emp GROUP BY dept",
            "SELECT STRING_AGG(name, ',' ORDER BY name) FROM emp GROUP BY dept",
            "1. Replace LISTAGG(col, delim) WITHIN GROUP (ORDER BY col) with STRING_AGG(col, delim ORDER BY col).\n2. The delimiter is the second argument to both functions.\n3. WITHIN GROUP (ORDER BY ...) becomes the ORDER BY clause inside STRING_AGG.",
            List.of(
                "NEVER use GROUP_CONCAT — that is MySQL syntax.",
                "The ORDER BY goes INSIDE STRING_AGG, not in a separate clause."
            )
        ),
        "REGEXP_SUBSTR(", new TranslationRecipe(
            "REGEXP_SUBSTR — COPY THE OUTPUT EXACTLY",
            "REGEXP_SUBSTR(",
            "SELECT REGEXP_SUBSTR(email, '[^@]+') FROM users",
            "SELECT (REGEXP_MATCHES(email, '[^@]+'))[1] FROM users",
            "COPY the Target example output character-by-character. Do NOT invent shortcuts like split_part. Use REGEXP_MATCHES (with S). Do NOT use SUBSTRING, regexp_match, or split_part.",
            List.of(
                "NEVER use SUBSTRING() for regex extraction.",
                "NEVER use regexp_match (singular, without S). Use REGEXP_MATCHES (plural).",
                "NEVER use split_part() as a shortcut for REGEXP_SUBSTR — it is not equivalent for general regex patterns."
            )
        )
    );

    /** 根据检测到的特征关键词查找匹配的 Recipe。 */
    public static TranslationRecipe get(String sourceFeature) {
        if (sourceFeature == null) return null;
        return RECIPES.get(sourceFeature.toUpperCase());
    }

    /** 将 Recipe 列表格式化为 prompt-ready 文本块。 */
    public static String formatRecipesForPrompt(List<TranslationRecipe> recipes) {
        if (recipes == null || recipes.isEmpty()) return "";
        StringBuilder sb = new StringBuilder();
        sb.append("\n=== Detailed Conversion Recipes (MUST FOLLOW step-by-step) ===\n");
        for (TranslationRecipe r : recipes) {
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
