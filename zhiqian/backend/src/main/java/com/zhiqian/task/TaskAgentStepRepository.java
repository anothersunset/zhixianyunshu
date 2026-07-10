package com.zhiqian.task;

import org.springframework.data.repository.CrudRepository;

import java.util.List;

public interface TaskAgentStepRepository extends CrudRepository<TaskAgentStep, Long> {
    List<TaskAgentStep> findByTaskIdOrderByIdAsc(Long taskId);
}
