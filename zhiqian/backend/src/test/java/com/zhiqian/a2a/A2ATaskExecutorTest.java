package com.zhiqian.a2a;

import org.junit.jupiter.api.Test;
import org.springframework.core.task.SyncTaskExecutor;
import org.springframework.http.HttpEntity;
import org.springframework.web.client.RestTemplate;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class A2ATaskExecutorTest {
    @Test
    void sendsTheRagTranspileDtoToTheConfiguredBaseUrl() {
        RestTemplate rest = mock(RestTemplate.class);
        when(rest.postForObject(eq("http://rag.internal:8001/transpile"), any(HttpEntity.class), eq(Map.class)))
            .thenReturn(Map.of("ok", true, "target", "SELECT 1"));
        A2ATaskExecutor executor = new A2ATaskExecutor(
            new SyncTaskExecutor(), rest, "http://rag.internal:8001/"
        );
        A2ATask task = task(Map.of(
            "skill", "sql.transpile",
            "arguments", Map.of(
                "source_sql", "SELECT IFNULL(a, b) FROM t",
                "source_dialect", "mysql",
                "target_dialect", "opengauss"
            )
        ));

        executor.run(task);

        assertThat(task.state).isEqualTo("completed");
        @SuppressWarnings("unchecked")
        var request = org.mockito.ArgumentCaptor.forClass(HttpEntity.class);
        verify(rest).postForObject(eq("http://rag.internal:8001/transpile"), request.capture(), eq(Map.class));
        assertThat(request.getValue().getBody()).isEqualTo(Map.of(
            "sql", "SELECT IFNULL(a, b) FROM t",
            "source", "mysql",
            "target", "opengauss"
        ));
    }

    @Test
    void marksUnknownSkillsAsFailedInsteadOfCompletedArtifacts() {
        A2ATaskExecutor executor = new A2ATaskExecutor(
            new SyncTaskExecutor(), mock(RestTemplate.class), "http://rag.internal:8001"
        );
        A2ATask task = task(Map.of("skill", "unknown.skill"));

        org.assertj.core.api.Assertions.assertThatThrownBy(() -> executor.run(task))
            .isInstanceOf(IllegalArgumentException.class);

        assertThat(task.state).isEqualTo("failed");
        assertThat(task.errorMessage).contains("unknown skill");
        assertThat(task.artifacts).isEmpty();
    }

    private A2ATask task(Map<String, Object> input) {
        A2ATask task = new A2ATask();
        task.id = "task-1";
        task.state = "submitted";
        task.createdAt = Instant.now();
        task.updatedAt = task.createdAt;
        task.input = input;
        return task;
    }
}
