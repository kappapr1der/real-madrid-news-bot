#!/bin/bash
echo "☕ Обновляем зависимости Coffee Bot..."
cd ~/coffee-bot || exit 1

# Убиваем старый процесс (если запущен)
PID=$(pgrep -f "python3 main.py")
if [ -n "$PID" ]; then
    echo "🛑 Останавливаем старый процесс Coffee Bot (PID=$PID)..."
    kill -9 $PID
else
    echo "ℹ️ Coffee Bot не был запущен."
fi

# Устанавливаем зависимости из requirements.txt
pip3 install -r requirements.txt --force-reinstall

echo "✅ Зависимости обновлены!"

# Запускаем Coffee Bot заново через твой startbot.sh
echo "🚀 Запускаем Coffee Bot..."
bash ~/coffee-bot/startbot.sh &

echo "✅ Coffee Bot перезапущен!"
