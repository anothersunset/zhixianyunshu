-- Postgres 初始化：Flyway 连接之前先创建 schema
CREATE SCHEMA IF NOT EXISTS zhiqian;
GRANT ALL ON SCHEMA zhiqian TO zhiqian;
