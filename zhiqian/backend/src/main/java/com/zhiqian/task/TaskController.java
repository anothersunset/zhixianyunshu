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

/**
 * v2-step-03 修改：SSE 街口从 TaskSseDemoEmitter 切换到 TaskExecutionService，背后走 LLM 驱动的真流水线。
 */
@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskRepository taskRepository;
    private final SuggestionRepository suggestionRepository;
    private final TaskExecutionService executionService;

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
        return executionService.subscribe(id);
    }
}
