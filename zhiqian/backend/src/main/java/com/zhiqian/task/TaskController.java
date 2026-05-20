package com.zhiqian.task;

import com.zhiqian.common.Result;
import com.zhiqian.suggestion.Suggestion;
import com.zhiqian.suggestion.SuggestionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.stream.StreamSupport;

@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskRepository taskRepository;
    private final SuggestionRepository suggestionRepository;
    private final TaskSseDemoEmitter sseEmitter;

    @GetMapping
    public Result<List<Task>> list() {
        var items = StreamSupport
            .stream(taskRepository.findAll().spliterator(), false)
            .toList();
        return Result.ok(items);
    }

    @GetMapping("/{id}")
    public Result<Task> detail(@PathVariable Long id) {
        return Result.ok(taskRepository.findById(id)
            .orElseThrow(() -> new IllegalArgumentException("任务不存在")));
    }

    @GetMapping("/{id}/suggestions")
    public Result<List<Suggestion>> suggestions(@PathVariable Long id) {
        return Result.ok(suggestionRepository.findByTaskId(id));
    }

    @GetMapping(value = "/{id}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@PathVariable Long id) {
        return sseEmitter.subscribe(id);
    }
}
