package com.zhiqian.migration;

import org.junit.jupiter.api.Test;

import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 验证 sqlserver 方言特征链路在 Java 侧真实可用。
 * 特征来源是 kb/active/dialects/sqlserver.yaml（YAML 驱动、零硬编码回退），
 * TranslationRecipeRegistry 启动时加载，DialectFeatureScanner 派生检测。
 */
class SqlserverDialectFeatureSupportTest {

    @Test
    void registryLoadsTwelveSqlserverFeaturesFromKbYaml() {
        // kb/active/dialects/sqlserver.yaml 当前定义 12 条特征；
        // 若该断言失败说明 YAML 目录解析失败，回退到了无 sqlserver 的硬编码集
        assertThat(TranslationRecipeRegistry.allFor("sqlserver")).hasSize(12);
    }

    @Test
    void scannerDetectsSqlserverConstructsAndSuppliesRecipes() {
        var features = DialectFeatureScanner.scan(
            "SELECT TOP 10 * FROM emp WHERE created > GETDATE()", "sqlserver");

        var byKeyword = features.stream()
            .collect(Collectors.toMap(DialectFeatureScanner.DetectedFeature::sourceFeature, f -> f));
        assertThat(byKeyword).containsKeys("TOP", "GETDATE()");
        // 零参函数已按注册特征命中，不允许再被 Phase 2 重复标记为 UNKNOWN
        assertThat(byKeyword).doesNotContainKey("GETDATE(");
        assertThat(byKeyword.get("TOP").targetMapping()).isEqualTo("LIMIT");
        assertThat(byKeyword.get("TOP").isRecipe()).isTrue();
        assertThat(byKeyword.get("GETDATE()").targetMapping()).isEqualTo("CURRENT_TIMESTAMP");

        var recipes = DialectFeatureScanner.getRecipes(features, "sqlserver");
        assertThat(recipes)
            .extracting(TranslationRecipeRegistry.RegisteredFeature::sourceKeyword)
            .contains("TOP", "GETDATE()");

        String hints = DialectFeatureScanner.toPromptHints(features, recipes);
        assertThat(hints).contains("TOP").contains("SELECT * FROM emp ORDER BY salary DESC LIMIT 10");
    }

    @Test
    void squareBracketIdentifierIsDetectedAsSqlserverFeature() {
        var features = DialectFeatureScanner.scan(
            "SELECT [name] FROM [dbo].[users]", "sqlserver");

        assertThat(features)
            .extracting(DialectFeatureScanner.DetectedFeature::sourceFeature)
            .contains("[");
    }

    @Test
    void sqlserverSimpleMappingsSurviveIntoPromptHints() {
        var features = DialectFeatureScanner.scan(
            "SELECT ISNULL(name, 'n/a'), LEN(name) FROM users", "sqlserver");

        var byKeyword = features.stream()
            .collect(Collectors.toMap(DialectFeatureScanner.DetectedFeature::sourceFeature, f -> f));
        assertThat(byKeyword).containsKeys("ISNULL(", "LEN(");
        assertThat(byKeyword.get("ISNULL(").targetMapping()).isEqualTo("COALESCE");
        assertThat(byKeyword.get("LEN(").targetMapping()).isEqualTo("LENGTH");
    }
}
