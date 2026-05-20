package com.zhiqian.suggestion;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("suggestion")
public class Suggestion {
    @Id
    private Long id;
    @Column("task_id")
    private Long taskId;
    private String category;
    private String target;
    @Column("risk_level")
    private String riskLevel;
    private Double confidence;
    @Column("review_status")
    private String reviewStatus;
    @Column("unified_diff")
    private String unifiedDiff;
    private String rationale;
    @Column("created_at")
    private Instant createdAt;
}
