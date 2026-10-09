-- V2 的演示种子数据给任务 id=2 留下一条 status='RUNNING' 的 agent_step（05-reasoner）。
-- V4 已把任务本身从 RUNNING 改为 PENDING，但这条步骤行漏改：
-- 任务处于 PENDING（未在执行），演示页却显示一个永远"运行中"的步骤。
-- 本迁移只修正新装环境的种子数据；运行期进程重启造成的卡死
-- 由 com.zhiqian.bootstrap.RunningTaskReconciler 在启动时对账（见 V4）。
-- 与 V2 中其余已完成演示步骤保持同一状态词汇（agent_step 完成态为 'OK'）。
UPDATE agent_step SET status = 'OK'
WHERE task_id = 2 AND status = 'RUNNING';
