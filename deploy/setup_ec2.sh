#!/bin/bash
# EC2 인스턴스 초기 설정 스크립트

set -e

echo "🚀 EC2 인스턴스 설정 시작..."

# 시스템 업데이트
echo "📦 시스템 업데이트..."
sudo apt-get update
sudo apt-get upgrade -y

# Docker 설치
echo "🐳 Docker 설치..."
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Docker 권한 설정
sudo usermod -aG docker $USER

# Git 설치
echo "📥 Git 설치..."
sudo apt-get install -y git

# 방화벽 설정
echo "🔥 방화벽 설정..."
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 8000
sudo ufw --force enable

echo "✅ EC2 설정 완료!"
echo "⚠️  로그아웃 후 다시 로그인하여 Docker 권한을 적용하세요."
