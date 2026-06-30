package com.zhiqian.migration;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.yaml.snakeyaml.Yaml;

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
        "ROLLBACK", "GRANT", "REVOKE", "TRUNCATE", "EXPLAIN", "ANALYZE", "VACUUM",
        // SQL:2003+ PG standard clauses (Phase 2 误检会导致 LLM 过度转换)
        "FILTER", "OVER", "PARTITION", "FRAME", "ROWS", "RANGE", "FETCH", "FIRST", "NEXT", "ONLY",
        "USING", "RETURNING", "LATERAL", "WINDOW", "ILIKE", "SIMILAR", "BETWEEN", "LIKE",
        "ANY", "ALL", "SOME", "ASC", "DESC", "NULLS", "TRUE", "FALSE", "IF", "LOOP", "RETURN",
        "DECLARE", "EXCEPTION", "PERFORM", "FOREACH", "ARRAY", "JSONB", "JSON", "BOOLEAN",
        "TEXT", "VARCHAR", "INTEGER", "BIGINT", "NUMERIC", "TIMESTAMP", "TIMESTAMPTZ", "DATE",
        "INTERVAL", "SERIAL", "BIGSERIAL", "UUID", "BYTEA", "FLOAT8", "FLOAT4", "INT2", "INT4", "INT8"
    );

    private static final Logger log = LoggerFactory.getLogger(DialectFeatureScanner.class);

    // ── Per-dialect whitelist additions loaded from YAML ──
    private static final Map<String, Set<String>> DIALECT_WHITELIST_ADDITIONS = loadWhitelistFromYaml();

    @SuppressWarnings("unchecked")
    private static Map<String, Set<String>> loadWhitelistFromYaml() {
        Map<String, Set<String>> result = new ConcurrentHashMap<>();
        try {
            Path dir = resolveDialectsDir();
            if (Files.isDirectory(dir)) {
                Yaml yaml = new Yaml();
                try (Stream<Path> files = Files.list(dir)) {
                    for (Path f : files.filter(p -> p.toString().endsWith(".yaml")).toList()) {
                        Map<String, Object> data = yaml.load(Files.readString(f));
                        String dialect = (String) data.get("name");
                        List<String> whitelist = (List<String>) data.get("standard_whitelist");
                        if (dialect != null && whitelist != null && !whitelist.isEmpty()) {
                            result.put(dialect, Set.copyOf(whitelist));
                            log.info("[DialectFeatureScanner] Loaded {} whitelist entries for dialect '{}'",
                                    whitelist.size(), dialect);
                        }
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[DialectFeatureScanner] Failed to load whitelist from YAML: {}", e.getMessage());
        }
        return result;
    }

    private static Path resolveDialectsDir() {
        String configured = System.getProperty("kb.yaml.path", "");
        if (!configured.isBlank()) {
            return Paths.get(configured, "dialects");
        }
        Path cwd = Paths.get(System.getProperty("user.dir", "."));
        for (int i = 0; i < 5; i++) {
            Path kb = cwd.resolve("kb/active/dialects");
            if (Files.isDirectory(kb)) return kb;
            cwd = cwd.getParent();
            if (cwd == null) break;
        }
        return Paths.get("kb/active/dialects");
    }

    // 大写函数调用正则：至少 3 个字符的大写标识符后跟 (
    private static final Pattern CAP_FUNC = Pattern.compile("\\b([A-Z][A-Z0-9_]{2,})\\s*\\(");

    /**
     * 双阶段扫描 SQL，返回检测到的特征。
     * P2: 先剥离注释和字符串字面量，避免评论/字面量中的关键词导致误检。
     */
    public static List<DetectedFeature> scan(String sql, String sourceDialect) {
        if (sql == null || sql.isBlank()) return List.of();
        String dial = sourceDialect.toLowerCase(Locale.ROOT);
        List<RegisteredFeature> registry = TranslationRecipeRegistry.allFor(dial);
        if (registry.isEmpty()) return List.of();

        // P2: 剥离注释和字符串字面量后再做匹配
        String clean = stripCommentsAndStrings(sql);
        String lower = clean.toLowerCase(Locale.ROOT);

        List<DetectedFeature> found = new ArrayList<>();

        // ── Phase 1: 已注册特征的精确关键词匹配（基于清洁后的 SQL）──
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

        // ── Phase 2: 启发式宽筛 — 检测大写函数调用中的未注册项（基于清洁后的 SQL）──
        Set<String> phase1Keywords = found.stream()
            .map(f -> f.sourceFeature().toUpperCase(Locale.ROOT))
            .collect(Collectors.toSet());

        Set<String> seen = new LinkedHashSet<>();
        java.util.regex.Matcher m = CAP_FUNC.matcher(clean);
        while (m.find()) {
            String func = m.group(1).toUpperCase(Locale.ROOT);
            // 跳过 PG 标准函数（含 per-dialect 白名单扩展）、SQL 关键字、已注册特征
            if (PG_STANDARD.contains(func)) continue;
            Set<String> dialectAdditions = DIALECT_WHITELIST_ADDITIONS.get(dial);
            if (dialectAdditions != null && dialectAdditions.contains(func)) continue;
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

    // ── P2: 注释/字面量剥离 ──

    /**
     * 剥离 SQL 中的注释和字符串字面量，用空格替换被剥离的内容。
     * 消除以下误检场景：
     *   - 注释中的关键词：-- Use CONNECT BY for hierarchy
     *   - 字符串中的关键词：SELECT 'ROWNUM is not supported' FROM dual
     *   - 多行注释中的函数名：/&#42; NVL() is deprecated &#42;/
     */
    private static String stripCommentsAndStrings(String sql) {
        StringBuilder out = new StringBuilder(sql.length());
        int i = 0;
        int len = sql.length();
        while (i < len) {
            char c = sql.charAt(i);
            // 单行注释 --
            if (c == '-' && i + 1 < len && sql.charAt(i + 1) == '-') {
                out.append(' '); // replace first -
                out.append(' '); // replace second -
                i += 2;
                while (i < len && sql.charAt(i) != '\n') {
                    out.append(' ');
                    i++;
                }
                if (i < len) { out.append('\n'); i++; }
                continue;
            }
            // 多行注释 /* */
            if (c == '/' && i + 1 < len && sql.charAt(i + 1) == '*') {
                out.append(' '); // replace /
                out.append(' '); // replace *
                i += 2;
                while (i + 1 < len && !(sql.charAt(i) == '*' && sql.charAt(i + 1) == '/')) {
                    out.append(sql.charAt(i) == '\n' ? '\n' : ' ');
                    i++;
                }
                if (i + 1 < len) { out.append("  "); i += 2; } // replace */
                continue;
            }
            // 字符串字面量 '...'（处理转义 '' → 两个单引号）
            if (c == '\'') {
                out.append(' '); // replace opening '
                i++;
                while (i < len) {
                    if (sql.charAt(i) == '\'' && i + 1 < len && sql.charAt(i + 1) == '\'') {
                        out.append("  "); // escaped quote ''
                        i += 2;
                    } else if (sql.charAt(i) == '\'') {
                        out.append(' '); // replace closing '
                        i++;
                        break;
                    } else {
                        out.append(sql.charAt(i) == '\n' ? '\n' : ' ');
                        i++;
                    }
                }
                continue;
            }
            out.append(c);
            i++;
        }
        return out.toString();
    }

    // ── 关键词匹配 ──

    private static boolean matches(String keyword, String lowerSql) {
        return switch (keyword) {
            case "(+)" -> lowerSql.contains("(+)");
            case "`" -> lowerSql.indexOf('`') >= 0;
            case "[" -> lowerSql.indexOf('[') >= 0;
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
        if (keyword.contains("(") || keyword.equalsIgnoreCase("SYSDATE") || keyword.equalsIgnoreCase("SYSTIMESTAMP")) return "function";
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
