package com.zhiqian.task;

import com.zhiqian.common.Result;
import com.zhiqian.project.Project;
import com.zhiqian.report.MigrationReport;
import com.zhiqian.report.MigrationReportRepository;
import com.zhiqian.suggestion.Suggestion;
import com.zhiqian.suggestion.SuggestionRepository;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.Instant;
import java.util.List;

@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {
    private final TaskRepository taskRepository;
    private final SuggestionRepository suggestionRepository;
    private final TaskAgentStepRepository stepRepository;
    private final MigrationReportRepository reportRepository;
    private final TaskExecutionService executionService;
    private final TaskAccessService accessService;

    @GetMapping
    public Result<List<Task>> list(Authentication authentication) {
        return Result.ok(accessService.visibleTasks(authentication));
    }

    @PostMapping
    public ResponseEntity<Result<Task>> create(
        @Valid @RequestBody CreateTaskRequest request,
        Authentication authentication
    ) {
        Project project = accessService.requireProject(request.projectId(), authentication);
        validateDialect(project.getSourceDb(), "source");
        validateDialect(project.getTargetDb(), "target");

        Task task = new Task();
        task.setProjectId(project.getId());
        task.setName(request.name().trim());
        task.setSourceSql(request.sourceSql().trim());
        task.setStatus("PENDING");
        task.setReviewRequired(0);
        task.setCreatedAt(Instant.now());
        return ResponseEntity.status(HttpStatus.CREATED).body(Result.ok(taskRepository.save(task)));
    }

    @GetMapping("/{id}")
    public Result<Task> detail(@PathVariable Long id, Authentication authentication) {
        return Result.ok(accessService.requireTask(id, authentication));
    }

    @GetMapping("/{id}/suggestions")
    public Result<List<Suggestion>> suggestions(@PathVariable Long id, Authentication authentication) {
        accessService.requireTask(id, authentication);
        return Result.ok(suggestionRepository.findByTaskId(id));
    }

    @GetMapping("/{id}/steps")
    public Result<List<TaskAgentStep>> steps(@PathVariable Long id, Authentication authentication) {
        accessService.requireTask(id, authentication);
        return Result.ok(stepRepository.findByTaskIdOrderByIdAsc(id));
    }

    @PostMapping("/{id}/execute")
    public ResponseEntity<Result<TaskExecutionService.StartResponse>> execute(
        @PathVariable Long id,
        Authentication authentication
    ) {
        Task task = accessService.requireTask(id, authentication);
        Project project = accessService.requireProject(task.getProjectId(), authentication);
        return ResponseEntity.accepted().body(Result.ok(executionService.start(task, project)));
    }

    @GetMapping(value = "/{id}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(
        @PathVariable Long id,
        @RequestParam String runId,
        Authentication authentication
    ) {
        Task task = accessService.requireTask(id, authentication);
        return executionService.subscribe(task, runId);
    }

    @GetMapping("/{id}/report")
    public Result<MigrationReport> report(@PathVariable Long id, Authentication authentication) {
        accessService.requireTask(id, authentication);
        return Result.ok(reportRepository.findFirstByTaskIdOrderByIdDesc(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "report not found")));
    }

    @GetMapping("/{id}/report/download")
    public ResponseEntity<String> downloadReport(@PathVariable Long id, Authentication authentication) {
        Task task = accessService.requireTask(id, authentication);
        MigrationReport report = reportRepository.findFirstByTaskIdOrderByIdDesc(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "report not found"));
        return ResponseEntity.ok()
            .header(
                HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=task-" + task.getId() + "-migration-report.md"
            )
            .contentType(MediaType.parseMediaType("text/markdown;charset=UTF-8"))
            .body(report.getContentMd());
    }

    private void validateDialect(String dialect, String side) {
        String normalized = dialect == null ? "" : dialect.toLowerCase();
        boolean supported = normalized.contains("mysql")
            || normalized.contains("oracle")
            || normalized.contains("sqlserver")
            || normalized.contains("sql server")
            || normalized.contains("postgres")
            || normalized.contains("opengauss");
        if (!supported) {
            throw new ResponseStatusException(
                HttpStatus.BAD_REQUEST,
                "unsupported " + side + " dialect: " + dialect
            );
        }
    }

    public record CreateTaskRequest(
        @NotNull Long projectId,
        @NotBlank String name,
        @NotBlank String sourceSql
    ) {}
}
