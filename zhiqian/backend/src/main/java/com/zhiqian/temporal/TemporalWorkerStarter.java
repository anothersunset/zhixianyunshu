package com.zhiqian.temporal;

import com.zhiqian.temporal.workflow.MigrationActivitiesImpl;
import com.zhiqian.temporal.workflow.MigrationWorkflowImpl;
import io.temporal.worker.Worker;
import io.temporal.worker.WorkerFactory;
import io.temporal.worker.WorkerOptions;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.SmartLifecycle;
import org.springframework.stereotype.Component;

/**
 * v2-step-14: Temporal worker 启动器。
 *
 * <p>Spring boot 完成初始化后启动 worker poll Temporal task queue,
 * 代理执行 MigrationWorkflow + MigrationActivities。
 *
 * <p>优雅关闭: stop() 会让 worker 停止接受新任务, 等待进行中任务完成。
 */
@Slf4j
@Component
@RequiredArgsConstructor
@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")
public class TemporalWorkerStarter implements SmartLifecycle {

    private final WorkerFactory workerFactory;
    private final TemporalProperties props;
    private final MigrationActivitiesImpl activitiesBean;

    private volatile boolean running = false;

    @Override
    public void start() {
        if (running) return;
        Worker worker = workerFactory.newWorker(
                props.getTaskQueue(),
                WorkerOptions.newBuilder()
                        .setMaxConcurrentActivityExecutionSize(props.getWorkerConcurrentActivityExecutionSize())
                        .build());
        // workflow 必须是 impl class (worker 在需要时 newInstance)
        worker.registerWorkflowImplementationTypes(MigrationWorkflowImpl.class);
        // activity 是现成实例 (Spring bean), 能注入 AgentRunner
        worker.registerActivitiesImplementations(activitiesBean);
        workerFactory.start();
        running = true;
        log.info("[temporal] worker started, task_queue={}", props.getTaskQueue());
    }

    @Override
    public void stop() {
        if (!running) return;
        log.info("[temporal] worker stopping (graceful)...");
        workerFactory.shutdown();
        running = false;
    }

    @Override
    public boolean isRunning() {
        return running;
    }

    /** 启动顺序: 在 Spring 默认阶段 (0) 后, 让 LLM/Langfuse 先完成。 */
    @Override
    public int getPhase() {
        return 100;
    }
}
