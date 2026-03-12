# AWS EC2 배포 가이드

## 사전 준비

### 1. Qdrant Cloud 설정 (무료)
1. https://cloud.qdrant.io 접속
2. 회원가입 및 로그인
3. "Create Cluster" 클릭
4. Free tier 선택
5. Cluster URL과 API Key 복사

### 2. Elastic Cloud 설정 (무료 14일)
1. https://cloud.elastic.co 접속
2. 회원가입 및 로그인
3. "Create deployment" 클릭
4. Free trial 선택
5. Elasticsearch endpoint와 password 복사

### 3. AWS EC2 인스턴스 생성
1. AWS Console → EC2 → Launch Instance
2. 설정:
   - Name: rag-chatbot
   - AMI: Ubuntu Server 22.04 LTS
   - Instance type: t3.medium (최소 t3.small)
   - Key pair: 새로 생성 또는 기존 사용
   - Security group:
     - SSH (22): My IP
     - HTTP (80): Anywhere
     - HTTPS (443): Anywhere
     - Custom TCP (8000): Anywhere
3. Launch instance

## 배포 단계

### 1단계: EC2 접속
```bash
# SSH 키 권한 설정
chmod 400 your-key.pem

# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### 2단계: EC2 초기 설정
```bash
# 설정 스크립트 다운로드
curl -O https://raw.githubusercontent.com/your-repo/deploy/setup_ec2.sh
chmod +x setup_ec2.sh

# 실행
./setup_ec2.sh

# 로그아웃 후 재접속 (Docker 권한 적용)
exit
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

### 3단계: 코드 배포
```bash
# Git 클론
git clone https://github.com/your-repo/rag-chatbot.git
cd rag-chatbot

# 환경 변수 설정
cp .env.production.example .env.production
nano .env.production
```

`.env.production` 파일 편집:
```bash
# Qdrant Cloud 정보 입력
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# Elastic Cloud 정보 입력
ELASTICSEARCH_URL=https://your-cluster.es.io:9243
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=your_elastic_password

# OpenAI, Cohere API 키 입력
OPENAI_API_KEY=sk-...
COHERE_API_KEY=...

# Google OAuth (나중에 설정)
GOOGLE_CLIENT_ID=...

# 관리자 이메일
DOC_ADMIN_EMAILS=your@kookmin.ac.kr

# JWT 비밀키 (랜덤 문자열)
JWT_SECRET=production_secret_key_12345
```

### 4단계: Docker로 배포
```bash
# 배포 스크립트 실행 권한
chmod +x deploy/deploy.sh

# 배포
./deploy/deploy.sh
```

### 5단계: 프론트엔드 설정
로컬에서 `config.js` 수정:
```javascript
window.APP_CONFIG = {
  API_BASE: "http://YOUR_EC2_PUBLIC_IP:8000",
  GOOGLE_CLIENT_ID: "your_google_client_id",
  ALLOWED_DOMAIN: "kookmin.ac.kr"
};
```

Git push:
```bash
git add config.js
git commit -m "Update API_BASE for production"
git push
```

EC2에서 pull:
```bash
cd rag-chatbot
git pull
./deploy/deploy.sh
```

### 6단계: 접속 확인
브라우저에서:
- `http://YOUR_EC2_PUBLIC_IP:8000/health` → {"status":"ok"}
- `http://YOUR_EC2_PUBLIC_IP:8000/static/index.html` → 챗봇 UI

## 문서 업로드

### 방법 1: 웹 UI
1. `http://YOUR_EC2_PUBLIC_IP:8000/static/index.html` 접속
2. 로그인 (관리자 계정)
3. "문서관리" 메뉴에서 업로드

### 방법 2: 스크립트
```bash
# 로컬에서 실행
python scripts/upload_docs.py \
  http://YOUR_EC2_PUBLIC_IP:8000 \
  YOUR_TOKEN \
  ./documents
```

