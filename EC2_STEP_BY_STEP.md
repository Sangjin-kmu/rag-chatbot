# EC2 생성부터 배포까지 완벽 가이드

## 사전 준비

### 1. AWS 계정 생성
1. https://aws.amazon.com/ko/ 접속
2. "AWS 계정 생성" 클릭
3. 이메일, 비밀번호 입력
4. 신용카드 등록 (프리 티어는 무료, 확인용)
5. 전화번호 인증

### 2. AWS Console 로그인
1. https://console.aws.amazon.com 접속
2. 이메일, 비밀번호로 로그인
3. 우측 상단에서 리전 선택: "아시아 태평양(서울) ap-northeast-2"

---

## STEP 1: EC2 인스턴스 생성

### 1-1. EC2 대시보드 이동
```
AWS Console 상단 검색창에 "EC2" 입력 → EC2 클릭
```

### 1-2. 인스턴스 시작
```
좌측 메뉴: "인스턴스" 클릭
→ 우측 상단: "인스턴스 시작" 버튼 클릭 (주황색)
```

### 1-3. 이름 및 태그
```
이름: rag-chatbot
(다른 건 건드리지 않음)
```

### 1-4. 애플리케이션 및 OS 이미지 (AMI)
```
빠른 시작 탭에서:
- Ubuntu 선택 (주황색 아이콘)
- Ubuntu Server 22.04 LTS (HVM), SSD Volume Type
- 아키텍처: 64비트(x86)
```

### 1-5. 인스턴스 유형
```
인스턴스 유형: t2.micro
(프리 티어 사용 가능 - 초록색 표시 확인)
```

### 1-6. 키 페어 (로그인)
```
"새 키 페어 생성" 클릭

팝업창에서:
- 키 페어 이름: rag-chatbot-key
- 키 페어 유형: RSA
- 프라이빗 키 파일 형식: .pem (Mac/Linux) 또는 .ppk (Windows PuTTY)
- "키 페어 생성" 클릭

→ rag-chatbot-key.pem 파일이 다운로드됨
→ 이 파일을 안전한 곳에 보관! (분실 시 서버 접속 불가)
```

### 1-7. 네트워크 설정
```
"편집" 버튼 클릭

VPC: 기본값 유지
서브넷: 기본값 유지
퍼블릭 IP 자동 할당: 활성화

방화벽(보안 그룹):
- "보안 그룹 생성" 선택
- 보안 그룹 이름: rag-chatbot-sg
- 설명: Security group for RAG chatbot

인바운드 보안 그룹 규칙:
기본으로 SSH 규칙이 있음 (포트 22)

"보안 그룹 규칙 추가" 버튼 2번 클릭해서 총 3개 규칙:

규칙 1 (기본):
- 유형: SSH
- 프로토콜: TCP
- 포트 범위: 22
- 소스 유형: 내 IP (자동으로 현재 IP 입력됨)

규칙 2 (추가):
- 유형: HTTP
- 프로토콜: TCP
- 포트 범위: 80
- 소스 유형: Anywhere (0.0.0.0/0)

규칙 3 (추가):
- 유형: 사용자 지정 TCP
- 프로토콜: TCP
- 포트 범위: 8000
- 소스 유형: Anywhere (0.0.0.0/0)
```

### 1-8. 스토리지 구성
```
기본값 유지:
- 1x 30 GiB gp3 루트 볼륨
- 프리 티어: 최대 30GB까지 무료
```

### 1-9. 고급 세부 정보
```
건드리지 않음 (기본값 유지)
```

### 1-10. 요약 확인 및 시작
```
우측 "요약" 패널 확인:
- 인스턴스 개수: 1
- 인스턴스 유형: t2.micro
- 프리 티어 사용 가능 확인

"인스턴스 시작" 버튼 클릭 (주황색)
```

### 1-11. 인스턴스 시작 확인
```
"인스턴스 시작 성공" 메시지 확인
"인스턴스 보기" 버튼 클릭
```

