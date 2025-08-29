#!/usr/bin/env bash
set -euo pipefail

REPO="/home/coffee/coffee-bot"
cd "$REPO"

# Безопасность: работаем от имени текущего пользователя
git config --global --add safe.directory "$REPO"

# Автор коммитов (можешь поменять)
git config user.name  "coffee-bot"
git config user.email "bot@localhost"

# Обновим из origin (автостеш, ребейз)
git pull --rebase --autostash || {
  echo "[autopush] pull --rebase failed"; exit 1;
}

# Добавим все новые/изменённые, кроме игнорируемых
git add -A

# Если нечего коммитить — выходим
if git diff --cached --quiet; then
  echo "[autopush] nothing to commit"; exit 0
fi

# Коммит с меткой времени
TS="$(date '+%Y-%m-%d %H:%M:%S %z')"
git commit -m "Auto-commit on ${TS}"

# Пуш
git push
echo "[autopush] pushed successfully at ${TS}"
