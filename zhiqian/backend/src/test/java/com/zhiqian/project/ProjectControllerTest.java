package com.zhiqian.project;

import com.zhiqian.security.JwtService;
import com.zhiqian.task.TaskAccessService;
import com.zhiqian.user.User;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * ProjectController 切片测试：创建（校验/字段映射/201）、列表（admin 全量 vs 普通用户仅本人）。
 * owner 归属的端到端行为见 ProjectOwnershipIntegrationTest。
 */
@WebMvcTest(controllers = ProjectController.class)
@AutoConfigureMockMvc(addFilters = false)
class ProjectControllerTest {

    @Autowired MockMvc mvc;
    @MockBean ProjectRepository projectRepository;
    @MockBean TaskAccessService accessService;
    @MockBean JwtService jwtService; // JwtAuthenticationFilter 在 WebMvc 切片内必需

    private User user(long id, String role) {
        User u = new User();
        u.setId(id);
        u.setUsername("user-" + id);
        u.setRole(role);
        return u;
    }

    private Project project(long id, String name, Long ownerId) {
        Project p = new Project();
        p.setId(id);
        p.setName(name);
        p.setSourceDb("MySQL 8.0");
        p.setTargetDb("PostgreSQL 16");
        p.setStatus("NEW");
        p.setOwnerId(ownerId);
        p.setCreatedAt(Instant.now());
        return p;
    }

    @Test
    void listForNonAdminReturnsOnlyOwnedProjects() throws Exception {
        User alice = user(7L, "USER");
        when(accessService.currentUser(null)).thenReturn(alice);
        when(accessService.isAdmin(alice)).thenReturn(false);
        when(projectRepository.findByOwnerId(7L))
            .thenReturn(List.of(project(1L, "alice-a", 7L), project(2L, "alice-b", 7L)));

        mvc.perform(get("/api/projects"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.length()").value(2))
            .andExpect(jsonPath("$.data[0].name").value("alice-a"));

        verify(projectRepository, never()).findAll();
    }

    @Test
    void listForAdminReturnsAllProjects() throws Exception {
        User admin = user(1L, "ADMIN");
        when(accessService.currentUser(null)).thenReturn(admin);
        when(accessService.isAdmin(admin)).thenReturn(true);
        when(projectRepository.findAll())
            .thenReturn(List.of(project(1L, "p1", 7L), project(2L, "p2", 8L), project(3L, "p3", 9L)));

        mvc.perform(get("/api/projects"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.length()").value(3));

        verify(projectRepository, never()).findByOwnerId(any());
    }

    @Test
    void createTrimsFieldsSetsNewStatusAndOwnerThenReturns201() throws Exception {
        User alice = user(7L, "USER");
        when(accessService.currentUser(null)).thenReturn(alice);
        when(projectRepository.save(any(Project.class))).thenAnswer(inv -> {
            Project p = inv.getArgument(0);
            p.setId(42L);
            return p;
        });

        mvc.perform(post("/api/projects")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {"name":"  demo  ","sourceDb":" MySQL 8.0 ","targetDb":" PostgreSQL 16 ",
                     "framework":"Spring Boot 3","description":"desc"}
                    """))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.id").value(42))
            .andExpect(jsonPath("$.data.name").value("demo"))
            .andExpect(jsonPath("$.data.status").value("NEW"))
            .andExpect(jsonPath("$.data.ownerId").value(7));

        ArgumentCaptor<Project> saved = ArgumentCaptor.forClass(Project.class);
        verify(projectRepository).save(saved.capture());
        assertThat(saved.getValue().getSourceDb()).isEqualTo("MySQL 8.0");
        assertThat(saved.getValue().getOwnerId()).isEqualTo(7L);
    }

    @Test
    void createRejectsBlankNameWith400() throws Exception {
        mvc.perform(post("/api/projects")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"\",\"sourceDb\":\"MySQL\",\"targetDb\":\"PG\"}"))
            .andExpect(status().isBadRequest());

        verify(projectRepository, never()).save(any());
    }

    @Test
    void detailDelegatesToAccessService() throws Exception {
        User alice = user(7L, "USER");
        when(accessService.currentUser(null)).thenReturn(alice);
        when(accessService.requireProject(5L, null)).thenReturn(project(5L, "owned", 7L));

        mvc.perform(get("/api/projects/5"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.id").value(5))
            .andExpect(jsonPath("$.data.name").value("owned"));
    }
}
