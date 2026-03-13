# KDD (Kookmin Digital Doc) - Backend API

국민대학교 학칙·학사규정 RAG 기반 질의응답 시스템 백엔드

## 기술 스택

| 구분 | 기술 |
|------|------|
| Framework | Spring Boot 3.2 (Java 17) |
| DB | SQLite (JPA/Hibernate) |
| Vector DB | Qdrant Cloud |
| 임베딩 | Gemini embedding-001 (3072차원) |
| 생성 | Gemini 2.5 Flash |
| 리랭킹 | Cohere rerank-multilingual-v3.0 |
| 인증 | Google OAuth + JWT |
| 배포 | Docker Compose (EC2) |

## 검색 파이프라인

```
질문 → Gemini 임베딩 → Qdrant 벡터 검색 (top 20)
                                    ↓
                              Cohere Rerank (relevance ≥ 0.25)
                                    ↓
                              Gemini 답변 생성 + 출처 반환
```

## 실행 방법

```bash
cd backend
cp .env.example .env   # API 키 설정
docker-compose up --build
```

서버: `http://localhost:8000`

---

## API 명세서

### 1. 인증 (Auth)

#### `POST /auth/google`
Google OAuth 로그인

**Request Body:**
```json
{
  "credential": "Google ID Token (string)"
}
```

