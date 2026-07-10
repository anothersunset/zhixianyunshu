package com.zhiqian.task;

import com.zhiqian.project.Project;
import com.zhiqian.project.ProjectRepository;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TaskAccessService {
    private final UserRepository userRepository;
    private final ProjectRepository projectRepository;
    private final TaskRepository taskRepository;

    public User currentUser(Authentication authentication) {
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "authentication required");
        }
        return userRepository.findByUsername(authentication.getName())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "user not found"));
    }

    public boolean isAdmin(User user) {
        return "ADMIN".equalsIgnoreCase(user.getRole());
    }

    public Project requireProject(Long projectId, Authentication authentication) {
        User user = currentUser(authentication);
        Project project = projectRepository.findById(projectId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "project not found"));
        if (!isAdmin(user) && !user.getId().equals(project.getOwnerId())) {
            throw new AccessDeniedException("project access denied");
        }
        return project;
    }

    public Task requireTask(Long taskId, Authentication authentication) {
        Task task = taskRepository.findById(taskId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "task not found"));
        requireProject(task.getProjectId(), authentication);
        return task;
    }

    public List<Task> visibleTasks(Authentication authentication) {
        User user = currentUser(authentication);
        if (isAdmin(user)) {
            return java.util.stream.StreamSupport.stream(taskRepository.findAll().spliterator(), false)
                .toList();
        }
        return taskRepository.findByOwnerId(user.getId());
    }
}
