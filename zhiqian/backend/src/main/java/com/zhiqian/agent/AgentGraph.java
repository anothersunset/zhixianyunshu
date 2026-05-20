package com.zhiqian.agent;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.function.Function;

/** LangGraph 风格状态机：节点 + 条件路由边。 */
public class AgentGraph {
	private final Map<String, AgentTool> nodes = new LinkedHashMap<>();
	private final Map<String, Function<AgentContext, String>> routers = new LinkedHashMap<>();
	private String entry;

	public AgentGraph addNode(String name, AgentTool tool) {
		nodes.put(name, tool);
		return this;
	}

	public AgentGraph addEdge(String from, Function<AgentContext, String> router) {
		routers.put(from, router);
		return this;
	}

	public AgentGraph entry(String name) { this.entry = name; return this; }

	public String entryNode() { return entry; }
	public AgentTool node(String name) { return nodes.get(name); }
	public String next(String current, AgentContext ctx) {
		var r = routers.get(current);
		return r == null ? null : r.apply(ctx);
	}
}
