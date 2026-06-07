package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.llm.MockLlmClient;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertFalse;

class ContextRetrieverAgentTest {

    @Test
    void returnsGoldAlignedKbIdsForMysqlOpenGaussFunctions() {
        AgentContext ctx = new AgentContext(1L, 1L);
        ctx.state().put("source_sql", "SELECT IFNULL(name,'x'), DATE_FORMAT(created_at,'%Y-%m') FROM users");
        ctx.state().put("pair", "mysql->opengauss");
        ctx.state().put("retrieval", "full");

        Map<String, Object> out = new ContextRetrieverAgent(new MockLlmClient()).run(ctx, Map.of());
        List<String> ids = ids(out);

        assertTrue(ids.contains("kb-func-ifnull"), ids.toString());
        assertTrue(ids.contains("kb-func-dateformat"), ids.toString());
        assertFalse(ids.contains("kb-func-nvl"), ids.toString());
    }

    @Test
    void returnsGoldAlignedKbIdsForUpsertAndAutoIncrement() {
        AgentContext ctx = new AgentContext(1L, 1L);
        ctx.state().put("source_sql", "CREATE TABLE u(id BIGINT AUTO_INCREMENT); INSERT INTO stat(d,c) VALUES(1,1) ON DUPLICATE KEY UPDATE c=c+VALUES(c)");
        ctx.state().put("pair", "mysql->postgresql");
        ctx.state().put("retrieval", "full");

        Map<String, Object> out = new ContextRetrieverAgent(new MockLlmClient()).run(ctx, Map.of());
        List<String> ids = ids(out);

        assertTrue(ids.contains("kb-type-autoincrement"), ids.toString());
        assertTrue(ids.contains("kb-syntax-upsert"), ids.toString());
    }

    @SuppressWarnings("unchecked")
    private List<String> ids(Map<String, Object> out) {
        return ((List<Map<String, Object>>) out.get("retrieved")).stream()
            .map(row -> String.valueOf(row.get("id")))
            .toList();
    }
}
