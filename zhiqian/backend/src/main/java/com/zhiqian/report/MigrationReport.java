package com.zhiqian.report;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("report")
public class MigrationReport {
    @Id
    private Long id;
    @Column("task_id")
    private Long taskId;
    private String title;
    private String summary;
    @Column("artifact_url")
    private String artifactUrl;
    @Column("content_md")
    private String contentMd;
    @Column("created_at")
    private Instant createdAt;
}
