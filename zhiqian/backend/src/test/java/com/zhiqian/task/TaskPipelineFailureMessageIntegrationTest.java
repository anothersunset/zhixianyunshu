package com.zhiqian.task;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.agent.AgentRunner;
import com.zhiqian.agent.AgentStep;
import com.zhiqian.llm.LlmClient;
import com.zhiqian.observability.LangfuseClient;
import com.zhiqian.project.Project;
import com.zhiqian.project.ProjectRepository;
import com.zhiqian.security.JwtService;
import com.zhiqian.task.MigrationPipelineService.MigrationInput;
import com.zhiqian.task.MigrationPipelineService.PipelineResult;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 流水线失败时 error_message 必须是可读文本（含失败阶段名），
 * 而不是裸的阶段代号（此前前端会直接展示 "05-critic" 这样的字符串）。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class TaskPipelineFailureMessageIntegrationTest {
    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper mapper;
    @Autowired JwtService jwtService;
    @Autowired UserRepository userRepository;
    @Autowired ProjectRepository projectRepository;
    @Autowired TaskRepository taskRepository;

    private String adminToken;
    private Project project;

    @BeforeEach
    void setUp() {
        User admin = userRepository.findByUsername("admin").orElseThrow();
        adminToken = jwtService.issue(admin.getUsername(), admin.getRole());

        project = new Project();
        project.setName("failure-message-test-" + System.nanoTime());
        project.setSourceDb("MySQL 8.0");
        project.setTargetDb("PostgreSQL 16");
        project.setStatus("NEW");
        project.setOwnerId(admin.getId());
        project.setCreatedAt(Instant.now());
        project = projectRepository.save(project);
    }

    @Test
    void failedPipelinePersistsReadableStageMessage() throws Exception {
        String createBody = mapper.writeValueAsString(new TaskController.CreateTaskRequest(
            project.getId(), "failed-stage", "SELECT IFNULL(name, 'a') FROM users"));
        String created = mockMvc.perform(post("/api/tasks")
                .header("Authorization", "Bearer " + adminToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(createBody))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        long taskId = mapper.readTree(created).path("data").path("id").asLong();

        mockMvc.perform(post("/api/tasks/{id}/execute", taskId)
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isAccepted());

        Task finished = awaitTerminal(taskId);
        assertThat(finished.getStatus()).isEqualTo("FAILED");
        assertThat(finished.getErrorMessage()).isEqualTo("pipeline failed at stage: 05-critic");
        assertThat(finished.getFinishedAt()).isNotNull();
    }

    private Task awaitTerminal(long taskId) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
        while (System.nanoTime() < deadline) {
            Task task = taskRepository.findById(taskId).orElseThrow();
            if (!"RUNNING".equals(task.getStatus())) return task;
            Thread.sleep(100);
        }
        throw new AssertionError("task did not reach a terminal state");
    }

    @TestConfiguration
    static class FailingPipelineConfig {
        @Bean
        @Primary
        MigrationPipelineService failingPipeline(LlmClient llm, AgentRunner runner, LangfuseClient langfuse) {
            return new MigrationPipelineService(llm, runner, langfuse) {
                @Override
                public PipelineResult execute(MigrationInput input, Consumer<AgentStep> listener) {
                    return new PipelineResult(
                        "FAILED", "", "report md", "05-critic", false,
                        Map.of(), List.of(), null);
                }
            };
        }
    }
}
