package com.zhiqian.task;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("migration_task")
public class Task {
    @Id
    private Long id;
    @Column("project_id")
    private Long projectId;
    private String name;
    private String status;
    @Column("avg_confidence")
    private Double avgConfidence;
    @Column("total_units")
    private Integer totalUnits;
    @Column("review_required")
    private Integer reviewRequired;
    @Column("created_at")
    private Instant createdAt;
    @Column("finished_at")
    private Instant finishedAt;
}
