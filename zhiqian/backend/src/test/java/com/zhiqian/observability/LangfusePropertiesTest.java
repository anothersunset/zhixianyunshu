package com.zhiqian.observability;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: LangfuseProperties POJO 烟测。
 */
class LangfusePropertiesTest {

    @Test
    void enabledFalseByDefaultOrSettable() {
        LangfuseProperties p = new LangfuseProperties();
        // 默认 enabled 不启, 设值可读回
        p.setEnabled(true);
        p.setHost("https://cloud.langfuse.com");
        p.setPublicKey("pk-test");
        p.setSecretKey("sk-test");
        assertTrue(p.isEnabled());
        assertEquals("https://cloud.langfuse.com", p.getHost());
        assertEquals("pk-test", p.getPublicKey());
        assertEquals("sk-test", p.getSecretKey());
    }
}
