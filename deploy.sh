#!/bin/bash
set -e

echo "🚀 Деплой на VPS..."
ssh $SSH_USER@$SSH_HOST "cd ~/real-madrid-bot && git pull && docker compose down && docker compose up -d --build"