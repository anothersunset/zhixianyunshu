package com.zhiqian.bootstrap;

import com.zhiqian.task.TaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * 启动对账：进程重启后，status='RUNNING' 的任务不可能再有线程在执行，
 * 但 TaskExecutionService.start() 会对 RUNNING 任务返回 409，导致其永久卡死。
 * 这里在启动时统一把它们标记为 FAILED，交由用户重新执行。
 */
@Slf4j
@Component
@Order(5)
@RequiredArgsConstructor
public class RunningTaskReconciler implements ApplicationRunner {

    static final String INTERRUPTED_MESSAGE = "interrupted_by_restart";

    private final TaskRepository taskRepository;

    @Override
    public void run(ApplicationArguments args) {
        int fixed = taskRepository.failAllRunningTasks(Instant.now());
        if (fixed > 0) {
            log.warn("✓ 启动对账：{} 个因重启中断的 RUNNING 任务已标记为 FAILED", fixed);
        }
    }
}
