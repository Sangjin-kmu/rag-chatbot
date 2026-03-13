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
public class EmbeddingService {

    private final AppConfig appConfig;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final WebClient webClient = WebClient.create();

    /**
     * Gemini embedding-001로 임베딩 생성 (3072차원)
     */
    public List<Double> getEmbedding(String text) {
        String url = "https://generativelanguage.googleapis.com/v1/models/gemini-embedding-001:embedContent?key="
                + appConfig.getGeminiApiKey();

        Map<String, Object> body = Map.of("content", Map.of("parts", List.of(Map.of("text", text))));

        String response = webClient.post()
                .uri(url)
                .header("Content-Type", "application/json")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();

        try {
            JsonNode root = objectMapper.readTree(response);
            JsonNode values = root.path("embedding").path("values");
            return objectMapper.convertValue(values,
                    objectMapper.getTypeFactory().constructCollectionType(List.class, Double.class));
        } catch (Exception e) {
            throw new RuntimeException("Embedding 생성 실패: " + e.getMessage(), e);
        }
    }
}
