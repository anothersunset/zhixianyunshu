package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class FeatureScannerAgentTest {
    @Test
    void marksUnknownVendorFunctionsForReviewWithoutPerfectConfidence() {
        AgentContext context = new AgentContext(1L, 1L);
        context.state().put("source_sql", "SELECT MYSTERY_VENDOR_FN(id) FROM users");
        context.state().put("pair", "mysql->postgresql");

        Map<String, Object> result = new FeatureScannerAgent().run(context, Map.of());

        assertThat(result.get("unknown_feature_count")).isEqualTo(1);
        assertThat(result.get("unknown_features")).asList().contains("MYSTERY_VENDOR_FN(");
        assertThat(result.get("review_reason")).isEqualTo("UNKNOWN_FEATURE");
        assertThat(result.get("_confidence")).isEqualTo(0.0);
    }
}
