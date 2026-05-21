package com.zhiqian.temporal;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: TemporalProperties POJO 烟测。
 */
class TemporalPropertiesTest {

    @Test
    void roundTripAllFields() {
        TemporalProperties p = new TemporalProperties();
        p.setEnabled(true);
        p.setServiceTarget("temporal:7233");
        p.setNamespace("default");
        p.setTaskQueue("zhiqian-migration");
        p.setWorkflowExecutionTimeoutMinutes(30);
        p.setActivityStartToCloseTimeoutSeconds(600);
        p.setActivityMaxAttempts(3);
        p.setWorkerConcurrentActivityExecutionSize(20);

        assertTrue(p.isEnabled());
        assertEquals("temporal:7233", p.getServiceTarget());
        assertEquals("default", p.getNamespace());
        assertEquals("zhiqian-migration", p.getTaskQueue());
        assertEquals(30, p.getWorkflowExecutionTimeoutMinutes());
        assertEquals(600, p.getActivityStartToCloseTimeoutSeconds());
        assertEquals(3, p.getActivityMaxAttempts());
        assertEquals(20, p.getWorkerConcurrentActivityExecutionSize());
    }

    @Test
    void disabledByDefault() {
        TemporalProperties p = new TemporalProperties();
        // enabled 默认不应为 true (生产默认关)
        assertFalse(p.isEnabled(), "Temporal 默认应关闭, 避免意外起 worker");
    }
}
