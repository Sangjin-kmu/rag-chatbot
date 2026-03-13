#!/bin/bash
# EC2 배포 스크립트
set -e

echo "📥 최신 코드 pull..."
git pull origin main

echo "🛑 기존 컨테이너 종료..."
docker-compose -f deploy/docker-compose.prod.yml down

echo "🔨 빌드 + 시작..."
docker-compose -f deploy/docker-compose.prod.yml up -d --build

echo "✅ 배포 완료"
docker-compose -f deploy/docker-compose.prod.yml ps
