#!/bin/bash
cd /home/coffee/coffee-bot || exit

# Добавляем изменения
git add .

# Делаем коммит (если есть изменения)
if git commit -m "Auto-commit on $(date '+%Y-%m-%d %H:%M:%S')"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ✅ Commit created" >> /home/coffee/coffee-bot/autopush.log
    if git push origin main; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') 🚀 Push successful" >> /home/coffee/coffee-bot/autopush.log
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ Push failed" >> /home/coffee/coffee-bot/autopush.log
    fi
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ⚠️ Nothing to commit" >> /home/coffee/coffee-bot/autopush.log
fi
