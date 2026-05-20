package com.zhiqian.agent;

import java.util.Map;

public record AgentStep(
	String stage,
	String agentName,
	Map<String, Object> input,
	Map<String, Object> output,
	String model,
	Double confidence,
	Long elapsedMs,
	Integer tokenIn,
	Integer tokenOut,
	String status
) {}
