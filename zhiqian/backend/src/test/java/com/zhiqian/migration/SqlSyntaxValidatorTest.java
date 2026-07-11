package com.zhiqian.migration;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

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
}
