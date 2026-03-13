package com.kdd.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kdd.config.AppConfig;
import com.kdd.dto.ChatRequest;
import com.kdd.dto.ChatResponse;
import com.kdd.entity.ChatLog;
import com.kdd.entity.UserProfile;
import com.kdd.repository.ChatLogRepository;
import com.kdd.repository.UserProfileRepository;
import com.kdd.security.JwtService;
import com.kdd.service.AnswerService;
import com.kdd.service.SearchService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.*;

@RestController
@RequiredArgsConstructor
public class ChatController {

    private final SearchService searchService;
    private final AnswerService answerService;
    private final JwtService jwtService;
    private final AppConfig appConfig;
    private final ChatLogRepository chatLogRepo;
    private final UserProfileRepository profileRepo;
    private final ObjectMapper objectMapper;

    @PostMapping("/")
    public ResponseEntity<?> chat(
            @RequestBody ChatRequest req,
            @RequestHeader(value = "Authorization", required = false) String auth) {
        try {
            String email = jwtService.extractEmail(auth);

            // 사용자 컨텍스트 구성
            String userContext = "";
            if (email != null) {
                Optional<UserProfile> profile = profileRepo.findById(email);
                if (profile.isPresent()) {
                    UserProfile p = profile.get();
                    List<String> parts = new ArrayList<>();
                    if (p.getDepartment() != null && !p.getDepartment().isBlank())
                        parts.add("학과: " + p.getDepartment());
                    if (p.getGrade() != null && !p.getGrade().isBlank())
                        parts.add("학년: " + p.getGrade());
                    if (!parts.isEmpty()) userContext = "[사용자 정보] " + String.join(", ", parts);
                }
            }

            // 검색
            List<Map<String, Object>> contexts = searchService.search(req.getMessage(), appConfig.getFinalContextSize());

            if (contexts.isEmpty()) {
                saveChatLog(req.getMessage(), "관련된 정보를 찾을 수 없습니다.", List.of(), email);
                return ResponseEntity.ok(ChatResponse.builder()
                        .answer("죄송합니다. 관련된 정보를 찾을 수 없습니다. 질문을 다르게 표현해보시거나, 더 구체적으로 질문해주세요.")
                        .sources(List.of())
                        .contextCount(0)
                        .build());
            }

            // 답변 생성
            String history = req.getHistory() != null ? req.getHistory() : "";
            if (!userContext.isBlank()) history = userContext + "\n" + history;

            ChatResponse result = answerService.generate(req.getMessage(), contexts, history);
            saveChatLog(req.getMessage(), result.getAnswer(), result.getSources(), email);
            return ResponseEntity.ok(result);

        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    private void saveChatLog(String question, String answer, List<Map<String, Object>> sources, String email) {
        try {
            chatLogRepo.save(ChatLog.builder()
                    .question(question)
                    .answer(answer)
                    .sources(objectMapper.writeValueAsString(sources))
                    .userEmail(email != null ? email : "")
                    .build());
        } catch (Exception ignored) {}
    }
}
