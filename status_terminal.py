#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import time
import sys

SERVICES = {
    "Digest": ("coffee-digest.service", "\033[1;32m"),   # зеленый
    "Breaking": ("coffee-breaking.service", "\033[1;34m"), # синий
    "Ping": ("coffee-ping.service", "\033[1;33m"),       # желтый
    "Filters": ("coffee-filters-log.service", "\033[1;31m"), # красный
}

prev_statuses = {}

def get_status(service):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"

def print_status_bar():
    global prev_statuses
    parts = []
    for name, (svc, color) in SERVICES.items():
        status = get_status(svc)
        blink = False
        if prev_statuses.get(name) and prev_statuses[name] != status:
            blink = True
        prev_statuses[name] = status

        if status == "active":
            s_colored = f"{color}{status}\033[0m"
        elif status == "failed":
            s_colored = f"\033[1;31m{status}\033[0m"
        else:
            s_colored = f"\033[1;33m{status}\033[0m"

        if blink:
            s_colored = f"\033[5m{s_colored}\033[0m"

        parts.append(f"{name}: {s_colored}")

    line = " | ".join(parts)
    sys.stdout.write("\033[s")      # сохранить позицию курсора
    sys.stdout.write("\033[1F")     # подняться на строку выше
    sys.stdout.write("\033[2K")     # очистить строку
    sys.stdout.write(line + "\n")
    sys.stdout.write("\033[u")      # вернуть курсор
    sys.stdout.flush()

if __name__ == "__main__":
    print()
    while True:
        print_status_bar()
        time.sleep(5)
