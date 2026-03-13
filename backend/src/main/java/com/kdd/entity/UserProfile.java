package com.kdd.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "user_profiles")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class UserProfile {
    @Id
    private String email;

    private String name;
    private String studentId;
    private String department;
    private String grade;

    @Builder.Default
    private LocalDateTime updatedAt = LocalDateTime.now();
}
