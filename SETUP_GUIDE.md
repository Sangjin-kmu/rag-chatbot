# 설치 및 실행 가이드

## 1단계: 환경 준비

### Python 설치 확인
```bash
python --version  # Python 3.9 이상 필요
```

### Docker 설치 확인
```bash
docker --version
docker-compose --version
```

## 2단계: 프로젝트 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (필수!)
nano .env
```

필수 설정 항목:
```
OPENAI_API_KEY=sk-...                    # OpenAI API 키
COHERE_API_KEY=...                       # Cohere API 키
GOOGLE_CLIENT_ID=...                     # Google OAuth 클라이언트 ID
JWT_SECRET=랜덤한_비밀키_여기에_입력      # JWT 서명용 비밀키
DOC_ADMIN_EMAILS=admin@kookmin.ac.kr     # 관리자 이메일 (쉼표로 구분)
```

## 3단계: 검색 엔진 실행

### Docker Compose로 Qdrant + Elasticsearch 실행
```bash
# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 상태 확인
docker-compose ps
```

정상 실행 확인:
- Qdrant: http://localhost:6333/dashboard
- Elasticsearch: http://localhost:9200

## 4단계: FastAPI 서버 실행

```bash
# 개발 모드 (자동 재시작)
python main.py

# 또는 uvicorn 직접 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

서버 실행 확인:
```bash
curl http://localhost:8000/health
# 응답: {"status":"ok"}
```

## 5단계: 문서 업로드

### 방법 1: 웹 UI 사용
1. 브라우저에서 `http://localhost:8000/static/index.html` 접속
2. Google 계정으로 로그인 (kookmin.ac.kr 도메인)
3. 관리자 계정이면 "문서관리" 메뉴 표시
4. 파일 드래그 앤 드롭 또는 선택해서 업로드

### 방법 2: 스크립트 사용
```bash
# 먼저 로그인해서 토큰 받기
# (웹 UI에서 로그인 후 개발자 도구에서 토큰 복사)

# 단일 파일 업로드
curl -X POST "http://localhost:8000/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@document.pdf"

# 디렉토리 일괄 업로드
python scripts/upload_docs.py http://localhost:8000 YOUR_TOKEN ./documents
```

## 6단계: 테스트

### 검색 테스트
```bash
python scripts/test_search.py http://localhost:8000 YOUR_TOKEN "졸업 학점은?"
```

### 평가 실행
```bash
# gold_set.json 편집 후
python evaluation/evaluate.py
```

## 문제 해결

### Qdrant 연결 실패
```bash
# Qdrant 재시작
docker-compose restart qdrant

# 로그 확인
docker-compose logs qdrant
```

### Elasticsearch 연결 실패
```bash
# Elasticsearch 재시작
docker-compose restart elasticsearch

# 메모리 부족 시 docker-compose.yml에서 메모리 조정
# ES_JAVA_OPTS=-Xms512m -Xmx512m
```

### OpenAI API 오류
- API 키 확인: `.env` 파일의 `OPENAI_API_KEY`
- 잔액 확인: https://platform.openai.com/account/usage

### Cohere API 오류
- API 키 확인: `.env` 파일의 `COHERE_API_KEY`
- 무료 티어: https://cohere.com/pricing

### Google OAuth 오류
- 클라이언트 ID 확인
- 허용된 도메인 확인 (kookmin.ac.kr)

## 성능 최적화

### 1. 청킹 파라미터 조정
`.env` 파일:
```
CHUNK_SIZE=550        # 청크 크기 (토큰)
CHUNK_OVERLAP=100     # 오버랩 (토큰)
```

### 2. 검색 파라미터 조정
`.env` 파일:
```
BM25_TOP_K=20         # BM25 상위 K개
VECTOR_TOP_K=20       # 벡터 상위 K개
RERANK_TOP_K=6        # Rerank 후 최종 K개
FINAL_CONTEXT_SIZE=5  # LLM에 전달할 컨텍스트 수
```

### 3. HNSW 파라미터 조정
`search/hybrid_search.py` 파일의 `init_collections()`:
```python
hnsw_config={
    "m": 32,              # 16~64 (높을수록 정확, 메모리↑)
    "ef_construct": 200   # 100~500 (높을수록 정확, 느림)
}
```

검색 시:
```python
search_params={"hnsw_ef": 128}  # 64~256 (높을수록 정확, 느림)
```

## 배포

### Docker로 전체 시스템 배포
```bash
# Dockerfile 생성 (FastAPI 서버용)
# docker-compose.yml에 app 서비스 추가
# 전체 빌드 및 실행
docker-compose up -d --build
```

### 클라우드 배포
- FastAPI: Heroku, Railway, Fly.io
- Qdrant: Qdrant Cloud (무료 티어 있음)
- Elasticsearch: Elastic Cloud (무료 티어 있음)

## 다음 단계

1. ✅ 검색 엔진 실행
2. ✅ 서버 실행
3. ✅ 문서 업로드
4. ✅ 테스트
5. 🎯 골드셋 작성 및 평가
6. 🎯 파라미터 튜닝
7. 🎯 프로덕션 배포
