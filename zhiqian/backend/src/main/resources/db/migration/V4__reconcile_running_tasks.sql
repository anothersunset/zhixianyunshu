-- V2 种子数据把演示任务 id=2 插入为 status='RUNNING'，该状态的任务永远无法被执行
-- （TaskExecutionService.start 对 RUNNING 任务返回 409）。
-- 本迁移只修正新装环境的种子数据；已安装环境中因进程重启卡死的任务
-- 由 com.zhiqian.bootstrap.RunningTaskReconciler 在启动时对账修复。
UPDATE migration_task SET status = 'PENDING'
WHERE id = 2 AND status = 'RUNNING';
