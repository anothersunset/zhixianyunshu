package com.zhiqian.auth;

import com.zhiqian.common.Result;
import com.zhiqian.security.JwtService;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    @PostMapping("/login")
    public Result<Map<String, Object>> login(@RequestBody LoginReq req) {
        User u = userRepository.findByUsername(req.getUsername())
            .orElseThrow(() -> new IllegalArgumentException("账户不存在"));
        if (!passwordEncoder.matches(req.getPassword(), u.getPasswordHash())) {
            throw new IllegalArgumentException("密码错误");
        }
        String token = jwtService.issue(u.getUsername(), u.getRole());
        return Result.ok(Map.of(
            "token", token,
            "role", u.getRole(),
            "username", u.getUsername(),
            "displayName", u.getDisplayName()
        ));
    }

    @Data
    public static class LoginReq {
        private String username;
        private String password;
    }
}
