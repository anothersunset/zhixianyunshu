package com.zhiqian.llm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * OpenAI 兼容 /chat/completions 请求体。
 */
public record ChatRequestPayload(
        String model,
        List<ChatMessage> messages,
        double temperature,
        @JsonProperty("max_tokens") int maxTokens,
        boolean stream
) {}
