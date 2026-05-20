-- ZhiQian YunShu 初始化表结构 (PostgreSQL)
-- 运行于 Flyway；openGauss 也兼容 PostgreSQL 语法

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    display_name VARCHAR(128),
    role VARCHAR(32) NOT NULL DEFAULT 'USER',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    source_db VARCHAR(64) NOT NULL,
    target_db VARCHAR(64) NOT NULL,
    framework VARCHAR(128),
    description TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS migration_task (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    avg_confidence DOUBLE PRECISION,
    total_units INTEGER,
    review_required INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agent_step (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES migration_task(id) ON DELETE CASCADE,
    stage VARCHAR(64) NOT NULL,
    agent_name VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    elapsed_ms INTEGER,
    confidence DOUBLE PRECISION,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suggestion (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES migration_task(id) ON DELETE CASCADE,
    category VARCHAR(32) NOT NULL,
    target VARCHAR(256) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    confidence DOUBLE PRECISION,
    review_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    unified_diff TEXT,
    rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS script_validation (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES migration_task(id) ON DELETE CASCADE,
    script_type VARCHAR(32) NOT NULL,
    file_path VARCHAR(256) NOT NULL,
    content TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS report (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES migration_task(id) ON DELETE CASCADE,
    title VARCHAR(256) NOT NULL,
    summary TEXT,
    artifact_url VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    action VARCHAR(64) NOT NULL,
    target VARCHAR(256),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_project ON migration_task(project_id);
CREATE INDEX IF NOT EXISTS idx_suggestion_task ON suggestion(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_step_task ON agent_step(task_id);
CREATE INDEX IF NOT EXISTS idx_report_task ON report(task_id);
