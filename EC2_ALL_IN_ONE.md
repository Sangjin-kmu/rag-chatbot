# EC2 올인원 배포 가이드 (완전 무료!)

## 아키텍처

**EC2 하나에 모든 것:**
- FastAPI 서버 (Docker)
- Qdrant 벡터 DB (Docker)
- SQLite FTS5 (내장)

**비용: $0** (EC2 프리 티어 12개월)

## 장점

1. ✅ 완전 무료 (프리 티어 기간)
2. ✅ 설정 간단 (외부 DB 불필요)
3. ✅ 네트워크 지연 없음 (모두 같은 서버)
4. ✅ 관리 편함 (하나의 서버만)

## 단점

1. ⚠️ 스토리지 제한 (30GB 프리 티어)
2. ⚠️ 메모리 제한 (1GB, t2.micro)
3. ⚠️ 백업 직접 관리 필요

## 권장 사양

### 프리 티어 (무료)
- Instance: t2.micro
- vCPU: 1
- RAM: 1GB
- Storage: 30GB
- 용량: 문서 ~1000개, 사용자 ~50명

### 소규모 프로덕션 ($8/월)
- Instance: t3.small
- vCPU: 2
- RAM: 2GB
- Storage: 50GB
- 용량: 문서 ~5000개, 사용자 ~200명

## 배포 단계

### 1. EC2 인스턴스 생성

1. AWS Console → EC2 → Launch Instance
2. 설정:
   - Name: rag-chatbot-allinone
   - AMI: Ubuntu Server 22.04 LTS
   - Instance type: t2.micro (프리 티어)
   - Storage: 30GB (프리 티어)
   - Key pair: 새로 생성 또는 기존 사용
   - Security group:
     - SSH (22): My IP
     - HTTP (80): Anywhere
     - Custom TCP (8000): Anywhere

### 2. EC2 접속 및 초기 설정

```bash
# SSH 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 초기 설정 스크립트 실행
sudo apt-get update
sudo apt-get upgrade -y

# Docker 설치
sudo apt-get install -y docker.io docker-compose
sudo usermod -aG docker ubuntu

# Git 설치
sudo apt-get install -y git

# 로그아웃 후 재접속 (Docker 권한 적용)
exit
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
```

### 3. 코드 배포

```bash
# 코드 클론
git clone https://github.com/your-username/rag-chatbot.git
cd rag-chatbot

# 환경 변수 설정
cp .env.production.example .env.production
nano .env.production
```

`.env.production` 편집:
```bash
# API Keys
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...
GOOGLE_CLIENT_ID=...

# Qdrant (EC2 내부)
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=

# 앱 설정
DOC_ADMIN_EMAILS=your@kookmin.ac.kr
JWT_SECRET=랜덤한_비밀키_입력
```

### 4. Docker Compose로 실행

```bash
# 배포 스크립트 실행
chmod +x deploy/quick_deploy.sh
./deploy/quick_deploy.sh
```

### 5. 접속 확인

```bash
# 헬스체크
curl http://localhost:8000/health

# 브라우저에서
http://YOUR_EC2_IP:8000/static/index.html
```

## 모니터링

### 로그 확인
```bash
cd rag-chatbot
docker-compose -f deploy/docker-compose.prod.yml logs -f
```

### 컨테이너 상태
```bash
docker-compose -f deploy/docker-compose.prod.yml ps
```

### 디스크 사용량
```bash
df -h
```

### 메모리 사용량
```bash
free -h
```

## 백업

### 1. Qdrant 데이터 백업
```bash
# 백업 생성
docker-compose -f deploy/docker-compose.prod.yml exec qdrant \
  tar -czf /qdrant/storage/backup-$(date +%Y%m%d).tar.gz /qdrant/storage/collections

# 로컬로 다운로드
scp -i your-key.pem ubuntu@YOUR_EC2_IP:~/rag-chatbot/qdrant_data/backup-*.tar.gz ./
```

### 2. SQLite 데이터 백업
```bash
# 백업 생성
tar -czf data-backup-$(date +%Y%m%d).tar.gz data/

# 로컬로 다운로드
scp -i your-key.pem ubuntu@YOUR_EC2_IP:~/rag-chatbot/data-backup-*.tar.gz ./
```

### 3. 업로드 파일 백업
```bash
# 백업 생성
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz uploads/

# 로컬로 다운로드
scp -i your-key.pem ubuntu@YOUR_EC2_IP:~/rag-chatbot/uploads-backup-*.tar.gz ./
```

## 성능 최적화

### 1. 스왑 메모리 추가 (t2.micro 필수!)
```bash
# 2GB 스왑 생성
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2. Docker 메모리 제한
`deploy/docker-compose.prod.yml` 수정:
```yaml
services:
  qdrant:
    mem_limit: 512m
  app:
    mem_limit: 512m
```

### 3. 로그 로테이션
```bash
# Docker 로그 크기 제한
sudo nano /etc/docker/daemon.json
```

추가:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

재시작:
```bash
sudo systemctl restart docker
```

## 문제 해결

### 메모리 부족
```bash
# 스왑 메모리 확인
free -h

# 스왑 추가 (위 참고)
```

### 디스크 부족
```bash
# 사용량 확인
df -h

# Docker 정리
docker system prune -a

# 로그 정리
docker-compose -f deploy/docker-compose.prod.yml logs --tail=0
```

### Qdrant 연결 실패
```bash
# Qdrant 재시작
docker-compose -f deploy/docker-compose.prod.yml restart qdrant

# 로그 확인
docker-compose -f deploy/docker-compose.prod.yml logs qdrant
```

## 업그레이드 경로

### 프리 티어 → 유료 (필요 시)

**t3.small ($8/월)**
- RAM: 2GB
- 문서 ~5000개
- 사용자 ~200명

**t3.medium ($16/월)**
- RAM: 4GB
- 문서 ~20000개
- 사용자 ~1000명

## 비용 비교

### EC2 올인원
- EC2 t2.micro: $0 (12개월) → $8/월
- OpenAI API: ~$5/월
- Cohere API: $0 (1000회 이내)
- **총: $5/월 (프리 티어) → $13/월**

### 클라우드 DB 사용
- EC2 t2.micro: $0 → $8/월
- Qdrant Cloud: $0 (1GB)
- OpenAI API: ~$5/월
- Cohere API: $0
- **총: $5/월 → $13/월**

**결론: 비용 동일, EC2 올인원이 더 간단!**

## 다음 단계

1. ✅ EC2 인스턴스 생성
2. ✅ Docker 설치
3. ✅ 코드 배포
4. ✅ 서비스 실행
5. 🎯 문서 업로드
6. 🎯 사용자 테스트
7. 🎯 백업 자동화
