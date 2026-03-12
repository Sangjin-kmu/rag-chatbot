# 완전 무료 배포 가이드

## 비용 구조

### 완전 무료
- ✅ Qdrant Cloud: 1GB 무료 (영구)
- ✅ SQLite FTS5: 완전 무료 (서버 내장)
- ✅ EC2 프리 티어: 12개월 무료 (t2.micro)

### 사용량 기반 (API 호출 시에만)
- OpenAI API: 사용한 만큼만 ($0.0001/1K tokens)
- Cohere Rerank: 월 1000회 무료

## 1단계: Qdrant Cloud 설정 (5분)

1. https://cloud.qdrant.io 접속
2. 회원가입 (GitHub/Google 계정으로 가능)
3. "Create Cluster" 클릭
4. 설정:
   - Name: rag-chatbot
   - Cloud: AWS
   - Region: ap-northeast-2 (서울)
   - Cluster type: Free (1GB)
5. Create 클릭
6. Cluster URL과 API Key 복사

## 2단계: 로컬 테스트

### 패키지 재설치
```bash
pip install -r requirements.txt
```

### .env 파일 수정
```bash
# Qdrant Cloud 정보 입력
QDRANT_URL=https://your-cluster-id.qdrant.io
QDRANT_API_KEY=your_api_key_here
```

### 서버 실행
```bash
python main.py
```

### 접속 확인
```
http://localhost:8000/static/index.html
```

## 3단계: EC2 프리 티어 배포

### EC2 인스턴스 생성
1. AWS Console → EC2 → Launch Instance
2. 설정:
   - Name: rag-chatbot
   - AMI: Ubuntu Server 22.04 LTS (프리 티어)
   - Instance type: t2.micro (프리 티어)
   - Key pair: 새로 생성
   - Security group:
     - SSH (22): My IP
     - HTTP (80): Anywhere
     - Custom TCP (8000): Anywhere

### 배포
```bash
# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 초기 설정
curl -O https://raw.githubusercontent.com/your-repo/deploy/setup_ec2.sh
chmod +x setup_ec2.sh
./setup_ec2.sh

# 로그아웃 후 재접속
exit
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 코드 클론
git clone https://github.com/your-repo/rag-chatbot.git
cd rag-chatbot

# 환경 변수 설정
cp .env.production.example .env.production
nano .env.production
# Qdrant Cloud URL과 API Key 입력

# 배포
chmod +x deploy/quick_deploy.sh
./deploy/quick_deploy.sh
```

### 접속
```
http://YOUR_EC2_IP:8000/static/index.html
```

## 비용 최적화 팁

### 1. OpenAI API 비용 절감
- 모델: gpt-4-turbo-preview 대신 gpt-3.5-turbo 사용 (10배 저렴)
- 임베딩: text-embedding-3-small 사용 (이미 적용됨)

### 2. Cohere Rerank 무료 사용
- 월 1000회 무료
- 초과 시: $1/1000 requests

### 3. EC2 비용
- 프리 티어: 12개월 무료 (t2.micro, 750시간/월)
- 프리 티어 종료 후: ~$8/월
- 사용하지 않을 때 인스턴스 중지

### 4. Qdrant Cloud
- 1GB 무료 (영구)
- 약 100만 개 청크 저장 가능
- 초과 시: $25/월 (4GB)

## 예상 월 비용

### 소규모 (학생 프로젝트)
- EC2: $0 (프리 티어) 또는 $8
- Qdrant: $0 (1GB 이내)
- OpenAI: ~$5 (월 100회 질문)
- Cohere: $0 (1000회 이내)
- **총: $5~13/월**

### 중규모 (학과 전체)
- EC2: $8 (t2.micro)
- Qdrant: $0 (1GB 이내)
- OpenAI: ~$20 (월 500회 질문)
- Cohere: $2 (2000회)
- **총: $30/월**

## 다음 단계

1. ✅ Qdrant Cloud 가입
2. ✅ 로컬 테스트
3. ✅ EC2 배포
4. 🎯 문서 업로드
5. 🎯 사용자 테스트
