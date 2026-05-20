package com.zhiqian.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.Map;

@Service
public class JwtService {

    private final SecretKey key;
    private final long ttlMillis;

    public JwtService(
        @Value("${app.jwt.secret:change-me-please-change-me-please-32bytes-min}") String secret,
        @Value("${app.jwt.ttl-minutes:720}") long ttlMinutes
    ) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttlMillis = ttlMinutes * 60_000L;
    }

    public String issue(String username, String role) {
        Instant now = Instant.now();
        return Jwts.builder()
            .subject(username)
            .claims(Map.of("role", role))
            .issuedAt(Date.from(now))
            .expiration(Date.from(now.plusMillis(ttlMillis)))
            .signWith(key)
            .compact();
    }

    public Claims parse(String token) {
        return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
    }
}
