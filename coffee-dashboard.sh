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

# Бесконечный цикл обновления панели
while true; do
    clear
    status_line
    echo "┌────────── Logs ──────────"
    journalctl -u coffee-main.service -u coffee-digest.service -u coffee-breaking.service -n 10 --no-pager
    echo "└─────────────────────────"
    sleep 5
done
