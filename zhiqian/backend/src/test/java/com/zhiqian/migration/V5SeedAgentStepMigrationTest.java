package com.zhiqian.migration;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * V5__reconcile_seed_agent_step.sql 冒烟测试（参考 RunningTaskReconcilerTest 的 H2 基建）。
 *
 * <p>V2 种子给演示任务 id=2 留下一条 status='RUNNING' 的 agent_step；V4 已把任务改为
 * PENDING 但漏改该步骤行。V5 必须只把种子演示步骤（task_id=2）的 RUNNING 改为 OK，
 * 不触碰其他任务的步骤。</p>
 */
@SpringBootTest
@ActiveProfiles("test")
@Transactional
class V5SeedAgentStepMigrationTest {

    @Autowired JdbcTemplate jdbc;

    @Test
    void v5ReconcilesOnlySeedDemoStepAndLeavesOtherTasksUntouched() throws Exception {
        // 共享 H2 中 id=2 可能已被其他测试占用，先在事务内清理（结束后回滚恢复）
        jdbc.update("DELETE FROM agent_step WHERE task_id = 2");
        jdbc.update("DELETE FROM migration_task WHERE id = 2");

        jdbc.update("INSERT INTO project (id, name, source_db, target_db, status) VALUES (990001, 'v5-smoke', 'MySQL 8.0', 'PostgreSQL 16', 'NEW')");
        // 种子演示任务 id=2：V4 之后应为 PENDING
        jdbc.update("INSERT INTO migration_task (id, project_id, name, status) VALUES (2, 990001, 'demo-incremental', 'PENDING')");
        // V2:57 的顽固行 + 一条正常完成行
        jdbc.update("INSERT INTO agent_step (task_id, stage, agent_name, status) VALUES (2, '05-reasoner', 'Reasoner', 'RUNNING')");
        jdbc.update("INSERT INTO agent_step (task_id, stage, agent_name, status) VALUES (2, '02-analyzer', 'Analyzer', 'OK')");
        // 非种子任务的 RUNNING 步骤不应被 V5 修改
        jdbc.update("INSERT INTO migration_task (id, project_id, name, status) VALUES (990002, 990001, 'live-task', 'RUNNING')");
        jdbc.update("INSERT INTO agent_step (task_id, stage, agent_name, status) VALUES (990002, '05-reasoner', 'Reasoner', 'RUNNING')");

        String sql = new String(
            new ClassPathResource("db/migration/V5__reconcile_seed_agent_step.sql").getInputStream().readAllBytes(),
            StandardCharsets.UTF_8);
        for (String stmt : sql.split(";")) {
            if (!stmt.isBlank()) jdbc.execute(stmt);
        }

        assertThat(stepStatus(2, "05-reasoner")).isEqualTo("OK");           // 种子 RUNNING → OK
        assertThat(stepStatus(2, "02-analyzer")).isEqualTo("OK");           // 已完成行保持不变
        assertThat(stepStatus(990002, "05-reasoner")).isEqualTo("RUNNING"); // 其他任务不受影响
    }

    private String stepStatus(long taskId, String stage) {
        return jdbc.queryForObject(
            "SELECT status FROM agent_step WHERE task_id = ? AND stage = ?",
            String.class, taskId, stage);
    }
}
