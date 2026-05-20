package com.zhiqian.task;

import org.springframework.data.jdbc.repository.query.Query;
import org.springframework.data.repository.CrudRepository;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface TaskRepository extends CrudRepository<Task, Long> {
    @Query("SELECT * FROM migration_task WHERE project_id = :pid ORDER BY id DESC")
    List<Task> findByProjectId(@Param("pid") Long pid);
}
