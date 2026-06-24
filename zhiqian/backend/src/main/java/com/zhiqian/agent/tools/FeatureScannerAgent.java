package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.agent.AgentTool;
import com.zhiqian.migration.DialectFeatureScanner;
import com.zhiqian.migration.TranslationRecipeRegistry;
import com.zhiqian.migration.TranslationRecipeRegistry.RegisteredFeature;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Stage 01 (v4) — 规则驱动的方言特征扫描器。
 * 零 LLM 调用，纯关键词/正则在毫秒级完成。
 * 输出 features 列表和 prompt-ready 的 feature_hints 字符串。
 */
public class FeatureScannerAgent implements AgentTool {

    @Override public String name() { return "Feature Scanner"; }
    @Override public String description() { return "规则扫描 SQL 方言特征（零 LLM）"; }

    @Override public Map<String, Object> run(AgentContext ctx, Map<String, Object> input) {
        String sql = String.valueOf(ctx.state().getOrDefault("source_sql", ""));
        String pair = String.valueOf(ctx.state().getOrDefault("pair", ""));
        String sourceDialect = pair.split("->")[0].trim();

        List<DialectFeatureScanner.DetectedFeature> features =
            DialectFeatureScanner.scan(sql, sourceDialect);
        List<RegisteredFeature> recipes =
            DialectFeatureScanner.getRecipes(features, sourceDialect);
        String hints = DialectFeatureScanner.toPromptHints(features, recipes);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("features", features);
        out.put("feature_recipes", recipes);
        out.put("feature_hints", hints);
        out.put("feature_count", features.size());
        out.put("_model", "rule-based");
        out.put("_confidence", 1.0);
        out.put("_real", false);
        return out;
    }
}
