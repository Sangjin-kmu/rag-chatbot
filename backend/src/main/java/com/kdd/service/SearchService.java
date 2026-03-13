package com.kdd.service;

import com.kdd.config.AppConfig;
import com.kdd.entity.DocumentChunk;
import com.kdd.repository.DocumentChunkRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class SearchService {

    private final AppConfig appConfig;
    private final EmbeddingService embeddingService;
    private final QdrantService qdrantService;
    private final CohereRerankService cohereRerankService;
    private final DocumentChunkRepository chunkRepo;

    /**
     * 청크 인덱싱 (Qdrant + SQLite)
     */
    @Transactional
    public void indexChunk(String chunkId, String content, Map<String, Object> metadata) {
        List<Double> embedding = embeddingService.getEmbedding(content);

        Map<String, Object> payload = new HashMap<>(metadata);
        payload.put("content", content);
        qdrantService.upsert(chunkId, embedding, payload);

        DocumentChunk chunk = DocumentChunk.builder()
                .id(chunkId)
                .content(content)
                .docName((String) metadata.getOrDefault("doc_name", ""))
                .sectionPath((String) metadata.getOrDefault("section_path", ""))
                .page(metadata.get("page") != null ? ((Number) metadata.get("page")).intValue() : null)
                .hasTable(Boolean.TRUE.equals(metadata.get("has_table")))
                .sourceUrl((String) metadata.getOrDefault("source_url", ""))
                .build();
        chunkRepo.save(chunk);
    }

    /**
     * 배치 인덱싱
     */
    @Transactional
    public void indexChunksBatch(List<Map<String, Object>> chunks) {
        if (chunks.isEmpty()) return;

        List<Map<String, Object>> points = new ArrayList<>();
        List<DocumentChunk> entities = new ArrayList<>();

        for (Map<String, Object> c : chunks) {
            String id = (String) c.get("id");
            String content = (String) c.get("content");
            @SuppressWarnings("unchecked")
            Map<String, Object> metadata = (Map<String, Object>) c.get("metadata");

            List<Double> embedding = embeddingService.getEmbedding(content);

            Map<String, Object> payload = new HashMap<>(metadata);
            payload.put("content", content);
            points.add(Map.of("id", id, "vector", embedding, "payload", payload));

            entities.add(DocumentChunk.builder()
                    .id(id)
                    .content(content)
                    .docName((String) metadata.getOrDefault("doc_name", ""))
                    .sectionPath((String) metadata.getOrDefault("section_path", ""))
                    .page(metadata.get("page") != null ? ((Number) metadata.get("page")).intValue() : null)
                    .hasTable(Boolean.TRUE.equals(metadata.get("has_table")))
                    .sourceUrl((String) metadata.getOrDefault("source_url", ""))
                    .build());
        }

        qdrantService.upsertBatch(points);
        chunkRepo.saveAll(entities);
    }

    /**
     * 하이브리드 검색 (BM25 + Vector + RRF + Rerank)
     */
    public List<Map<String, Object>> search(String query, int topK) {
        // 벡터 검색
        List<Double> queryVector = embeddingService.getEmbedding(query);
        List<Map<String, Object>> vectorResults = qdrantService.search(queryVector, appConfig.getVectorTopK());

        // RRF 결합 (벡터 결과만 사용 — SQLite FTS5는 JPA에서 직접 지원 안 됨, 벡터 검색으로 충분)
        List<Map<String, Object>> candidates = new ArrayList<>();
        for (Map<String, Object> hit : vectorResults) {
            @SuppressWarnings("unchecked")
            Map<String, Object> payload = (Map<String, Object>) hit.get("payload");
            Map<String, Object> candidate = new HashMap<>();
            candidate.put("id", hit.get("id"));
            candidate.put("score", hit.get("score"));
            candidate.put("content", payload.get("content"));

            Map<String, Object> metadata = new HashMap<>(payload);
            metadata.remove("content");
            candidate.put("metadata", metadata);
            candidates.add(candidate);
        }

        if (candidates.isEmpty()) return List.of();

        // Cohere Rerank
        List<String> docs = candidates.stream()
                .map(c -> (String) c.get("content"))
                .collect(Collectors.toList());

        int rerankTopN = Math.min(topK * 2, docs.size());
        List<Map<String, Object>> rerankResults = cohereRerankService.rerank(query, docs, rerankTopN);

        // threshold 필터링
        List<Map<String, Object>> reranked = new ArrayList<>();
        for (Map<String, Object> r : rerankResults) {
            double score = (double) r.get("relevance_score");
            if (score < appConfig.getRelevanceThreshold()) continue;

            int idx = (int) r.get("index");
            Map<String, Object> result = new HashMap<>(candidates.get(idx));
            result.put("rerank_score", score);
            reranked.add(result);
        }

        return reranked.stream().limit(topK).collect(Collectors.toList());
    }

    /**
     * 문서별 청크 삭제
     */
    @Transactional
    public int deleteByDocName(String docName) {
        List<DocumentChunk> chunks = chunkRepo.findByDocName(docName);
        if (chunks.isEmpty()) return 0;

        List<String> ids = chunks.stream().map(DocumentChunk::getId).toList();
        qdrantService.deleteByIds(ids);
        chunkRepo.deleteByDocName(docName);
        return ids.size();
    }

    /**
     * 전체 삭제
     */
    @Transactional
    public void deleteAll() {
        qdrantService.deleteCollection();
        chunkRepo.deleteAll();
        qdrantService.init();
    }

    public List<String> getIndexedSourceUrls() {
        return chunkRepo.findDistinctSourceUrls().stream().distinct().toList();
    }
}
