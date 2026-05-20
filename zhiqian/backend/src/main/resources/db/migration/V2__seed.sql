-- 演示种子数据（admin 账户由 DataBootstrap 在启动时插入）

INSERT INTO project (id, name, source_db, target_db, framework, description, status)
VALUES (1, '智迁云枢演示项目', 'MySQL 5.7', 'openGauss 5.0',
        'Spring Boot 2.7 + MyBatis 3.5',
        '以 312 个 Java 源文件、78 条 SQL、19 个配置项为代表的 MySQL 迁 openGauss 完整演示项目。',
        'IN_REVIEW')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('project','id'),
              GREATEST(1,(SELECT COALESCE(MAX(id),0) FROM project)));

INSERT INTO migration_task (id, project_id, name, status, avg_confidence, total_units, review_required, created_at, finished_at) VALUES
(1, 1, 'demo-full-run-2026-05-01',    'DONE',    0.89, 96, 12, NOW() - INTERVAL '3 day', NOW() - INTERVAL '3 day' + INTERVAL '6 minute'),
(2, 1, 'demo-incremental-2026-05-20', 'RUNNING', 0.81, 24, 5,  NOW(), NULL)
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('migration_task','id'),
              GREATEST(1,(SELECT COALESCE(MAX(id),0) FROM migration_task)));

INSERT INTO suggestion (id, task_id, category, target, risk_level, confidence, review_status, unified_diff, rationale) VALUES
(1, 1, 'SQL_REWRITE',  'com.demo.UserMapper.xml#listActive',     'LOW',    0.94, 'APPROVED',
  E'--- a\n+++ b\n@@\n-SELECT IFNULL(name, ''匿名'') FROM users WHERE deleted=0\n+SELECT COALESCE(name, ''匿名'') FROM users WHERE deleted=0',
  'MySQL IFNULL 语义等价于 openGauss COALESCE，可安全替换'),
(2, 1, 'TYPE_MAPPING', 'com.demo.entity.Order.amount',           'MEDIUM', 0.82, 'PENDING',
  E'--- a\n+++ b\n@@\n-private java.math.BigDecimal amount;\n+private java.math.BigDecimal amount; // openGauss: NUMERIC(20,4)',
  'BigDecimal 在 openGauss 推荐显示指定 NUMERIC(p,s)，需在 DDL 同步修改'),
(3, 1, 'DIALECT',      'com.demo.report.ReportMapper.xml#monthly','HIGH',  0.71, 'PENDING',
  E'--- a\n+++ b\n@@\n-DATE_FORMAT(t.created_at, ''%Y-%m'')\n+TO_CHAR(t.created_at, ''YYYY-MM'')',
  'MySQL DATE_FORMAT 在 openGauss 不存在，需转换为 TO_CHAR，人工复核'),
(4, 1, 'CONFIG',       'application-prod.yml#spring.datasource.url','LOW', 0.96, 'APPROVED',
  E'--- a\n+++ b\n@@\n-url: jdbc:mysql://10.0.0.1:3306/demo?useUnicode=true\n+url: jdbc:opengauss://10.0.0.1:5432/demo?targetServerType=master',
  'JDBC URL 切换：mysql→opengauss，端口 3306→5432'),
(5, 2, 'SQL_REWRITE',  'com.demo.OrderMapper.xml#topN',          'MEDIUM', 0.78, 'PENDING',
  E'--- a\n+++ b\n@@\n-LIMIT 10\n+LIMIT 10 -- openGauss 兼容',
  'LIMIT 语法保留，但需补充 ORDER BY 以保证可重现'),
(6, 2, 'DEPENDENCY',   'pom.xml#mysql-connector-java',           'LOW',    0.92, 'APPROVED',
  E'--- a\n+++ b\n@@\n-<artifactId>mysql-connector-java</artifactId>\n+<artifactId>opengauss-jdbc</artifactId>',
  '驱动依赖切换为 openGauss 官方 JDBC')
ON CONFLICT (id) DO NOTHING;

SELECT setval(pg_get_serial_sequence('suggestion','id'),
              GREATEST(1,(SELECT COALESCE(MAX(id),0) FROM suggestion)));

INSERT INTO agent_step (task_id, stage, agent_name, status, elapsed_ms, confidence, payload) VALUES
(1, '01-bootstrap', 'Bootstrap',  'OK', 120,  NULL, '{"msg":"加载工程结构"}'::jsonb),
(1, '02-analyzer',  'Analyzer',   'OK', 850,  NULL, '{"files":312,"sqls":78,"configs":19}'::jsonb),
(1, '03-ckg-build', 'CkgBuilder', 'OK', 410,  NULL, '{"nodes":1842,"edges":5631}'::jsonb),
(1, '04-retriever', 'Retriever',  'OK', 220,  0.78, '{"top_k":50,"top_n":5}'::jsonb),
(1, '05-reasoner',  'Reasoner',   'OK', 1300, 0.81, '{"risk_units":14}'::jsonb),
(1, '06-patcher',   'Patcher',    'OK', 780,  0.89, '{"patches":12,"review_required":2}'::jsonb),
(1, '07-validator', 'Validator',  'OK', 540,  0.92, '{"scripts":18}'::jsonb),
(1, '08-reporter',  'Reporter',   'OK', 180,  NULL, '{"report_url":"/api/reports/demo.html"}'::jsonb),
(2, '01-bootstrap', 'Bootstrap',  'OK', 110,  NULL, '{"msg":"加载增量变更"}'::jsonb),
(2, '02-analyzer',  'Analyzer',   'OK', 420,  NULL, '{"files":48,"sqls":11,"configs":3}'::jsonb),
(2, '04-retriever', 'Retriever',  'OK', 180,  0.74, '{"top_k":30,"top_n":5}'::jsonb),
(2, '05-reasoner',  'Reasoner',  'RUNNING', 0, NULL, '{"msg":"推理进行中"}'::jsonb);

INSERT INTO report (task_id, title, summary, artifact_url) VALUES
(1, '智迁云枢演示项目 全量迁移报告',
    '本任务生成 12 条改造建议、18 个验证脚本，平均置信度 0.89，二类风险项 2 个。',
    '/api/reports/demo.html');
