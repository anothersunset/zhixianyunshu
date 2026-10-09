package com.zhiqian.project;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.zhiqian.security.JwtService;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * 项目 owner 归属端到端测试（真实安全链：JWT 过滤器 + TaskAccessService + H2）。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ProjectOwnershipIntegrationTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;
    @Autowired JwtService jwtService;
    @Autowired UserRepository userRepository;
    @Autowired ProjectRepository projectRepository;

    @Test
    void ownerSeesOwnProjectWhileStrangerIsForbiddenAndAnonymousUnauthorized() throws Exception {
        User alice = persistUser("alice");
        User bob = persistUser("bob");
        String aliceToken = jwtService.issue(alice.getUsername(), alice.getRole());
        String bobToken = jwtService.issue(bob.getUsername(), bob.getRole());

        Project owned = new Project();
        owned.setName("alice-secret-" + System.nanoTime());
        owned.setSourceDb("MySQL 8.0");
        owned.setTargetDb("PostgreSQL 16");
        owned.setStatus("NEW");
        owned.setOwnerId(alice.getId());
        owned.setCreatedAt(Instant.now());
        owned = projectRepository.save(owned);

        // 匿名：401
        mvc.perform(get("/api/projects"))
            .andExpect(status().isUnauthorized());

        // owner 本人可见
        mvc.perform(get("/api/projects/" + owned.getId())
                .header("Authorization", "Bearer " + aliceToken))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.id").value(owned.getId()));

        // 陌生人：403（TaskAccessService.requireProject 抛 AccessDeniedException）
        mvc.perform(get("/api/projects/" + owned.getId())
                .header("Authorization", "Bearer " + bobToken))
            .andExpect(status().isForbidden());

        // 普通用户列表只见自己的项目，看不到 alice 的
        String bobList = mvc.perform(get("/api/projects")
                .header("Authorization", "Bearer " + bobToken))
            .andExpect(status().isOk())
            .andReturn().getResponse().getContentAsString();
        assertThat(containsProjectId(mapper.readTree(bobList), owned.getId())).isFalse();
    }

    @Test
    void createAssignsCallerAsOwner() throws Exception {
        User carol = persistUser("carol");
        String token = jwtService.issue(carol.getUsername(), carol.getRole());

        String created = mvc.perform(post("/api/projects")
                .header("Authorization", "Bearer " + token)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"name\":\"owner-check\",\"sourceDb\":\"MySQL 8.0\",\"targetDb\":\"openGauss 5.0\"}"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.data.ownerId").value(carol.getId()))
            .andReturn().getResponse().getContentAsString();

        long id = mapper.readTree(created).path("data").path("id").asLong();
        assertThat(projectRepository.findById(id)).hasValueSatisfying(p ->
            assertThat(p.getOwnerId()).isEqualTo(carol.getId()));
    }

    private User persistUser(String prefix) {
        User u = new User();
        u.setUsername(prefix + "-" + System.nanoTime());
        u.setPasswordHash("not-a-real-hash");
        u.setDisplayName(prefix);
        u.setRole("USER");
        u.setCreatedAt(Instant.now());
        return userRepository.save(u);
    }

    private static boolean containsProjectId(JsonNode listResult, long projectId) {
        for (JsonNode item : listResult.path("data")) {
            if (item.path("id").asLong() == projectId) return true;
        }
        return false;
    }
}
