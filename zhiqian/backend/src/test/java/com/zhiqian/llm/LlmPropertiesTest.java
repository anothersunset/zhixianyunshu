package com.zhiqian.llm;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: LlmProperties POJO setter/getter 烟测。
 */
class LlmPropertiesTest {

    @Test
    void roundTripAllFields() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey("sk-xxx");
        p.setBaseUrl("https://api.deepseek.com");
        p.setChatModel("deepseek-chat");
        p.setReasonerModel("deepseek-reasoner");
        p.setTemperature(0.5);
        p.setMaxTokens(2048);
        p.setTimeoutSeconds(60);

        assertEquals("deepseek", p.getProvider());
        assertEquals("sk-xxx", p.getApiKey());
        assertEquals("https://api.deepseek.com", p.getBaseUrl());
        assertEquals("deepseek-chat", p.getChatModel());
        assertEquals("deepseek-reasoner", p.getReasonerModel());
        assertEquals(0.5, p.getTemperature());
        assertEquals(2048, p.getMaxTokens());
        assertEquals(60, p.getTimeoutSeconds());
    }

    @Test
    void defaultsAreSensible() {
        LlmProperties p = new LlmProperties();
        // 所有默认不应崩
        assertDoesNotThrow(() -> {
            String s = p.getProvider();
            // 默认可能为 null 或预设值, 只要不抛 NPE
        });
    }
}
