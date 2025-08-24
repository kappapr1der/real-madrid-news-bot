#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import time
from datetime import datetime

# Цвета терминала
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
RESET = '\033[0m'
BOLD = '\033[1m'

SERVICES = [
    "coffee-main.service",
    "coffee-digest.service",
    "coffee-breaking.service",
    "coffee-ping.service",
    "coffee-filters-log.service"
]

LOG_SERVICES = ["coffee-digest", "coffee-breaking"]

REFRESH_INTERVAL = 5  # секунд

def get_service_status(name):
    try:
        output = subprocess.check_output(["systemctl", "is-active", name], text=True).strip()
        return output
    except subprocess.CalledProcessError:
        return "unknown"

def color_status(status):
    if status == "active":
        return f"{GREEN}{status}{RESET}"
    elif status == "failed":
        return f"{RED}{status}{RESET}"
    else:
        return f"{YELLOW}{status}{RESET}"

def get_last_logs(name, n=5):
    log_file = f"/home/coffee/coffee-bot/logs/{name}.log"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        last_lines = "".join(lines[-n:])
        # Подсветка
        last_lines = last_lines.replace("FAILED", f"{RED}FAILED{RESET}")
        last_lines = last_lines.replace("ERROR", f"{RED}ERROR{RESET}")
        last_lines = last_lines.replace("WARNING", f"{YELLOW}WARNING{RESET}")
        last_lines = last_lines.replace("SUCCESS", f"{GREEN}SUCCESS{RESET}")
        last_lines = last_lines.replace("OK", f"{GREEN}OK{RESET}")
        return last_lines
    else:
        return "(логов нет)\n"

def main():
    while True:
        os.system("clear")
        print(f"{BOLD}{BLUE}☕ Coffee Bot Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
        print("-" * 60)
        for svc in SERVICES:
            status = get_service_status(svc)
            print(f"{svc:<30} : {color_status(status)}")
        print("-" * 60)
        for svc in LOG_SERVICES:
            print(f"{BOLD}{YELLOW}[{svc} logs]:{RESET}")
            logs = get_last_logs(svc)
            print(logs)
            print("-" * 40)
        print(f"{BOLD}Командная строка для ввода (Ctrl+C для выхода):{RESET}")
        try:
            cmd = input("> ")
            if cmd.strip():
                os.system(cmd)
        except KeyboardInterrupt:
            print("\nВыход...")
            break
        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()
