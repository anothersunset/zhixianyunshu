package com.zhiqian.llm;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * LlmClient 工厂。根据 api-key 是否为空决定走真实 impl 还是 mock。
 */
@Configuration
@EnableConfigurationProperties(LlmProperties.class)
public class LlmClientFactory {

    private static final Logger log = LoggerFactory.getLogger(LlmClientFactory.class);

    @Bean
    public LlmClient llmClient(LlmProperties props) {
        if (props.getApiKey() == null || props.getApiKey().isBlank()) {
            log.warn("[LLM] LLM_API_KEY 未配置，启用 MockLlmClient（占位回显）。在 zhiqian/deploy/.env 中填入 LLM_API_KEY 后重启 backend 即可启用真 LLM。");
            return new MockLlmClient();
        }
        log.info("[LLM] 启用 DeepSeekLlmClient。provider={}, base-url={}, chat-model={}, reasoner-model={}",
                props.getProvider(), props.getBaseUrl(), props.getChatModel(), props.getReasonerModel());
        return new DeepSeekLlmClient(props);
    }
}
