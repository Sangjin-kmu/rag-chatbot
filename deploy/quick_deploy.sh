#!/bin/bash
# 빠른 배포 스크립트 (EC2에서 실행)

set -e

echo "🚀 RAG 챗봇 빠른 배포 시작..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 환경 변수 확인
if [ ! -f .env.production ]; then
    echo -e "${RED}❌ .env.production 파일이 없습니다.${NC}"
    echo ""
    echo "다음 명령어로 생성하세요:"
    echo "  cp .env.production.example .env.production"
    echo "  nano .env.production"
    echo ""
    echo "필수 입력 항목:"
    echo "  - OPENAI_API_KEY"
    echo "  - COHERE_API_KEY"
    echo "  - QDRANT_URL (Qdrant Cloud)"
    echo "  - QDRANT_API_KEY"
    echo "  - ELASTICSEARCH_URL (Elastic Cloud)"
    echo "  - ELASTICSEARCH_PASSWORD"
    exit 1
fi

# 2. Docker 확인
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
    echo "deploy/setup_ec2.sh를 먼저 실행하세요."
    exit 1
fi

# 3. 이전 컨테이너 중지
echo -e "${YELLOW}🛑 이전 컨테이너 중지...${NC}"
docker compose -f deploy/docker-compose.prod.yml down 2>/dev/null || true

# 4. 이미지 빌드
echo -e "${YELLOW}🔨 Docker 이미지 빌드...${NC}"
docker compose -f deploy/docker-compose.prod.yml build

# 5. 컨테이너 실행
echo -e "${YELLOW}▶️  컨테이너 실행...${NC}"
docker compose -f deploy/docker-compose.prod.yml up -d

# 6. 헬스체크
echo -e "${YELLOW}🏥 헬스체크 대기...${NC}"
sleep 5

for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✅ 서버가 정상적으로 시작되었습니다!${NC}"
        echo ""
        echo "접속 정보:"
        echo "  - 헬스체크: http://$(curl -s ifconfig.me):8000/health"
        echo "  - 챗봇 UI: http://$(curl -s ifconfig.me):8000/static/index.html"
        echo ""
        echo "로그 확인:"
        echo "  docker compose -f deploy/docker-compose.prod.yml logs -f"
        exit 0
    fi
    echo "  대기 중... ($i/30)"
    sleep 2
done

echo -e "${RED}❌ 서버 시작 실패${NC}"
echo "로그를 확인하세요:"
echo "  docker compose -f deploy/docker-compose.prod.yml logs"
exit 1
