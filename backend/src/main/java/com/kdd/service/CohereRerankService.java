package com.kdd.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.config.AppConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.*;

@Service
@RequiredArgsConstructor
public class CohereRerankService {

    private final AppConfig appConfig;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final WebClient webClient = WebClient.create();

    /**
     * Cohere rerank-multilingual-v3.0으로 리랭킹
     * @return [{index, relevance_score}] 리스트
     */
    public List<Map<String, Object>> rerank(String query, List<String> documents, int topN) {
        Map<String, Object> body = Map.of(
                "model", "rerank-multilingual-v3.0",
                "query", query,
                "documents", documents,
                "top_n", topN
        );

        String response = webClient.post()
                .uri("https://api.cohere.ai/v1/rerank")
                .header("Authorization", "Bearer " + appConfig.getCohereApiKey())
                .header("Content-Type", "application/json")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();

        try {
            JsonNode root = objectMapper.readTree(response);
            JsonNode results = root.path("results");
            List<Map<String, Object>> ranked = new ArrayList<>();
            for (JsonNode r : results) {
                ranked.add(Map.of(
                        "index", r.path("index").asInt(),
                        "relevance_score", r.path("relevance_score").asDouble()
                ));
            }
            return ranked;
        } catch (Exception e) {
            throw new RuntimeException("Cohere rerank 실패: " + e.getMessage(), e);
        }
    }
}
