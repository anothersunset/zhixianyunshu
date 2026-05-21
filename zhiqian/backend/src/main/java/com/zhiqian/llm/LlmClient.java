package com.zhiqian.llm;

import com.zhiqian.llm.dto.ChatMessage;
import java.util.List;

/**
 * 三类能力抽象：
 * <ul>
 *   <li>{@link #chat(String)} / {@link #chat(List)} — 一般对话 / 代码生成，走 chat-model</li>
 *   <li>{@link #reason(String)} — 走推理模型（o1 / R1 类），用于 Critic 、跨表迁移决策等复杂任务</li>
 *   <li>{@link #isReal()} / {@link #providerName()} — 供 /api/llm/health 接口与可观测性使用</li>
 * </ul>
 */
public interface LlmClient {

    /** 单轮对话。 */
    String chat(String userPrompt);

    /** 多轮对话（OpenAI messages 格式）。 */
    String chat(List<ChatMessage> messages);

    /** 调用 reasoner 模型进行复杂推理。 */
    String reason(String userPrompt);

    /** true = 真 LLM；false = mock。 */
    boolean isReal();

    /** 运行时 provider 标识，例如 deepseek / mock / qwen 。 */
    String providerName();
}
