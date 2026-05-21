package com.zhiqian.agent;

import org.springframework.stereotype.Component;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;

/**
 * 顺序执行 AgentGraph。v2-step-03 增强：从 tool 输出中提取 _model / _confidence / _tokenIn / _tokenOut
 * 填到 AgentStep中，让上层 SSE 事件能拿到真实的 LLM 元信息。
 */
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
				output = new HashMap<>();
				output.put("error", e.getMessage());
				status = "FAIL";
			}
			long elapsed = System.currentTimeMillis() - t0;
			String model = output.get("_model") instanceof String s ? s : null;
			Double conf = output.get("_confidence") instanceof Number n ? n.doubleValue() : null;
			Integer tokenIn = output.get("_tokenIn") instanceof Number n ? n.intValue() : null;
			Integer tokenOut = output.get("_tokenOut") instanceof Number n ? n.intValue() : null;
			onStep.accept(new AgentStep(cur, tool.name(), input, output, model, conf, elapsed, tokenIn, tokenOut, status));
			if ("FAIL".equals(status)) break;
			cur = graph.next(cur, ctx);
		}
	}
}
