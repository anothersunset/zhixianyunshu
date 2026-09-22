package com.zhiqian.migration;

import org.junit.jupiter.api.Test;

import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

class SqlSyntaxValidatorTest {
    @Test
    void parsesJsonFromStdoutWithoutMixingSqlglotStderrDiagnostics() {
        var result = SqlSyntaxValidator.parseResult(
            "{\"valid\":false,\"error\":\"Expecting )\"}\n",
            "'unsupported syntax' contains unsupported syntax\n",
            0
        );

        assertThat(result.valid()).isFalse();
        assertThat(result.error()).isEqualTo("Expecting )");
    }

    @Test
    void reportsMissingValidatorOutputClearly() {
        var result = SqlSyntaxValidator.parseResult("", "python: module not found", 1);

        assertThat(result.valid()).isFalse();
        assertThat(result.error()).contains("code 1").contains("module not found");
    }

    @Test
    void mapsSqlserverDialectToSqlglotTsql() {
        assertThat(SqlSyntaxValidator.normalizeDialect("sqlserver")).isEqualTo("tsql");
        assertThat(SqlSyntaxValidator.normalizeDialect("SQLServer")).isEqualTo("tsql");
        assertThat(SqlSyntaxValidator.normalizeDialect("SQL Server")).isEqualTo("tsql");
        assertThat(SqlSyntaxValidator.normalizeDialect("mssql")).isEqualTo("tsql");

        // 既有映射不回归
        assertThat(SqlSyntaxValidator.normalizeDialect("opengauss")).isEqualTo("postgres");
        assertThat(SqlSyntaxValidator.normalizeDialect("mysql")).isEqualTo("mysql");
        assertThat(SqlSyntaxValidator.normalizeDialect("oracle")).isEqualTo("oracle");
        assertThat(SqlSyntaxValidator.normalizeDialect(null)).isEqualTo("postgres");
        assertThat(SqlSyntaxValidator.normalizeDialect("PostgreSQL 16")).isEqualTo("postgres");
    }

    @Test
    void validatesSqlserverTargetSqlWithoutFalsePositiveWhenPythonAvailable() throws Exception {
        assumeTrue(pythonWithSqlglotAvailable(), "python/sqlglot toolchain not available");

        // T-SQL 专属语法（TOP / 方括号标识符 / @参数）必须通过校验，
        // 此前 normalizeDialect 缺少 sqlserver→tsql 映射时必然误报
        var result = SqlSyntaxValidator.validate(
            "SELECT TOP (5) [name] FROM [dbo].[users] WHERE [id] = @id", "sqlserver");

        assertThat(result.valid()).as("error: %s", result.error()).isTrue();
    }

    private static boolean pythonWithSqlglotAvailable() {
        for (String python : new String[]{"python3", "python"}) {
            try {
                Process check = new ProcessBuilder(python, "-c", "import sqlglot")
                    .redirectErrorStream(true).start();
                if (check.waitFor(10, TimeUnit.SECONDS) && check.exitValue() == 0) {
                    return true;
                }
            } catch (Exception ignored) {
                // try next candidate
            }
        }
        return false;
    }
}
