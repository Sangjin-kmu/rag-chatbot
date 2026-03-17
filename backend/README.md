# KDD Backend API (Spring Boot)

> 국민대학교 학칙·학사규정 RAG(Retrieval-Augmented Generation) 기반 질의응답 시스템의 백엔드 서버
>
> 📦 **Backend Repository**: [kdd-api (SangJin 브랜치)](https://github.com/KDD-Kookmin-Digital-Doc/kdd-api/tree/SangJin)

---

## 목차

1. [시스템 개요](#시스템-개요)
2. [기술 스택 상세](#기술-스택-상세)
3. [아키텍처](#아키텍처)
4. [프로젝트 구조](#프로젝트-구조)
5. [로컬 개발 환경 설정 (IntelliJ)](#로컬-개발-환경-설정-intellij)
6. [Docker 실행](#docker-실행)
7. [환경변수](#환경변수)
8. [API 명세서](#api-명세서)
9. [프론트엔드/AI 연동 가이드](#프론트엔드ai-연동-가이드)
10. [핵심 기능 상세](#핵심-기능-상세)

---

## 시스템 개요

KDD(Kookmin Digital Doc)는 국민대학교의 학칙, 학사규정, 공지사항 등의 문서를
RAG 파이프라인으로 검색·분석하여 자연어 질의에 정확한 답변을 제공하는 시스템입니다.

### 주요 기능
- **RAG 기반 질의응답**: 벡터 검색 + Cohere Rerank + Gemini 생성
- **문서 관리**: PDF 업로드 → 자동 파싱 → 청킹 → 임베딩 → 인덱싱
- **Google OAuth 인증**: JWT 기반 사용자 인증 및 관리자 권한 분리
- **FAQ 자동 생성**: 최근 30일 질문을 Gemini로 그룹핑하여 FAQ 카드 생성
- **이용통계 대시보드**: 일별/시간대별 질문 수, TOP 10 참조 문서
- **사용자 프로필**: 학과/학년 정보로 개인화된 답변 제공
- **공지사항 자동 크롤링**: Playwright Java로 소융대 공지 크롤링 → Gemini LLM 유효성 판단 → PDF 변환 → 청킹 → RDB 저장

---

## 기술 스택 상세

| 분류 | 기술 | 버전 | 용도 |
|------|------|------|------|
| **Framework** | Spring Boot | 3.4.3 | 웹 애플리케이션 프레임워크 |
| **Language** | Java | 17 (LTS) | 메인 언어 |
| **Build** | Gradle | 8.5 | 빌드 도구 |
| **ORM** | Spring Data JPA + Hibernate | 6.4 | SQLite 데이터 접근 |
| **DB** | SQLite | 3.45 | 채팅 로그, 사용자 프로필, 문서 청크 메타데이터 |
| **Vector DB** | Qdrant | Cloud | 3072차원 벡터 저장 및 유사도 검색 |
| **임베딩** | Gemini embedding-001 | v1 | 텍스트 → 3072차원 벡터 변환 |
| **생성 AI** | Gemini 2.5 Flash | v1 | RAG 답변 생성, FAQ 그룹핑 |
| **리랭킹** | Cohere rerank-multilingual-v3.0 | v1 | 검색 결과 관련성 재정렬 |
| **인증** | Google OAuth 2.0 + JWT (jjwt) | 0.12.5 | 사용자 인증 |
| **보안** | Spring Security | 6.x | CSRF 비활성화, Stateless 세션 |
| **HTTP Client** | Spring WebFlux (WebClient) | 6.x | 외부 API 비동기 호출 (Gemini, Cohere, Qdrant) |
| **PDF 파싱** | Apache PDFBox | 3.0.1 | PDF → 텍스트 추출, 공지 본문 PDF 변환 |
| **크롤링** | Playwright Java | 1.49.0 | 헤드리스 Chromium 기반 SPA 크롤링 |
| **CORS** | Spring WebMvcConfigurer | - | 프론트엔드 크로스 오리진 허용 |
| **컨테이너** | Docker + Docker Compose | - | 배포 및 로컬 실행 |

### Spring Boot 핵심 기술 활용

- **`@ConfigurationProperties`**: `application.yml`의 `app.*` 설정을 `AppConfig` 클래스에 타입 안전하게 바인딩
- **Spring Data JPA**: `JpaRepository` 인터페이스로 SQLite CRUD + 커스텀 JPQL 쿼리 (`@Query`)
- **Spring Security**: `SecurityFilterChain` 빈으로 CSRF 비활성화, Stateless 세션, 전체 경로 허용 설정
- **WebClient (WebFlux)**: Gemini API, Cohere API, Qdrant REST API 호출에 논블로킹 HTTP 클라이언트 사용
- **`@PostConstruct`**: `QdrantService`에서 애플리케이션 시작 시 Qdrant 컬렉션 자동 초기화
- **`@Transactional`**: `SearchService`의 인덱싱/삭제 작업에서 SQLite + Qdrant 일관성 보장
- **`@EnableScheduling`**: 스케줄링 기능 활성화 (공지사항 자동 크롤링 확장 가능)
- **Multipart File Upload**: `MultipartFile`로 최대 500MB PDF 업로드 처리
- **Playwright Java**: Headless Chromium 기반 SPA 크롤링 (JavaScript 렌더링 필요한 공지사항 사이트)
- **Lombok**: `@Data`, `@Builder`, `@RequiredArgsConstructor` 등으로 보일러플레이트 코드 제거

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                    │
│                   index.html + config.js                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP REST API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Spring Boot Application                   │
│                      (port 8000)                            │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  Controller  │  │   Security   │  │     Config       │   │
│  │  (6개 API)   │→│ GoogleAuth   │  │ AppConfig          │   │
│  │             │  │ JwtService   │  │ SecurityConfig    │   │
│  │             │  │              │  │ WebConfig (CORS)  │   │
│  └──────┬──────┘  └──────────────┘  └───────────────────┘   │
│         │                                                   │
│  ┌──────▼──────────────────────────────────────────────┐    │
│  │                    Service Layer                    │    │
│  │                                                     │    │
│  │  SearchService ─→ EmbeddingService (Gemini 임베딩)    │    │
│  │       │         → QdrantService (벡터 검색)           │     │
│  │       │         → CohereRerankService (리랭킹)       │      │
│  │       ▼                                             │     │
│  │  AnswerService ─→ GeminiService (답변 생성)           │     │
│  │                                                     │     │
│  │  NoticeCrawlerService ─→ Playwright (Chromium)      │     │
│  │       │                → GeminiService (유효성 판단)   │     │
│  │       │                → PDFBox (PDF 생성/병합)       │      │
│  │       ▼                → ChunkerService (청킹)       │      │
│  │                                                     │     │
│  │  PdfParserService (PDF → 텍스트)                     │      │
│  │  ChunkerService (텍스트 → 청크 분할)                    │     │
│  └──────┬─────────────────────────────────────────────┘      │
│         │                                                    │
│  ┌──────▼──────────────────────────────────────────────┐     │
│  │              Repository Layer (JPA)                 │     │
│  │  ChatLogRepository │ DocumentChunkRepository        │     │
│  │  UserProfileRepository                              │     │
│  └──────┬──────────────────────────────────────────────┘     │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
    ┌─────▼─────┐     ┌──────────────┐
    │  SQLite   │     │   Qdrant     │
    │  (fts.db) │     │ (Vector DB)  │
    │           │     │  3072차원     │
    │ chat_logs │     │  Cosine      │
    │ user_prof │     │              │
    │ doc_chunks│     │              │
    └───────────┘     └──────────────┘
```

### 검색 파이프라인 (RAG)

```
사용자 질문
    │
    ▼
① Gemini embedding-001로 질문 벡터화 (3072차원)
    │
    ▼
② Qdrant 벡터 검색 (Cosine 유사도, top 20개)
    │
    ▼
③ Cohere rerank-multilingual-v3.0으로 리랭킹
    │
    ▼
④ relevance_score ≥ 0.25 필터링 → 상위 5개 선택
    │
    ▼
⑤ 선택된 문서 청크 + 질문 → Gemini 2.5 Flash로 답변 생성
    │
    ▼
⑥ 답변 + 출처(문서명, 페이지, 섹션) 반환
```

---

## 프로젝트 구조

```
backend/
├── build.gradle                          # Gradle 빌드 설정 (의존성 관리)
├── settings.gradle                       # 프로젝트 이름 설정
├── Dockerfile                            # 멀티스테이지 Docker 빌드
├── docker-compose.yml                    # Qdrant + App 컨테이너 구성
├── .env.example                          # 환경변수 템플릿
├── crawled_notices/                      # 크롤링된 공지 PDF 저장 디렉토리
│   └── pdf/                              # 공지별 PDF 파일
└── src/main/
    ├── java/com/kdd/
    │   ├── KddApplication.java           # @SpringBootApplication 메인 클래스
    │   │
    │   ├── config/
    │   │   ├── AppConfig.java            # @ConfigurationProperties - 환경변수 바인딩
    │   │   ├── SecurityConfig.java       # Spring Security 설정 (CSRF off, Stateless)
    │   │   └── WebConfig.java            # CORS 전역 설정 (모든 Origin 허용)
    │   │
    │   ├── controller/                   # REST API 엔드포인트
    │   │   ├── AuthController.java       # POST /auth/google, GET /auth/me
    │   │   ├── ChatController.java       # POST / (RAG 질의응답)
    │   │   ├── DocumentController.java   # 문서 업로드/삭제/목록/미리보기/인덱스 초기화
    │   │   ├── FaqController.java        # GET /faq (Gemini 그룹핑 FAQ)
    │   │   ├── StatsController.java      # GET /stats, GET /health
    │   │   └── ProfileController.java    # GET/POST /profile
    │   │
    │   ├── dto/                          # 요청/응답 DTO
    │   │   ├── AuthRequest.java          # { credential }
    │   │   ├── AuthResponse.java         # { token, user }
    │   │   ├── ChatRequest.java          # { message, history }
    │   │   ├── ChatResponse.java         # { answer, sources, contextCount }
    │   │   └── ProfileRequest.java       # { name, studentId, department, grade }
    │   │
    │   ├── entity/                       # JPA 엔티티 (SQLite 테이블)
    │   │   ├── ChatLog.java              # chat_logs 테이블
    │   │   ├── UserProfile.java          # user_profiles 테이블
    │   │   └── DocumentChunk.java        # document_chunks 테이블
    │   │
    │   ├── repository/                   # Spring Data JPA Repository
    │   │   ├── ChatLogRepository.java    # 채팅 로그 CRUD + 통계 쿼리
    │   │   ├── DocumentChunkRepository.java  # 문서 청크 CRUD + 집계 쿼리
    │   │   └── UserProfileRepository.java    # 사용자 프로필 CRUD
    │   │
    │   ├── security/                     # 인증/보안
    │   │   ├── GoogleAuthService.java    # Google ID Token 검증
    │   │   └── JwtService.java           # JWT 생성/파싱/이메일 추출
    │   │
    │   └── service/                      # 비즈니스 로직
    │       ├── SearchService.java        # 하이브리드 검색 (벡터 + Rerank)
    │       ├── AnswerService.java        # RAG 답변 생성 (프롬프트 구성)
    │       ├── EmbeddingService.java     # Gemini embedding-001 API 호출
    │       ├── GeminiService.java        # Gemini 2.5 Flash 텍스트 생성
    │       ├── QdrantService.java        # Qdrant REST API (upsert/search/delete)
    │       ├── CohereRerankService.java  # Cohere Rerank API 호출
    │       ├── PdfParserService.java     # PDFBox로 PDF → 페이지별 텍스트
    │       ├── ChunkerService.java       # 텍스트 → 고정 크기 청크 분할
    │       └── NoticeCrawlerService.java # 소융대 공지 크롤링 (Playwright + Gemini 필터)
    │
    └── resources/
        ├── application.yml               # Spring Boot 설정 파일
        ├── fonts/
        │   └── NanumGothic.ttf           # 한글 폰트 (PDF 생성용)
        └── static/
            └── api_test.html             # API 테스트 페이지
```

---

## 로컬 개발 환경 설정 (IntelliJ)

### 사전 요구사항

- **Java 17** (JDK 17 이상)
- **IntelliJ IDEA** (Community 또는 Ultimate)
- **Docker** (Qdrant 실행용)

### Step 1: 프로젝트 열기

1. IntelliJ IDEA 실행
2. `File` → `Open` → `backend/` 폴더 선택
3. Gradle 프로젝트로 자동 인식됨 → Import 진행
4. Gradle sync가 완료될 때까지 대기 (의존성 다운로드)

### Step 2: JDK 설정

1. `File` → `Project Structure` → `Project`
2. SDK: **17** 선택 (없으면 `Add SDK` → `Download JDK` → **temurin-17**)
3. Language level: **17** 선택

### Step 3: Lombok 플러그인 확인

1. `Settings` → `Plugins` → "Lombok" 검색 → 설치 확인
2. `Settings` → `Build, Execution, Deployment` → `Compiler` → `Annotation Processors`
3. **"Enable annotation processing"** 체크 ✅

### Step 4: 환경변수 설정

```bash
cd backend
cp .env.example .env
```

`.env` 파일을 열어 실제 API 키 입력:

```env
GEMINI_API_KEY=실제_Gemini_API_키
COHERE_API_KEY=실제_Cohere_API_키
GOOGLE_CLIENT_ID=879695241528-9t7rcohthseucdfsg5u259gbnl17340i.apps.googleusercontent.com
QDRANT_URL=http://localhost:6333
JWT_SECRET=아무_랜덤_문자열_32자_이상
DOC_ADMIN_EMAILS=본인이메일@kookmin.ac.kr
```

### Step 5: Qdrant 실행

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant:latest
```

또는 docker-compose로:

```bash
cd backend
docker-compose up -d qdrant
```

### Step 6: Playwright Chromium 설치

공지사항 크롤링 기능에 Playwright Java가 필요합니다. 최초 1회 Chromium 브라우저를 설치해야 합니다:

```bash
# Gradle 의존성 설치 후 Playwright CLI로 Chromium 설치
cd backend
./gradlew dependencies  # 의존성 다운로드
npx playwright install chromium
# 또는 Maven 경로에서 직접 실행
java -cp "$(find ~/.gradle -name 'playwright-*.jar' | head -1)" com.microsoft.playwright.CLI install chromium
```

설치된 Chromium 경로: `~/Library/Caches/ms-playwright/chromium-*` (macOS 기준)

### Step 7: IntelliJ Run Configuration 설정

1. 우측 상단 `Edit Configurations...` 클릭
2. `+` → `Spring Boot` 선택
3. 설정:
   - **Name**: `KddApplication`
   - **Main class**: `com.kdd.KddApplication`
   - **Environment variables**: `.env` 파일의 내용을 복사하거나, `EnvFile` 플러그인 사용
     - 직접 입력 예시: `GEMINI_API_KEY=xxx;COHERE_API_KEY=xxx;GOOGLE_CLIENT_ID=xxx;JWT_SECRET=xxx;QDRANT_URL=http://localhost:6333`
   - 또는 **EnvFile 플러그인** 설치 후 `.env` 파일 경로 지정
4. `Apply` → `OK`

### Step 8: 실행 및 테스트

1. `KddApplication.java` 파일 열기
2. `main` 메서드 옆 ▶️ 버튼 클릭 또는 `Shift + F10`
3. 콘솔에 `Started KddApplication in X seconds` 출력 확인
4. 브라우저에서 `http://localhost:8000/health` 접속 → `{"status":"ok"}` 확인

### API 테스트 (IntelliJ HTTP Client)

IntelliJ Ultimate에서는 `.http` 파일로 바로 테스트 가능:

```http
### 헬스체크
GET http://localhost:8000/health

### 문서 목록 조회
GET http://localhost:8000/documents

### 통계 조회
GET http://localhost:8000/stats

### FAQ 조회
GET http://localhost:8000/faq

### 채팅 (JWT 토큰 필요)
POST http://localhost:8000/
Content-Type: application/json
Authorization: Bearer {{jwt_token}}

{
  "message": "졸업 요건이 뭐야?",
  "history": ""
}

### PDF 업로드 (관리자 JWT 필요)
POST http://localhost:8000/upload
Authorization: Bearer {{admin_jwt_token}}
Content-Type: multipart/form-data; boundary=boundary

--boundary
Content-Disposition: form-data; name="file"; filename="학칙.pdf"
Content-Type: application/pdf

< ./uploads/학칙.pdf
--boundary--
```

### cURL로 테스트

```bash
# 헬스체크
curl http://localhost:8000/health

# 문서 목록
curl http://localhost:8000/documents

# 통계
curl http://localhost:8000/stats

# 채팅 (토큰 필요)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"message": "졸업 요건이 뭐야?", "history": ""}'
```

---

## Docker 실행

### docker-compose로 전체 실행

```bash
cd backend
cp .env.example .env   # API 키 설정
docker-compose up --build
```

이 명령으로 Qdrant + Spring Boot 앱이 함께 실행됩니다.

- Spring Boot 앱: `http://localhost:8000`
- Qdrant 대시보드: `http://localhost:6333/dashboard`

### Dockerfile 구조 (멀티스테이지 빌드)

```dockerfile
# 1단계: Gradle로 빌드
FROM gradle:8.5-jdk17 AS build
WORKDIR /app
COPY build.gradle settings.gradle ./
COPY src ./src
RUN gradle bootJar --no-daemon

# 2단계: 경량 JRE로 실행
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
RUN mkdir -p uploads data
EXPOSE 8000
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 환경변수

| 변수 | 설명 | 기본값 | 필수 |
|------|------|--------|------|
| `GEMINI_API_KEY` | Google Gemini API 키 ([AI Studio](https://aistudio.google.com/)에서 발급) | - | ✅ |
| `COHERE_API_KEY` | Cohere Rerank API 키 ([Cohere](https://dashboard.cohere.com/)에서 발급) | - | ✅ |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID ([Cloud Console](https://console.cloud.google.com/)에서 발급) | - | ✅ |
| `JWT_SECRET` | JWT 서명용 시크릿 키 (32자 이상 권장) | - | ✅ |
| `QDRANT_URL` | Qdrant 서버 URL | `http://localhost:6333` | |
| `QDRANT_API_KEY` | Qdrant Cloud API 키 (로컬이면 빈 값) | (빈 값) | |
| `ALLOWED_DOMAIN` | 허용 이메일 도메인 | `kookmin.ac.kr` | |
| `DOC_ADMIN_EMAILS` | 관리자 이메일 (쉼표 구분) | (빈 값) | |
| `UPLOAD_DIR` | PDF 업로드 디렉토리 경로 | `uploads` | |
| `CHUNK_SIZE` | 텍스트 청크 크기 (문자 수) | `550` | |
| `CHUNK_OVERLAP` | 청크 간 오버랩 (문자 수) | `100` | |
| `BM25_TOP_K` | BM25 검색 상위 K개 | `20` | |
| `VECTOR_TOP_K` | 벡터 검색 상위 K개 | `20` | |
| `FINAL_CONTEXT_SIZE` | 최종 답변 생성에 사용할 컨텍스트 수 | `5` | |
| `RELEVANCE_THRESHOLD` | Cohere Rerank 관련성 임계값 (이하 필터링) | `0.25` | |

---

## API 명세서

> Base URL: `http://localhost:8000`
>
> 인증이 필요한 API는 `Authorization: Bearer {JWT}` 헤더를 포함해야 합니다.
> 관리자 전용 API는 `DOC_ADMIN_EMAILS`에 등록된 이메일의 JWT가 필요합니다.

### 1. 인증 (Auth)

#### `POST /auth/google` — Google OAuth 로그인

프론트엔드에서 Google Sign-In으로 받은 `credential` (ID Token)을 전송하면,
서버에서 Google API로 토큰을 검증하고 JWT를 발급합니다.

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/auth/google` |
| Content-Type | `application/json` |
| 인증 | 불필요 |

**Request Body:**
```json
{
  "credential": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```
- `credential` (string, 필수): Google Sign-In에서 반환된 ID Token

**Response 200 OK:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6InVzZXJAa29va21pbi5hYy5rciIs...",
  "user": {
    "email": "user@kookmin.ac.kr",
    "name": "홍길동",
    "isDocAdmin": false
  }
}
```
- `token`: 이후 API 호출에 사용할 JWT (유효기간 7일)
- `user.isDocAdmin`: `DOC_ADMIN_EMAILS`에 포함된 이메일이면 `true`

**Response 401 Unauthorized:**
```json
{ "detail": "Google 인증 실패" }
```

**동작 상세:**
1. `GoogleAuthService`가 Google ID Token을 `GoogleIdTokenVerifier`로 검증
2. 검증 성공 시 `JwtService.createToken()`으로 JWT 생성 (HMAC-SHA256, 7일 만료)
3. 최초 로그인 시 `user_profiles` 테이블에 프로필 자동 생성

---

#### `GET /auth/me` — 현재 사용자 정보

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/auth/me` |
| 인증 | Bearer JWT 필수 |

**Response 200 OK:**
```json
{
  "user": {
    "email": "user@kookmin.ac.kr",
    "name": "홍길동",
    "isDocAdmin": false
  }
}
```

**Response 401 Unauthorized:**
```json
{ "detail": "Unauthorized" }
```

---

#### `GET /auth/dev-token` — 개발용 JWT 발급

개발/테스트 환경에서 Google 로그인 없이 JWT를 발급받을 수 있습니다.

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/auth/dev-token?email={email}&name={name}` |
| 인증 | 불필요 |

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `email` | string | `22615jin@kookmin.ac.kr` | 발급할 이메일 |
| `name` | string | `테스트유저` | 사용자 이름 |

**Response 200 OK:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiJ9...",
  "email": "22615jin@kookmin.ac.kr",
  "name": "테스트유저",
  "isDocAdmin": true
}
```

---

### 2. 채팅 (Chat) — RAG 질의응답

#### `POST /` — 질문에 대한 답변 생성

핵심 API. 사용자 질문을 받아 벡터 검색 → Rerank → Gemini 답변 생성 파이프라인을 실행합니다.

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/` |
| Content-Type | `application/json` |
| 인증 | Bearer JWT (선택, 프로필 기반 개인화에 사용) |

**Request Body:**
```json
{
  "message": "졸업 요건이 뭐야?",
  "history": "이전 질문: 학점은 몇 학점이야?\n이전 답변: 130학점입니다."
}
```
- `message` (string, 필수): 사용자 질문
- `history` (string, 선택): 이전 대화 내용 (멀티턴 대화 지원)

**Response 200 OK:**
```json
{
  "answer": "국민대학교의 졸업 요건은 다음과 같습니다...\n\n[출처: 학칙.pdf - 제8장: 졸업]",
  "sources": [
    {
      "uri": "학칙.pdf",
      "page": 15,
      "section": "제8장: 졸업",
      "has_table": false,
      "source_url": "",
      "rerank_score": 0.8523
    },
    {
      "uri": "학사규정.pdf",
      "page": 3,
      "section": "제2장: 수업 및 학점",
      "has_table": false,
      "source_url": "",
      "rerank_score": 0.7891
    }
  ],
  "contextCount": 3
}
```
- `answer`: Gemini가 생성한 답변 (출처 포함)
- `sources`: 참조된 문서 목록 (중복 제거됨)
  - `uri`: 문서 파일명
  - `page`: 페이지 번호
  - `section`: 섹션 경로 (예: "제8장: 졸업")
  - `has_table`: 표 포함 여부
  - `source_url`: 원본 URL (공지사항인 경우)
  - `rerank_score`: Cohere Rerank 관련성 점수 (0~1)
- `contextCount`: 답변 생성에 사용된 문서 청크 수

**검색 실패 시 (관련 문서 없음):**
```json
{
  "answer": "죄송합니다. 관련된 정보를 찾을 수 없습니다. 질문을 다르게 표현해보시거나, 더 구체적으로 질문해주세요.",
  "sources": [],
  "contextCount": 0
}
```

**동작 상세:**
1. JWT에서 이메일 추출 → `user_profiles`에서 학과/학년 조회 → 사용자 컨텍스트 구성
2. `SearchService.search()` 호출:
   - `EmbeddingService`로 질문 벡터화 (3072차원)
   - `QdrantService`로 벡터 검색 (top 20)
   - `CohereRerankService`로 리랭킹
   - `relevanceThreshold` (0.25) 이하 필터링
   - 상위 `finalContextSize` (5)개 반환
3. `AnswerService.generate()` 호출:
   - 시스템 프롬프트 + 문서 컨텍스트 + 질문 조합
   - `GeminiService`로 답변 생성
   - 출처 목록 구성 (중복 제거)
4. `chat_logs` 테이블에 질문/답변/출처 저장

---

### 3. 문서 관리 (Documents)

#### `POST /upload` — PDF 업로드 및 인덱싱

PDF 파일을 업로드하면 자동으로 파싱 → 청킹 → 임베딩 → Qdrant + SQLite 인덱싱됩니다.

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/upload` |
| Content-Type | `multipart/form-data` |
| 인증 | Bearer JWT (관리자 전용) |

**Request:**
| 필드 | 타입 | 설명 |
|------|------|------|
| `file` | File | PDF 파일 (최대 500MB) |

**Response 200 OK:**
```json
{
  "message": "Successfully indexed 42 chunks",
  "filename": "학칙.pdf",
  "chunks": 42
}
```

**동작 상세:**
1. `requireAdmin()`: JWT에서 이메일 추출 → `DOC_ADMIN_EMAILS` 포함 여부 확인
2. 파일을 `UPLOAD_DIR`에 저장
3. `PdfParserService.parse()`: PDFBox로 페이지별 텍스트 추출 + 섹션 경로 자동 감지
4. `ChunkerService.chunk()`: 각 페이지 텍스트를 `CHUNK_SIZE`(550자) 단위로 분할 (`CHUNK_OVERLAP` 100자 오버랩)
5. 각 청크마다:
   - UUID 생성
   - `SearchService.indexChunk()`: Gemini 임베딩 → Qdrant upsert + SQLite 저장

---

#### `GET /documents` — 문서 목록 조회

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/documents` |
| 인증 | 불필요 |

**Response 200 OK:**
```json
{
  "documents": [
    {
      "filename": "학칙.pdf",
      "size": 1048576,
      "type": ".pdf",
      "chunk_count": 42,
      "indexed": true
    },
    {
      "filename": "학사규정.pdf",
      "size": 524288,
      "type": ".pdf",
      "chunk_count": 0,
      "indexed": false
    }
  ]
}
```
- `chunk_count`: 인덱싱된 청크 수 (0이면 업로드만 되고 인덱싱 안 된 상태)
- `indexed`: 인덱싱 여부

---

#### `DELETE /documents/{filename}` — 문서 삭제

파일 + Qdrant 벡터 + SQLite 메타데이터를 모두 삭제합니다.

| 항목 | 값 |
|------|-----|
| Method | DELETE |
| URL | `/documents/{filename}` |
| 인증 | Bearer JWT (관리자 전용) |

**Response 200 OK:**
```json
{
  "message": "학칙.pdf 삭제 완료",
  "deleted_chunks": 42
}
```

---

#### `GET /documents/{filename}/preview` — 문서 미리보기/다운로드

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/documents/{filename}` |
| 인증 | 불필요 |

**Response 200:** 파일 바이너리 (`Content-Disposition: inline`)
**Response 404:** 파일 없음

---

#### `POST /reset` — 전체 인덱스 초기화

Qdrant 컬렉션 삭제 + SQLite 전체 삭제 + 컬렉션 재생성

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/reset` |
| 인증 | Bearer JWT (관리자 전용) |

**Response 200 OK:**
```json
{ "message": "Index reset successfully" }
```

---

### 4. 공지사항 크롤링 (Notices)

#### `POST /crawl/notices` — 소융대 공지사항 크롤링

국민대 소프트웨어융합대학 공지사항 사이트(`https://cs.kookmin.ac.kr/news/notice/`)에서
최근 N일 이내 공지를 자동 크롤링합니다.

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/crawl/notices?days={N}` |
| 인증 | Bearer JWT (관리자 전용) |

**Query Parameters:**
| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|--------|------|
| `days` | int | 7 | 최근 N일 이내 공지만 수집 |

**Response 200 OK:**
```json
{
  "success": 8,
  "fail": 0,
  "skipped": 2,
  "total_chunks": 13,
  "notices": [
    {
      "title": "2026학년도 1학기 조기졸업 신청 안내(3/17~3/20)",
      "date": "26.03.11",
      "chunks": 2,
      "attachments_merged": 0
    },
    {
      "title": "2026학년도 소프트웨어융합대학 멘토링 시스템 재개 안내",
      "date": "26.03.10",
      "chunks": 1,
      "attachments_merged": 1
    }
  ],
  "errors": []
}
```

| 필드 | 설명 |
|------|------|
| `success` | 성공적으로 크롤링된 공지 수 |
| `fail` | 크롤링 실패한 공지 수 |
| `skipped` | Gemini LLM 필터에 의해 제외된 공지 수 (마감 지난 공지 등) |
| `total_chunks` | 저장된 총 청크 수 |
| `notices` | 크롤링된 공지 상세 목록 |
| `attachments_merged` | 병합된 첨부 PDF 수 |

**크롤링 파이프라인:**
```
1. Playwright (Headless Chromium)로 공지 목록 페이지 접근
   └─ SPA(JavaScript 렌더링) 사이트이므로 Jsoup 대신 Playwright 사용
2. 날짜 필터: 최근 N일 이내 공지만 수집 (고정 공지 포함)
3. 각 공지 상세 페이지에서 본문 텍스트 수집
4. Gemini 2.5 Flash로 유효성 판단
   └─ 마감일 지난 공지, 종료된 행사 등 자동 제외
   └─ 학사 규정, 장학금, 수강신청 등 유용한 정보는 유지
5. 유효한 공지만:
   ├─ PDFBox로 본문 PDF 생성 (NanumGothic 한글 폰트)
   ├─ 첨부 PDF 다운로드 + 본문 PDF와 병합
   ├─ crawled_notices/pdf/ 디렉토리에 저장
   └─ 텍스트 청킹 → document_chunks 테이블에 저장
```

---

#### `GET /crawl/notices/list` — 인덱싱된 공지사항 목록

`[공지]` 접두사가 붙은 문서 목록을 반환합니다.

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/crawl/notices/list` |
| 인증 | 불필요 |

**Response 200 OK:**
```json
{
  "notices": [
    {
      "doc_name": "[공지] 2026학년도 1학기 조기졸업 신청 안내",
      "chunk_count": 2,
      "source_url": ""
    }
  ]
}
```

---

### 5. FAQ

#### `GET /faq` — 자주 묻는 질문

최근 30일간의 채팅 로그에서 빈도 높은 질문을 추출하고,
Gemini로 유사 질문을 그룹핑하여 최대 8개의 대표 FAQ를 생성합니다.

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/faq` |
| 인증 | 불필요 |

**Response 200 OK:**
```json
{
  "faqs": [
    {
      "question": "졸업 요건이 어떻게 되나요?",
      "category": "졸업",
      "answer": "국민대학교의 졸업 요건은...",
      "sources": [
        { "uri": "학칙.pdf", "page": 15, "section": "제8장: 졸업" }
      ],
      "count": 12
    }
  ]
}
```
- `category`: Gemini가 자동 분류한 카테고리 (졸업, 수강신청, 장학금, 학적, 기타 등)
- `count`: 해당 그룹에 속한 질문의 총 횟수

**동작 상세:**
1. `ChatLogRepository.findFrequentQuestions()`: 최근 30일 질문을 빈도순 정렬 (최대 30개)
2. Gemini에 질문 목록 전달 → JSON 배열로 그룹핑 결과 반환
3. 각 그룹에서 가장 빈도 높은 원본의 답변/출처를 매칭
4. 빈도순 정렬 후 최대 8개 반환
5. Gemini 호출 실패 시 빈 배열 반환 (graceful degradation)

---

### 6. 이용통계 (Stats)

#### `GET /stats` — 시스템 이용통계

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/stats` |
| 인증 | 불필요 |

**Response 200 OK:**
```json
{
  "total_questions": 150,
  "today_questions": 8,
  "daily_7d": [
    { "date": "2025-06-07", "count": 12 },
    { "date": "2025-06-08", "count": 8 }
  ],
  "hourly": [
    { "hour": 0, "count": 2 },
    { "hour": 1, "count": 0 },
    { "hour": 9, "count": 15 },
    { "hour": 14, "count": 22 }
  ],
  "total_docs": 25,
  "total_chunks": 1200,
  "docs_top10": [
    { "doc_name": "학칙.pdf", "count": 45 },
    { "doc_name": "학사규정.pdf", "count": 32 }
  ]
}
```

| 필드 | 설명 |
|------|------|
| `total_questions` | 전체 누적 질문 수 |
| `today_questions` | 오늘 질문 수 |
| `daily_7d` | 최근 7일 일별 질문 수 |
| `hourly` | 시간대별 질문 분포 (0~23시) |
| `total_docs` | 인덱싱된 고유 문서 수 |
| `total_chunks` | 전체 청크 수 |
| `docs_top10` | 최근 30일 가장 많이 참조된 문서 TOP 10 |

---

### 7. 사용자 프로필 (Profile)

#### `GET /profile` — 프로필 조회

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/profile` |
| 인증 | Bearer JWT |

**Response 200 OK:**
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

**JWT 없거나 프로필 없는 경우:**
```json
{ "profile": {} }
```

---

#### `POST /profile` — 프로필 저장

| 항목 | 값 |
|------|-----|
| Method | POST |
| URL | `/profile` |
| Content-Type | `application/json` |
| 인증 | Bearer JWT 필수 |

**Request Body:**
```json
{
  "name": "홍길동",
  "studentId": "20210001",
  "department": "소프트웨어학부",
  "grade": "3"
}
```

**Response 200 OK:**
```json
{ "message": "프로필 저장 완료" }
```

**Response 401:**
```json
{ "detail": "Unauthorized" }
```

**프로필 활용:**
- 채팅 시 학과/학년 정보가 시스템 프롬프트에 포함되어 개인화된 답변 제공
- 예: 소프트웨어학부 3학년 학생이 "졸업 요건" 질문 시, 해당 학과 관련 정보 우선 제공

---

### 8. 헬스체크

#### `GET /health`

| 항목 | 값 |
|------|-----|
| Method | GET |
| URL | `/health` |
| 인증 | 불필요 |

**Response 200 OK:**
```json
{ "status": "ok" }
```

---

## 프론트엔드/AI 연동 가이드

### 인증 플로우 (프론트엔드)

```
1. 프론트엔드: Google Sign-In 버튼 클릭
2. Google: credential (ID Token) 반환
3. 프론트엔드 → POST /auth/google { credential }
4. 백엔드: Google 토큰 검증 → JWT 발급
5. 프론트엔드: JWT를 localStorage에 저장
6. 이후 모든 API 호출 시 Authorization: Bearer {JWT} 헤더 포함
```

**프론트엔드 코드 예시 (JavaScript):**
```javascript
// Google Sign-In 콜백
function handleCredentialResponse(response) {
  fetch('/auth/google', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential: response.credential })
  })
  .then(res => res.json())
  .then(data => {
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
  });
}

// 인증된 API 호출
function apiCall(url, options = {}) {
  const token = localStorage.getItem('token');
  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
}
```

### 채팅 연동 (프론트엔드)

```javascript
// 질문 전송
async function sendMessage(message, history) {
  const response = await apiCall('/', {
    method: 'POST',
    body: JSON.stringify({ message, history })
  });
  const data = await response.json();

  // data.answer: 답변 텍스트
  // data.sources: 출처 배열
  // data.contextCount: 사용된 컨텍스트 수

  // 출처에서 PDF 미리보기 링크 생성
  data.sources.forEach(source => {
    const previewUrl = `/documents/${encodeURIComponent(source.uri)}/preview`;
    // previewUrl을 <a> 태그로 렌더링
  });
}
```

### 문서 업로드 연동 (프론트엔드)

```javascript
async function uploadDocument(file) {
  const token = localStorage.getItem('token');
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData  // Content-Type은 자동 설정됨
  });
  return response.json();
}
```

### AI 파이프라인 연동 (AI 팀)

AI 팀에서 검색/생성 로직을 수정하려면 다음 서비스를 참고:

| 서비스 | 파일 | 역할 | 수정 포인트 |
|--------|------|------|-------------|
| `EmbeddingService` | `service/EmbeddingService.java` | 텍스트 → 벡터 | 임베딩 모델 변경 시 |
| `GeminiService` | `service/GeminiService.java` | LLM 텍스트 생성 | 모델 변경, 파라미터 조정 |
| `CohereRerankService` | `service/CohereRerankService.java` | 검색 결과 리랭킹 | 리랭킹 모델/파라미터 변경 |
| `SearchService` | `service/SearchService.java` | 검색 파이프라인 통합 | 검색 로직 변경, threshold 조정 |
| `AnswerService` | `service/AnswerService.java` | 프롬프트 구성 + 답변 생성 | 시스템 프롬프트 수정 |
| `ChunkerService` | `service/ChunkerService.java` | 텍스트 청킹 | 청크 크기/오버랩 조정 |
| `PdfParserService` | `service/PdfParserService.java` | PDF 파싱 | 파싱 로직 개선 |

### 시스템 프롬프트 (AnswerService)

현재 `AnswerService.java`에 하드코딩된 시스템 프롬프트:

```
당신은 국민대학교 학칙 및 학사규정 전문가입니다.
규칙:
1. 주어진 문서 조각만을 근거로 답변하세요
2. 근거가 부족하면 추측하지 말고 "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답하세요
3. 숫자, 날짜, 조항은 원문 표현을 그대로 사용하세요
4. 답변 끝에 사용한 문서명과 섹션을 [출처: 문서명 - 섹션] 형식으로 표시하세요
5. 여러 문서를 참고했다면 모두 표시하세요
```

---

## 핵심 기능 상세

### 1. 하이브리드 검색 (SearchService)

`SearchService.search(query, topK)` 메서드가 전체 검색 파이프라인을 관리합니다:

```java
// 1. 질문 벡터화
List<Double> queryVector = embeddingService.getEmbedding(query);

// 2. Qdrant 벡터 검색 (Cosine 유사도, HNSW 인덱스)
List<Map<String, Object>> vectorResults = qdrantService.search(queryVector, vectorTopK);

// 3. Cohere Rerank로 관련성 재정렬
List<Map<String, Object>> rerankResults = cohereRerankService.rerank(query, docs, rerankTopN);

// 4. relevance_score >= 0.25 필터링 후 상위 topK개 반환
```

### 2. 문서 인덱싱 파이프라인

```
PDF 업로드
    │
    ▼
PdfParserService.parse()
    │  PDFBox로 페이지별 텍스트 추출
    │  섹션 경로 자동 감지 (정규식: "제N장: 제목")
    ▼
ChunkerService.chunk()
    │  550자 단위로 분할 (100자 오버랩)
    │  메타데이터: doc_name, section_path, page, chunk_index
    ▼
SearchService.indexChunk()
    │  EmbeddingService: Gemini embedding-001로 3072차원 벡터 생성
    │  QdrantService: 벡터 + payload를 Qdrant에 upsert
    │  DocumentChunkRepository: 메타데이터를 SQLite에 저장
    ▼
인덱싱 완료
```

### 3. JWT 인증 (JwtService)

- 알고리즘: HMAC-SHA256
- 만료: 7일
- 페이로드: `{ email, name, iat, exp }`
- 키 길이: 최소 32바이트 (부족 시 자동 패딩)

### 4. Qdrant 벡터 DB (QdrantService)

- 컬렉션명: `documents`
- 벡터 차원: 3072 (Gemini embedding-001)
- 거리 함수: Cosine
- HNSW 파라미터: `ef=128`
- `@PostConstruct`로 앱 시작 시 컬렉션 자동 생성 (이미 존재하면 무시)

### 5. SQLite 테이블 구조

```sql
-- 채팅 로그
CREATE TABLE chat_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer TEXT,
    sources TEXT,           -- JSON 문자열
    user_email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 사용자 프로필
CREATE TABLE user_profiles (
    email VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    student_id VARCHAR(255),
    department VARCHAR(255),
    grade VARCHAR(255),
    updated_at TIMESTAMP
);

-- 문서 청크 메타데이터
CREATE TABLE document_chunks (
    id VARCHAR(255) PRIMARY KEY,  -- UUID
    content TEXT,
    doc_name VARCHAR(255),
    section_path VARCHAR(255),
    page INTEGER,
    has_table BOOLEAN,
    source_url VARCHAR(255)
);
```

> 테이블은 Spring JPA의 `ddl-auto: update` 설정으로 자동 생성됩니다.

### 6. 공지사항 자동 크롤링 (NoticeCrawlerService)

소프트웨어융합대학 공지사항 사이트는 JavaScript SPA로 구현되어 있어
일반 HTTP 요청(Jsoup)으로는 콘텐츠를 가져올 수 없습니다.
Playwright Java(Headless Chromium)를 사용하여 브라우저 렌더링 후 데이터를 추출합니다.

**크롤링 전체 흐름:**

```
Playwright (Headless Chromium)
    │
    ▼
① 공지 목록 페이지 순회 (페이지네이션)
    │  - 고정 공지(Notice 라벨)와 일반 공지 분리
    │  - 날짜 파싱: YY.MM.DD 형식 (예: 26.03.11)
    │  - cutoff 날짜 이전 일반 공지 도달 시 순회 중단
    ▼
② 각 공지 상세 페이지 방문 → 본문 텍스트 수집
    │  - 여러 CSS 셀렉터 시도 (.board-view-content, .view-content 등)
    │  - 본문 최대 300자를 Gemini에 전달
    ▼
③ Gemini 2.5 Flash LLM 필터
    │  - 오늘 날짜 기준으로 유효성 판단
    │  - [저장 O]: 학사 규정, 유효한 신청 안내, 제도 변경, 학생 지원
    │  - [저장 X]: 마감일 지난 공지, 종료된 행사, 빈 본문
    │  - 응답 형식: "1:O\n2:X\n3:O\n..."
    ▼
④ 유효한 공지만 PDF 변환
    │  - PDFBox + NanumGothic 한글 폰트
    │  - 제목, 날짜, 작성자, URL, 본문 포함
    │  - 첨부 PDF 다운로드 후 본문 PDF와 병합
    │  - crawled_notices/pdf/ 디렉토리에 저장
    ▼
⑤ 텍스트 청킹 → RDB 저장
    │  - ChunkerService로 550자 단위 분할
    │  - doc_name: "[공지] 제목.pdf"
    │  - source_url: 원본 공지 URL
    │  - document_chunks 테이블에 저장
    ▼
크롤링 완료 (결과 JSON 반환)
```

**주요 기술 결정:**

| 결정 | 이유 |
|------|------|
| Jsoup 대신 Playwright | 공지 사이트가 JavaScript SPA라서 서버사이드 렌더링 필요 |
| Gemini LLM 필터 | 키워드 기반 필터링보다 정확한 유효성 판단 (마감일, 행사 종료 등 맥락 이해) |
| PDFBox로 PDF 생성 | 공지 본문을 PDF로 보존하여 원본 형태 유지 |
| NanumGothic 폰트 | macOS AppleGothic은 OS/2 테이블 누락으로 PDFBox 호환 불가 |
| 첨부 PDF 병합 | 공지 본문과 첨부파일을 하나의 PDF로 통합 관리 |
