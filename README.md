# KDD (Kookmin Digital Doc) — 국민대학교 학칙 RAG 챗봇

국민대학교 학칙 및 학사규정 PDF 문서를 업로드하면 자동으로 파싱·청킹·임베딩하여,
사용자가 자연어로 질문하면 관련 문서를 검색하고 근거 기반 답변을 생성하는
RAG(Retrieval-Augmented Generation) 시스템이다.

- 접속 URL: `http://kdd-chatbot.duckdns.org:8000/static/index.html`
- EC2 IP: `3.35.208.60`
- 관리자 이메일: `22615jin@kookmin.ac.kr`

---

## 1. 시스템 아키텍처

```
[사용자 브라우저] ──→ Google OAuth 로그인
        │
        ▼
┌────────────────────────────────────────────────────┐
│  FastAPI 서버 (main.py, 포트 8000)                  │
│                                                    │
│  POST /            → 채팅 (질문→검색→답변생성)       │
│  POST /auth/google → Google 로그인                  │
│  POST /upload      → PDF 업로드 + 자동 인덱싱       │
│  GET  /documents   → 업로드된 문서 목록              │
│  POST /reset       → 인덱스 초기화                  │
│  GET  /health      → 헬스체크                       │
└────────────┬───────────────────────────────────────┘
             │
    ┌────────┴────────┐
    ▼                 ▼
┌─────────┐    ┌───────────┐
│ SQLite  │    │  Qdrant   │
│ FTS5    │    │ (Docker)  │
│ (BM25)  │    │ (벡터검색) │
└────┬────┘    └─────┬─────┘
     └───────┬───────┘
             ▼
     RRF 결합 (점수 융합)
             ▼
     Cohere Rerank (재정렬)
             ▼
     Gemini 2.5 Flash (답변 생성)
             ▼
     근거 기반 답변 + 출처 반환
```

### 검색 파이프라인 상세

1. **BM25 검색 (SQLite FTS5)**: 키워드 기반 검색. "제42조", "졸업학점" 같은 정확한 용어 매칭에 강함
2. **벡터 검색 (Qdrant + Gemini Embedding)**: 의미 기반 검색. "학교 그만두려면?" → "자퇴" 매칭 가능
3. **RRF 결합**: 두 검색 결과를 Reciprocal Rank Fusion으로 점수 융합. 키워드+의미 검색의 장점을 모두 활용
4. **Cohere Rerank**: 결합된 후보를 다국어 리랭킹 모델로 최종 정렬. 한국어 학칙 문서에 최적화
5. **Gemini 답변 생성**: 상위 문서를 컨텍스트로 넣어 근거 기반 답변 생성. 출처(문서명, 페이지, 섹션) 포함

### 문서 처리 파이프라인

```
PDF 업로드 → PDFToMarkdown (표/섹션 구조 보존)
         → SemanticChunker (550자 단위, 100자 오버랩)
         → Gemini Embedding (3072차원 벡터)
         → Qdrant 저장 (벡터) + SQLite FTS5 저장 (텍스트)
```

---

## 2. 기술 스택 및 비용

| 구분 | 기술 | 설명 | 비용 |
|------|------|------|------|
| 백엔드 | FastAPI + Uvicorn | 비동기 Python 웹 프레임워크 | 무료 |
| LLM | Google Gemini 2.5 Flash | 답변 생성용 대규모 언어 모델 | 무료 티어 (분당 15회, 일 1500회) |
| 임베딩 | Gemini Embedding 001 | 3072차원 벡터 임베딩 | 무료 티어 |
| 벡터 DB | Qdrant (Docker) | HNSW 기반 벡터 유사도 검색 | 무료 (EC2 내부 Docker) |
| BM25 검색 | SQLite FTS5 | 키워드 기반 전문 검색 | 무료 (내장 DB) |
| 리랭킹 | Cohere Rerank v3 | 다국어 리랭킹 모델 | 무료 (월 1000회) |
| 인증 | Google OAuth 2.0 + JWT | 국민대 Google 계정 인증 | 무료 |
| 서버 | AWS EC2 t3.small | Ubuntu 22.04, Docker 기반 | ~$15/월 |
| 도메인 | DuckDNS | 무료 동적 DNS | 무료 |
| 프론트엔드 | HTML/CSS/JS (인라인) | index.html 단일 파일 | 무료 |

