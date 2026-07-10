package com.zhiqian.project;

import com.zhiqian.common.Result;
import com.zhiqian.task.TaskAccessService;
import lombok.RequiredArgsConstructor;
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

    @GetMapping("/{id}")
    public Result<Project> detail(@PathVariable Long id, Authentication authentication) {
        return Result.ok(accessService.requireProject(id, authentication));
    }

    @GetMapping("/ping")
    public Result<String> ping() {
        return Result.ok("pong");
    }
}
