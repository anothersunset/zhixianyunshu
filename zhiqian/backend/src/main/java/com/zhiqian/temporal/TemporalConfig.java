package com.zhiqian.temporal;

import io.temporal.client.WorkflowClient;
import io.temporal.client.WorkflowClientOptions;
import io.temporal.serviceclient.WorkflowServiceStubs;
import io.temporal.serviceclient.WorkflowServiceStubsOptions;
import io.temporal.worker.WorkerFactory;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * v2-step-14: Temporal bean 装配。仅在 app.temporal.enabled=true 时生效。
 * 不启用时原 AgentRunner 路径完全不受影响。
 */
@Slf4j
@Configuration
@RequiredArgsConstructor
@EnableConfigurationProperties(TemporalProperties.class)
@ConditionalOnProperty(name = "app.temporal.enabled", havingValue = "true")
public class TemporalConfig {

    private final TemporalProperties props;

    /** Temporal gRPC stub, JVM 生命周期单例。destroyMethod=shutdown 优雅关闭 gRPC channel。 */
    @Bean(destroyMethod = "shutdown")
    public WorkflowServiceStubs workflowServiceStubs() {
        log.info("[temporal] connecting to {} namespace={}", props.getServiceTarget(), props.getNamespace());
        return WorkflowServiceStubs.newServiceStubs(
                WorkflowServiceStubsOptions.newBuilder()
                        .setTarget(props.getServiceTarget())
                        .build());
    }

    /** 启动 workflow + 查询 workflow 状态都走这个 client。 */
    @Bean
    public WorkflowClient workflowClient(WorkflowServiceStubs stubs) {
        return WorkflowClient.newInstance(
                stubs,
                WorkflowClientOptions.newBuilder().setNamespace(props.getNamespace()).build());
    }

    /** worker 进程本地的工厂。TemporalWorkerStarter 里创建 Worker 实例。 */
    @Bean(destroyMethod = "shutdown")
    public WorkerFactory workerFactory(WorkflowClient client) {
        return WorkerFactory.newInstance(client);
    }
}
