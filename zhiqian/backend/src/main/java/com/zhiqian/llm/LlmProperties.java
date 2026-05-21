package com.zhiqian.llm;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * LLM 接入配置。默认面向 DeepSeek-V3.1，但所有字段都是 OpenAI 兼容协议的通用参数，
 * 切换到 Qwen / GLM / 本地 vLLM 只需改 .env 中的 LLM_BASE_URL / LLM_API_KEY / LLM_CHAT_MODEL。
 *
 * <p>设计原则：api-key 为空时走 MockLlmClient，docker compose 零配置也能启动。
 */
@ConfigurationProperties(prefix = "app.llm")
public class LlmProperties {

    /** 提供商名称，仅用于展示与日志。取值例：deepseek / qwen / glm / vllm-local。 */
    private String provider = "deepseek";

    /** OpenAI 兼容 API Key。留空则启用 MockLlmClient。 */
    private String apiKey = "";

    /** OpenAI 兼容 base URL。DeepSeek 默认 https://api.deepseek.com/v1。 */
    private String baseUrl = "https://api.deepseek.com/v1";

    /** 对话模型。DeepSeek-V3.1 、Qwen3-32B 、glm-4.5 等。 */
    private String chatModel = "deepseek-chat";

    /** 推理模型（o1 / R1 类型）。用于 Critic / 复杂 SQL 改写决策。 */
    private String reasonerModel = "deepseek-reasoner";

    /** 采样温度。SQL 生成场景建议 0.0-0.3。 */
    private double temperature = 0.2;

    /** 单次应答最大 token 数。 */
    private int maxTokens = 2048;

    /** HTTP 全链路超时（秒）。 */
    private int timeoutSeconds = 60;

    public String getProvider() { return provider; }
    public void setProvider(String provider) { this.provider = provider; }
    public String getApiKey() { return apiKey; }
    public void setApiKey(String apiKey) { this.apiKey = apiKey; }
    public String getBaseUrl() { return baseUrl; }
    public void setBaseUrl(String baseUrl) { this.baseUrl = baseUrl; }
    public String getChatModel() { return chatModel; }
    public void setChatModel(String chatModel) { this.chatModel = chatModel; }
    public String getReasonerModel() { return reasonerModel; }
    public void setReasonerModel(String reasonerModel) { this.reasonerModel = reasonerModel; }
    public double getTemperature() { return temperature; }
    public void setTemperature(double temperature) { this.temperature = temperature; }
    public int getMaxTokens() { return maxTokens; }
    public void setMaxTokens(int maxTokens) { this.maxTokens = maxTokens; }
    public int getTimeoutSeconds() { return timeoutSeconds; }
    public void setTimeoutSeconds(int timeoutSeconds) { this.timeoutSeconds = timeoutSeconds; }
}
