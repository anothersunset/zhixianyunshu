package com.zhiqian.agent.tools;

import com.zhiqian.agent.AgentContext;
import com.zhiqian.llm.LlmClient;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class SqlReasonerAgentRoutingTest {
    @Test
    void routesSimpleSqlToChatModel() {
        LlmClient llm = mock(LlmClient.class);
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("test");
        when(llm.chat(anyString())).thenReturn("simple reasoning");
        AgentContext context = context("SELECT IFNULL(name, 'x') FROM users", "mysql->postgresql");

        Map<String, Object> result = new SqlReasonerAgent(llm).run(context, Map.of());

        assertThat(result.get("complex_sql")).isEqualTo(false);
        verify(llm).chat(anyString());
        verify(llm, never()).reason(anyString());
    }

    @Test
    void routesComplexSqlToReasonerModel() {
        LlmClient llm = mock(LlmClient.class);
        when(llm.isReal()).thenReturn(true);
        when(llm.providerName()).thenReturn("test");
        when(llm.reason(anyString())).thenReturn("complex reasoning");
        AgentContext context = context(
            "WITH x AS (SELECT DECODE(a, 1, 'x') FROM dual) "
                + "SELECT * FROM x START WITH a = 1 CONNECT BY PRIOR id = parent_id",
            "oracle->postgresql"
        );

        Map<String, Object> result = new SqlReasonerAgent(llm).run(context, Map.of());

        assertThat(result.get("complex_sql")).isEqualTo(true);
        verify(llm).reason(anyString());
        verify(llm, never()).chat(anyString());
    }

    private AgentContext context(String sql, String pair) {
        AgentContext context = new AgentContext(1L, 1L);
        context.state().put("source_sql", sql);
        context.state().put("pair", pair);
        return context;
    }
}