---

## 3. 프로젝트 구조

```
.
├── main.py                      # FastAPI 서버 진입점. 모든 API 엔드포인트 정의
├── config.py                    # Pydantic Settings 기반 환경변수 관리
├── auth.py                      # Google OAuth 토큰 검증 + JWT 생성/검증
├── config.js                    # 프론트엔드 설정 (API 주소, Google Client ID)
├── index.html                   # 프론트엔드 전체 (HTML+CSS+JS 인라인)
├── requirements.txt             # Python 패키지 의존성
├── .env                         # 로컬 개발용 환경변수
├── .env.production              # EC2 운영용 환경변수 (git 미포함)
├── .env.production.example      # 운영 환경변수 템플릿
│
├── search/
│   └── free_hybrid_search.py    # 핵심: 하이브리드 검색 엔진
│                                #   - Qdrant 벡터 검색
│                                #   - SQLite FTS5 BM25 검색
│                                #   - RRF 결합
│                                #   - Cohere Rerank
│                                #   - Gemini 임베딩 생성
│
├── generation/
│   └── generator.py             # Gemini 2.5 Flash 기반 답변 생성기
│                                #   - 시스템 프롬프트 (학칙 전문가 역할)
│                                #   - 컨텍스트 포맷팅
│                                #   - 출처 정보 구성
│
├── preprocessing/
│   ├── pdf_parser.py            # PDF → Markdown 변환
│   │                            #   - pdfplumber로 텍스트+표 추출
│   │                            #   - 표를 Markdown 테이블로 변환
│   │                            #   - 섹션 경로 자동 추출 (제N장, 제N조)
│   ├── html_parser.py           # HTML → Markdown 변환
│   │                            #   - BeautifulSoup으로 구조 파싱
│   │                            #   - 제목/본문/표/리스트 변환
│   └── chunker.py               # 의미 단위 청킹
│                                #   - 일반 텍스트: 550자 단위, 100자 오버랩
│                                #   - 표 포함 텍스트: 구조 기반 분할
│
├── evaluation/
│   ├── evaluate.py              # RAG 시스템 평가 스크립트
│   └── gold_set.json            # 평가용 질문-답변 골드셋
│
├── scripts/
│   ├── import_local.py          # uploads/ 폴더의 PDF 일괄 인덱싱
│   ├── import_from_s3.py        # AWS S3에서 PDF 다운로드 후 인덱싱
│   ├── upload_docs.py           # API를 통한 문서 업로드
│   ├── test_search.py           # 검색 기능 테스트
│   ├── check_deployment.py      # 배포 상태 확인
│   └── init_cloud_db.py         # 클라우드 DB 초기화
│
├── deploy/
│   ├── Dockerfile               # Python 3.11-slim 기반 Docker 이미지
│   ├── docker-compose.prod.yml  # 운영 환경 (app + qdrant 컨테이너)
│   ├── quick_deploy.sh          # 원클릭 배포 스크립트
│   ├── setup_ec2.sh             # EC2 초기 설정 (Docker, Git, 방화벽)
│   └── nginx.conf               # Nginx 리버스 프록시 설정 (선택)
│
├── data/
│   └── fts.db                   # SQLite FTS5 데이터베이스 (BM25 인덱스)
│
└── uploads/                     # 업로드된 원본 문서 저장 폴더
```

---

## 4. 각 파일 상세 설명

### 4.1 main.py — FastAPI 서버

모든 API 엔드포인트가 정의된 서버 진입점이다.

