package com.zhiqian.auth;

import com.zhiqian.common.Result;
import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
public class UserController {

    private final UserRepository userRepository;

    @GetMapping("/me")
    public Result<Map<String, Object>> me(@AuthenticationPrincipal Object principal) {
        String username = principal == null ? null : principal.toString();
        if (username == null) return Result.fail(401, "未登录");
        User u = userRepository.findByUsername(username)
            .orElseThrow(() -> new IllegalStateException("账户丢失"));
        return Result.ok(Map.of(
            "id", u.getId(),
            "username", u.getUsername(),
            "displayName", u.getDisplayName(),
            "role", u.getRole()
        ));
    }
}
