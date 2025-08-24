#!/bin/bash

# Создаём сессию tmux если её нет
tmux has-session -t coffee 2>/dev/null && tmux kill-session -t coffee
tmux new-session -d -s coffee

# Окно 0 - Logs
tmux rename-window -t coffee:0 Logs
tmux send-keys -t coffee:0 '
while true; do
    clear
    for service in coffee-main.service coffee-breaking.service coffee-digest.service coffee-filters-log.service coffee-ping.service; do
        if systemctl is-active $service >/dev/null; then
            echo "🟢 $service"
        else
            echo "🔴 $service"
        fi
    done
    echo
    [ -f ~/coffee-bot/logs/breaking.log ] && tail -n 15 ~/coffee-bot/logs/breaking.log | sed "s/^/🔵 /"
    [ -f ~/coffee-bot/logs/digest.log ] && tail -n 15 ~/coffee-bot/logs/digest.log | sed "s/^/🟡 /"
    [ -f ~/coffee-bot/logs/filters.log ] && tail -n 15 ~/coffee-bot/logs/filters.log | sed "s/^/🟣 /"
    [ -f ~/coffee-bot/logs/ping.log ] && tail -n 15 ~/coffee-bot/logs/ping.log | sed "s/^/🟢 /"
    sleep 2
done
' C-m

# Окно 1 - Commands
tmux new-window -t coffee:1 -n Commands

# Подключение
tmux attach -t coffee