| 엔드포인트 | 메서드 | 인증 | 설명 |
|-----------|--------|------|------|
| `/` | POST | 선택 | 채팅. `{"message": "질문", "history": ""}` 전송 → 검색 → 답변 생성 → 출처 포함 응답 |
| `/auth/google` | POST | 없음 | Google OAuth credential을 받아 JWT 토큰 발급 |
| `/auth/me` | GET | 필수 | 현재 로그인 사용자 정보 반환 |
| `/upload` | POST | 관리자 | PDF/HTML 파일 업로드 → 파싱 → 청킹 → 임베딩 → 인덱싱 자동 처리 |
| `/documents` | GET | 선택 | uploads/ 폴더의 문서 목록 반환 |
| `/reset` | POST | 관리자 | Qdrant 컬렉션 + SQLite FTS5 테이블 전체 삭제 후 재생성 |
| `/health` | GET | 없음 | 서버 상태 확인 (`{"status": "ok"}`) |
| `/static/*` | GET | 없음 | 정적 파일 서빙 (index.html, config.js 등) |

서버 시작 시 `startup` 이벤트에서 Qdrant 컬렉션과 SQLite FTS5 테이블을 자동 초기화한다.

### 4.2 config.py — 환경변수 관리

Pydantic Settings를 사용하여 `.env` 파일에서 환경변수를 자동 로딩한다.
`extra = "ignore"` 설정으로 `.env`에 불필요한 변수가 있어도 에러가 나지 않는다.

주요 설정값:

| 환경변수 | 설명 | 기본값 |
|---------|------|--------|
| `GEMINI_API_KEY` | Google Gemini API 키 (필수) | - |
| `COHERE_API_KEY` | Cohere Rerank API 키 (필수) | - |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID (필수) | - |
| `QDRANT_URL` | Qdrant 서버 주소 | `http://localhost:6333` |
| `QDRANT_API_KEY` | Qdrant API 키 | `""` |
| `ALLOWED_DOMAIN` | 허용 이메일 도메인 | `kookmin.ac.kr` |
| `DOC_ADMIN_EMAILS` | 관리자 이메일 (쉼표 구분) | `""` |
| `JWT_SECRET` | JWT 서명 비밀키 (필수) | - |
| `CHUNK_SIZE` | 청크 크기 (문자 수) | `550` |
| `CHUNK_OVERLAP` | 청크 오버랩 (문자 수) | `100` |
| `BM25_TOP_K` | BM25 검색 상위 개수 | `20` |
| `VECTOR_TOP_K` | 벡터 검색 상위 개수 | `20` |
| `RERANK_TOP_K` | 리랭킹 후 상위 개수 | `6` |
| `FINAL_CONTEXT_SIZE` | 최종 답변 생성에 사용할 문서 수 | `5` |

### 4.3 auth.py — 인증 시스템

- `verify_google_token()`: Google OAuth ID 토큰을 검증하여 이메일, 이름 추출
- `create_token()`: 사용자 정보로 JWT 토큰 생성 (유효기간 7일)
- `verify_token()`: Authorization 헤더의 JWT 토큰 검증
- `verify_admin()`: 토큰 검증 + 관리자 이메일 확인 (DOC_ADMIN_EMAILS에 포함 여부)

### 4.4 search/free_hybrid_search.py — 하이브리드 검색 엔진

이 시스템의 핵심 모듈이다. 두 가지 검색 방식을 결합하여 정확도를 높인다.

**클래스: FreeHybridSearch**

