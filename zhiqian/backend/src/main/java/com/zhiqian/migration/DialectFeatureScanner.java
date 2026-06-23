package com.zhiqian.migration;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 规则引擎：零 LLM 调用的 SQL 方言特征扫描器。
 * 输入源 SQL + 源方言，输出检测到的特征及其目标映射。
 * 与旧 TYPE_MAPPING_HINTS 的关键区别：基于具体 SQL 动态检测，非固定模板。
 */
public class DialectFeatureScanner {

    private static final Map<String, Map<String, String>> FEATURE_MAP = Map.of(
        "oracle", Map.ofEntries(
            Map.entry("DECODE(", "CASE WHEN"),
            Map.entry("NVL(", "COALESCE"),
            Map.entry("NVL2(", "CASE WHEN ... THEN ... ELSE"),
            Map.entry("ROWNUM", "LIMIT (simple pagination) or ROW_NUMBER() OVER(ORDER BY ...) (complex)"),
            Map.entry("FROM DUAL", "omit DUAL"),
            Map.entry("(+)", "standard LEFT/RIGHT JOIN"),
            Map.entry("CONNECT BY", "WITH RECURSIVE"),
            Map.entry("START WITH", "WITH RECURSIVE anchor clause"),
            Map.entry("TO_CHAR(", "TO_CHAR (format review needed)"),
            Map.entry("TO_DATE(", "TO_DATE (format review needed)"),
            Map.entry("TRUNC(", "TRUNC for numbers (same in PG), DATE_TRUNC for dates"),
            Map.entry("INSTR(", "POSITION / STRPOS"),
            Map.entry("MONTHS_BETWEEN(", "===PRECISE OUTPUT: EXTRACT(YEAR FROM age(a,b))*12 + EXTRACT(MONTH FROM age(a,b))===. NO day components."),
            Map.entry("REGEXP_SUBSTR(", "===PRECISE OUTPUT: (REGEXP_MATCHES(str,pattern))[1]===. MATCHES has S. Not SUBSTRING."),
            Map.entry("ADD_MONTHS(", "date + INTERVAL 'n months'"),
            Map.entry("LISTAGG(", "STRING_AGG(col, delim ORDER BY col)"),
            Map.entry("SYSDATE", "CURRENT_TIMESTAMP"),
            Map.entry("USER", "CURRENT_USER"),
            Map.entry("UID", "CURRENT_USER"),
            Map.entry("INITCAP(", "INITCAP (pg compatible, verify)"),
            Map.entry("MERGE INTO", "INSERT ... ON CONFLICT"),
            Map.entry("PIVOT(", "CROSSTAB / conditional aggregation"),
            Map.entry("UNPIVOT(", "UNNEST / lateral join")
        ),
        "mysql", Map.ofEntries(
            Map.entry("IFNULL(", "COALESCE"),
            Map.entry("DATE_FORMAT(", "TO_CHAR"),
            Map.entry("GROUP_CONCAT(", "STRING_AGG"),
            Map.entry("AUTO_INCREMENT", "SERIAL / SEQUENCE"),
            Map.entry("ENUM(", "VARCHAR + CHECK or CREATE TYPE"),
            Map.entry("ON DUPLICATE KEY", "ON CONFLICT ... DO UPDATE"),
            Map.entry("REGEXP", "~ (or SIMILAR TO / regexp_matches)"),
            Map.entry("NOW()", "CURRENT_TIMESTAMP"),
            Map.entry("TINYINT", "SMALLINT"),
            Map.entry("BIT(", "BOOLEAN"),
            Map.entry("`", "remove backticks (use \" or unquoted)"),
            Map.entry("ENGINE=", "omit ENGINE clause"),
            Map.entry("CHARACTER SET", "omit or adjust charset"),
            Map.entry("COLLATE", "omit collation"),
            Map.entry("UNSIGNED", "use CHECK constraint instead"),
            Map.entry("ZEROFILL", "LPAD or format")
        )
    );

