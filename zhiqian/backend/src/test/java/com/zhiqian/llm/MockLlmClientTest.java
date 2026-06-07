package com.zhiqian.llm;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MockLlmClientTest {

    @Test
    void chatReturnsNonEmptyResponse() {
        MockLlmClient client = new MockLlmClient();
        String resp = client.chat("hello");
        assertFalse(resp.isBlank());
        assertTrue(resp.contains("Mock-Chat"));
    }

    @Test
    void reasonReturnsNonEmptyResponse() {
        MockLlmClient client = new MockLlmClient();
        String resp = client.reason("reason about migration");
        assertFalse(resp.isBlank());
        assertTrue(resp.contains("Mock-Reasoner"));
    }

    @Test
    void providerNameMarksMock() {
        MockLlmClient client = new MockLlmClient();
        assertTrue(client.providerName().contains("mock"));
        assertFalse(client.isReal());
    }
}
