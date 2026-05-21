package com.zhiqian.auth;

import com.zhiqian.common.Result;
import com.zhiqian.security.JwtService;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * AuthController 单元测试
 * 测试登录成功、用户不存在、密码错误等场景
 */
@ExtendWith(MockitoExtension.class)
class AuthControllerTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private JwtService jwtService;

    @InjectMocks
    private AuthController authController;

    // ========== 辅助方法 ==========

    private User createUser(String username, String passwordHash, String role, String displayName) {
        User user = new User();
        user.setId(1L);
        user.setUsername(username);
        user.setPasswordHash(passwordHash);
        user.setRole(role);
        user.setDisplayName(displayName);
        return user;
    }

    private AuthController.LoginReq loginReq(String username, String password) {
        AuthController.LoginReq req = new AuthController.LoginReq();
        req.setUsername(username);
        req.setPassword(password);
        return req;
    }

    // ========== 登录成功 ==========

    @Nested
    @DisplayName("登录成功")
    class LoginSuccess {

        @Test
        @DisplayName("正确用户名和密码登录成功，返回 token 和用户信息")
        void successfulLoginReturnsTokenAndUserInfo() {
            User user = createUser("alice", "hashed_pw", "ADMIN", "Alice Wang");

            when(userRepository.findByUsername("alice")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("correct_password", "hashed_pw")).thenReturn(true);
            when(jwtService.issue("alice", "ADMIN")).thenReturn("jwt-token-abc123");

            AuthController.LoginReq req = loginReq("alice", "correct_password");
            Result<Map<String, Object>> result = authController.login(req);

            assertNotNull(result);
            assertEquals(0, result.getCode());
            assertEquals("ok", result.getMessage());

            Map<String, Object> data = result.getData();
            assertNotNull(data);
            assertEquals("jwt-token-abc123", data.get("token"));
            assertEquals("ADMIN", data.get("role"));
            assertEquals("alice", data.get("username"));
            assertEquals("Alice Wang", data.get("displayName"));
        }

        @Test
        @DisplayName("登录成功时调用了正确的依赖方法")
        void successfulLoginCallsDependenciesCorrectly() {
            User user = createUser("bob", "hashed_pw2", "USER", "Bob Li");

            when(userRepository.findByUsername("bob")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("pass123", "hashed_pw2")).thenReturn(true);
            when(jwtService.issue("bob", "USER")).thenReturn("token-xyz");

            authController.login(loginReq("bob", "pass123"));

            verify(userRepository).findByUsername("bob");
            verify(passwordEncoder).matches("pass123", "hashed_pw2");
            verify(jwtService).issue("bob", "USER");
        }

        @Test
        @DisplayName("不同角色用户登录返回对应角色")
        void differentRolesLoginCorrectly() {
            User manager = createUser("carol", "hashed_pw3", "MANAGER", "Carol Zhang");

            when(userRepository.findByUsername("carol")).thenReturn(Optional.of(manager));
            when(passwordEncoder.matches("pass", "hashed_pw3")).thenReturn(true);
            when(jwtService.issue("carol", "MANAGER")).thenReturn("manager-token");

            Result<Map<String, Object>> result = authController.login(loginReq("carol", "pass"));

            assertEquals("MANAGER", result.getData().get("role"));
            assertEquals("manager-token", result.getData().get("token"));
        }
    }

    // ========== 用户不存在 ==========

    @Nested
    @DisplayName("用户不存在")
    class UserNotFound {

        @Test
        @DisplayName("用户不存在时抛出 IllegalArgumentException 并提示'账户不存在'")
        void userNotFoundThrowsException() {
            when(userRepository.findByUsername("nonexistent")).thenReturn(Optional.empty());

            AuthController.LoginReq req = loginReq("nonexistent", "any_password");

            IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> authController.login(req)
            );

            assertEquals("账户不存在", ex.getMessage());
        }

        @Test
        @DisplayName("用户不存在时不会调用 passwordEncoder")
        void userNotFoundSkipsPasswordCheck() {
            when(userRepository.findByUsername("ghost")).thenReturn(Optional.empty());

            assertThrows(
                IllegalArgumentException.class,
                () -> authController.login(loginReq("ghost", "pass"))
            );

            verify(passwordEncoder, never()).matches(anyString(), anyString());
            verify(jwtService, never()).issue(anyString(), anyString());
        }
    }

    // ========== 密码错误 ==========

    @Nested
    @DisplayName("密码错误")
    class WrongPassword {

        @Test
        @DisplayName("密码错误时抛出 IllegalArgumentException 并提示'密码错误'")
        void wrongPasswordThrowsException() {
            User user = createUser("alice", "hashed_correct_pw", "ADMIN", "Alice");

            when(userRepository.findByUsername("alice")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("wrong_password", "hashed_correct_pw")).thenReturn(false);

            AuthController.LoginReq req = loginReq("alice", "wrong_password");

            IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> authController.login(req)
            );

            assertEquals("密码错误", ex.getMessage());
        }

        @Test
        @DisplayName("密码错误时不会签发 token")
        void wrongPasswordDoesNotIssueToken() {
            User user = createUser("alice", "hashed_correct_pw", "ADMIN", "Alice");

            when(userRepository.findByUsername("alice")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("wrong", "hashed_correct_pw")).thenReturn(false);

            assertThrows(
                IllegalArgumentException.class,
                () -> authController.login(loginReq("alice", "wrong"))
            );

            verify(jwtService, never()).issue(anyString(), anyString());
        }

        @Test
        @DisplayName("密码验证使用了正确的编码比较")
        void passwordVerificationUsesEncodedComparison() {
            User user = createUser("bob", "$2a$10$hashed", "USER", "Bob");

            when(userRepository.findByUsername("bob")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("raw_password", "$2a$10$hashed")).thenReturn(false);

            assertThrows(
                IllegalArgumentException.class,
                () -> authController.login(loginReq("bob", "raw_password"))
            );

            verify(passwordEncoder).matches("raw_password", "$2a$10$hashed");
        }
    }

    // ========== Result 格式验证 ==========

    @Nested
    @DisplayName("Result 格式验证")
    class ResultFormat {

        @Test
        @DisplayName("成功登录返回的 Result 包含 code=0")
        void successfulResultCodeIsZero() {
            User user = createUser("test", "hash", "USER", "Test User");

            when(userRepository.findByUsername("test")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("pass", "hash")).thenReturn(true);
            when(jwtService.issue("test", "USER")).thenReturn("tok");

            Result<Map<String, Object>> result = authController.login(loginReq("test", "pass"));

            assertEquals(0, result.getCode());
            assertNotNull(result.getTimestamp());
        }

        @Test
        @DisplayName("成功登录返回的 data 包含所有必需字段")
        void resultDataContainsAllRequiredFields() {
            User user = createUser("full", "hash", "ADMIN", "Full User");

            when(userRepository.findByUsername("full")).thenReturn(Optional.of(user));
            when(passwordEncoder.matches("p", "hash")).thenReturn(true);
            when(jwtService.issue("full", "ADMIN")).thenReturn("tok");

            Result<Map<String, Object>> result = authController.login(loginReq("full", "p"));
            Map<String, Object> data = result.getData();

            assertAll(
                () -> assertTrue(data.containsKey("token"), "应包含 token"),
                () -> assertTrue(data.containsKey("role"), "应包含 role"),
                () -> assertTrue(data.containsKey("username"), "应包含 username"),
                () -> assertTrue(data.containsKey("displayName"), "应包含 displayName")
            );
        }
    }
}
