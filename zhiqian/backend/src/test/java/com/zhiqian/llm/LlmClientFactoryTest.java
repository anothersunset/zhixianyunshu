package com.zhiqian.llm;

import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.observability.LangfuseProperties;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LlmClientFactoryTest {

    @Test
    void emptyApiKeyReturnsMock() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey("");
        LlmClient client = build(p);
        assertNotNull(client);
        assertTrue(client instanceof MockLlmClient);
    }

    @Test
    void nullApiKeyReturnsMock() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey(null);
        LlmClient client = build(p);
        assertNotNull(client);
        assertTrue(client instanceof MockLlmClient);
    }

    @Test
    void realApiKeyReturnsDeepSeek() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey("sk-fake-key-for-test");
        p.setBaseUrl("https://api.deepseek.com");
        p.setChatModel("deepseek-v4-pro");
        p.setReasonerModel("deepseek-v4-pro");
        p.setTemperature(0.2);
        p.setMaxTokens(1024);
        p.setTimeoutSeconds(30);
        LlmClient client = build(p);
        assertNotNull(client);
        assertTrue(client instanceof DeepSeekLlmClient);
    }

    private LlmClient build(LlmProperties p) {
        return new LlmClientFactory().llmClient(p, new LangfuseClient(new LangfuseProperties()));
    }
}
