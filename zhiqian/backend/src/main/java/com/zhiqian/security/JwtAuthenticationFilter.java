package com.zhiqian.security;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtService jwtService;

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse resp, FilterChain chain)
        throws ServletException, IOException {
        String token = extractToken(req);
        if (token != null) {
            try {
                Claims c = jwtService.parse(token);
                String username = c.getSubject();
                String role = c.get("role", String.class);
                if (username != null && SecurityContextHolder.getContext().getAuthentication() == null) {
                    var auth = new UsernamePasswordAuthenticationToken(
                        username, null,
                        List.of(new SimpleGrantedAuthority(role == null ? "USER" : role))
                    );
                    SecurityContextHolder.getContext().setAuthentication(auth);
                }
            } catch (Exception e) {
                log.debug("jwt parse failed: {}", e.getMessage());
            }
        }
        chain.doFilter(req, resp);
    }

    private String extractToken(HttpServletRequest req) {
        String h = req.getHeader("Authorization");
        if (h != null && h.startsWith("Bearer ")) return h.substring(7);
        return req.getParameter("token");
    }
}
