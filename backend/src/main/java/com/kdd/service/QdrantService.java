package com.kdd.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.config.AppConfig;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import jakarta.annotation.PostConstruct;
import java.util.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class QdrantService {

    private final AppConfig appConfig;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private WebClient qdrantClient;

    private static final String COLLECTION = "documents";

    @PostConstruct
    public void init() {
        WebClient.Builder builder = WebClient.builder().baseUrl(appConfig.getQdrantUrl());
        if (appConfig.getQdrantApiKey() != null && !appConfig.getQdrantApiKey().isBlank()) {
            builder.defaultHeader("api-key", appConfig.getQdrantApiKey());
        }
        this.qdrantClient = builder.build();
        initCollection();
    }

    private void initCollection() {
        try {
            Map<String, Object> body = Map.of(
                    "vectors", Map.of("size", 3072, "distance", "Cosine")
            );
            qdrantClient.put()
                    .uri("/collections/" + COLLECTION)
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
            log.info("Qdrant 컬렉션 생성 완료: {}", COLLECTION);
        } catch (Exception e) {
            log.info("Qdrant 컬렉션 이미 존재: {}", e.getMessage());
        }
    }

    public void upsert(String id, List<Double> vector, Map<String, Object> payload) {
        Map<String, Object> point = Map.of(
                "id", id,
                "vector", vector,
                "payload", payload
        );
        Map<String, Object> body = Map.of("points", List.of(point));

        qdrantClient.put()
                .uri("/collections/" + COLLECTION + "/points")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }

    public void upsertBatch(List<Map<String, Object>> points) {
        if (points.isEmpty()) return;
        Map<String, Object> body = Map.of("points", points);
        qdrantClient.put()
                .uri("/collections/" + COLLECTION + "/points")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }

    public List<Map<String, Object>> search(List<Double> queryVector, int limit) {
        Map<String, Object> body = Map.of(
                "vector", queryVector,
                "limit", limit,
                "with_payload", true,
                "params", Map.of("hnsw_ef", 128)
        );

        String response = qdrantClient.post()
                .uri("/collections/" + COLLECTION + "/points/search")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();

        try {
            JsonNode root = objectMapper.readTree(response);
            JsonNode results = root.path("result");
            List<Map<String, Object>> hits = new ArrayList<>();
            for (JsonNode r : results) {
                Map<String, Object> hit = new HashMap<>();
                hit.put("id", r.path("id").asText());
                hit.put("score", r.path("score").asDouble());
                Map<String, Object> payload = objectMapper.convertValue(r.path("payload"), Map.class);
                hit.put("payload", payload);
                hits.add(hit);
            }
            return hits;
        } catch (Exception e) {
            throw new RuntimeException("Qdrant 검색 실패: " + e.getMessage(), e);
        }
    }

    public void deleteByIds(List<String> ids) {
        if (ids.isEmpty()) return;
        Map<String, Object> body = Map.of("points", ids);
        qdrantClient.post()
                .uri("/collections/" + COLLECTION + "/points/delete")
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }

    public void deleteCollection() {
        try {
            qdrantClient.delete()
                    .uri("/collections/" + COLLECTION)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();
        } catch (Exception e) {
            log.warn("컬렉션 삭제 실패: {}", e.getMessage());
        }
    }
}