| 메서드 | 설명 |
|--------|------|
| `__init__()` | Qdrant 클라이언트, SQLite 연결, Cohere 클라이언트, Gemini 임베딩 초기화 |
| `init_collections()` | Qdrant 컬렉션(3072차원, COSINE, HNSW) + SQLite FTS5 테이블 생성 |
| `index_chunk(chunk_id, content, metadata)` | 청크를 벡터 임베딩 후 Qdrant + SQLite에 동시 저장 |
| `search(query, top_k)` | BM25 + 벡터 검색 → RRF 결합 → Cohere Rerank → 상위 결과 반환 |
| `_get_embedding(text)` | Gemini `gemini-embedding-001` 모델로 3072차원 벡터 생성 |
| `_bm25_search(query, top_k)` | SQLite FTS5의 `MATCH` + `bm25()` 함수로 키워드 검색 |
| `_vector_search(query, top_k)` | Qdrant HNSW 인덱스로 코사인 유사도 검색 |
| `_rrf_combine(bm25, vector, k=60)` | RRF 공식: `score = Σ 1/(k + rank)` 로 두 결과 융합 |
| `_rerank(query, candidates, top_k)` | Cohere `rerank-multilingual-v3.0`으로 최종 정렬 |
| `delete_all()` | Qdrant 컬렉션 삭제 + SQLite 테이블 삭제 후 재생성 |

### 4.5 generation/generator.py — 답변 생성기

Gemini 2.5 Flash 모델을 사용하여 검색된 문서 컨텍스트 기반으로 답변을 생성한다.

- 시스템 프롬프트: "국민대학교 학칙 및 학사규정 전문가" 역할 부여
- 규칙: 문서 근거만 사용, 추측 금지, 원문 표현 유지, 출처 표시 필수
- 출력: 답변 텍스트 + 출처 리스트 (문서명, 페이지, 섹션, 스니펫)

### 4.6 preprocessing/ — 문서 전처리

**pdf_parser.py (PDFToMarkdown)**
- pdfplumber로 PDF 페이지별 텍스트 + 표 추출
- 표를 Markdown 테이블 형식으로 변환 (`| 헤더 | ... |`)
- 섹션 경로 자동 추출: "제1장: ...", "제42조: ..." 패턴 인식
- 메타데이터: 문서명, 섹션경로, 페이지번호, 표 포함 여부, 총 페이지수

**html_parser.py (HTMLToMarkdown)**
- BeautifulSoup으로 HTML 구조 파싱
- h1~h6 제목 기반 섹션 분리, 섹션 경로 자동 구성
- 표, 리스트, 인용문 등 Markdown 변환

**chunker.py (SemanticChunker)**
- 일반 텍스트: 550자 단위 슬라이딩 윈도우, 100자 오버랩
- 표 포함 텍스트: 표 단위로 분리하여 표가 잘리지 않도록 보존
- 각 청크에 메타데이터(chunk_index, char_count) 부착

### 4.7 config.js — 프론트엔드 설정

```javascript
window.APP_CONFIG = {
  API_BASE: "http://kdd-chatbot.duckdns.org:8000",  // API 서버 주소
  GOOGLE_CLIENT_ID: "879695241528-...",               // Google OAuth 클라이언트 ID
  ALLOWED_DOMAIN: "kookmin.ac.kr"                     // 허용 도메인
};
```

로컬 테스트 시 `API_BASE`를 `"http://localhost:8000"`으로 변경하면 된다.
EC2 배포 시 반드시 도메인 주소로 되돌려야 한다.

---

## 5. 웹 페이지 기능 설명

### 5.1 전체 레이아웃

좌측 사이드바 + 우측 메인 영역 구조이다.

**사이드바 메뉴:**
- 학칙 질의응답 (기본 화면)
- 문서관리 (관리자 로그인 시에만 표시)
- FAQ관리 (미구현, 플레이스홀더)
- 이용통계 (미구현, 플레이스홀더)
- 설정 (미구현, 플레이스홀더)

**상단바:**
- 시스템 제목: "KDD (Kookmin Digital Doc)"
- 사용자 정보 표시 (로그인 후)
- Google 로그인 버튼 / 로그아웃 버튼

### 5.2 학칙 질의응답 (채팅)

- Google 로그인 후 활성화됨
- 하단 텍스트 입력창에 질문 입력 → Enter 또는 전송 버튼 클릭
- "답변 생성중..." 로딩 표시 후 답변 출력
- 답변 하단에 근거(출처) 표시: 문서명, 페이지, 스니펫
- 문서가 인덱싱되지 않은 상태면 "관련된 정보를 찾을 수 없습니다" 응답

