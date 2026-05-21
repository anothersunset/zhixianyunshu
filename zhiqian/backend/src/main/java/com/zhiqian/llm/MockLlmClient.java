package com.zhiqian.llm;

import com.zhiqian.llm.dto.ChatMessage;
import java.util.List;

/**
 * API Key 未配置时的占位实现。保证 docker compose 零配置也能启动、所有 LLM 入口都不会抛异常。
 * 返回的文本会明示告知用户 “未配置，请填入 .env ”。
 */
public class MockLlmClient implements LlmClient {

    private static final String NOTICE = "\n\n以上为 Mock LLM 返回的占位文本。请在 zhiqian/deploy/.env 中填入 LLM_API_KEY 后重启 backend 容器启用真 LLM。";

    @Override
    public String chat(String userPrompt) {
        return "[Mock-Chat] 收到 prompt：" + truncate(userPrompt) + NOTICE;
    }

    @Override
    public String chat(List<ChatMessage> messages) {
        String last = messages.isEmpty() ? "" : messages.get(messages.size() - 1).content();
        return chat(last);
    }

    @Override
    public String reason(String userPrompt) {
        return "[Mock-Reasoner] 推理 prompt：" + truncate(userPrompt) + "\n\n推理过程（虚拟）：步骤 1、2、3..." + NOTICE;
    }

    @Override
    public boolean isReal() { return false; }

    @Override
    public String providerName() { return "mock"; }

    private String truncate(String s) {
        if (s == null) return "";
        return s.length() > 200 ? s.substring(0, 200) + "…" : s;
    }
}
