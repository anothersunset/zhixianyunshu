ALTER TABLE project ADD COLUMN IF NOT EXISTS owner_id BIGINT REFERENCES users(id);

ALTER TABLE migration_task ADD COLUMN IF NOT EXISTS source_sql TEXT;
ALTER TABLE migration_task ADD COLUMN IF NOT EXISTS result_sql TEXT;
ALTER TABLE migration_task ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE migration_task ADD COLUMN IF NOT EXISTS run_id VARCHAR(64);

ALTER TABLE report ADD COLUMN IF NOT EXISTS content_md TEXT;
ALTER TABLE agent_step ALTER COLUMN payload TYPE TEXT USING payload::text;

CREATE INDEX IF NOT EXISTS idx_project_owner ON project(owner_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_task_run_id ON migration_task(run_id) WHERE run_id IS NOT NULL;