### 5.3 문서관리 (관리자 전용)

관리자 이메일(`DOC_ADMIN_EMAILS`)로 로그인한 경우에만 사이드바에 "문서관리" 탭이 표시된다.

**좌측: 파일 업로드 영역**
- 드래그 앤 드롭으로 파일 업로드 가능
- "파일 선택" 버튼으로 파일 탐색기에서 선택 가능
- 지원 형식: PDF (HWP는 현재 미지원)
- 업로드 대기 목록에 파일이 표시되며, ✕ 버튼으로 제거 가능
- "업로드 시작" 클릭 시 서버로 전송 → 자동 파싱·청킹·임베딩·인덱싱
- 업로드 완료 후 문서 현황 자동 갱신

**우측: 문서 현황**
- 업로드된 문서 목록 (파일명, 크기)
- "목록 새로고침" 버튼으로 수동 갱신

### 5.4 Google 로그인

- Google Identity Services (GSI) 라이브러리 사용
- 국민대 Google 계정(`@kookmin.ac.kr`)으로 로그인
- 로그인 성공 시 JWT 토큰 발급, 이후 API 요청에 Bearer 토큰으로 인증
- 로그아웃 버튼으로 세션 종료

---

## 6. 환경변수 설정

### 6.1 로컬 개발용 (.env)

```env
# API Keys
GEMINI_API_KEY=AIzaSy...
COHERE_API_KEY=FPBVeo...
GOOGLE_CLIENT_ID=879695241528-...apps.googleusercontent.com

# Qdrant (로컬은 Docker 내부 Qdrant 사용)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# 앱 설정
ALLOWED_DOMAIN=kookmin.ac.kr
DOC_ADMIN_EMAILS=22615jin@kookmin.ac.kr
JWT_SECRET=아무_랜덤_문자열

# 청킹/검색 설정
CHUNK_SIZE=550
CHUNK_OVERLAP=100
BM25_TOP_K=20
VECTOR_TOP_K=20
RERANK_TOP_K=6
FINAL_CONTEXT_SIZE=5
```

### 6.2 EC2 운영용 (.env.production)

EC2의 `~/rag-chatbot/.env.production` 파일이다. git에 포함되지 않으므로 EC2에서 직접 생성/수정해야 한다.

```env
# API Keys
GEMINI_API_KEY=AIzaSy...
COHERE_API_KEY=FPBVeo...
GOOGLE_CLIENT_ID=879695241528-...apps.googleusercontent.com

# Qdrant (Docker 내부 네트워크에서는 서비스명으로 접근)
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=

# 앱 설정
ALLOWED_DOMAIN=kookmin.ac.kr
DOC_ADMIN_EMAILS=22615jin@kookmin.ac.kr
JWT_SECRET=운영용_비밀키

# 청킹/검색 설정
CHUNK_SIZE=550
CHUNK_OVERLAP=100
BM25_TOP_K=20
VECTOR_TOP_K=20
RERANK_TOP_K=6
FINAL_CONTEXT_SIZE=5
```

**중요:** 로컬 `.env`에서는 `QDRANT_URL=http://localhost:6333`이지만,
EC2 `.env.production`에서는 `QDRANT_URL=http://qdrant:6333`이다.
Docker Compose 내부 네트워크에서 서비스명(`qdrant`)으로 접근하기 때문이다.

---

## 7. 로컬 개발 환경 설정

### 7.1 사전 요구사항

- Python 3.11 이상
- Git

### 7.2 설치 및 실행

```bash
# 1. 저장소 클론
git clone https://github.com/Sangjin-kmu/rag-chatbot.git
cd rag-chatbot

# 2. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
nano .env  # API 키 등 실제 값 입력

# 5. config.js를 로컬용으로 변경
# API_BASE를 "http://localhost:8000"으로 수정

# 6. 서버 실행
python main.py
```

브라우저에서 `http://localhost:8000/static/index.html` 접속.

