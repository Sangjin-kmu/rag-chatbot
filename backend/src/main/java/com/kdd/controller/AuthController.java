package com.kdd.controller;

import com.kdd.config.AppConfig;
import com.kdd.dto.AuthRequest;
import com.kdd.dto.AuthResponse;
import com.kdd.entity.UserProfile;
import com.kdd.repository.UserProfileRepository;
import com.kdd.security.GoogleAuthService;
import com.kdd.security.JwtService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

@RestController
@RequiredArgsConstructor
public class AuthController {

    private final GoogleAuthService googleAuthService;
    private final JwtService jwtService;
    private final AppConfig appConfig;
    private final UserProfileRepository profileRepo;

    @PostMapping("/auth/google")
    public ResponseEntity<?> googleLogin(@RequestBody AuthRequest req) {
        Map<String, String> userInfo = googleAuthService.verifyToken(req.getCredential());
        if (userInfo == null || userInfo.get("email") == null) {
            return ResponseEntity.status(401).body(Map.of("detail", "Google 인증 실패"));
        }

        String email = userInfo.get("email");
        String name = userInfo.getOrDefault("name", "");
        String token = jwtService.createToken(email, name);
        boolean isAdmin = appConfig.getAdminEmailList().contains(email);

        // 프로필 자동 생성
        if (!profileRepo.existsById(email)) {
            profileRepo.save(UserProfile.builder()
                    .email(email).name(name)
                    .studentId("").department("").grade("")
                    .updatedAt(LocalDateTime.now())
                    .build());
        }

        return ResponseEntity.ok(AuthResponse.builder()
                .token(token)
                .user(Map.of("email", email, "name", name, "isDocAdmin", isAdmin))
                .build());
    }

    @GetMapping("/auth/me")
    public ResponseEntity<?> getMe(@RequestHeader(value = "Authorization", required = false) String auth) {
        String email = jwtService.extractEmail(auth);
        if (email == null) return ResponseEntity.status(401).body(Map.of("detail", "Unauthorized"));

        boolean isAdmin = appConfig.getAdminEmailList().contains(email);
        Map<String, String> claims = jwtService.parseToken(auth.substring(7));
        return ResponseEntity.ok(Map.of("user", Map.of(
                "email", email, "name", claims.getOrDefault("name", ""), "isDocAdmin", isAdmin
        )));
    }
}
