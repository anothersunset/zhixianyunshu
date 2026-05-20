package com.zhiqian.project;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("project")
public class Project {
    @Id
    private Long id;
    private String name;
    @Column("source_db")
    private String sourceDb;
    @Column("target_db")
    private String targetDb;
    private String framework;
    private String description;
    private String status;
    @Column("created_at")
    private Instant createdAt;
}
