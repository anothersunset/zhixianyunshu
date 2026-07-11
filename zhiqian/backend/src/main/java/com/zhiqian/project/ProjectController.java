package com.zhiqian.project;

import com.zhiqian.common.Result;
import com.zhiqian.task.TaskAccessService;
import lombok.RequiredArgsConstructor;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.stream.StreamSupport;

@RestController
@RequestMapping("/api/projects")
@RequiredArgsConstructor
public class ProjectController {
    private final ProjectRepository projectRepository;
    private final TaskAccessService accessService;

    @GetMapping
    public Result<List<Project>> list(Authentication authentication) {
        var user = accessService.currentUser(authentication);
        List<Project> items = accessService.isAdmin(user)
            ? StreamSupport.stream(projectRepository.findAll().spliterator(), false).toList()
            : projectRepository.findByOwnerId(user.getId());
        return Result.ok(items);
    }

    @PostMapping
    public ResponseEntity<Result<Project>> create(
        @Valid @RequestBody CreateProjectRequest request,
        Authentication authentication
    ) {
        var user = accessService.currentUser(authentication);
        Project project = new Project();
        project.setName(request.name().trim());
        project.setSourceDb(request.sourceDb().trim());
        project.setTargetDb(request.targetDb().trim());
        project.setFramework(request.framework());
        project.setDescription(request.description());
        project.setStatus("NEW");
        project.setOwnerId(user.getId());
        project.setCreatedAt(java.time.Instant.now());
        return ResponseEntity.status(HttpStatus.CREATED).body(Result.ok(projectRepository.save(project)));
    }

    @GetMapping("/{id}")
    public Result<Project> detail(@PathVariable Long id, Authentication authentication) {
        return Result.ok(accessService.requireProject(id, authentication));
    }

    @GetMapping("/ping")
    public Result<String> ping() {
        return Result.ok("pong");
    }

    public record CreateProjectRequest(
        @NotBlank String name,
        @NotBlank String sourceDb,
        @NotBlank String targetDb,
        String framework,
        String description
    ) {}
}
