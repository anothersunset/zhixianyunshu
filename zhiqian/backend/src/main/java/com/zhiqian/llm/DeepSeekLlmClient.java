package com.zhiqian.llm;

import com.zhiqian.llm.dto.ChatCompletionResponse;
import com.zhiqian.llm.dto.ChatMessage;
import com.zhiqian.llm.dto.ChatRequestPayload;
import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.observability.TraceHandle;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * DeepSeek / OpenAI 兼容 LLM 实现。使用 Spring 6 原生 RestClient,零额外依赖。
 *
 * <p>在 base-url 上拼接 /chat/completions,与 OpenAI、Moonshot、Zhipu、Qwen Dashscope-Compat 同型。</p>
 *
 * <p>v2-step-08: 在 callModel 内记录调用起止时间,调 {@link LangfuseClient#current()} 拿到当前 trace,
 * 把本次调用作为 generation 挑 attach,拿到 prompt-tokens & completion-tokens 一并上报。失败也上报一笔以便
 * 在 Langfuse UI 中定位错误。</p>
 */
public class DeepSeekLlmClient implements LlmClient {

    private static final Logger log = LoggerFactory.getLogger(DeepSeekLlmClient.class);

    private final LlmProperties props;
    private final RestClient client;
    private final LangfuseClient langfuse;

    public DeepSeekLlmClient(LlmProperties props, LangfuseClient langfuse) {
        this.props = props;
        this.langfuse = langfuse;
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
        return callModel(props.getChatModel(), messages, "llm.chat");
    }

    @Override
    public String reason(String userPrompt) {
        return callModel(props.getReasonerModel(), List.of(new ChatMessage("user", userPrompt)), "llm.reason");
    }

    private String callModel(String model, List<ChatMessage> messages, String genName) {
        ChatRequestPayload payload = new ChatRequestPayload(
                model, messages, props.getTemperature(), props.getMaxTokens(), false);
        Instant start = Instant.now();
        try {
            ChatCompletionResponse resp = client.post()
                    .uri("/chat/completions")
                    .body(payload)
                    .retrieve()
                    .body(ChatCompletionResponse.class);
            Instant end = Instant.now();
            if (resp == null || resp.choices() == null || resp.choices().isEmpty()) {
                throw new IllegalStateException("LLM 返回为空");
            }
            String content = resp.choices().get(0).message().content();
            Integer pt = (resp.usage() == null) ? null : resp.usage().prompt_tokens();
            Integer ct = (resp.usage() == null) ? null : resp.usage().completion_tokens();
            log.debug("[LLM] model={}, prompt-tokens={}, completion-tokens={}", model, pt, ct);
            attachToCurrentTrace(genName, model, start, end, messages, content, pt, ct);
            return content;
        } catch (RestClientException e) {
            log.error("[LLM] 调用失败 model={}, base-url={}, error={}", model, props.getBaseUrl(), e.getMessage());
            attachToCurrentTrace(genName + ".error", model, start, Instant.now(), messages,
                    "[ERROR] " + e.getMessage(), null, null);
            throw new IllegalStateException("LLM 调用失败:" + e.getMessage(), e);
        }
    }

    private void attachToCurrentTrace(String name, String model, Instant start, Instant end,
                                       List<ChatMessage> messages, String completion,
                                       Integer pt, Integer ct) {
        TraceHandle tr = LangfuseClient.current();
        if (tr == null || tr.isNoop()) return;
        List<Map<String, String>> msgs = messages.stream()
                .map(m -> Map.of("role", m.role(), "content", m.content()))
                .toList();
        tr.generation(name, model, start, end, msgs, completion, pt, ct);
    }

    @Override
    public boolean isReal() { return true; }

    @Override
    public String providerName() { return props.getProvider(); }
}
