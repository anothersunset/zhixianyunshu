package com.zhiqian.temporal.workflow;

import java.util.List;
import java.util.Map;

/**
 * v2-step-14: Temporal workflow 返回。
 * stages 存每个 activity 的摘要 (不存原始 prompt, 避免锁定 Temporal payload 上限)。
 */
public record MigrationResult(
        long taskId,
        String status,                          // success / partial / failed
        List<Map<String, Object>> stages,       // [{stage, ok, elapsedMs, summary}]
        Map<String, Object> finalReport
) {}
