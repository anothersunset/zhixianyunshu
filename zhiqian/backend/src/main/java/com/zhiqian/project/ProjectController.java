package com.zhiqian.project;

import com.zhiqian.common.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.StreamSupport;

@RestController
@RequestMapping("/api/projects")
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectRepository projectRepository;

    @GetMapping
    public Result<List<Project>> list() {
        var items = StreamSupport
            .stream(projectRepository.findAll().spliterator(), false)
            .toList();
        return Result.ok(items);
    }

    @GetMapping("/{id}")
    public Result<Project> detail(@PathVariable Long id) {
        return Result.ok(projectRepository.findById(id)
            .orElseThrow(() -> new IllegalArgumentException("项目不存在")));
    }

    @GetMapping("/ping")
    public Result<String> ping() {
        return Result.ok("pong");
    }
}
