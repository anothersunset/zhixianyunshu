package com.zhiqian.bootstrap;

import com.zhiqian.user.User;
import com.zhiqian.user.UserRepository;
import com.zhiqian.project.ProjectRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.annotation.Order;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * 启动时创建默认管理员账户 admin / admin123。
 * 仅在 users 表为空时插入，不会覆盖现有数据。
 */
@Slf4j
@Component
@Order(10)
@RequiredArgsConstructor
public class DataBootstrap implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final ProjectRepository projectRepository;
    @Value("${app.admin.password:}")
    private String adminPassword;

    @Override
    public void run(String... args) {
        User admin = userRepository.findByUsername("admin").orElse(null);
        if (admin == null) {
            if (adminPassword == null || adminPassword.isBlank()) {
                log.error("✗ 未配置 APP_ADMIN_PASSWORD 环境变量，拒绝创建默认管理员账户");
                return;
            }
            User u = new User();
            u.setUsername("admin");
            u.setPasswordHash(passwordEncoder.encode(adminPassword));
            u.setDisplayName("系统管理员");
            u.setRole("ADMIN");
            u.setCreatedAt(Instant.now());
            admin = userRepository.save(u);
            log.info("✓ 初始化默认管理员账户 admin (首次启动请及时修改密码)");
        }
        if (admin != null) {
            for (var project : projectRepository.findAll()) {
                if (project.getOwnerId() == null) {
                    project.setOwnerId(admin.getId());
                    projectRepository.save(project);
                }
            }
        }
    }
}
