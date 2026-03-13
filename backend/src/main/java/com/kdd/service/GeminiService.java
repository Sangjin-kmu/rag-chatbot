package com.kdd.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.config.AppConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class GeminiService {

    private final AppConfig appConfig;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final WebClient webClient = WebClient.create();

    /**
     * Gemini 2.5 Flash로 텍스트 생성
     */
    public String generate(String prompt) {
        String url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key="
                + appConfig.getGeminiApiKey();

        Map<String, Object> body = Map.of(
                "contents", List.of(Map.of("parts", List.of(Map.of("text", prompt))))
        );

        String response = webClient.post()
                .uri(url)
                .header("Content-Type", "application/json")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();

        try {
            JsonNode root = objectMapper.readTree(response);
            return root.path("candidates").get(0)
                    .path("content").path("parts").get(0)
                    .path("text").asText();
        } catch (Exception e) {
            throw new RuntimeException("Gemini 생성 실패: " + e.getMessage(), e);
        }
    }
}
