package com.zhiqian.temporal.workflow;

import io.temporal.activity.ActivityInterface;
import io.temporal.activity.ActivityMethod;
import java.util.Map;

/**
 * v2-step-14: 迁移 activity 接口。每个方法绑定一个 Agent。
 * 输入 ctx 是累计上下文, 输出需含 _ok / _elapsedMs / _model / _confidence 元数据。
 */
@ActivityInterface
public interface MigrationActivities {
    @ActivityMethod Map<String, Object> runSchemaAnalyzer(Map<String, Object> ctx);
    @ActivityMethod Map<String, Object> runContextRetriever(Map<String, Object> ctx);
    @ActivityMethod Map<String, Object> runSqlReasoner(Map<String, Object> ctx);
    @ActivityMethod Map<String, Object> runSqlPatcher(Map<String, Object> ctx);
    @ActivityMethod Map<String, Object> runSqlCritic(Map<String, Object> ctx);
    @ActivityMethod Map<String, Object> runReportSummarizer(Map<String, Object> ctx);
}
