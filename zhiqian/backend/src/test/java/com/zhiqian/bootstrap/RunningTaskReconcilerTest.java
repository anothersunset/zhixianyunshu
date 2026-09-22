package com.zhiqian.bootstrap;

import com.zhiqian.project.Project;
import com.zhiqian.project.ProjectRepository;
import com.zhiqian.task.Task;
import com.zhiqian.task.TaskRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
class RunningTaskReconcilerTest {
    @Autowired RunningTaskReconciler reconciler;
    @Autowired TaskRepository taskRepository;
    @Autowired ProjectRepository projectRepository;

    @Test
    void marksInterruptedRunningTasksAsFailedAndLeavesOthersUntouched() {
        Project project = new Project();
        project.setName("reconciler-test-" + System.nanoTime());
        project.setSourceDb("MySQL 8.0");
        project.setTargetDb("PostgreSQL 16");
        project.setStatus("NEW");
        project.setCreatedAt(Instant.now());
        project = projectRepository.save(project);

        Task running = task("project is stuck after restart", project.getId());
        running.setStatus("RUNNING");
        running = taskRepository.save(running);

        Task pending = task("project fresh pending", project.getId());
        pending.setStatus("PENDING");
        pending = taskRepository.save(pending);

        Task done = task("project finished normally", project.getId());
        done.setStatus("DONE");
        done.setErrorMessage(null);
        done = taskRepository.save(done);

        reconciler.run(null);

        Task failed = taskRepository.findById(running.getId()).orElseThrow();
        assertThat(failed.getStatus()).isEqualTo("FAILED");
        assertThat(failed.getErrorMessage()).isEqualTo("interrupted_by_restart");
        assertThat(failed.getFinishedAt()).isNotNull();

        assertThat(taskRepository.findById(pending.getId()).orElseThrow().getStatus()).isEqualTo("PENDING");
        assertThat(taskRepository.findById(done.getId()).orElseThrow().getStatus()).isEqualTo("DONE");
    }

    private Task task(String name, Long projectId) {
        Task task = new Task();
        task.setProjectId(projectId);
        task.setName(name);
        task.setSourceSql("SELECT IFNULL(name, 'anonymous') FROM users");
        task.setStatus("PENDING");
        task.setReviewRequired(0);
        task.setCreatedAt(Instant.now());
        return task;
    }
}
