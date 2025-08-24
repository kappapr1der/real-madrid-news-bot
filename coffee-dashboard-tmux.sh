#!/bin/bash

# Цвета
GREEN="\e[32m"
RED="\e[31m"
YELLOW="\e[33m"
RESET="\e[0m"

# Функция для строки состояния
status_line() {
    services=("coffee-main.service" "coffee-digest.service" "coffee-breaking.service" "coffee-filters-log.service" "coffee-ping.service")
    line=""
    for s in "${services[@]}"; do
        state=$(systemctl is-active "$s")
        if [ "$state" = "active" ]; then
            line+="${GREEN}${s}:●${RESET} "
        elif [ "$state" = "failed" ]; then
            line+="${RED}${s}:✖${RESET} "
        else
            line+="${YELLOW}${s}:${state}${RESET} "
        fi
    done
    echo -e "$line"
}

# Проверяем, что tmux установлен
if ! command -v tmux &> /dev/null; then
    echo "Tmux не установлен. Установите его: sudo apt install tmux"
    exit 1
fi

# Запускаем новую сессию tmux, если ещё нет
SESSION_NAME="coffee_dashboard"
tmux has-session -t $SESSION_NAME 2>/dev/null
if [ $? != 0 ]; then
    tmux new-session -d -s $SESSION_NAME
fi

# Верхний тайл — строка состояния и логи
tmux send-keys -t $SESSION_NAME "while true; do clear; status_line; echo '── Logs ──'; journalctl -u coffee-main.service -u coffee-digest.service -u coffee-breaking.service -n 10 --no-pager; sleep 5; done" C-m

# Нижний тайл — интерактивная командная строка
tmux split-window -v -t $SESSION_NAME
tmux select-pane -t 1

# Присоединяемся к сессии
tmux attach-session -t $SESSION_NAME
