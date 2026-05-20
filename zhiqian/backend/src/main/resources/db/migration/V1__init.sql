-- 用户与角色
CREATE TABLE sys_user (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	username VARCHAR(64) NOT NULL UNIQUE,
	password VARCHAR(128) NOT NULL,
	nickname VARCHAR(64),
	role VARCHAR(32) NOT NULL DEFAULT 'DEVELOPER',
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 项目
CREATE TABLE project (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	name VARCHAR(128) NOT NULL,
	source_type VARCHAR(16) NOT NULL,
	source_path VARCHAR(512),
	owner_id BIGINT NOT NULL,
	target_stack VARCHAR(128),
	status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 迁移任务
CREATE TABLE migration_task (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	project_id BIGINT NOT NULL,
	status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
	progress INT DEFAULT 0,
	current_stage VARCHAR(64),
	started_at DATETIME,
	finished_at DATETIME,
	INDEX idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Agent 步骤记录
CREATE TABLE agent_step (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	task_id BIGINT NOT NULL,
	stage VARCHAR(64) NOT NULL,
	agent_name VARCHAR(64),
	input_json LONGTEXT,
	output_json LONGTEXT,
	model VARCHAR(64),
	confidence DECIMAL(4,3),
	elapsed_ms BIGINT,
	token_in INT,
	token_out INT,
	status VARCHAR(16),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 改造建议CREATE TABLE suggestion (
CREATE TABLE suggestion (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	task_id BIGINT NOT NULL,
	category VARCHAR(32) NOT NULL,
	target VARCHAR(256),
	content LONGTEXT,
	risk_level VARCHAR(16),
	effort_days DECIMAL(5,2),
	confidence DECIMAL(4,3),
	source_json LONGTEXT,
	review_status VARCHAR(16) DEFAULT 'PENDING',
	reviewer_id BIGINT,
	review_reason TEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 报告
CREATE TABLE report (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	task_id BIGINT NOT NULL,
	report_type VARCHAR(32) NOT NULL,
	content LONGTEXT,
	file_path VARCHAR(512),
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 审计日志
CREATE TABLE audit_log (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	user_id BIGINT,
	action VARCHAR(64) NOT NULL,
	target_type VARCHAR(32),
	target_id BIGINT,
	detail_json LONGTEXT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	INDEX idx_user_action (user_id, action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 长期记忆
CREATE TABLE memory_record (
	id BIGINT PRIMARY KEY AUTO_INCREMENT,
	namespace VARCHAR(64) NOT NULL,
	key_text VARCHAR(512),
	value_json LONGTEXT,
	embedding_id VARCHAR(64),
	project_id BIGINT,
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	INDEX idx_ns (namespace)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