### 7.3 로컬에서 문서 인덱싱 테스트

```bash
# uploads/ 폴더에 PDF 파일 넣기
cp 테스트문서.pdf uploads/

# 인덱싱 스크립트 실행
python scripts/import_local.py
```

---

## 8. EC2 서버 운영 가이드

### 8.1 EC2 접속

```bash
ssh -i ~/.ssh/rag-chatbot-key.pem ubuntu@3.35.208.60
# 또는 키가 등록되어 있으면
ssh ubuntu@3.35.208.60
```

### 8.2 프로젝트 위치

```bash
cd ~/rag-chatbot
```

### 8.3 Docker 컨테이너 구조

`docker-compose.prod.yml`에 2개 컨테이너가 정의되어 있다:

| 컨테이너 | 이미지 | 포트 | 역할 |
|----------|--------|------|------|
| `app` | 커스텀 빌드 (Dockerfile) | 8000 | FastAPI 서버 |
| `qdrant` | qdrant/qdrant:latest | 6333 | 벡터 데이터베이스 |

### 8.4 자주 쓰는 Docker 명령어

```bash
# 컨테이너 상태 확인
docker-compose -f deploy/docker-compose.prod.yml ps

# 로그 확인 (실시간)
docker-compose -f deploy/docker-compose.prod.yml logs -f

# app 컨테이너 로그만 확인
docker-compose -f deploy/docker-compose.prod.yml logs -f app

# 컨테이너 재시작 (코드 변경 없이 재시작만)
docker-compose -f deploy/docker-compose.prod.yml restart app

# 컨테이너 중지
docker-compose -f deploy/docker-compose.prod.yml down

# 이미지 재빌드 + 실행 (코드 변경 후 반드시 필요)
docker-compose -f deploy/docker-compose.prod.yml build
docker-compose -f deploy/docker-compose.prod.yml up -d

# 컨테이너 안에서 명령어 실행
docker-compose -f deploy/docker-compose.prod.yml exec app python scripts/import_local.py

# 컨테이너 안에서 셸 접속
docker-compose -f deploy/docker-compose.prod.yml exec app bash
```

### 8.5 코드 수정 후 배포 절차

로컬에서 코드를 수정한 후 EC2에 반영하는 전체 흐름이다.

```bash
# === 로컬 (개발 PC) ===

# 1. 코드 수정 후 커밋 & 푸시
git add .
git commit -m "변경 내용 설명"
git push origin main

# === EC2 서버 ===

# 2. EC2 접속
ssh ubuntu@3.35.208.60

# 3. 최신 코드 받기
cd ~/rag-chatbot
git pull origin main

# 4. Docker 재빌드 & 실행
docker-compose -f deploy/docker-compose.prod.yml down
docker-compose -f deploy/docker-compose.prod.yml build
docker-compose -f deploy/docker-compose.prod.yml up -d

# 5. 정상 동작 확인
curl http://localhost:8000/health
# {"status":"ok"} 가 나오면 성공
```

**주의사항:**
- `git pull` 시 `.env.production`은 git에 포함되지 않으므로 덮어쓰이지 않는다
- 코드만 변경한 경우 `build` + `up -d`가 필요하다 (restart만으로는 새 코드 반영 안 됨)
- `.env.production`을 수정한 경우 `restart`만으로 충분하다

### 8.6 .env.production 수정

```bash
cd ~/rag-chatbot
nano .env.production
# 수정 후 저장 (Ctrl+O → Enter → Ctrl+X)

# 재시작
docker-compose -f deploy/docker-compose.prod.yml restart app
```

### 8.7 S3에서 문서 가져와서 인덱싱

