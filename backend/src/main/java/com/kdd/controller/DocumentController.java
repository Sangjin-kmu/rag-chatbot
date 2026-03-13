package com.kdd.controller;

import com.kdd.config.AppConfig;
import com.kdd.repository.DocumentChunkRepository;
import com.kdd.security.JwtService;
import com.kdd.service.ChunkerService;
import com.kdd.service.PdfParserService;
import com.kdd.service.SearchService;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.nio.file.*;
import java.util.*;

@RestController
@RequiredArgsConstructor
public class DocumentController {

    private final AppConfig appConfig;
    private final JwtService jwtService;
    private final SearchService searchService;
    private final PdfParserService pdfParser;
    private final ChunkerService chunkerService;
    private final DocumentChunkRepository chunkRepo;

    private void requireAdmin(String auth) {
        String email = jwtService.extractEmail(auth);
        if (email == null || !appConfig.getAdminEmailList().contains(email)) {
            throw new RuntimeException("Admin access required");
        }
    }

    @PostMapping("/upload")
    public ResponseEntity<?> upload(
            @RequestParam("file") MultipartFile file,
            @RequestHeader("Authorization") String auth) {
        requireAdmin(auth);
        try {
            Path uploadDir = Paths.get(appConfig.getUploadDir());
            Files.createDirectories(uploadDir);
            Path filePath = uploadDir.resolve(file.getOriginalFilename());
            file.transferTo(filePath.toFile());

            List<Map<String, Object>> parsed;
            if (file.getOriginalFilename().endsWith(".pdf")) {
                parsed = pdfParser.parse(filePath.toString(), file.getOriginalFilename());
            } else {
                return ResponseEntity.badRequest().body(Map.of("detail", "Unsupported file type"));
            }

            List<Map<String, Object>> allChunks = new ArrayList<>();
            for (Map<String, Object> section : parsed) {
                @SuppressWarnings("unchecked")
                Map<String, Object> metadata = (Map<String, Object>) section.get("metadata");
                List<Map<String, Object>> sub = chunkerService.chunk((String) section.get("content"), metadata);
                allChunks.addAll(sub);
            }

            for (Map<String, Object> chunk : allChunks) {
                String chunkId = UUID.randomUUID().toString();
                @SuppressWarnings("unchecked")
                Map<String, Object> metadata = (Map<String, Object>) chunk.get("metadata");
                searchService.indexChunk(chunkId, (String) chunk.get("content"), metadata);
            }

            return ResponseEntity.ok(Map.of(
                    "message", "Successfully indexed " + allChunks.size() + " chunks",
                    "filename", file.getOriginalFilename(),
                    "chunks", allChunks.size()
            ));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @GetMapping("/documents")
    public ResponseEntity<?> listDocuments() {
        try {
            Map<String, Long> indexed = new HashMap<>();
            for (Object[] row : chunkRepo.countByDocNameGrouped()) {
                indexed.put((String) row[0], (Long) row[1]);
            }

            Path uploadDir = Paths.get(appConfig.getUploadDir());
            List<Map<String, Object>> files = new ArrayList<>();
            if (Files.exists(uploadDir)) {
                for (File f : uploadDir.toFile().listFiles()) {
                    if (f.isFile()) {
                        long chunkCount = indexed.getOrDefault(f.getName(), 0L);
                        files.add(Map.of(
                                "filename", f.getName(),
                                "size", f.length(),
                                "type", f.getName().substring(f.getName().lastIndexOf(".")),
                                "chunk_count", chunkCount,
                                "indexed", chunkCount > 0
                        ));
                    }
                }
            }
            return ResponseEntity.ok(Map.of("documents", files));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("detail", e.getMessage()));
        }
    }

    @DeleteMapping("/documents/{filename}")
    public ResponseEntity<?> deleteDocument(
            @PathVariable String filename,
            @RequestHeader("Authorization") String auth) {
        requireAdmin(auth);
        int deleted = searchService.deleteByDocName(filename);
        Path filePath = Paths.get(appConfig.getUploadDir(), filename);
        try { Files.deleteIfExists(filePath); } catch (Exception ignored) {}
        return ResponseEntity.ok(Map.of("message", filename + " 삭제 완료", "deleted_chunks", deleted));
    }

    @GetMapping("/documents/{filename}/preview")
    public ResponseEntity<Resource> previewDocument(@PathVariable String filename) {
        Path filePath = Paths.get(appConfig.getUploadDir(), filename);
        if (!Files.exists(filePath)) {
            return ResponseEntity.notFound().build();
        }
        Resource resource = new FileSystemResource(filePath);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + filename + "\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
    }

    @PostMapping("/reset")
    public ResponseEntity<?> resetIndex(@RequestHeader("Authorization") String auth) {
        requireAdmin(auth);
        searchService.deleteAll();
        return ResponseEntity.ok(Map.of("message", "Index reset successfully"));
    }

    @GetMapping("/crawl/notices/list")
    public ResponseEntity<?> getNoticeList() {
        List<Object[]> rows = chunkRepo.findNoticeDocs();
        List<Map<String, Object>> notices = new ArrayList<>();
        for (Object[] row : rows) {
            notices.add(Map.of(
                    "doc_name", row[0],
                    "chunk_count", row[1],
                    "source_url", ""
            ));
        }
        return ResponseEntity.ok(Map.of("notices", notices));
    }
}
