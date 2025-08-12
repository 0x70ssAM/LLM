#!/bin/bash
set -e

# === Update system packages ===
sudo apt update -y

# === Install prerequisites ===
sudo apt install -y curl apt-transport-https ca-certificates gnupg lsb-release

# === Install Ollama ===
curl -fsSL https://ollama.com/install.sh | sh

# Start and enable the Ollama service
sudo systemctl start ollama
sudo systemctl enable ollama

# Check Ollama version
ollama --version

# Pull models
ollama pull llama3
ollama pull gpt-oss
#ollama pull deepseek-r1:14b  # optional

# Replace Ollama systemd service to listen on all interfaces
sudo tee /etc/systemd/system/ollama.service > /dev/null << 'EOF'
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin"
Environment="OLLAMA_HOST=0.0.0.0"

[Install]
WantedBy=default.target
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama

# === Install Docker Engine ===
sudo apt install -y docker.io

# Enable & start Docker
sudo systemctl enable docker
sudo systemctl start docker

# === Install docker-compose (binary, not plugin) ===
DOCKER_COMPOSE_VERSION="1.29.2"
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify docker-compose
docker-compose --version

# === Build & run your app via docker-compose ===
cd "$(dirname "$0")"   # change to the script's directory
docker-compose build
docker-compose up -d

