package com.kdd.service;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.stereotype.Service;

import java.io.File;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
public class PdfParserService {

    public List<Map<String, Object>> parse(String filePath, String docName) {
        List<Map<String, Object>> chunks = new ArrayList<>();

        try (PDDocument doc = PDDocument.load(new File(filePath))) {
            int totalPages = doc.getNumberOfPages();
            PDFTextStripper stripper = new PDFTextStripper();

            for (int i = 1; i <= totalPages; i++) {
                stripper.setStartPage(i);
                stripper.setEndPage(i);
                String text = stripper.getText(doc);

                if (text != null && !text.isBlank()) {
                    String sectionPath = extractSectionPath(text);
                    Map<String, Object> chunk = new HashMap<>();
                    chunk.put("content", text);
                    Map<String, Object> metadata = new HashMap<>();
                    metadata.put("doc_name", docName);
                    metadata.put("section_path", sectionPath);
                    metadata.put("page", i);
                    metadata.put("has_table", false);
                    metadata.put("total_pages", totalPages);
                    chunk.put("metadata", metadata);
                    chunks.add(chunk);
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("PDF 파싱 실패: " + e.getMessage(), e);
        }
        return chunks;
    }

    private String extractSectionPath(String text) {
        Pattern p = Pattern.compile("제\\s*(\\d+)\\s*장[:\\s]+([^\\n]+)");
        Matcher m = p.matcher(text.substring(0, Math.min(500, text.length())));
        if (m.find()) {
            return "제" + m.group(1) + "장: " + m.group(2).trim();
        }
        return "본문";
    }
}
