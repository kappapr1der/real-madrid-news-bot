#!/usr/bin/env bash
set -euo pipefail

REPO="/home/coffee/coffee-bot"
cd "$REPO"

# Цвета
RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
RESET="\033[0m"

log() {
  local level="$1"; shift
  local color="$1"; shift
  echo -e "${color}[autopush][$level]${RESET} $*"
}

git config --global --add safe.directory "$REPO"
git config user.name  "coffee-bot"
git config user.email "bot@localhost"

# Подтягиваем изменения
if git pull --rebase --autostash; then
  log INFO "$GREEN" "Pull success"
else
  log ERROR "$RED" "Pull failed"
  exit 1
fi

# Добавляем новые файлы
git add -A

# Если нечего коммитить
if git diff --cached --quiet; then
  log INFO "$YELLOW" "Nothing to commit"
  exit 0
fi

TS="$(date '+%Y-%m-%d %H:%M:%S %z')"
if git commit -m "Auto-commit on ${TS}"; then
  log INFO "$GREEN" "Committed changes"
else
  log ERROR "$RED" "Commit failed"
  exit 1
fi

# Пуш
if git push; then
  log INFO "$GREEN" "Pushed successfully at ${TS}"
else
  log ERROR "$RED" "Push failed"
  exit 1
fi
