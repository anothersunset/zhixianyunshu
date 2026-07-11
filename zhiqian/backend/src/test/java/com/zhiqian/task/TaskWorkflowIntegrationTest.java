package com.zhiqian.task;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.project.Project;
import com.zhiqian.project.ProjectRepository;
import com.zhiqian.report.MigrationReportRepository;
import com.zhiqian.security.JwtService;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class TaskWorkflowIntegrationTest {
    @Autowired MockMvc mockMvc;
    @Autowired ObjectMapper mapper;
    @Autowired JwtService jwtService;
    @Autowired UserRepository userRepository;
    @Autowired ProjectRepository projectRepository;
    @Autowired TaskRepository taskRepository;
    @Autowired TaskAgentStepRepository stepRepository;
    @Autowired MigrationReportRepository reportRepository;

    private String adminToken;
    private Project project;

    @BeforeEach
    void setUp() {
        User admin = userRepository.findByUsername("admin").orElseThrow();
        adminToken = jwtService.issue(admin.getUsername(), admin.getRole());

        project = new Project();
        project.setName("workflow-test-" + System.nanoTime());
        project.setSourceDb("MySQL 8.0");
        project.setTargetDb("PostgreSQL 16");
        project.setStatus("NEW");
        project.setOwnerId(admin.getId());
        project.setCreatedAt(Instant.now());
        project = projectRepository.save(project);
    }

    @Test
    void createsExecutesAndPersistsRealTaskInput() throws Exception {
        String sourceSql = "SELECT IFNULL(name, 'anonymous')\nFROM users\nWHERE deleted = 0";
        String createBody = mapper.writeValueAsString(new TaskController.CreateTaskRequest(
            project.getId(),
            "mysql-to-postgres",
            sourceSql
        ));
        String createJson = mockMvc.perform(post("/api/tasks")
                .header("Authorization", "Bearer " + adminToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(createBody))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        long taskId = mapper.readTree(createJson).path("data").path("id").asLong();
        assertThat(taskRepository.findById(taskId).orElseThrow().getSourceSql()).isEqualTo(sourceSql);

        String startJson = mockMvc.perform(post("/api/tasks/{id}/execute", taskId)
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isAccepted())
            .andReturn().getResponse().getContentAsString();
        JsonNode start = mapper.readTree(startJson).path("data");
        assertThat(start.path("runId").asText()).startsWith("run-");

        mockMvc.perform(post("/api/tasks/{id}/execute", taskId)
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isConflict());

        Task finished = awaitTerminal(taskId);
        assertThat(finished.getStatus()).isIn("DONE", "REVIEW_REQUIRED");
        assertThat(finished.getResultSql()).isNotBlank();
        assertThat(stepRepository.findByTaskIdOrderByIdAsc(taskId)).hasSizeGreaterThanOrEqualTo(6);
        assertThat(reportRepository.findFirstByTaskIdOrderByIdDesc(taskId)).isPresent();

        mockMvc.perform(get("/api/tasks/{id}/stream", taskId)
                .param("runId", start.path("runId").asText()))
            .andExpect(status().isUnauthorized());
        mockMvc.perform(get("/api/tasks/{id}/stream", taskId)
                .param("runId", start.path("runId").asText())
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isOk())
            .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM));
        mockMvc.perform(get("/api/tasks/{id}/report/download", taskId)
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isOk())
            .andExpect(header().string("Content-Disposition", "attachment; filename=task-" + taskId + "-migration-report.md"))
            .andExpect(content().contentTypeCompatibleWith("text/markdown"));
    }

    @Test
    void rejectsAnonymousAndCrossOwnerTaskAccess() throws Exception {
        Task task = new Task();
        task.setProjectId(project.getId());
        task.setName("private-task");
        task.setSourceSql("SELECT 1");
        task.setStatus("PENDING");
        task.setCreatedAt(Instant.now());
        task = taskRepository.save(task);

        mockMvc.perform(get("/api/tasks/{id}", task.getId()))
            .andExpect(status().isUnauthorized());

        User other = new User();
        other.setUsername("other-" + System.nanoTime());
        other.setPasswordHash("unused");
        other.setDisplayName("Other");
        other.setRole("USER");
        other.setCreatedAt(Instant.now());
        other = userRepository.save(other);
        String otherToken = jwtService.issue(other.getUsername(), other.getRole());

        mockMvc.perform(get("/api/tasks/{id}", task.getId())
                .header("Authorization", "Bearer " + otherToken))
            .andExpect(status().isForbidden());
    }

    @Test
    void unknownDialectFeatureRequiresHumanReview() throws Exception {
        String createBody = mapper.writeValueAsString(new TaskController.CreateTaskRequest(
            project.getId(),
            "unknown-feature",
            "SELECT MYSTERY_VENDOR_FN(id) FROM users"
        ));
        String createJson = mockMvc.perform(post("/api/tasks")
                .header("Authorization", "Bearer " + adminToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(createBody))
            .andExpect(status().isCreated())
            .andReturn().getResponse().getContentAsString();
        long taskId = mapper.readTree(createJson).path("data").path("id").asLong();

        mockMvc.perform(post("/api/tasks/{id}/execute", taskId)
                .header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isAccepted());

        Task finished = awaitTerminal(taskId);
        assertThat(finished.getStatus()).isEqualTo("REVIEW_REQUIRED");
        assertThat(finished.getReviewRequired()).isEqualTo(1);
    }

    @Test
    void returnsTooManyRequestsWhenMigrationQueueIsFull() throws Exception {
        long first = createTask("queue-first", "SELECT IFNULL(name, 'a') FROM users");
        long second = createTask("queue-second", "SELECT IFNULL(name, 'b') FROM users");
        long third = createTask("queue-third", "SELECT IFNULL(name, 'c') FROM users");

        mockMvc.perform(post("/api/tasks/{id}/execute", first).header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isAccepted());
        mockMvc.perform(post("/api/tasks/{id}/execute", second).header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isAccepted());
        mockMvc.perform(post("/api/tasks/{id}/execute", third).header("Authorization", "Bearer " + adminToken))
            .andExpect(status().isTooManyRequests());
        assertThat(taskRepository.findById(third).orElseThrow().getStatus()).isEqualTo("PENDING");
        assertThat(taskRepository.findById(third).orElseThrow().getRunId()).isNull();

        awaitTerminal(first);
        awaitTerminal(second);
    }

    private long createTask(String name, String sql) throws Exception {
        String body = mapper.writeValueAsString(new TaskController.CreateTaskRequest(project.getId(), name, sql));
        String json = mockMvc.perform(post("/api/tasks")
                .header("Authorization", "Bearer " + adminToken)
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
            .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        return mapper.readTree(json).path("data").path("id").asLong();
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
}
