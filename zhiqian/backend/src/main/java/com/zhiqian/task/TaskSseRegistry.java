package com.zhiqian.task;

import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class TaskSseRegistry {
	private static final Map<Long, SseEmitter> EMITTERS = new ConcurrentHashMap<>();

	public static SseEmitter register(Long taskId) {
		SseEmitter e = new SseEmitter(0L);
		e.onCompletion(() -> EMITTERS.remove(taskId));
		e.onTimeout(() -> EMITTERS.remove(taskId));
		EMITTERS.put(taskId, e);
		return e;
	}

	public static void send(Long taskId, String event, Object data) {
		var e = EMITTERS.get(taskId);
		if (e == null) return;
		try { e.send(SseEmitter.event().name(event).data(data)); }
		catch (Exception ex) { EMITTERS.remove(taskId); }
	}
}
