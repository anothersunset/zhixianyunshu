package com.zhiqian.llm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.List;
import java.util.Map;

/**
 * OpenAI 兼容 /chat/completions 请求体。
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ChatRequestPayload(
        String model,
        List<ChatMessage> messages,
        Double temperature,
        @JsonProperty("max_tokens") int maxTokens,
        boolean stream,
        Map<String, String> thinking,
        @JsonProperty("reasoning_effort") String reasoningEffort
) {}
