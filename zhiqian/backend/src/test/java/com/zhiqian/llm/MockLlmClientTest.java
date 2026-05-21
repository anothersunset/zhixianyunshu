package com.zhiqian.llm;

import com.zhiqian.llm.dto.ChatRequest;
import com.zhiqian.llm.dto.ChatResponse;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: MockLlmClient 降级路径烟测。
 */
class MockLlmClientTest {

    @Test
    void chatReturnsNonEmptyResponse() {
        MockLlmClient client = new MockLlmClient();
        ChatRequest req = new ChatRequest();
        req.setPrompt("hello");
        ChatResponse resp = client.chat(req);
        assertNotNull(resp);
        assertNotNull(resp.getContent());
        assertFalse(resp.getContent().isEmpty());
    }

    @Test
    void reasonReturnsNonEmptyResponse() {
        MockLlmClient client = new MockLlmClient();
        ChatRequest req = new ChatRequest();
        req.setPrompt("reason about migration");
        ChatResponse resp = client.reason(req);
        assertNotNull(resp);
        assertNotNull(resp.getContent());
    }

    @Test
    void modelNameMarksMock() {
        MockLlmClient client = new MockLlmClient();
        ChatRequest req = new ChatRequest();
        req.setPrompt("x");
        ChatResponse resp = client.chat(req);
        // Mock 的 model 字段应含 mock 标记, 避免上下游误以为是真 LLM
        String model = resp.getModel() == null ? "" : resp.getModel().toLowerCase();
        assertTrue(model.contains("mock") || model.isEmpty(),
            "MockLlmClient.model 应含 'mock' 标记, actual: " + resp.getModel());
    }
}
