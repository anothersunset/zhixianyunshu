package com.zhiqian.task;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * <h2>已废弃—仅作交付谐接。</h2>
 * <p>v2-step-03 后 SSE 主流路已切换到 {@link TaskExecutionService}。本类保留仅为了允许身源回滚时
 * 现有依赖不报错。任何新代码不应再注入本类。</p>
 * <p>未来提交将完全删除本类。</p>
 */
@Deprecated(forRemoval = true, since = "v2-step-03")
@Component
@RequiredArgsConstructor
public class TaskSseDemoEmitter {

    private final TaskExecutionService delegate;

    /** @deprecated 请直接调用 {@link TaskExecutionService#subscribe(Long)}。 */
    @Deprecated(forRemoval = true, since = "v2-step-03")
    public SseEmitter subscribe(Long taskId) {
        return delegate.subscribe(taskId);
    }
}
