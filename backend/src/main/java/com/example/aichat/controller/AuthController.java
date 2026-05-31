package com.example.aichat.controller;

import com.example.aichat.config.JwtUtil;
import com.example.aichat.model.SysUser;
import com.example.aichat.repository.UserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;

    public AuthController(UserRepository userRepository,
                          PasswordEncoder passwordEncoder,
                          JwtUtil jwtUtil) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtil = jwtUtil;
    }

    @PostMapping("/login")
    public Mono<ResponseEntity<Map<String, String>>> login(@RequestBody Map<String, String> body) {
        String username = body.getOrDefault("username", "");
        String password = body.getOrDefault("password", "");

        Optional<SysUser> userOpt = userRepository.findByUsername(username);
        if (userOpt.isEmpty()) {
            return Mono.just(ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "用户名或密码错误")));
        }

        SysUser user = userOpt.get();
        if (!passwordEncoder.matches(password, user.getPassword())) {
            return Mono.just(ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error", "用户名或密码错误")));
        }

        String token = jwtUtil.generateToken(user.getUsername());
        return Mono.just(ResponseEntity.ok(Map.of("token", token)));
    }

    @GetMapping("/userinfo")
    public Mono<ResponseEntity<Map<String, String>>> userInfo(@RequestHeader("Authorization") String authHeader) {
        String token = authHeader.replace("Bearer ", "");
        String username = jwtUtil.getUsernameFromToken(token);
        return Mono.just(ResponseEntity.ok(Map.of("username", username)));
    }
}
