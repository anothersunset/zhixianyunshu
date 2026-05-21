package com.zhiqian.llm.dto;

/**
 * OpenAI 兼容 messages 单元。role 取值：system / user / assistant / tool。
 */
public record ChatMessage(String role, String content) {}
