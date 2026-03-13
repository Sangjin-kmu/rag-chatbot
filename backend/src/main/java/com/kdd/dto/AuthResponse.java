package com.kdd.dto;

import lombok.Builder;
import lombok.Data;
import java.util.Map;

@Data @Builder
public class AuthResponse {
    private String token;
    private Map<String, Object> user;
}