```bash
# 1. AWS CLI 설정 (최초 1회)
aws configure
# Access Key, Secret Key, Region: ap-northeast-2

# 2. S3에서 PDF 다운로드
mkdir -p ~/s3_docs
aws s3 sync s3://school-rag-kb-apne2/rules/ ~/s3_docs/ \
  --exclude "*" --include "*.pdf"

# 3. 컨테이너에 파일 복사
docker cp ~/s3_docs/. \
  $(docker-compose -f deploy/docker-compose.prod.yml ps -q app):/app/uploads/

# 4. 인덱싱 실행
docker-compose -f deploy/docker-compose.prod.yml exec app \
  python scripts/import_local.py
```

Gemini 무료 티어는 분당 15회 임베딩 제한이 있어서, 14청크마다 62초 대기한다.
PDF 31개 기준 수 시간 소요될 수 있다.

### 8.8 인덱스 초기화 (전체 삭제)

문서를 전부 삭제하고 처음부터 다시 인덱싱하고 싶을 때:

```bash
docker-compose -f deploy/docker-compose.prod.yml exec app python -c "
from search.free_hybrid_search import FreeHybridSearch
s = FreeHybridSearch()
s.delete_all()
print('인덱스 초기화 완료')
"
```

### 8.9 헬스체크 및 디버깅

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 컨테이너 상태 확인
docker-compose -f deploy/docker-compose.prod.yml ps

# 실시간 로그 확인
docker-compose -f deploy/docker-compose.prod.yml logs -f app

# 컨테이너 안에서 Python 셸로 디버깅
docker-compose -f deploy/docker-compose.prod.yml exec app python
>>> from search.free_hybrid_search import FreeHybridSearch
>>> s = FreeHybridSearch()
>>> results = s.search("졸업학점")
>>> print(len(results), "개 결과")
```

---

## 9. API 사용 예시

### 9.1 채팅 (질문 → 답변)

```bash
curl -X POST http://kdd-chatbot.duckdns.org:8000/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"message": "졸업에 필요한 학점은?", "history": ""}'
```

응답:
```json
{
  "answer": "졸업에 필요한 최소 학점은 130학점입니다. [출처: 학칙 - 제42조]",
  "sources": [
    {
      "uri": "2025국민대학교요람.pdf",
      "page": 15,
      "section": "제6장: 졸업",
      "snippet": "제42조 졸업에 필요한 최소 이수학점은...",
      "has_table": false
    }
  ],
  "context_count": 3
}
```

### 9.2 문서 업로드

```bash
curl -X POST http://kdd-chatbot.duckdns.org:8000/upload \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@학칙.pdf"
```

### 9.3 문서 목록 조회

```bash
curl http://kdd-chatbot.duckdns.org:8000/documents
```

---

## 10. 코드 수정 가이드

### 10.1 답변 생성 모델 변경

`generation/generator.py`에서 모델명을 변경한다:

```python
# 현재
self.model = genai.GenerativeModel('gemini-2.5-flash')

# 다른 모델로 변경 시
self.model = genai.GenerativeModel('gemini-2.5-pro')
```

### 10.2 시스템 프롬프트 수정

`generation/generator.py`의 `generate()` 메서드 내 `system_prompt` 변수를 수정한다.
현재는 "국민대학교 학칙 및 학사규정 전문가" 역할이 부여되어 있다.

### 10.3 검색 파라미터 튜닝

`.env` 또는 `.env.production`에서 조정한다:

- `BM25_TOP_K=20`: BM25 검색 후보 수. 늘리면 재현율↑, 속도↓
- `VECTOR_TOP_K=20`: 벡터 검색 후보 수. 늘리면 재현율↑, 속도↓
- `RERANK_TOP_K=6`: 리랭킹 후 최종 후보 수
- `FINAL_CONTEXT_SIZE=5`: 답변 생성에 사용할 문서 수. 늘리면 정보↑, 비용↑
- `CHUNK_SIZE=550`: 청크 크기. 늘리면 문맥↑, 검색 정밀도↓
- `CHUNK_OVERLAP=100`: 청크 오버랩. 늘리면 정보 손실↓, 청크 수↑

### 10.4 임베딩 모델 변경

`search/free_hybrid_search.py`의 `_get_embedding()` 메서드에서 모델명을 변경한다.
모델을 변경하면 벡터 차원이 달라질 수 있으므로, `init_collections()`의 `size` 값도 함께 변경하고
기존 Qdrant 컬렉션을 삭제 후 재생성해야 한다.

```python
# 현재: gemini-embedding-001 (3072차원)
result = genai.embed_content(
    model="models/gemini-embedding-001",
    content=text
)
```

### 10.5 관리자 이메일 추가

`.env` 또는 `.env.production`에서 쉼표로 구분하여 추가한다:

```env
DOC_ADMIN_EMAILS=22615jin@kookmin.ac.kr,another@kookmin.ac.kr
```

### 10.6 Google OAuth 클라이언트 ID 변경

1. https://console.cloud.google.com → API 및 서비스 → 사용자 인증 정보
2. OAuth 2.0 클라이언트 ID에서 "승인된 JavaScript 원본"에 도메인 추가
   - `http://localhost:8000` (로컬 테스트용)
   - `http://kdd-chatbot.duckdns.org:8000` (EC2 운영용)
