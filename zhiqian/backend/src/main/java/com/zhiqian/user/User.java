package com.zhiqian.user;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

import java.time.Instant;

@Data
@Table("users")
public class User {
    @Id
    private Long id;
    private String username;
    @Column("password_hash")
    private String passwordHash;
    @Column("display_name")
    private String displayName;
    private String role;
    @Column("created_at")
    private Instant createdAt;
}
