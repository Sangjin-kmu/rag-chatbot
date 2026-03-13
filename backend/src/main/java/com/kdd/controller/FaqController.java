package com.kdd.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.repository.ChatLogRepository;
import com.kdd.service.GeminiService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.*;

@RestController
@RequiredArgsConstructor
public class FaqController {

    private final ChatLogRepository chatLogRepo;
    private final GeminiService geminiService;
    private final ObjectMapper objectMapper;

    @GetMapping("/faq")
    public ResponseEntity<?> getFaq() {
        try {
            List<Object[]> raw = chatLogRepo.findFrequentQuestions(LocalDateTime.now().minusDays(30));
            if (raw.isEmpty()) return ResponseEntity.ok(Map.of("faqs", List.of()));

            // 최대 30개까지
            List<Map<String, Object>> questions = new ArrayList<>();
            for (int i = 0; i < Math.min(raw.size(), 30); i++) {
                Object[] r = raw.get(i);
                questions.add(Map.of(
                        "question", r[0], "answer", r[1],
                        "sources", r[2] != null ? r[2] : "[]",
                        "count", r[3]
                ));
            }

            // Gemini로 그룹핑
            StringBuilder lines = new StringBuilder();
            for (int i = 0; i < questions.size(); i++) {
                lines.append(i + 1).append(". (").append(questions.get(i).get("count"))
                        .append("회) ").append(questions.get(i).get("question")).append("\n");
            }

            String prompt = "아래는 대학교 학칙 질의응답 시스템에서 최근 30일간 들어온 질문 목록이야.\n" +
                    "유사한 질문끼리 그룹핑해서 대표 FAQ를 최대 8개 만들어줘.\n\n" +
                    "규칙:\n- 대표 질문은 자연스럽고 간결하게 다듬어줘\n- 카테고리를 붙여줘\n- 원본 번호를 포함해줘\n\n" +
                    "아래 JSON 배열 형식으로만 답해줘:\n" +
                    "[{\"question\": \"대표 질문\", \"category\": \"카테고리\", \"original_indices\": [1,3,5]}]\n\n" +
                    "질문 목록:\n" + lines;

            String text = geminiService.generate(prompt).trim();
            if (text.contains("```")) {
                text = text.split("```")[1];
                if (text.startsWith("json")) text = text.substring(4);
            }

            List<Map<String, Object>> groups = objectMapper.readValue(text,
                    objectMapper.getTypeFactory().constructCollectionType(List.class, Map.class));

            List<Map<String, Object>> faqs = new ArrayList<>();
            for (Map<String, Object> g : groups) {
                if (faqs.size() >= 8) break;
                @SuppressWarnings("unchecked")
                List<Integer> indices = (List<Integer>) g.get("original_indices");
                Map<String, Object> best = null;
                for (int idx : indices) {
                    if (idx >= 1 && idx <= questions.size()) {
                        Map<String, Object> candidate = questions.get(idx - 1);
                        if (best == null || ((Number) candidate.get("count")).intValue() > ((Number) best.get("count")).intValue()) {
                            best = candidate;
                        }
                    }
                }
                if (best != null) {
                    String sourcesStr = String.valueOf(best.get("sources"));
                    List<Object> sources = sourcesStr.startsWith("[")
                            ? objectMapper.readValue(sourcesStr, List.class) : List.of();
                    int totalCount = indices.stream()
                            .filter(i -> i >= 1 && i <= questions.size())
                            .mapToInt(i -> ((Number) questions.get(i - 1).get("count")).intValue())
                            .sum();
                    faqs.add(Map.of(
                            "question", g.get("question"),
                            "category", g.getOrDefault("category", "기타"),
                            "answer", best.get("answer"),
                            "sources", sources,
                            "count", totalCount
                    ));
                }
            }

            faqs.sort((a, b) -> ((Number) b.get("count")).intValue() - ((Number) a.get("count")).intValue());
            return ResponseEntity.ok(Map.of("faqs", faqs));

        } catch (Exception e) {
            return ResponseEntity.ok(Map.of("faqs", List.of()));
        }
    }
}
