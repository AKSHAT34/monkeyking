#!/bin/bash
# MonkeyKing — Deploy to VPS
# Usage: ssh root@<YOUR_VPS_IP> 'bash -s' < deploy.sh

set -e

echo "🐵 MonkeyKing — Deploying..."

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# Create app directory
mkdir -p /opt/monkeyking
cd /opt/monkeyking

echo "Building and starting containers..."
docker compose up -d --build

echo ""
echo "✅ MonkeyKing is running!"
echo "   Frontend: http://$(hostname -I | awk '{print $1}'):3000"
echo "   Backend:  http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop:      docker compose down"
