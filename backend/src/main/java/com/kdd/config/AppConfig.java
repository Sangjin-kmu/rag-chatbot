package com.kdd.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.Arrays;
import java.util.List;

@Configuration
@ConfigurationProperties(prefix = "app")
@Getter @Setter
public class AppConfig {
    private String geminiApiKey;
    private String cohereApiKey;
    private String googleClientId;
    private String qdrantUrl;
    private String qdrantApiKey;
    private String allowedDomain;
    private String docAdminEmails;
    private String jwtSecret;
    private String uploadDir;
    private int chunkSize;
    private int chunkOverlap;
    private int bm25TopK;
    private int vectorTopK;
    private int finalContextSize;
    private double relevanceThreshold;

    public List<String> getAdminEmailList() {
        if (docAdminEmails == null || docAdminEmails.isBlank()) return List.of();
        return Arrays.stream(docAdminEmails.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
    }
}
