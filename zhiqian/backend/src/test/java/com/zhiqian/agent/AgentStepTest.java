package com.zhiqian.agent;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: AgentStep record 语义烟测。
 */
class AgentStepTest {

    @Test
    void recordRoundTripPreservesAllFields() {
        AgentStep s = new AgentStep(
            "SCHEMA",
            "schemaAnalyzerAgent",
            "input text",
            "output text",
            "deepseek-chat",
            0.85,
            120L,
            500,
            300,
            "ok"
        );
        assertEquals("SCHEMA", s.stage());
        assertEquals("schemaAnalyzerAgent", s.agentName());
        assertEquals("input text", s.input());
        assertEquals("output text", s.output());
        assertEquals("deepseek-chat", s.model());
        assertEquals(0.85, s.confidence());
        assertEquals(120L, s.elapsedMs());
        assertEquals(500, s.tokenIn());
        assertEquals(300, s.tokenOut());
        assertEquals("ok", s.status());
    }

    @Test
    void recordsAreEqualByValue() {
        AgentStep a = new AgentStep("X", "x", "i", "o", "m", 0.5, 1L, 1, 1, "ok");
        AgentStep b = new AgentStep("X", "x", "i", "o", "m", 0.5, 1L, 1, 1, "ok");
        assertEquals(a, b);
        assertEquals(a.hashCode(), b.hashCode());
    }
}
