#!/bin/bash
# 배포 스크립트

set -e

echo "🚀 배포 시작..."

# 환경 변수 확인
if [ ! -f .env.production ]; then
    echo "❌ .env.production 파일이 없습니다."
    echo "   .env.production.example을 복사해서 .env.production을 만들고 값을 입력하세요."
    exit 1
fi

# 이전 컨테이너 중지 및 제거
echo "🛑 이전 컨테이너 중지..."
docker compose -f deploy/docker-compose.prod.yml down || true

# 이미지 빌드
echo "🔨 Docker 이미지 빌드..."
docker compose -f deploy/docker-compose.prod.yml build

# 컨테이너 실행
echo "▶️  컨테이너 실행..."
docker compose -f deploy/docker-compose.prod.yml up -d

# 로그 확인
echo "📋 로그 확인..."
docker compose -f deploy/docker-compose.prod.yml logs -f --tail=50
