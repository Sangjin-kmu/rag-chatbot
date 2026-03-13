package com.kdd.service;

import com.kdd.dto.ChatResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
@RequiredArgsConstructor
public class AnswerService {

    private final GeminiService geminiService;

    public ChatResponse generate(String query, List<Map<String, Object>> contexts, String history) {
        String contextText = formatContexts(contexts);

        String systemPrompt = """
            당신은 국민대학교 학칙 및 학사규정 전문가입니다.
            규칙:
            1. 주어진 문서 조각만을 근거로 답변하세요
            2. 근거가 부족하면 추측하지 말고 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요
            3. 숫자, 날짜, 조항은 원문 표현을 그대로 사용하세요
            4. 답변 끝에 사용한 문서명과 섹션을 [출처: 문서명 - 섹션] 형식으로 표시하세요
            5. 여러 문서를 참고했다면 모두 표시하세요""";

        String userPrompt = systemPrompt + "\n\n질문: " + query + "\n\n참고 문서:\n" + contextText
                + "\n\n위 문서를 바탕으로 질문에 답변해주세요.";

        if (history != null && !history.isBlank()) {
            userPrompt = "이전 대화:\n" + history + "\n\n" + userPrompt;
        }

        String answer = geminiService.generate(userPrompt);
        List<Map<String, Object>> sources = buildSources(contexts);

        return ChatResponse.builder()
                .answer(answer)
                .sources(sources)
                .contextCount(contexts.size())
                .build();
    }

    private String formatContexts(List<Map<String, Object>> contexts) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < contexts.size(); i++) {
            @SuppressWarnings("unchecked")
            Map<String, Object> metadata = (Map<String, Object>) contexts.get(i).get("metadata");
            String content = (String) contexts.get(i).get("content");

            sb.append("[문서 ").append(i + 1).append("]\n");
            sb.append("문서명: ").append(metadata.getOrDefault("doc_name", "알 수 없음")).append("\n");
            if (metadata.get("section_path") != null)
                sb.append("섹션: ").append(metadata.get("section_path")).append("\n");
            if (metadata.get("page") != null)
                sb.append("페이지: ").append(metadata.get("page")).append("\n");
            sb.append("\n내용:\n").append(content).append("\n\n---\n");
        }
        return sb.toString();
    }

    private List<Map<String, Object>> buildSources(List<Map<String, Object>> contexts) {
        List<Map<String, Object>> sources = new ArrayList<>();
        Set<String> seen = new HashSet<>();

        for (Map<String, Object> ctx : contexts) {
            @SuppressWarnings("unchecked")
            Map<String, Object> metadata = (Map<String, Object>) ctx.get("metadata");
            String docName = (String) metadata.getOrDefault("doc_name", "알 수 없음");
            String dedupKey = docName + "_" + metadata.getOrDefault("page", "");
            if (seen.contains(dedupKey)) continue;
            seen.add(dedupKey);

            Map<String, Object> source = new LinkedHashMap<>();
            source.put("uri", docName);
            source.put("page", metadata.get("page"));
            source.put("section", metadata.getOrDefault("section_path", ""));
            source.put("has_table", metadata.getOrDefault("has_table", false));
            source.put("source_url", metadata.getOrDefault("source_url", ""));
            source.put("rerank_score", ctx.getOrDefault("rerank_score", 0.0));
            sources.add(source);
        }
        return sources;
    }
}
