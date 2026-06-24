package com.zhiqian.migration;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import com.zhiqian.migration.TranslationRecipeRegistry.RegisteredFeature;

/**
 * 规则引擎：零 LLM 调用的 SQL 方言特征扫描器。
 * 两阶段检测：
 *   Phase 1 — 从 TranslationRecipeRegistry 统一注册表做精确关键词匹配
 *   Phase 2 — 启发式宽筛，用 PG 标准函数白名单过滤，未知函数标记为 UNKNOWN
 */
public class DialectFeatureScanner {

    // PG 标准函数/关键字白名单 — 永远不会是需要转换的方言特征
    private static final Set<String> PG_STANDARD = Set.of(
        "ABS", "TRIM", "UPPER", "LOWER", "LENGTH", "COUNT", "SUM", "AVG", "MAX", "MIN",
        "COALESCE", "CAST", "EXTRACT", "SUBSTRING", "POSITION", "NULLIF",
        "ROW_NUMBER", "RANK", "DENSE_RANK", "LEAD", "LAG", "FIRST_VALUE", "LAST_VALUE",
        "STRING_AGG", "ARRAY_AGG", "NOW", "CURRENT_DATE", "CURRENT_TIMESTAMP",
        "EXISTS", "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP",
        "CASE", "WHEN", "THEN", "ELSE", "END", "IN", "NOT", "AND", "OR", "IS", "NULL",
        "LEFT", "RIGHT", "INNER", "OUTER", "JOIN", "CROSS", "FULL", "ON", "WHERE",
        "GROUP", "ORDER", "BY", "HAVING", "UNION", "INTERSECT", "EXCEPT", "LIMIT", "OFFSET",
        "WITH", "RECURSIVE", "VALUES", "DISTINCT", "AS", "FROM", "INTO", "SET", "DEFAULT",
        "TABLE", "INDEX", "VIEW", "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "CONSTRAINT",
        "CHECK", "UNIQUE", "NOT_NULL", "ADD", "COLUMN", "TYPE", "RENAME", "BEGIN", "COMMIT",
        "ROLLBACK", "GRANT", "REVOKE", "TRUNCATE", "EXPLAIN", "ANALYZE", "VACUUM"
    );

    // 大写函数调用正则：至少 3 个字符的大写标识符后跟 (
    private static final Pattern CAP_FUNC = Pattern.compile("\\b([A-Z][A-Z0-9_]{2,})\\s*\\(");

    /**
     * 双阶段扫描 SQL，返回检测到的特征。
     */
    public static List<DetectedFeature> scan(String sql, String sourceDialect) {
        if (sql == null || sql.isBlank()) return List.of();
        String lower = sql.toLowerCase(Locale.ROOT);
        String dial = sourceDialect.toLowerCase(Locale.ROOT);
        List<RegisteredFeature> registry = TranslationRecipeRegistry.allFor(dial);
        if (registry.isEmpty()) return List.of();

        List<DetectedFeature> found = new ArrayList<>();

        // ── Phase 1: 已注册特征的精确关键词匹配 ──
        for (RegisteredFeature f : registry) {
            String keyword = f.sourceKeyword().toLowerCase(Locale.ROOT);
            if (matches(keyword, lower)) {
                found.add(new DetectedFeature(
                    f.sourceKeyword(),
                    f.targetMapping(),
                    categorize(keyword),
                    f.isRecipe()
                ));
            }
        }

        // ── Phase 2: 启发式宽筛 — 检测大写函数调用中的未注册项 ──
        Set<String> phase1Keywords = found.stream()
            .map(f -> f.sourceFeature().toUpperCase(Locale.ROOT))
            .collect(Collectors.toSet());

        Set<String> seen = new LinkedHashSet<>();
        java.util.regex.Matcher m = CAP_FUNC.matcher(sql);
        while (m.find()) {
            String func = m.group(1).toUpperCase(Locale.ROOT);
            // 跳过 PG 标准函数、SQL 关键字、已注册特征
            if (PG_STANDARD.contains(func)) continue;
            if (phase1Keywords.contains(func)) continue;
            // 同义词去重（INSTR 和 INSTR( 可能分别注册）
            if (phase1Keywords.contains(func + "(")) continue;
            if (!seen.add(func)) continue;

            found.add(new DetectedFeature(
                func + "(",
                "⚠ UNKNOWN: check PG equivalent",
                "function",
                false
            ));
        }

        return found;
    }

