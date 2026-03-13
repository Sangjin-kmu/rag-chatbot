package com.kdd.dto;

import lombok.Builder;
import lombok.Data;
import java.util.List;
import java.util.Map;

@Data @Builder
public class ChatResponse {
    private String answer;
    private List<Map<String, Object>> sources;
    private int contextCount;
}