    /**
     * 扫描 SQL，返回检测到的特征及其目标映射。
     */
    public static List<DetectedFeature> scan(String sql, String sourceDialect) {
        if (sql == null || sql.isBlank()) return List.of();
        String lower = sql.toLowerCase(Locale.ROOT);
        Map<String, String> mappings = FEATURE_MAP.getOrDefault(
            sourceDialect.toLowerCase(Locale.ROOT), Map.of());

        List<DetectedFeature> found = new ArrayList<>();
        for (var entry : mappings.entrySet()) {
            String keyword = entry.getKey().toLowerCase(Locale.ROOT);
            if (matches(keyword, lower)) {
                found.add(new DetectedFeature(entry.getKey(), entry.getValue(), categorize(keyword)));
            }
        }
        return found;
    }

    /**
     * 根据检测到的特征查找匹配的翻译配方。
     */
    public static List<TranslationRecipeRegistry.TranslationRecipe> getRecipes(List<DetectedFeature> features) {
        if (features == null || features.isEmpty()) return List.of();
        return features.stream()
            .map(f -> TranslationRecipeRegistry.get(f.sourceFeature()))
            .filter(Objects::nonNull)
            .toList();
    }

    /**
     * 格式化为 prompt-ready 简短提示。
     */
    public static String toPromptHints(List<DetectedFeature> features) {
        return toPromptHints(features, getRecipes(features));
    }

    /**
     * 格式化为 prompt-ready 提示，含完整翻译配方。
     * 有配方的特征标记为 SEE DETAILED RECIPE，并在末尾追加配方文本。
     */
    public static String toPromptHints(List<DetectedFeature> features,
                                        List<TranslationRecipeRegistry.TranslationRecipe> recipes) {
        if (features == null || features.isEmpty()) return "";
        // 有配方的特征名集合
        Set<String> recipeFeatures = recipes != null
            ? recipes.stream()
                .map(r -> r.detectionKeyword().toUpperCase(Locale.ROOT))
                .collect(Collectors.toSet())
            : Set.of();

        StringBuilder sb = new StringBuilder();
        sb.append("Detected source-dialect features — convert each:\n");
        for (var f : features) {
            if (recipeFeatures.contains(f.sourceFeature().toUpperCase(Locale.ROOT))) {
                sb.append("  ").append(f.sourceFeature())
                  .append(" → SEE DETAILED RECIPE BELOW\n");
            } else {
                sb.append("  ").append(f.sourceFeature())
                  .append(" → ").append(f.targetMapping()).append("\n");
            }
        }
        // 追加完整 recipe 文本
        String recipeText = TranslationRecipeRegistry.formatRecipesForPrompt(recipes);
        if (!recipeText.isBlank()) {
            sb.append(recipeText);
        }
        return sb.toString();
    }

    /** 特征匹配，处理特殊关键词。 */
    private static boolean matches(String keyword, String lowerSql) {
        return switch (keyword) {
            case "(+)" -> lowerSql.contains("(+)");
            case "`" -> lowerSql.indexOf('`') >= 0;
            case "from dual" ->
                // 匹配 FROM DUAL（可能跨行）
                lowerSql.replaceAll("\\s+", " ").contains("from dual");
            case "character set" -> lowerSql.contains("character set");
            case "on duplicate key" ->
                lowerSql.contains("on duplicate key");
            case "connect by" -> lowerSql.contains("connect by");
            case "start with" -> lowerSql.contains("start with");
            case "merge into" ->
                lowerSql.replaceAll("\\s+", " ").contains("merge into");
            default -> {
                // 一般匹配：keyword 作为独立词或带 ( 后缀
                if (keyword.endsWith("(")) {
                    yield lowerSql.contains(keyword);
                }
                // 用单词边界匹配（含行首行尾）
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

    public record DetectedFeature(String sourceFeature, String targetMapping, String category) {}
}
