package com.kdd.service;

import com.kdd.entity.DocumentChunk;
import com.kdd.repository.DocumentChunkRepository;
import com.microsoft.playwright.*;
import com.microsoft.playwright.options.WaitUntilState;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.Loader;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class NoticeCrawlerService {

    private final DocumentChunkRepository chunkRepo;
    private final ChunkerService chunkerService;
    private final GeminiService geminiService;

    private static final String BASE_URL = "https://cs.kookmin.ac.kr/news/notice/";
    private static final String NOTICE_PDF_DIR = "crawled_notices/pdf";
    private static final int WAIT_MS = 2000;

    /**
     * 최근 N일 이내 공지 크롤링
     * 1) Playwright로 공지 목록 + 본문 수집
     * 2) Gemini로 유효성 판단 (마감 지난 공지 등 제외)
     * 3) 유효한 공지만 PDF 변환 + RDB 저장
     */
    public Map<String, Object> crawlRecentNotices(int days) {
        int success = 0, fail = 0, skipped = 0, totalChunks = 0;
        LocalDate cutoff = LocalDate.now().minusDays(days);
        List<Map<String, Object>> crawledList = new ArrayList<>();
        List<String> errors = new ArrayList<>();
        Set<String> processedUrls = new HashSet<>();

        try (Playwright pw = Playwright.create()) {
            Browser browser = pw.chromium().launch(
                new BrowserType.LaunchOptions().setHeadless(true));
            BrowserContext context = browser.newContext(
                new Browser.NewContextOptions()
                    .setUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"));
            Page page = context.newPage();

            log.info("공지 목록 수집 시작 (최근 {}일)", days);
            page.navigate(BASE_URL, new Page.NavigateOptions()
                .setWaitUntil(WaitUntilState.NETWORKIDLE).setTimeout(30000));
            page.waitForTimeout(3000);

            // === 1단계: 공지 목록 수집 (날짜 필터) ===
            List<Map<String, String>> allNotices = new ArrayList<>();
            boolean keepGoing = true;

            for (int pn = 0; keepGoing && pn < 30; pn++) {
                page.navigate(BASE_URL + "?&pn=" + pn, new Page.NavigateOptions()
                    .setWaitUntil(WaitUntilState.NETWORKIDLE).setTimeout(30000));
                page.waitForTimeout(WAIT_MS);

                List<Map<String, String>> pageNotices = extractNoticeList(page);
                log.info("페이지 {} - {}개 공지", pn + 1, pageNotices.size());
                if (pageNotices.isEmpty()) break;

                for (Map<String, String> n : pageNotices) {
                    boolean isPinned = "true".equals(n.get("pinned"));
                    LocalDate nd = parseDate(n.get("date"));

                    if (!isPinned && nd != null && nd.isBefore(cutoff)) {
                        keepGoing = false;
                        continue;
                    }
                    if (isPinned && nd != null && nd.isBefore(cutoff)) {
                        skipped++;
                        continue;
                    }
                    if (processedUrls.contains(n.get("url"))) continue;
                    processedUrls.add(n.get("url"));
                    allNotices.add(n);
                }
            }

            log.info("날짜 필터 후 {}개 공지", allNotices.size());

            // === 2단계: 각 공지 상세 페이지에서 본문 수집 ===
            List<Map<String, String>> detailedNotices = new ArrayList<>();
            for (Map<String, String> notice : allNotices) {
                try {
                    page.navigate(notice.get("url"), new Page.NavigateOptions()
                        .setWaitUntil(WaitUntilState.NETWORKIDLE).setTimeout(30000));
                    page.waitForTimeout(WAIT_MS);

                    String content = "";
                    for (String sel : new String[]{".board-view-content", ".view-content",
                            ".content-view", ".board-content", ".view-body", ".content"}) {
                        Locator el = page.locator(sel);
                        if (el.count() > 0) {
                            String c = el.first().innerText().trim();
                            if (!c.isEmpty()) { content = c; break; }
                        }
                    }
                    notice.put("content", content);
                    detailedNotices.add(notice);
                } catch (Exception e) {
                    log.warn("본문 수집 실패: {} - {}", notice.get("title"), e.getMessage());
                }
            }

            // === 3단계: Gemini LLM 필터 (유효성 판단) ===
            Set<Integer> validIndices = filterWithGemini(detailedNotices);
            log.info("Gemini 필터: {}개 중 {}개 유효", detailedNotices.size(), validIndices.size());

            // === 4단계: 유효한 공지만 PDF 변환 + 저장 ===
            for (int i = 0; i < detailedNotices.size(); i++) {
                Map<String, String> notice = detailedNotices.get(i);
                if (!validIndices.contains(i)) {
                    skipped++;
                    log.info("LLM 필터 제외: {}", notice.get("title"));
                    continue;
                }
                try {
                    // 상세 페이지로 다시 이동해서 첨부파일 등 처리
                    Map<String, Object> result = processNotice(
                        page, context, notice);
                    totalChunks += (int) result.get("chunks_saved");
                    success++;
                    crawledList.add(Map.of(
                        "title", result.get("title"),
                        "date", notice.get("date"),
                        "chunks", result.get("chunks_saved"),
                        "attachments_merged", result.get("attachments_merged")
                    ));
                } catch (Exception e) {
                    log.error("크롤링 실패: {} - {}", notice.get("title"), e.getMessage());
                    fail++;
                    errors.add(notice.get("title") + ": " + e.getMessage());
                }
            }

            browser.close();
        } catch (Exception e) {
            log.error("Playwright 초기화 실패: {}", e.getMessage(), e);
            errors.add("Playwright 초기화 실패: " + e.getMessage());
        }

        Map<String, Object> result = new HashMap<>();
        result.put("success", success);
        result.put("fail", fail);
        result.put("skipped", skipped);
        result.put("total_chunks", totalChunks);
        result.put("notices", crawledList);
        if (!errors.isEmpty()) {
            result.put("errors", errors.subList(0, Math.min(errors.size(), 10)));
        }
        return result;
    }

    /**
     * Gemini로 공지 유효성 판단
     * 본문 내용을 보고 아직 유효한 공지인지 판단
     */
    private Set<Integer> filterWithGemini(List<Map<String, String>> notices) {
        Set<Integer> valid = new HashSet<>();
        if (notices.isEmpty()) return valid;

        String today = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyy년 M월 d일"));

        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < notices.size(); i++) {
            Map<String, String> n = notices.get(i);
            String contentPreview = n.getOrDefault("content", "");
            if (contentPreview.length() > 300) {
                contentPreview = contentPreview.substring(0, 300) + "...";
            }
            sb.append(String.format("%d. [%s] %s\n본문: %s\n\n",
                i + 1, n.get("date"), n.get("title"), contentPreview));
        }

        String prompt = String.format("""
오늘 날짜: %s

아래는 대학교 소프트웨어융합대학 공지사항 목록이야.
각 공지의 제목과 본문을 보고, RAG 지식베이스(학생 질의응답 시스템)에 저장할 가치가 있는지 판단해줘.

[저장 O] 기준:
- 학사 규정, 졸업 요건, 수강신청, 장학금, 출석인정 등 학생에게 유용한 정보
- 신청/마감일이 오늘 기준 아직 유효한 안내
- 제도 변경, 인증 요건 등 지속적으로 참조될 정보
- 노트북 대여, 멘토링 등 학생 지원 관련 안내

[저장 X] 기준:
- 신청 마감일이 이미 지난 공지 (오늘 이전에 마감)
- 이미 종료된 행사나 프로그램
- 본문이 비어있거나 의미 없는 공지

결과를 아래 형식으로만 답해 (다른 말 없이):
1:O
2:X
3:O
...

공지 목록:
%s""", today, sb.toString());

        try {
            String response = geminiService.generate(prompt);
            log.info("Gemini 필터 응답: {}", response.trim());

            for (String line : response.trim().split("\n")) {
                line = line.trim();
                if (line.contains(":")) {
                    String[] parts = line.split(":", 2);
                    try {
                        int idx = Integer.parseInt(parts[0].trim()) - 1;
                        boolean keep = parts[1].trim().toUpperCase().startsWith("O");
                        if (keep && idx >= 0 && idx < notices.size()) {
                            valid.add(idx);
                        }
                    } catch (NumberFormatException ignored) {}
                }
            }
        } catch (Exception e) {
            log.warn("Gemini 필터 실패, 전체 포함: {}", e.getMessage());
            // 실패 시 전체 포함
            for (int i = 0; i < notices.size(); i++) valid.add(i);
        }

        return valid;
    }

    /**
     * 유효한 공지 1개: 상세 페이지 재방문 -> 첨부파일 처리 -> PDF 변환 -> RDB 저장
     */
    private Map<String, Object> processNotice(Page page, BrowserContext context,
            Map<String, String> notice) throws Exception {

        String noticeUrl = notice.get("url");
        String date = notice.get("date");
        String author = notice.get("author");
        String content = notice.getOrDefault("content", "");

        page.navigate(noticeUrl, new Page.NavigateOptions()
            .setWaitUntil(WaitUntilState.NETWORKIDLE).setTimeout(30000));
        page.waitForTimeout(WAIT_MS);

        // 제목 추출
        String title = notice.get("title");
        for (String sel : new String[]{".board-view-title", ".view-title", "h2"}) {
            Locator el = page.locator(sel);
            if (el.count() > 0) {
                String t = el.first().innerText().trim();
                if (!t.isEmpty()) { title = t; break; }
            }
        }

        // 첨부파일 링크 추출
        List<Map<String, String>> attachments = new ArrayList<>();
        Locator attachLinks = page.locator(
            ".board-view-file a, .view-file a, .file-list a, .attach a, a[href*='download'], a[href*='/file/']");
        for (int i = 0; i < attachLinks.count(); i++) {
            String href = attachLinks.nth(i).getAttribute("href");
            String name = attachLinks.nth(i).innerText().trim();
            if (href != null && !href.isEmpty() && !name.isEmpty()) {
                String fullUrl = href.startsWith("http") ? href : "https://cs.kookmin.ac.kr" + href;
                attachments.add(Map.of("name", name, "url", fullUrl));
            }
        }
        if (attachments.isEmpty()) {
            Locator allLinks = page.locator("a[href]");
            for (int i = 0; i < allLinks.count(); i++) {
                String href = allLinks.nth(i).getAttribute("href");
                if (href == null) continue;
                if (href.toLowerCase().matches(".*\\.(pdf|hwp|hwpx|docx|doc|xlsx|xls|zip|pptx|ppt).*")) {
                    String name = allLinks.nth(i).innerText().trim();
                    if (name.isEmpty()) name = href.substring(href.lastIndexOf('/') + 1);
                    String fullUrl = href.startsWith("http") ? href : "https://cs.kookmin.ac.kr" + href;
                    attachments.add(Map.of("name", name, "url", fullUrl));
                }
            }
        }

        log.info("공지 처리: {} / 본문 {}자 / 첨부 {}개", title, content.length(), attachments.size());

        // 1. 본문 PDF 생성
        File bodyPdf = createNoticePdf(title, date, author, noticeUrl, content);

        // 2. 첨부 PDF 다운로드
        List<File> pdfAttachments = new ArrayList<>();
        for (Map<String, String> attach : attachments) {
            String name = attach.get("name").toLowerCase();
            if (name.endsWith(".pdf") || attach.get("url").toLowerCase().contains(".pdf")) {
                try {
                    APIResponse resp = context.request().get(attach.get("url"));
                    if (resp.ok()) {
                        File tempFile = File.createTempFile("attach_", ".pdf");
                        Files.write(tempFile.toPath(), resp.body());
                        pdfAttachments.add(tempFile);
                        log.info("첨부 다운로드: {}", attach.get("name"));
                    }
                } catch (Exception e) {
                    log.warn("첨부 다운로드 실패: {} - {}", attach.get("name"), e.getMessage());
                }
            }
        }

        // 3. PDF 병합
        File finalPdf;
        if (!pdfAttachments.isEmpty()) {
            finalPdf = mergePdfs(bodyPdf, pdfAttachments);
            bodyPdf.delete();
            pdfAttachments.forEach(File::delete);
        } else {
            finalPdf = bodyPdf;
        }

        // 4. 최종 PDF 저장
        Path outputDir = Paths.get(NOTICE_PDF_DIR);
        Files.createDirectories(outputDir);
        String safeName = title.replaceAll("[\\\\/*?:\"<>|]", "_").trim();
        if (safeName.length() > 80) safeName = safeName.substring(0, 80);
        Path outputPath = outputDir.resolve(safeName + ".pdf");
        Files.copy(finalPdf.toPath(), outputPath, StandardCopyOption.REPLACE_EXISTING);
        finalPdf.delete();

        // 5. 텍스트 청킹 -> RDB 저장
        int savedChunks = 0;
        if (!content.isEmpty()) {
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("doc_name", "[공지] " + safeName + ".pdf");
            metadata.put("source", noticeUrl);
            metadata.put("category", "공지사항");
            metadata.put("page", 1);

            List<Map<String, Object>> chunks = chunkerService.chunk(content, metadata);
            for (Map<String, Object> chunk : chunks) {
                DocumentChunk entity = DocumentChunk.builder()
                    .id(UUID.randomUUID().toString())
                    .docName("[공지] " + safeName + ".pdf")
                    .content((String) chunk.get("content"))
                    .page(1)
                    .sourceUrl(noticeUrl)
                    .build();
                chunkRepo.save(entity);
                savedChunks++;
            }
        }

        return Map.of(
            "title", title,
            "pdf_path", outputPath.toString(),
            "chunks_saved", savedChunks,
            "attachments_merged", pdfAttachments.size(),
            "attachments_total", attachments.size()
        );
    }

    // === 공지 목록 추출 ===

    private List<Map<String, String>> extractNoticeList(Page page) {
        List<Map<String, String>> notices = new ArrayList<>();
        try {
            Locator rows = page.locator(".list-tbody ul");
            int count = rows.count();
            for (int i = 0; i < count; i++) {
                Locator row = rows.nth(i);
                Locator subjectLink = row.locator("li.subject a");
                if (subjectLink.count() == 0) continue;

                String href = subjectLink.getAttribute("href");
                String title = subjectLink.innerText().trim();
                if (href == null || title.isEmpty()) continue;

                String fullUrl = "https://cs.kookmin.ac.kr/news/notice/" + href.replace("./", "");

                boolean pinned = false;
                Locator noticeLabel = row.locator("li.notice");
                if (noticeLabel.count() > 0) {
                    String t = noticeLabel.innerText().trim();
                    if (t.contains("Notice") || t.contains("공지")) pinned = true;
                }
                Locator numberEl = row.locator("li.number");
                if (numberEl.count() > 0) {
                    String t = numberEl.innerText().trim();
                    if (t.contains("Notice") || t.contains("공지")) pinned = true;
                }

                String date = "";
                Locator dateEl = row.locator("li.date");
                if (dateEl.count() > 0) date = dateEl.innerText().trim();

                Locator lis = row.locator("li");
                String author = lis.count() >= 4 ? lis.nth(2).innerText().trim() : "";

                Map<String, String> notice = new HashMap<>();
                notice.put("title", title);
                notice.put("url", fullUrl);
                notice.put("date", date);
                notice.put("author", author);
                notice.put("pinned", pinned ? "true" : "false");
                notices.add(notice);
            }
        } catch (Exception e) {
            log.error("목록 추출 실패: {}", e.getMessage());
        }
        return notices;
    }

    // === PDF 생성 ===

    private File createNoticePdf(String title, String date, String author,
                                  String url, String content) throws IOException {
        File tempFile = File.createTempFile("notice_", ".pdf");
        try (PDDocument document = new PDDocument()) {
            InputStream fontStream = findKoreanFont();
            PDType0Font font = PDType0Font.load(document, fontStream);
            float margin = 40, pageWidth = PDRectangle.A4.getWidth() - 2 * margin;
            float yStart = PDRectangle.A4.getHeight() - margin, fontSize = 10, leading = fontSize * 1.5f;

            PDPage pdfPage = new PDPage(PDRectangle.A4);
            document.addPage(pdfPage);
            PDPageContentStream cs = new PDPageContentStream(document, pdfPage);
            float y = yStart;

            cs.beginText(); cs.setFont(font, 14); cs.newLineAtOffset(margin, y);
            cs.showText(truncate(title, 60)); cs.endText(); y -= 25;

            cs.setFont(font, 8);
            for (String meta : new String[]{"날짜: " + date, "작성자: " + author, "URL: " + truncate(url, 80)}) {
                cs.beginText(); cs.newLineAtOffset(margin, y); cs.showText(meta); cs.endText(); y -= 12;
            }
            y -= 10;
            cs.moveTo(margin, y); cs.lineTo(PDRectangle.A4.getWidth() - margin, y); cs.stroke(); y -= 15;

            cs.setFont(font, fontSize);
            for (String line : wrapText(content, font, fontSize, pageWidth)) {
                if (y < margin + 20) {
                    cs.close(); pdfPage = new PDPage(PDRectangle.A4); document.addPage(pdfPage);
                    cs = new PDPageContentStream(document, pdfPage); cs.setFont(font, fontSize); y = yStart;
                }
                cs.beginText(); cs.newLineAtOffset(margin, y); cs.showText(line); cs.endText(); y -= leading;
            }
            cs.close(); document.save(tempFile);
        }
        return tempFile;
    }

    private File mergePdfs(File mainPdf, List<File> attachmentPdfs) throws IOException {
        File mergedFile = File.createTempFile("merged_", ".pdf");
        try (PDDocument merged = Loader.loadPDF(mainPdf)) {
            for (File f : attachmentPdfs) {
                try (PDDocument doc = Loader.loadPDF(f)) {
                    for (PDPage p : doc.getPages()) merged.addPage(merged.importPage(p));
                } catch (Exception e) { log.warn("첨부 병합 실패: {}", e.getMessage()); }
            }
            merged.save(mergedFile);
        }
        return mergedFile;
    }

    // === 유틸리티 ===

    private LocalDate parseDate(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) return null;
        try {
            String[] parts = dateStr.trim().split("\\.");
            if (parts.length == 3) {
                int y = Integer.parseInt(parts[0].trim());
                if (y < 100) y += 2000;
                return LocalDate.of(y, Integer.parseInt(parts[1].trim()), Integer.parseInt(parts[2].trim()));
            }
            return LocalDate.parse(dateStr.trim().replace(".", "-"));
        } catch (Exception e) { return null; }
    }

    private InputStream findKoreanFont() throws IOException {
        InputStream is = getClass().getResourceAsStream("/fonts/NanumGothic.ttf");
        if (is != null) return is;
        for (String p : new String[]{"/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                "/System/Library/Fonts/Supplemental/AppleGothic.ttf"}) {
            File f = new File(p);
            if (f.exists() && p.endsWith(".ttf")) return new FileInputStream(f);
        }
        throw new IOException("한글 폰트를 찾을 수 없습니다.");
    }

    private List<String> wrapText(String text, PDType0Font font, float fontSize, float maxWidth) throws IOException {
        List<String> lines = new ArrayList<>();
        if (text == null || text.isEmpty()) return lines;
        for (String para : text.split("\n")) {
            StringBuilder line = new StringBuilder();
            for (char c : para.toCharArray()) {
                try {
                    float w = font.getStringWidth(line.toString() + c) / 1000 * fontSize;
                    if (w > maxWidth) { lines.add(line.toString()); line = new StringBuilder(String.valueOf(c)); }
                    else line.append(c);
                } catch (Exception e) { line.append(' '); }
            }
            if (!line.isEmpty()) lines.add(line.toString());
        }
        return lines;
    }

    private String truncate(String s, int max) {
        return s != null && s.length() > max ? s.substring(0, max) + "..." : (s != null ? s : "");
    }
}
