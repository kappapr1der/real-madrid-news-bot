#!/bin/bash
set -e

LOG_DIR="/home/coffee/coffee-bot/logs"
LOG_FILE="$LOG_DIR/deploy.log"

mkdir -p "$LOG_DIR"

# Пишем и в терминал, и в лог-файл
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================"
echo "🚀 Coffee Bot deployment started at $(date)"
echo "============================"

cd /home/coffee/coffee-bot

# Активируем виртуальное окружение
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Обновляем pip
pip install --upgrade pip

# Устанавливаем зависимости из requirements.txt
echo "📚 Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Страхуемся — докидываем основные модули, если вдруг не указаны
echo "🛠 Checking and installing essential modules..."
pip install aiogram requests feedparser beautifulsoup4 lxml loguru schedule apscheduler deep-translator googletrans==4.0.0-rc1 python-dotenv tenacity

# Выходим из окружения
deactivate

# Перезапускаем сервисы
echo "🔄 Restarting systemd services..."
sudo systemctl daemon-reload
sudo systemctl restart coffee-bot.target

# Проверяем статус
echo "✅ Deployment finished. Current status:"
systemctl status coffee-bot --no-pager -l | head -n 20

echo "============================"
echo "✔️ Finished at $(date)"
echo "Log saved to $LOG_FILE"
echo "============================"
