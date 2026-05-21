package com.zhiqian.temporal.workflow;

import io.temporal.workflow.QueryMethod;
import io.temporal.workflow.WorkflowInterface;
import io.temporal.workflow.WorkflowMethod;

/**
 * v2-step-14: 迁移任务 workflow 接口。
 *
 * <p>Workflow code 必须是 deterministic, 不能直接调 Spring bean / IO / clock。
 * 所有副作用都需通过 activity 完成, activity 在 worker 侧调现有 AgentRunner。
 */
@WorkflowInterface
public interface MigrationWorkflow {

    /** 入口: 逐节点调 activity, 收集返回, 组装成 MigrationResult。 */
    @WorkflowMethod
    MigrationResult migrate(MigrationRequest request);

    /**
     * 前端轮询当前阶段。与 SSE 互补:
     * <ul>
     *   <li>SSE 适合活跃连接</li>
     *   <li>QueryMethod 适合“别的页面重新打开”这种断连后拉状态</li>
     * </ul>
     */
    @QueryMethod
    String currentStage();
}