**Response 200:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "user": {
    "email": "user@kookmin.ac.kr",
    "name": "홍길동",
    "isDocAdmin": false
  }
}
```

**Response 401:**
```json
{ "detail": "Google 인증 실패" }
```

---

#### `GET /auth/me`
현재 로그인 사용자 정보 조회

**Headers:** `Authorization: Bearer {JWT}`

**Response 200:**
```json
{
  "user": {
    "email": "user@kookmin.ac.kr",
    "name": "홍길동",
    "isDocAdmin": false
  }
}
```

**Response 401:**
```json
{ "detail": "Unauthorized" }
```

---

### 2. 채팅 (Chat)

#### `POST /`
질문에 대한 RAG 기반 답변 생성

**Headers:** `Authorization: Bearer {JWT}`

**Request Body:**
```json
{
  "message": "졸업 요건이 뭐야?",
  "history": "(이전 대화 내용, 선택)"
}
```

**Response 200:**
```json
{
  "answer": "국민대학교 졸업 요건은...",
  "sources": [
    {
      "uri": "학칙.pdf",
      "page": 15,
      "section": "제8장: 졸업",
      "has_table": false,
      "source_url": "",
      "rerank_score": 0.85
    }
  ],
  "contextCount": 3
}
```

**Response 500:**
```json
{ "detail": "에러 메시지" }
```

---

### 3. 문서 관리 (Documents)

#### `POST /upload`
PDF 문서 업로드 및 인덱싱 (관리자 전용)

**Headers:** `Authorization: Bearer {JWT}` (관리자 권한 필요)

**Request:** `multipart/form-data`
| 필드 | 타입 | 설명 |
|------|------|------|
| file | File | PDF 파일 |

**Response 200:**
```json
{
  "message": "Successfully indexed 42 chunks",
  "filename": "학칙.pdf",
  "chunks": 42
}
```

---

#### `GET /documents`
업로드된 문서 목록 조회

**Response 200:**
```json
{
  "documents": [
    {
      "filename": "학칙.pdf",
      "size": 1048576,
      "type": ".pdf",
      "chunk_count": 42,
      "indexed": true
    }
  ]
}
```

---

#### `DELETE /documents/{filename}`
문서 삭제 (파일 + 인덱스 모두 삭제, 관리자 전용)

**Headers:** `Authorization: Bearer {JWT}` (관리자 권한 필요)

**Response 200:**
```json
{
  "message": "학칙.pdf 삭제 완료",
  "deleted_chunks": 42
}
```

---

#### `GET /documents/{filename}/preview`
문서 파일 미리보기/다운로드

**Response 200:** 파일 바이너리 (application/octet-stream)

**Response 404:** 파일 없음

---

### 4. 공지사항 (Notices)

#### `GET /crawl/notices/list`
인덱싱된 공지사항 문서 목록

**Response 200:**
```json
{
  "notices": [
    {
      "doc_name": "[공지] 2025학년도 1학기 수강신청 안내",
      "chunk_count": 5,
      "source_url": ""
    }
  ]
}
```

---

### 5. FAQ

#### `GET /faq`
자주 묻는 질문 (최근 30일, Gemini 그룹핑)

**Response 200:**
```json
{
  "faqs": [
    {
      "question": "졸업 요건이 어떻게 되나요?",
      "category": "졸업",
      "answer": "국민대학교 졸업 요건은...",
      "sources": [
        { "uri": "학칙.pdf", "page": 15 }
      ],
      "count": 12
    }
  ]
}
```

---

### 6. 이용통계 (Stats)

#### `GET /stats`
시스템 이용통계 데이터

**Response 200:**
```json
{
  "total_questions": 150,
  "today_questions": 8,
  "daily_7d": [
    { "date": "2025-06-01", "count": 5 }
  ],
  "hourly": [
    { "hour": 0, "count": 2 },
    { "hour": 1, "count": 0 }
  ],
  "total_docs": 25,
  "total_chunks": 1200,
  "docs_top10": [
    { "doc_name": "학칙.pdf", "count": 45 }
  ]
}
```

---

### 7. 사용자 프로필 (Profile)

#### `GET /profile`
사용자 프로필 조회

**Headers:** `Authorization: Bearer {JWT}`

**Response 200:**
```json
{
  "profile": {
    "email": "user@kookmin.ac.kr",
    "name": "홍길동",
    "student_id": "20210001",
    "department": "소프트웨어학부",
    "grade": "3"
  }
}
```

---

#### `POST /profile`
사용자 프로필 저장

**Headers:** `Authorization: Bearer {JWT}`

**Request Body:**
```json
{
  "name": "홍길동",
  "studentId": "20210001",
  "department": "소프트웨어학부",
  "grade": "3"
}
```

**Response 200:**
```json
{ "message": "프로필 저장 완료" }
```

**Response 401:**
```json
{ "detail": "Unauthorized" }
```

---

### 8. 인덱스 관리

#### `POST /reset`
전체 인덱스 초기화 (관리자 전용)

**Headers:** `Authorization: Bearer {JWT}` (관리자 권한 필요)

**Response 200:**
```json
{ "message": "Index reset successfully" }
```

---

### 9. 헬스체크

#### `GET /health`

**Response 200:**
```json
{ "status": "ok" }
```

---

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API 키 | (필수) |
| `COHERE_API_KEY` | Cohere Rerank API 키 | (필수) |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | (필수) |
| `JWT_SECRET` | JWT 서명 시크릿 | (필수) |
| `QDRANT_URL` | Qdrant 서버 URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API 키 | (빈 값) |
| `ALLOWED_DOMAIN` | 허용 이메일 도메인 | `kookmin.ac.kr` |
| `DOC_ADMIN_EMAILS` | 관리자 이메일 (쉼표 구분) | (빈 값) |
| `UPLOAD_DIR` | 업로드 디렉토리 경로 | `uploads` |
| `CHUNK_SIZE` | 청크 크기 (문자 수) | `550` |
| `CHUNK_OVERLAP` | 청크 오버랩 (문자 수) | `100` |
| `BM25_TOP_K` | BM25 검색 상위 K | `20` |
| `VECTOR_TOP_K` | 벡터 검색 상위 K | `20` |
| `FINAL_CONTEXT_SIZE` | 최종 컨텍스트 수 | `5` |
| `RELEVANCE_THRESHOLD` | Rerank 관련성 임계값 | `0.25` |

## 프로젝트 구조

```
backend/
├── build.gradle
├── settings.gradle
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── src/main/java/com/kdd/
    ├── KddApplication.java          # 메인 클래스
    ├── config/
    │   ├── AppConfig.java            # 환경변수 바인딩
    │   ├── SecurityConfig.java       # Spring Security 설정
    │   └── WebConfig.java            # CORS 설정
    ├── controller/
    │   ├── AuthController.java       # 인증 API
    │   ├── ChatController.java       # 채팅 API
    │   ├── DocumentController.java   # 문서 관리 API
    │   ├── FaqController.java        # FAQ API
    │   ├── StatsController.java      # 통계 API
    │   └── ProfileController.java    # 프로필 API
    ├── dto/
    │   ├── AuthRequest.java
    │   ├── AuthResponse.java
    │   ├── ChatRequest.java
    │   ├── ChatResponse.java
    │   └── ProfileRequest.java
    ├── entity/
    │   ├── ChatLog.java
    │   ├── UserProfile.java
    │   └── DocumentChunk.java
    ├── repository/
    │   ├── ChatLogRepository.java
    │   ├── DocumentChunkRepository.java
    │   └── UserProfileRepository.java
    ├── security/
    │   ├── GoogleAuthService.java    # Google OAuth 검증
    │   └── JwtService.java           # JWT 생성/검증
    └── service/
        ├── AnswerService.java        # 답변 생성 (Gemini)
        ├── ChunkerService.java       # 텍스트 청킹
        ├── CohereRerankService.java  # Cohere 리랭킹
        ├── EmbeddingService.java     # Gemini 임베딩
        ├── GeminiService.java        # Gemini API 호출
        ├── PdfParserService.java     # PDF 파싱
        ├── QdrantService.java        # Qdrant 벡터 DB
        └── SearchService.java        # 하이브리드 검색
```
