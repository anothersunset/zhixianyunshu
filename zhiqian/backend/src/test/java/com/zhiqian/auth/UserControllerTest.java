package com.zhiqian.auth;

import com.zhiqian.security.JwtService;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * GET /api/users/me：持有效 JWT 返回当前用户画像；匿名请求 401。
 */
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class UserControllerTest {

    @Autowired MockMvc mvc;
    @Autowired JwtService jwtService;
    @Autowired UserRepository userRepository;

    @Test
    void meReturnsCurrentUserForValidToken() throws Exception {
        User user = new User();
        user.setUsername("me-user-" + System.nanoTime());
        user.setPasswordHash("not-a-real-hash");
        user.setDisplayName("Me User");
        user.setRole("USER");
        user.setCreatedAt(Instant.now());
        user = userRepository.save(user);

        String token = jwtService.issue(user.getUsername(), user.getRole());

        mvc.perform(get("/api/users/me").header("Authorization", "Bearer " + token))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.code").value(0))
            .andExpect(jsonPath("$.data.id").value(user.getId()))
            .andExpect(jsonPath("$.data.username").value(user.getUsername()))
            .andExpect(jsonPath("$.data.displayName").value("Me User"))
            .andExpect(jsonPath("$.data.role").value("USER"));
    }

    @Test
    void meRejectsAnonymousRequestWith401() throws Exception {
        mvc.perform(get("/api/users/me"))
            .andExpect(status().isUnauthorized());
    }
}
