package com.zhiqian.migration;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * fixupStubbornPatterns 直接单测（方法已改包私有，先例：DialectFeatureScanner.normalizeDialect）。
 * 只断言每条规则代表性的输入→输出，不测正则实现细节。
 */
class FixupStubbornPatternsTest {

    @Test
    void blankOrNullSqlPassesThroughUnchanged() {
        assertThat(MigrationEvalController.fixupStubbornPatterns(null, "SELECT SYSDATE FROM dual")).isNull();
        assertThat(MigrationEvalController.fixupStubbornPatterns("", "SELECT 1")).isEmpty();
        assertThat(MigrationEvalController.fixupStubbornPatterns("   ", "SELECT 1")).isEqualTo("   ");
    }

    @Test
    void rewritesConnectByLevelStartFromZero() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "WITH RECURSIVE t AS (SELECT 1 AS lvl UNION ALL SELECT lvl + 1 FROM t WHERE lvl < 5) SELECT * FROM t",
            "SELECT LEVEL FROM dual CONNECT BY LEVEL <= 5");
        assertThat(fixed).contains("SELECT 0 AS lvl");
        assertThat(fixed).doesNotContain("1 AS lvl");
        // 递增项 lvl + 1 不应被误改
        assertThat(fixed).contains("lvl + 1");
    }

    @Test
    void stripsMonthsBetweenDayFraction() {
        // deepseek-chat 常见的错误加项：+ EXTRACT(DAY FROM age(...))[/30.4]，可带 ::numeric
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT EXTRACT(YEAR FROM age(end_d, start_d)) * 12 + EXTRACT(MONTH FROM age(end_d, start_d))"
                + " + EXTRACT(DAY FROM age(end_d, start_d))::numeric / 30.4 AS m FROM t",
            "SELECT MONTHS_BETWEEN(end_d, start_d) FROM contracts");
        assertThat(fixed).doesNotContain("EXTRACT(DAY");
        assertThat(fixed).doesNotContain("::numeric");
        assertThat(fixed).contains("EXTRACT(YEAR FROM age(end_d, start_d)) * 12 + EXTRACT(MONTH FROM age(end_d, start_d))");
    }

    @Test
    void removesRedundantMonthsBetweenAlias() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT EXTRACT(YEAR FROM age(end_d, start_d)) * 12 AS months_between FROM t",
            "SELECT MONTHS_BETWEEN(end_d, start_d) FROM contracts");
        assertThat(fixed).doesNotContainIgnoringCase("AS months_between");
    }

    @Test
    void simplifiesRowNumberCombinedWithLimit() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT id, ROW_NUMBER() AS rn, name FROM users ORDER BY id LIMIT 10",
            "SELECT * FROM (SELECT a.*, ROWNUM rn FROM a) WHERE rn <= 10");
        assertThat(fixed).doesNotContain("ROW_NUMBER");
        assertThat(fixed).contains("LIMIT 10");
        assertThat(fixed).contains("name FROM users");
    }

    @Test
    void singularRegexpMatchBecomesPlural() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT regexp_match(email, '@corp.com') FROM users", "SELECT 1");
        assertThat(fixed).contains("REGEXP_MATCHES(email");
        assertThat(fixed).doesNotContain("regexp_match(email");
    }

    @Test
    void sysdateSourceForcesTimestampAndStripsDateCast() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT (created_at)::date AS d, CURRENT_DATE - INTERVAL '1' DAY FROM t",
            "SELECT SYSDATE - 1 FROM dual");
        assertThat(fixed).contains("CURRENT_TIMESTAMP - INTERVAL");
        assertThat(fixed).doesNotContain("CURRENT_DATE - INTERVAL");
        assertThat(fixed).doesNotContain("::date");
    }

    @Test
    void substringFromPatternBecomesRegexpMatchesIndexOne() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT SUBSTRING(email FROM '[^@]+') FROM users",
            "SELECT REGEXP_SUBSTR(email, '[^@]+') FROM users");
        assertThat(fixed).contains("(REGEXP_MATCHES(email, '[^@]+'))[1]");
        assertThat(fixed).doesNotContain("SUBSTRING(email");
    }

    @Test
    void splitPartShortcutIsRestoredToRegexpMatchesFromSource() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT split_part(email, '@', 2) FROM users",
            "SELECT REGEXP_SUBSTR(email, '@.+') FROM users");
        assertThat(fixed).contains("(REGEXP_MATCHES(email, '@.+'))[1]");
        assertThat(fixed).doesNotContain("split_part");
    }

    @Test
    void manualMonthsBetweenFormulaIsRewrittenToAge() {
        String fixed = MigrationEvalController.fixupStubbornPatterns(
            "SELECT (EXTRACT(YEAR FROM end_d) - EXTRACT(YEAR FROM start_d)) * 12"
                + " + (EXTRACT(MONTH FROM end_d) - EXTRACT(MONTH FROM start_d)) AS m FROM t",
            "SELECT MONTHS_BETWEEN(end_d, start_d) FROM contracts");
        assertThat(fixed).contains("EXTRACT(YEAR FROM age(end_d, start_d)) * 12"
            + " + EXTRACT(MONTH FROM age(end_d, start_d))");
        assertThat(fixed).doesNotContain("EXTRACT(YEAR FROM end_d)");
    }
}
