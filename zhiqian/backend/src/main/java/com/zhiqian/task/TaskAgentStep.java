package com.zhiqian.task;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("agent_step")
public class TaskAgentStep {
    @Id
    private Long id;
    @Column("task_id")
    private Long taskId;
    private String stage;
    @Column("agent_name")
    private String agentName;
    private String status;
    @Column("elapsed_ms")
    private Integer elapsedMs;
    private Double confidence;
    private String payload;
    @Column("created_at")
    private Instant createdAt;
}
