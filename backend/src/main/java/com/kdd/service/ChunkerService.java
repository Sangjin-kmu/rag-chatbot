package com.kdd.service;

import com.kdd.config.AppConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
@RequiredArgsConstructor
public class ChunkerService {

    private final AppConfig appConfig;

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> chunk(String content, Map<String, Object> metadata) {
        int chunkSize = appConfig.getChunkSize();
        int overlap = appConfig.getChunkOverlap();
        List<Map<String, Object>> chunks = new ArrayList<>();
        int start = 0;
        int idx = 0;

        while (start < content.length()) {
            int end = Math.min(start + chunkSize, content.length());
            String text = content.substring(start, end);

            Map<String, Object> meta = new HashMap<>(metadata);
            meta.put("chunk_index", idx);
            meta.put("char_count", text.length());

            chunks.add(Map.of("content", text, "metadata", meta));
            start += chunkSize - overlap;
            idx++;
        }
        return chunks;
    }
}
