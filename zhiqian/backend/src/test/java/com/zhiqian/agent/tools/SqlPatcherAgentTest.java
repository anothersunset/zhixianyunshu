package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.llm.MockLlmClient;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class SqlPatcherAgentTest {
    @Test
    void mockModeTransformsTheActualSourceSqlDeterministically() {
        AgentContext context = new AgentContext(1L, 1L);
        context.state().put("source_sql", "SELECT IFNULL(`name`, 'n/a') FROM users LIMIT 10, 20;");
        context.state().put("pair", "mysql->postgresql");

        Map<String, Object> output = new SqlPatcherAgent(new MockLlmClient()).run(context, Map.of());

        assertThat(output.get("patch_preview").toString())
            .contains("COALESCE(\"name\", 'n/a')")
            .contains("LIMIT 20 OFFSET 10")
            .doesNotContain("CREATE TABLE orders");
        assertThat(output.get("review_required")).isEqualTo(0);
    }
}
