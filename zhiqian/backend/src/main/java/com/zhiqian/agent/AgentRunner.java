package com.zhiqian.agent;

import org.springframework.stereotype.Component;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;

@Component
public class AgentRunner {
	public void run(AgentGraph graph, AgentContext ctx, Consumer<AgentStep> onStep) {
		String cur = graph.entryNode();
		while (cur != null) {
			long t0 = System.currentTimeMillis();
			var tool = graph.node(cur);
			Map<String, Object> input = new HashMap<>(ctx.state());
			Map<String, Object> output;
			String status = "OK";
			try {
				output = tool.run(ctx, input);
				ctx.state().putAll(output);
			} catch (Exception e) {
				output = Map.of("error", e.getMessage());
				status = "FAIL";
			}
			long elapsed = System.currentTimeMillis() - t0;
			onStep.accept(new AgentStep(cur, tool.name(), input, output, null, null, elapsed, null, null, status));
			if ("FAIL".equals(status)) break;
			cur = graph.next(cur, ctx);
		}
	}
}
