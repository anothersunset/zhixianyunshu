package com.zhiqian.a2a;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * v2-step-24: A2A Task 状态对象。不打算上 Redis (内存 demo 足够), 生产需换 RedisHash。
 */
public class A2ATask {
    public String id;
    public String sessionId;
    public String state;     // submitted / working / completed / failed
    public Instant createdAt;
    public Instant updatedAt;
    public Map<String, Object> input;
    public List<Map<String, Object>> artifacts = new ArrayList<>();
    public List<Map<String, Object>> history = new ArrayList<>();
    public String errorMessage;

    public Map<String, Object> toJson() {
        return Map.of(
            "id", id,
            "sessionId", sessionId == null ? "" : sessionId,
            "status", Map.of(
                "state", state,
                "timestamp", (updatedAt == null ? createdAt : updatedAt).toString(),
                "error", errorMessage == null ? "" : errorMessage
            ),
            "artifacts", artifacts,
            "history", history
        );
    }
}
