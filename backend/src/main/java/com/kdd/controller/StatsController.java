package com.kdd.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.repository.ChatLogRepository;
import com.kdd.repository.DocumentChunkRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.*;

@RestController
@RequiredArgsConstructor
public class StatsController {

    private final ChatLogRepository chatLogRepo;
    private final DocumentChunkRepository chunkRepo;
    private final ObjectMapper objectMapper;

    @GetMapping("/stats")
    public ResponseEntity<?> getStats() {
        Map<String, Object> stats = new LinkedHashMap<>();

        stats.put("total_questions", chatLogRepo.count());
        stats.put("today_questions", chatLogRepo.countByCreatedAtAfter(
                LocalDateTime.now().toLocalDate().atStartOfDay()));

        // 최근 7일 일별
        List<Object[]> daily = chatLogRepo.findDailyStats(LocalDateTime.now().minusDays(7));
        List<Map<String, Object>> daily7d = new ArrayList<>();
        for (Object[] r : daily) {
            daily7d.add(Map.of("date", String.valueOf(r[0]), "count", r[1]));
        }
        stats.put("daily_7d", daily7d);

        // 시간대별
        List<Object[]> hourly = chatLogRepo.findHourlyStats();
        Map<Integer, Long> hourMap = new HashMap<>();
        for (Object[] r : hourly) {
            hourMap.put(Integer.parseInt(String.valueOf(r[0])), (Long) r[1]);
        }
        List<Map<String, Object>> hourlyList = new ArrayList<>();
        for (int h = 0; h < 24; h++) {
            hourlyList.add(Map.of("hour", h, "count", hourMap.getOrDefault(h, 0L)));
        }
        stats.put("hourly", hourlyList);

        // 문서 수 / 청크 수
        stats.put("total_docs", chunkRepo.countDistinctDocNames());
        stats.put("total_chunks", chunkRepo.count());

        // TOP 10 참조 문서
        List<String> sourcesJson = chatLogRepo.findSourcesSince(LocalDateTime.now().minusDays(30));
        Map<String, Integer> docCounts = new HashMap<>();
        for (String json : sourcesJson) {
            try {
                List<Map<String, Object>> sources = objectMapper.readValue(json,
                        objectMapper.getTypeFactory().constructCollectionType(List.class, Map.class));
                for (Map<String, Object> s : sources) {
                    String name = (String) s.getOrDefault("uri", s.getOrDefault("doc_name", ""));
                    if (name != null && !name.isBlank()) {
                        docCounts.merge(name, 1, Integer::sum);
                    }
                }
            } catch (Exception ignored) {}
        }
        List<Map<String, Object>> top10 = docCounts.entrySet().stream()
                .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
                .limit(10)
                .map(e -> Map.<String, Object>of("doc_name", e.getKey(), "count", e.getValue()))
                .toList();
        stats.put("docs_top10", top10);

        return ResponseEntity.ok(stats);
    }

    @GetMapping("/health")
    public ResponseEntity<?> health() {
        return ResponseEntity.ok(Map.of("status", "ok"));
    }
}
