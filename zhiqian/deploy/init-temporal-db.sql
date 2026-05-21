-- v2-step-14: Temporal auto-setup 需要 temporal / temporal_visibility 两个 database
-- 预先创建。Temporal 启动后会自动建表。
CREATE DATABASE temporal WITH OWNER = zhiqian;
CREATE DATABASE temporal_visibility WITH OWNER = zhiqian;
