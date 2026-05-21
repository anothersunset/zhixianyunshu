package com.zhiqian.llm;

import com.zhiqian.llm.dto.ChatCompletionResponse;
import com.zhiqian.llm.dto.ChatMessage;
import com.zhiqian.llm.dto.ChatRequestPayload;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.util.List;

/**
 * DeepSeek / OpenAI 兼容 LLM 实现。使用 Spring 6 原生 RestClient，零额外依赖。
 *
 * <p>在 base-url 上拼接 /chat/completions，与 OpenAI、Moonshot、Zhipu、Qwen Dashscope-Compat 同型。</p>
 */
public class DeepSeekLlmClient implements LlmClient {

    private static final Logger log = LoggerFactory.getLogger(DeepSeekLlmClient.class);

    private final LlmProperties props;
    private final RestClient client;

    public DeepSeekLlmClient(LlmProperties props) {
        this.props = props;
        SimpleClientHttpRequestFactory rf = new SimpleClientHttpRequestFactory();
        rf.setConnectTimeout((int) Duration.ofSeconds(10).toMillis());
        rf.setReadTimeout((int) Duration.ofSeconds(props.getTimeoutSeconds()).toMillis());
        this.client = RestClient.builder()
                .baseUrl(props.getBaseUrl())
                .requestFactory(rf)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + props.getApiKey())
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .build();
    }

    @Override
    public String chat(String userPrompt) {
        return chat(List.of(new ChatMessage("user", userPrompt)));
    }

    @Override
    public String chat(List<ChatMessage> messages) {
        return callModel(props.getChatModel(), messages);
    }

    @Override
    public String reason(String userPrompt) {
        return callModel(props.getReasonerModel(), List.of(new ChatMessage("user", userPrompt)));
    }

    private String callModel(String model, List<ChatMessage> messages) {
        ChatRequestPayload payload = new ChatRequestPayload(
                model, messages, props.getTemperature(), props.getMaxTokens(), false);
        try {
            ChatCompletionResponse resp = client.post()
                    .uri("/chat/completions")
                    .body(payload)
                    .retrieve()
                    .body(ChatCompletionResponse.class);
            if (resp == null || resp.choices() == null || resp.choices().isEmpty()) {
                throw new IllegalStateException("LLM 返回为空");
            }
            String content = resp.choices().get(0).message().content();
            log.debug("[LLM] model={}, prompt-tokens={}, completion-tokens={}",
                    model,
                    resp.usage() == null ? -1 : resp.usage().prompt_tokens(),
                    resp.usage() == null ? -1 : resp.usage().completion_tokens());
            return content;
        } catch (RestClientException e) {
            log.error("[LLM] 调用失败 model={}, base-url={}, error={}", model, props.getBaseUrl(), e.getMessage());
            throw new IllegalStateException("LLM 调用失败：" + e.getMessage(), e);
        }
    }

    @Override
    public boolean isReal() { return true; }

    @Override
    public String providerName() { return props.getProvider(); }
}
