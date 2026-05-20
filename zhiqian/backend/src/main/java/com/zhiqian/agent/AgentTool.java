package com.zhiqian.agent;

import java.util.Map;

public interface AgentTool {
	String name();
	String description();
	Map<String, Object> run(AgentContext ctx, Map<String, Object> input);
}
