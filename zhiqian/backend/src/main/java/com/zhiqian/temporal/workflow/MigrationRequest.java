package com.zhiqian.temporal.workflow;

import java.util.Map;

/**
 * v2-step-14: Temporal workflow 入参。
 * 轻量 record, JSON-friendly, 避免依赖重型领域类。
 */
public record MigrationRequest(
        long taskId,
        long projectId,
        String sourceDialect,
        String targetDialect,
        Map<String, Object> options
) {}