### 방법 3: EC2에서 직접
```bash
# EC2 접속
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
cd rag-chatbot

# 문서 복사 (로컬 → EC2)
# 로컬 터미널에서:
scp -i your-key.pem -r ./documents ubuntu@YOUR_EC2_PUBLIC_IP:~/rag-chatbot/

# EC2에서 업로드 스크립트 실행
python3 scripts/upload_docs.py \
  http://localhost:8000 \
  YOUR_TOKEN \
  ./documents
```

## Nginx 설정 (선택사항)

도메인이 있으면 Nginx로 리버스 프록시 설정:

```bash
# Nginx 설치
sudo apt-get install -y nginx

# 설정 파일 복사
sudo cp deploy/nginx.conf /etc/nginx/sites-available/rag-chatbot

# 도메인 수정
sudo nano /etc/nginx/sites-available/rag-chatbot
# server_name을 실제 도메인으로 변경

# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/rag-chatbot /etc/nginx/sites-enabled/

# 기본 설정 제거
sudo rm /etc/nginx/sites-enabled/default

# Nginx 재시작
sudo nginx -t
sudo systemctl restart nginx
```

이제 `http://your-domain.com`으로 접속 가능!

## SSL 인증서 (Let's Encrypt)

```bash
# Certbot 설치
sudo apt-get install -y certbot python3-certbot-nginx

# 인증서 발급
sudo certbot --nginx -d your-domain.com

# 자동 갱신 확인
sudo certbot renew --dry-run
```

이제 `https://your-domain.com`으로 접속 가능!

## 모니터링

### 로그 확인
```bash
# 실시간 로그
docker compose -f deploy/docker-compose.prod.yml logs -f

# 최근 100줄
docker compose -f deploy/docker-compose.prod.yml logs --tail=100
```

### 컨테이너 상태
```bash
docker compose -f deploy/docker-compose.prod.yml ps
```

### 재시작
```bash
docker compose -f deploy/docker-compose.prod.yml restart
```

### 중지
```bash
docker compose -f deploy/docker-compose.prod.yml down
```

## 백업

### 업로드 파일 백업
```bash
# EC2에서
tar -czf uploads-backup-$(date +%Y%m%d).tar.gz uploads/

# 로컬로 다운로드
scp -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP:~/rag-chatbot/uploads-backup-*.tar.gz ./
```

### 벡터 DB 백업
Qdrant Cloud는 자동 백업됨 (무료 티어도 포함)

## 문제 해결

### 서버가 안 떠요
```bash
# 로그 확인
docker compose -f deploy/docker-compose.prod.yml logs

# 컨테이너 재시작
docker compose -f deploy/docker-compose.prod.yml restart
```

### Qdrant 연결 실패
- `.env.production`의 `QDRANT_URL`과 `QDRANT_API_KEY` 확인
- Qdrant Cloud 대시보드에서 클러스터 상태 확인

### Elasticsearch 연결 실패
- `.env.production`의 `ELASTICSEARCH_URL`, `ELASTICSEARCH_USER`, `ELASTICSEARCH_PASSWORD` 확인
- Elastic Cloud 대시보드에서 deployment 상태 확인

### 메모리 부족
```bash
# 스왑 메모리 추가
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 비용 최적화

### EC2 인스턴스
- 개발/테스트: t3.small ($0.0208/시간)
- 프로덕션: t3.medium ($0.0416/시간)
- 사용하지 않을 때 중지하면 스토리지 비용만 발생

### Qdrant Cloud
- Free tier: 1GB 무료 (영구)
- 소규모 프로젝트는 충분

### Elastic Cloud
- Free trial: 14일 무료
- 이후 $95/월 (Standard)
- 대안: OpenSearch (AWS) 또는 자체 호스팅

## 다음 단계

1. ✅ EC2 인스턴스 생성
2. ✅ Qdrant Cloud 설정
3. ✅ Elastic Cloud 설정
4. ✅ 코드 배포
5. ✅ 문서 업로드
6. 🎯 Google OAuth 설정
7. 🎯 도메인 연결
8. 🎯 SSL 인증서 설정
9. 🎯 모니터링 설정
