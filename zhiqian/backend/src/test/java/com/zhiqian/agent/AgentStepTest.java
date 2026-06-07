package com.zhiqian.agent;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class AgentStepTest {

    @Test
    void recordRoundTripPreservesAllFields() {
        AgentStep s = new AgentStep(
            "SCHEMA",
            "schemaAnalyzerAgent",
            Map.of("sql", "input text"),
            Map.of("summary", "output text"),
            "deepseek-v4-pro",
            0.85,
            120L,
            500,
            300,
            "ok"
        );
        assertEquals("SCHEMA", s.stage());
        assertEquals("schemaAnalyzerAgent", s.agentName());
        assertEquals(Map.of("sql", "input text"), s.input());
        assertEquals(Map.of("summary", "output text"), s.output());
        assertEquals("deepseek-v4-pro", s.model());
        assertEquals(0.85, s.confidence());
        assertEquals(120L, s.elapsedMs());
        assertEquals(500, s.tokenIn());
        assertEquals(300, s.tokenOut());
        assertEquals("ok", s.status());
    }

    @Test
    void recordsAreEqualByValue() {
        AgentStep a = new AgentStep("X", "x", Map.of("i", "i"), Map.of("o", "o"), "m", 0.5, 1L, 1, 1, "ok");
        AgentStep b = new AgentStep("X", "x", Map.of("i", "i"), Map.of("o", "o"), "m", 0.5, 1L, 1, 1, "ok");
        assertEquals(a, b);
        assertEquals(a.hashCode(), b.hashCode());
    }
}
