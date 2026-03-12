# KDD RAG Chatbot - 완전 무료 버전

국민대학교 학칙 및 학사규정 RAG 기반 챗봇 시스템

## 아키텍처

- **검색**: Qdrant (벡터) + SQLite FTS5 (BM25) + RRF + Cohere Rerank
- **생성**: OpenAI GPT-4
- **배포**: EC2 올인원 (Docker)

## 비용

- EC2 프리 티어: $0 (12개월)
- 프리 티어 종료 후: ~$15/월 (t3.small)
- API 사용료: ~$5/월 (소규모)

## 빠른 시작

### 로컬 개발
```bash
# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
nano .env  # API 키 입력

# Qdrant 실행 (Docker)
docker run -p 6333:6333 qdrant/qdrant

# 서버 실행
python main.py
```

### EC2 배포
자세한 내용은 `EC2_STEP_BY_STEP.md` 참고

```bash
# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 코드 클론
git clone https://github.com/your-username/rag-chatbot.git
cd rag-chatbot

# 환경 변수 설정
cp .env.production.example .env.production
nano .env.production

# 배포
chmod +x deploy/quick_deploy.sh
./deploy/quick_deploy.sh
```

## 문서

- `EC2_STEP_BY_STEP.md`: EC2 생성부터 배포까지 완벽 가이드
- `EC2_ALL_IN_ONE.md`: EC2 올인원 구성 상세 설명
- `FREE_DEPLOYMENT.md`: 무료 배포 가이드
- `SETUP_GUIDE.md`: 로컬 개발 환경 설정

## 주요 기능

- ✅ 하이브리드 검색 (BM25 + 벡터 + RRF)
- ✅ Cohere Rerank로 정확도 향상
- ✅ 구조 보존 전처리 (표, 제목, 리스트)
- ✅ 의미 단위 청킹
- ✅ 근거 기반 답변 생성
- ✅ 출처 자동 표시

## 프로젝트 구조

```
.
├── main.py                    # FastAPI 서버
├── config.py                  # 설정
├── auth.py                    # 인증
├── requirements.txt           # 의존성
├── preprocessing/             # 전처리
│   ├── html_parser.py
│   ├── pdf_parser.py
│   └── chunker.py
├── search/                    # 검색
│   └── free_hybrid_search.py
├── generation/                # 생성
│   └── generator.py
├── deploy/                    # 배포
│   ├── docker-compose.prod.yml
│   ├── Dockerfile
│   └── quick_deploy.sh
└── scripts/                   # 유틸리티
    ├── upload_docs.py
    └── test_search.py
```

## 라이선스

MIT
