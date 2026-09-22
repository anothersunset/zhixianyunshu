package com.zhiqian.task;

import org.springframework.data.jdbc.repository.query.Modifying;
import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

public interface TaskRepository extends CrudRepository<Task, Long> {
    @Query("SELECT * FROM migration_task WHERE project_id = :pid ORDER BY id DESC")
    List<Task> findByProjectId(@Param("pid") Long pid);

    Optional<Task> findByRunId(String runId);

    @Query("SELECT t.* FROM migration_task t JOIN project p ON p.id = t.project_id "
        + "WHERE p.owner_id = :uid ORDER BY t.id DESC")
    List<Task> findByOwnerId(@Param("uid") Long uid);

    /** 启动对账：重启后仍为 RUNNING 的任务已无线程执行，统一标记失败（见 RunningTaskReconciler）。 */
    @Modifying
    @Query("UPDATE migration_task SET status = 'FAILED', "
        + "error_message = 'interrupted_by_restart', finished_at = :now WHERE status = 'RUNNING'")
    int failAllRunningTasks(@Param("now") Instant now);
}
