package com.zhiqian.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * JwtService 单元测试
 * 测试 JWT 签发、解析、过期、篡改、密钥校验等场景
 */
class JwtServiceTest {

    /** 至少 32 字节的合法密钥 */
    private static final String VALID_SECRET = "test-jwt-secret-key-32bytes-long-enough!!";

    private JwtService jwtService;

    @BeforeEach
    void setUp() {
        jwtService = new JwtService(VALID_SECRET, 60);
    }

    // ========== 签发 token ==========

    @Nested
    @DisplayName("签发 token")
    class IssueToken {

        @Test
        @DisplayName("签发的 token 包含正确的 subject (username)")
        void tokenContainsCorrectSubject() {
            String token = jwtService.issue("alice", "ADMIN");
            Claims claims = jwtService.parse(token);

            assertEquals("alice", claims.getSubject());
        }

        @Test
        @DisplayName("签发的 token 包含正确的 role claim")
        void tokenContainsCorrectRole() {
            String token = jwtService.issue("bob", "USER");
            Claims claims = jwtService.parse(token);

            assertEquals("USER", claims.get("role", String.class));
        }

        @Test
        @DisplayName("签发的 token 同时包含正确的 subject 和 role")
        void tokenContainsBothSubjectAndRole() {
            String token = jwtService.issue("charlie", "MANAGER");
            Claims claims = jwtService.parse(token);

            assertAll(
                () -> assertEquals("charlie", claims.getSubject()),
                () -> assertEquals("MANAGER", claims.get("role", String.class)),
                () -> assertNotNull(claims.getIssuedAt()),
                () -> assertNotNull(claims.getExpiration())
            );
        }

        @Test
        @DisplayName("issue 返回非空字符串")
        void issueReturnsNonEmptyString() {
            String token = jwtService.issue("dave", "USER");
            assertNotNull(token);
            assertFalse(token.isEmpty());
        }
    }

    // ========== 解析 token ==========

    @Nested
    @DisplayName("解析 token")
    class ParseToken {

        @Test
        @DisplayName("解析 token 能正确提取所有 claims")
        void parseExtractsAllClaims() {
            String token = jwtService.issue("alice", "ADMIN");
            Claims claims = jwtService.parse(token);

            assertAll(
                () -> assertEquals("alice", claims.getSubject()),
                () -> assertEquals("ADMIN", claims.get("role", String.class)),
                () -> assertNotNull(claims.getIssuedAt()),
                () -> assertNotNull(claims.getExpiration()),
                () -> assertTrue(claims.getExpiration().after(claims.getIssuedAt()))
            );
        }

        @Test
        @DisplayName("用同一个 service 签发和解析保持一致性")
        void issueAndParseConsistent() {
            String token1 = jwtService.issue("user1", "ROLE_A");
            String token2 = jwtService.issue("user1", "ROLE_A");

            Claims c1 = jwtService.parse(token1);
            Claims c2 = jwtService.parse(token2);

            assertEquals(c1.getSubject(), c2.getSubject());
            assertEquals(c1.get("role"), c2.get("role"));
        }
    }

    // ========== 过期 token ==========

    @Nested
    @DisplayName("过期 token")
    class ExpiredToken {

        @Test
        @DisplayName("ttlMinutes=0 时签发的 token 立即过期，解析应抛出 ExpiredJwtException")
        void expiredTokenThrowsExpiredJwtException() {
            // ttlMinutes=0 → ttlMillis=0 → 已经过期
            JwtService shortLived = new JwtService(VALID_SECRET, 0);
            String token = shortLived.issue("alice", "ADMIN");

            // 需要短暂等待确保已过期
            assertThrows(ExpiredJwtException.class, () -> shortLived.parse(token));
        }
    }

    // ========== 篡改 token ==========

    @Nested
    @DisplayName("篡改 token")
    class TamperedToken {

        @Test
        @DisplayName("篡改 token 内容后解析应抛出 JwtException")
        void tamperedTokenThrowsJwtException() {
            String token = jwtService.issue("alice", "ADMIN");

            // 篡改 token：翻转最后一个字符
            char lastChar = token.charAt(token.length() - 1);
            char replacement = (lastChar == 'a') ? 'b' : 'a';
            String tampered = token.substring(0, token.length() - 1) + replacement;

            assertThrows(JwtException.class, () -> jwtService.parse(tampered));
        }

        @Test
        @DisplayName("完全随机字符串解析应抛出异常")
        void randomStringThrowsException() {
            assertThrows(Exception.class, () -> jwtService.parse("not-a-valid-token"));
        }

        @Test
        @DisplayName("用不同密钥签发的 token 解析应抛出异常")
        void differentSecretTokenThrowsException() {
            JwtService otherService = new JwtService("other-jwt-secret-key-32bytes-long-ok!!", 60);
            String token = otherService.issue("alice", "ADMIN");

            assertThrows(JwtException.class, () -> jwtService.parse(token));
        }
    }

    // ========== 密钥长度校验 ==========

    @Nested
    @DisplayName("密钥长度校验")
    class SecretValidation {

        @Test
        @DisplayName("密钥长度不足 32 字节时构造函数抛出 IllegalArgumentException")
        void shortSecretThrowsIllegalArgumentException() {
            IllegalArgumentException ex = assertThrows(
                IllegalArgumentException.class,
                () -> new JwtService("short", 60)
            );
            assertTrue(ex.getMessage().contains("32"));
        }

        @Test
        @DisplayName("空密钥抛出 IllegalArgumentException")
        void emptySecretThrowsIllegalArgumentException() {
            assertThrows(
                IllegalArgumentException.class,
                () -> new JwtService("", 60)
            );
        }

        @Test
        @DisplayName("恰好 32 字节的密钥可以正常使用")
        void exactly32BytesSecretWorks() {
            // 32 个字符
            String secret32 = "12345678901234567890123456789012";
            JwtService service = new JwtService(secret32, 60);
            String token = service.issue("test", "USER");
            Claims claims = service.parse(token);
            assertEquals("test", claims.getSubject());
        }

        @Test
        @DisplayName("超过 32 字节的密钥可以正常使用")
        void longerSecretWorks() {
            JwtService service = new JwtService(VALID_SECRET + "extra-padding", 60);
            String token = service.issue("test", "USER");
            Claims claims = service.parse(token);
            assertEquals("test", claims.getSubject());
        }
    }
}
