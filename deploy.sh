#!/bin/bash
set -e

PROJECT_DIR="/home/ec2-user/dockpulse"
REPO_URL="https://github.com/purvanshiattri/DockPulse.git"

echo "=== Starting deployment ==="

if [ ! -d "$PROJECT_DIR/.git" ]; then
    echo "Directory $PROJECT_DIR is not a git repository. Re-initializing clone..."
    # Clean up directory to allow fresh clone
    rm -rf "$PROJECT_DIR"
    git clone "$REPO_URL" "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"
echo "Fetching latest changes from repository..."
git fetch --all
git reset --hard origin/main
git pull origin main

echo "Rebuilding and restarting services via Docker Compose..."
docker-compose up -d --build --remove-orphans

echo "Verifying running containers..."
docker ps

echo "=== Deployment completed successfully ==="