    /**
     * 根据检测到的特征，筛选出含 few-shot 的 Recipe 条目。
     */
    public static List<RegisteredFeature> getRecipes(
            List<DetectedFeature> features, String sourceDialect) {
        if (features == null || features.isEmpty()) return List.of();
        String dial = sourceDialect.toLowerCase(Locale.ROOT);
        return features.stream()
            .filter(DetectedFeature::isRecipe)
            .map(f -> TranslationRecipeRegistry.get(f.sourceFeature(), dial))
            .filter(r -> r != null && r.isRecipe())
            .toList();
    }

    /**
     * 格式化为 prompt-ready 简短提示（自动附带 recipe）。
     */
    public static String toPromptHints(List<DetectedFeature> features, String sourceDialect) {
        List<RegisteredFeature> recipes = getRecipes(features, sourceDialect);
        return toPromptHints(features, recipes);
    }

    /**
     * 格式化为 prompt-ready 提示，含完整翻译配方。
     * 有配方的特征标记为 SEE DETAILED RECIPE，并在末尾追加配方文本。
     */
    public static String toPromptHints(List<DetectedFeature> features,
                                        List<RegisteredFeature> recipes) {
        if (features == null || features.isEmpty()) return "";
        Set<String> recipeKeywords = recipes != null
            ? recipes.stream()
                .map(r -> r.sourceKeyword().toUpperCase(Locale.ROOT))
                .collect(Collectors.toSet())
            : Set.of();

        StringBuilder sb = new StringBuilder();
        sb.append("Detected source-dialect features — convert each:\n");
        for (var f : features) {
            if (recipeKeywords.contains(f.sourceFeature().toUpperCase(Locale.ROOT))) {
                sb.append("  ").append(f.sourceFeature())
                  .append(" → SEE DETAILED RECIPE BELOW\n");
            } else {
                sb.append("  ").append(f.sourceFeature())
                  .append(" → ").append(f.targetMapping()).append("\n");
            }
        }
        String recipeText = TranslationRecipeRegistry.formatRecipesForPrompt(recipes);
        if (!recipeText.isBlank()) {
            sb.append(recipeText);
        }
        return sb.toString();
    }

    // ── 关键词匹配 ──

    private static boolean matches(String keyword, String lowerSql) {
        return switch (keyword) {
            case "(+)" -> lowerSql.contains("(+)");
            case "`" -> lowerSql.indexOf('`') >= 0;
            case "from dual" ->
                lowerSql.replaceAll("\\s+", " ").contains("from dual");
            case "character set" -> lowerSql.contains("character set");
            case "on duplicate key" ->
                lowerSql.contains("on duplicate key");
            case "connect by" -> lowerSql.contains("connect by");
            case "start with" -> lowerSql.contains("start with");
            case "merge into" ->
                lowerSql.replaceAll("\\s+", " ").contains("merge into");
            default -> {
                if (keyword.endsWith("(")) {
                    yield lowerSql.contains(keyword);
                }
                yield lowerSql.matches("(?s).*\\b" + java.util.regex.Pattern.quote(keyword) + "\\b.*");
            }
        };
    }

    private static String categorize(String keyword) {
        if (keyword.contains("(") || keyword.equalsIgnoreCase("SYSDATE")) return "function";
        if (keyword.equalsIgnoreCase("CONNECT BY") || keyword.equalsIgnoreCase("START WITH")
            || keyword.equalsIgnoreCase("ON DUPLICATE KEY") || keyword.equalsIgnoreCase("MERGE INTO")
            || keyword.equalsIgnoreCase("FROM DUAL") || keyword.equalsIgnoreCase("PIVOT(")
            || keyword.equalsIgnoreCase("UNPIVOT(")) return "syntax";
        if (keyword.equalsIgnoreCase("ENUM(") || keyword.equalsIgnoreCase("AUTO_INCREMENT")
            || keyword.equalsIgnoreCase("TINYINT") || keyword.equalsIgnoreCase("BIT(")) return "type";
        if (keyword.equals("(+)")) return "operator";
        if (keyword.equalsIgnoreCase("ROWNUM")) return "pseudo-column";
        return "misc";
    }

    public record DetectedFeature(
        String sourceFeature,
        String targetMapping,
        String category,
        boolean isRecipe
    ) {}
}
