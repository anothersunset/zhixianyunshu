package com.zhiqian.agent;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class AgentContext {
	private final Long taskId;
	private final Long projectId;
	private final Map<String, Object> state = new ConcurrentHashMap<>();
	private final Map<String, Object> memory = new HashMap<>();

	public AgentContext(Long taskId, Long projectId) {
		this.taskId = taskId;
		this.projectId = projectId;
	}

	public Long taskId() { return taskId; }
	public Long projectId() { return projectId; }
	public Map<String, Object> state() { return state; }
	public Map<String, Object> memory() { return memory; }
}
