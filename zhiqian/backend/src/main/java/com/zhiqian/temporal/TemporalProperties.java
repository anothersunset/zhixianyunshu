package com.zhiqian.temporal;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * v2-step-14: Temporal 配置。
 *
 * <p>设计原则:
 * <ul>
 *   <li>默认 enabled=false, 不装载 Temporal bean, 不影响现有 AgentRunner 路径。</li>
 *   <li>开启后需 docker compose 拉 temporal-server (含 cassandra/postgres + UI)。</li>
 *   <li>本项使用轻量 SDK (io.temporal:temporal-sdk), 不引 spring-boot-starter (avoid auto-config 越级)。</li>
 * </ul>
 */
@Data
@ConfigurationProperties(prefix = "app.temporal")
public class TemporalProperties {

    /** 是否启用 Temporal worker。默认 false, 仅走现有 AgentRunner。 */
    private boolean enabled = false;

    /** Temporal server 地址 host:port。docker compose 下为 temporal:7233。 */
    private String serviceTarget = "127.0.0.1:7233";

    /** Temporal namespace。多租户隔离。 */
    private String namespace = "default";

    /** task queue, worker 与启动 workflow 都需在同名队列。 */
    private String taskQueue = "zhiqian-migration";

    /** workflow 全生命周期超时 (分钟)。超过后 Temporal 会报 timeout。 */
    private int workflowExecutionTimeoutMinutes = 60;

    /** 单个 activity startToClose 超时 (秒)。 */
    private int activityStartToCloseTimeoutSeconds = 600;

    /** activity 重试次数。 */
    private int activityMaxAttempts = 3;

    /** worker 只在本 JVM 为集群中多个节点启动时需要为不同 task queue。 */
    private int workerConcurrentActivityExecutionSize = 8;
}