### 1-12. 인스턴스 상태 확인
```
인스턴스 목록에서:
- 인스턴스 상태: running (초록색)
- 상태 검사: 2/2 검사 통과 (2-3분 소요)

퍼블릭 IPv4 주소 복사 (예: 3.34.123.45)
→ 이게 서버 주소!
```

---

## STEP 2: SSH 접속 준비

### 2-1. 키 파일 권한 설정 (Mac/Linux)
```bash
# 터미널 열기
cd ~/Downloads  # 키 파일 다운로드 위치로 이동

# 권한 변경 (필수!)
chmod 400 rag-chatbot-key.pem

# 안전한 곳으로 이동
mkdir -p ~/.ssh
mv rag-chatbot-key.pem ~/.ssh/
```

### 2-2. SSH 접속 테스트
```bash
# YOUR_EC2_IP를 실제 IP로 변경
ssh -i ~/.ssh/rag-chatbot-key.pem ubuntu@YOUR_EC2_IP

# 예시:
# ssh -i ~/.ssh/rag-chatbot-key.pem ubuntu@3.34.123.45

# 처음 접속 시 메시지:
# "Are you sure you want to continue connecting (yes/no/[fingerprint])?"
# → yes 입력

# 접속 성공하면:
# ubuntu@ip-xxx-xxx-xxx-xxx:~$
```

---

## STEP 3: 서버 초기 설정

### 3-1. 시스템 업데이트
```bash
# 패키지 목록 업데이트
sudo apt-get update

# 설치된 패키지 업그레이드
sudo apt-get upgrade -y
# (Y/n 물어보면 엔터)
```

### 3-2. Docker 설치
```bash
# Docker 설치
sudo apt-get install -y docker.io

# Docker Compose 설치
sudo apt-get install -y docker-compose

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker ubuntu

# 설치 확인
docker --version
docker-compose --version
```

### 3-3. Git 설치
```bash
sudo apt-get install -y git

# 설치 확인
git --version
```

### 3-4. 로그아웃 후 재접속 (중요!)
```bash
# Docker 권한 적용을 위해 로그아웃
exit

# 다시 접속
ssh -i ~/.ssh/rag-chatbot-key.pem ubuntu@YOUR_EC2_IP

# Docker 권한 확인 (sudo 없이 실행)
docker ps
# 에러 없이 실행되면 성공!
```

---

## STEP 4: 코드 배포

### 4-1. GitHub에 코드 업로드 (로컬에서)
```bash
# 로컬 터미널에서 프로젝트 폴더로 이동
cd ~/RAG_test/site

# Git 초기화 (아직 안 했다면)
git init
git add .
git commit -m "Initial commit"

# GitHub 저장소 생성 후
git remote add origin https://github.com/your-username/rag-chatbot.git
git branch -M main
git push -u origin main
```

### 4-2. EC2에서 코드 클론
```bash
# EC2 터미널에서
cd ~

# 코드 클론
git clone https://github.com/your-username/rag-chatbot.git

# 폴더 이동
cd rag-chatbot

# 파일 확인
ls -la
```

### 4-3. 환경 변수 설정
```bash
# .env.production 파일 생성
cp .env.production.example .env.production

# 편집
nano .env.production
```

nano 에디터에서 수정:
```bash
# API Keys (실제 값으로 변경)
OPENAI_API_KEY=sk-proj-...
COHERE_API_KEY=...
GOOGLE_CLIENT_ID=...

# Qdrant (EC2 내부)
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=

# 앱 설정
ALLOWED_DOMAIN=kookmin.ac.kr
DOC_ADMIN_EMAILS=22615jin@kookmin.ac.kr
JWT_SECRET=랜덤한_긴_문자열_입력_예시_abc123xyz789

# 나머지는 기본값 유지
```

저장 및 종료:
```
Ctrl + O (저장)
Enter (확인)
Ctrl + X (종료)
```

### 4-4. 스왑 메모리 추가 (t2.micro 필수!)
```bash
# 2GB 스왑 파일 생성
sudo fallocate -l 2G /swapfile

# 권한 설정
sudo chmod 600 /swapfile

# 스왑 영역 설정
sudo mkswap /swapfile

# 스왑 활성화
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 확인
free -h
# Swap 행에 2.0Gi 표시되면 성공!
```