3. 클라이언트 ID를 `config.js`의 `GOOGLE_CLIENT_ID`와 `.env`의 `GOOGLE_CLIENT_ID`에 설정

---

## 11. 트러블슈팅

### Gemini API 429 에러 (Rate Limit)

```
429 You exceeded your current quota
```

- 무료 티어: 분당 15회, 일 1,500회 제한
- 문서 인덱싱 시 대량 임베딩 요청으로 발생
- 해결: 1분 대기 후 재시도, 또는 GCP 결제 연결하여 유료 티어 전환

### Qdrant 벡터 차원 에러

```
Wrong input: Vector dimension error: expected dim: 1536, got 3072
```

- 임베딩 모델 변경 후 기존 컬렉션과 차원 불일치
- 해결: 인덱스 초기화 (8.8절 참고) 후 문서 재인덱싱

### Google 로그인 403 에러

```
The given origin is not allowed for the given client ID
```

- Google Cloud Console에서 승인된 JavaScript 원본에 현재 도메인이 없음
- 해결: OAuth 클라이언트 설정에서 도메인 추가 (10.6절 참고)

### Docker 빌드 실패

```
unable to evaluate symlinks in Dockerfile path
```

- `docker-compose.prod.yml`의 `context`가 상위 디렉토리(`..`)를 가리키는데 경로 문제
- 해결: 반드시 `~/rag-chatbot` 디렉토리에서 실행

### 컨테이너에서 S3 접근 불가

```
NoCredentialsError: Unable to locate credentials
```

- Docker 컨테이너 안에는 AWS 자격증명이 없음
- 해결: EC2에서 먼저 S3 파일을 다운로드한 후 `docker cp`로 컨테이너에 복사 (8.7절 참고)

---

## 12. 평가 시스템

`evaluation/evaluate.py`로 RAG 시스템의 정확도를 측정할 수 있다.

```bash
# gold_set.json에 질문-답변 쌍 작성 후
python evaluation/evaluate.py
```

`evaluation/gold_set.json` 형식:
```json
[
  {
    "question": "졸업에 필요한 학점은?",
    "answer": "130학점",
    "type": "사실형"
  },
  {
    "question": "외계인 입학 절차는?",
    "answer": null,
    "type": "답변불가형"
  }
]
```

- `answer`가 문자열이면: 답변에 해당 문자열이 포함되는지 확인
- `answer`가 null이면: "찾을 수 없" 등 거절 응답인지 확인 (환각 방지 테스트)

---

## 13. 비용 요약

| 항목 | 월 비용 |
|------|---------|
| EC2 t3.small | ~$15 (프리 티어 종료 후) |
| Gemini API | $0 (무료 티어) |
| Cohere Rerank | $0 (월 1000회 이내) |
| Qdrant | $0 (EC2 내부 Docker) |
| SQLite FTS5 | $0 (내장) |
| DuckDNS 도메인 | $0 |
| **합계** | **~$15/월** |
