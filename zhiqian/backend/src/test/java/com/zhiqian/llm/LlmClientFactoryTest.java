package com.zhiqian.llm;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * v2-step-17: LlmClientFactory 按 api-key 选 real/mock 的分支逻辑。
 * 补充说明: 生产环境无 DEEPSEEK_API_KEY 时, /api/llm/chat 需能走 mock 不报错。
 */
class LlmClientFactoryTest {

    @Test
    void emptyApiKeyReturnsMock() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey("");
        LlmClientFactory factory = new LlmClientFactory(p);
        LlmClient client = factory.build();
        assertNotNull(client);
        assertTrue(client instanceof MockLlmClient,
            "empty api-key 应走 MockLlmClient, actual: " + client.getClass().getSimpleName());
    }

    @Test
    void nullApiKeyReturnsMock() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey(null);
        LlmClientFactory factory = new LlmClientFactory(p);
        LlmClient client = factory.build();
        assertNotNull(client);
        assertTrue(client instanceof MockLlmClient);
    }

    @Test
    void realApiKeyReturnsDeepSeek() {
        LlmProperties p = new LlmProperties();
        p.setProvider("deepseek");
        p.setApiKey("sk-fake-key-for-test");
        p.setBaseUrl("https://api.deepseek.com");
        p.setChatModel("deepseek-chat");
        p.setReasonerModel("deepseek-reasoner");
        p.setTemperature(0.2);
        p.setMaxTokens(1024);
        p.setTimeoutSeconds(30);
        LlmClientFactory factory = new LlmClientFactory(p);
        LlmClient client = factory.build();
        assertNotNull(client);
        assertTrue(client instanceof DeepSeekLlmClient,
            "实 key 应走 DeepSeekLlmClient, actual: " + client.getClass().getSimpleName());
    }
}
