package com.zhiqian.migration;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 调用 Python sqlglot 脚本验证目标 SQL 语法。
 * 通过 ProcessBuilder 执行，3 秒超时。
 * 注意：这是语法层面验证（token/parse错误），不检查语义或方言兼容性。
 */
public class SqlSyntaxValidator {

    private static final Logger log = LoggerFactory.getLogger(SqlSyntaxValidator.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    // 从 zhiqian/backend/ 到 eval/sql_validate.py
    private static final String SCRIPT_PATH = "../../eval/sql_validate.py";

    /** 验证 SQL 在目标方言上是否语法正确。 */
    public static ValidationResult validate(String sql, String targetDialect) {
        if (sql == null || sql.isBlank()) {
            return new ValidationResult(false, "Empty SQL");
        }
        String dialect = normalizeDialect(targetDialect);

        try {
            ProcessBuilder pb = new ProcessBuilder(
                findPython(), SCRIPT_PATH, sql, dialect);
            pb.redirectErrorStream(true);
            Process proc = pb.start();

            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(proc.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line);
                }
            }
            boolean finished = proc.waitFor(5, TimeUnit.SECONDS);
            if (!finished) {
                proc.destroyForcibly();
                return new ValidationResult(false, "Validation timed out (5s)");
            }

            @SuppressWarnings("unchecked")
            Map<String, Object> result = MAPPER.readValue(output.toString(), Map.class);
            boolean valid = Boolean.TRUE.equals(result.get("valid"));
            String error = result.get("error") != null ? String.valueOf(result.get("error")) : null;
            return new ValidationResult(valid, error);

        } catch (Exception e) {
            log.warn("[SqlSyntaxValidator] validation failed: {}", e.getMessage());
            return new ValidationResult(false, "Validator error: " + e.getMessage());
        }
    }

    private static String findPython() {
        // 尝试 python3, python 顺序
        for (String candidate : new String[]{"python3", "python"}) {
            try {
                ProcessBuilder pb = new ProcessBuilder(candidate, "--version");
                pb.redirectErrorStream(true);
                Process proc = pb.start();
                boolean ok = proc.waitFor(3, TimeUnit.SECONDS);
                if (ok && proc.exitValue() == 0) return candidate;
            } catch (Exception ignored) { }
        }
        return "python3"; // 默认
    }

    /** 将后端方言名映射为 sqlglot 方言名 */
    private static String normalizeDialect(String dialect) {
        if (dialect == null) return "postgres";
        return switch (dialect.toLowerCase()) {
            case "opengauss" -> "postgres";
            case "mysql" -> "mysql";
            case "oracle" -> "oracle";
            default -> dialect.contains("postgres") ? "postgres" : dialect.toLowerCase();
        };
    }

    public record ValidationResult(boolean valid, String error) {}
}