---

## STEP 5: 서비스 실행

### 5-1. 배포 스크립트 실행
```bash
# 실행 권한 부여
chmod +x deploy/quick_deploy.sh

# 배포 실행!
./deploy/quick_deploy.sh
```

실행 과정:
```
🚀 RAG 챗봇 빠른 배포 시작...
🔨 Docker 이미지 빌드...
(5-10분 소요)
▶️  컨테이너 실행...
🏥 헬스체크 대기...
✅ 서버가 정상적으로 시작되었습니다!

접속 정보:
  - 헬스체크: http://YOUR_IP:8000/health
  - 챗봇 UI: http://YOUR_IP:8000/static/index.html
```

### 5-2. 서비스 확인
```bash
# 컨테이너 상태 확인
docker-compose -f deploy/docker-compose.prod.yml ps

# 로그 확인
docker-compose -f deploy/docker-compose.prod.yml logs -f
# (Ctrl+C로 종료)
```

---

## STEP 6: 접속 및 테스트

### 6-1. 브라우저에서 접속
```
http://YOUR_EC2_IP:8000/static/index.html

예시: http://3.34.123.45:8000/static/index.html
```

### 6-2. 로그인 테스트
```
1. Google 로그인 버튼 클릭
2. 자동으로 로그인됨 (테스트 모드)
3. "문서관리" 메뉴 표시 확인
```

### 6-3. 문서 업로드 테스트
```
1. "문서관리" 클릭
2. PDF 파일 드래그 앤 드롭
3. "업로드 시작" 클릭
4. 인덱싱 완료 대기
```

### 6-4. 챗봇 테스트
```
1. "학칙 질의응답" 클릭
2. 질문 입력: "졸업 학점은?"
3. 답변 확인
```

---

## 문제 해결

### 접속이 안 돼요
```bash
# 1. 보안 그룹 확인
AWS Console → EC2 → 보안 그룹 → rag-chatbot-sg
→ 인바운드 규칙에 포트 8000 있는지 확인

# 2. 서비스 상태 확인
docker-compose -f deploy/docker-compose.prod.yml ps

# 3. 로그 확인
docker-compose -f deploy/docker-compose.prod.yml logs
```

### 메모리 부족 에러
```bash
# 스왑 메모리 확인
free -h

# 스왑이 없으면 위 STEP 4-4 참고
```

### Docker 권한 에러
```bash
# 로그아웃 후 재접속
exit
ssh -i ~/.ssh/rag-chatbot-key.pem ubuntu@YOUR_EC2_IP
```

---

## 다음 단계

### 1. 도메인 연결 (선택)
- Route 53에서 도메인 구매
- A 레코드로 EC2 IP 연결

### 2. HTTPS 설정 (선택)
- Nginx 설치
- Let's Encrypt SSL 인증서

### 3. 백업 자동화
- cron으로 매일 백업
- S3에 업로드

### 4. 모니터링
- CloudWatch 알람 설정
- 디스크/메모리 사용량 모니터링

---

## 비용 확인

### AWS Billing 확인
```
AWS Console 우측 상단 계정명 클릭
→ "결제 대시보드"
→ 프리 티어 사용량 확인
```

### 프리 티어 한도
- EC2 t2.micro: 월 750시간 (24시간 * 31일 = 744시간)
- EBS 스토리지: 30GB
- 데이터 전송: 15GB/월

---

## 요약

1. ✅ EC2 인스턴스 생성 (t2.micro, Ubuntu 22.04)
2. ✅ 보안 그룹 설정 (포트 22, 80, 8000)
3. ✅ SSH 접속
4. ✅ Docker, Git 설치
5. ✅ 코드 클론 및 환경 변수 설정
6. ✅ 스왑 메모리 추가
7. ✅ 배포 스크립트 실행
8. ✅ 브라우저에서 접속

**예상 소요 시간: 30분**
**예상 비용: $0 (프리 티어) → $13/월 (프리 티어 종료 후)**
