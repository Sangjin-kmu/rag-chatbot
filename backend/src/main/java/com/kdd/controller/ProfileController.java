package com.kdd.controller;

import com.kdd.dto.ProfileRequest;
import com.kdd.entity.UserProfile;
import com.kdd.repository.UserProfileRepository;
import com.kdd.security.JwtService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.Map;

@RestController
@RequiredArgsConstructor
public class ProfileController {

    private final JwtService jwtService;
    private final UserProfileRepository profileRepo;

    @GetMapping("/profile")
    public ResponseEntity<?> getProfile(
            @RequestHeader(value = "Authorization", required = false) String auth) {
        String email = jwtService.extractEmail(auth);
        if (email == null) return ResponseEntity.ok(Map.of("profile", Map.of()));

        return profileRepo.findById(email)
                .map(p -> ResponseEntity.ok(Map.of("profile", Map.of(
                        "email", p.getEmail(),
                        "name", p.getName() != null ? p.getName() : "",
                        "student_id", p.getStudentId() != null ? p.getStudentId() : "",
                        "department", p.getDepartment() != null ? p.getDepartment() : "",
                        "grade", p.getGrade() != null ? p.getGrade() : ""
                ))))
                .orElse(ResponseEntity.ok(Map.of("profile", Map.of())));
    }

    @PostMapping("/profile")
    public ResponseEntity<?> saveProfile(
            @RequestBody ProfileRequest req,
            @RequestHeader(value = "Authorization", required = false) String auth) {
        String email = jwtService.extractEmail(auth);
        if (email == null) return ResponseEntity.status(401).body(Map.of("detail", "Unauthorized"));

        profileRepo.save(UserProfile.builder()
                .email(email)
                .name(req.getName())
                .studentId(req.getStudentId())
                .department(req.getDepartment())
                .grade(req.getGrade())
                .updatedAt(LocalDateTime.now())
                .build());

        return ResponseEntity.ok(Map.of("message", "프로필 저장 완료"));
    }
}
