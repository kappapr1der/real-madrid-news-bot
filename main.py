import subprocess
import logging
import sys
import time
import schedule
from collections import deque
from colorama import init, Fore, Style

from runtime_config import (
    DIGEST_DAY_TIME,
    DIGEST_EVENING_TIME,
    DIGEST_MORNING_TIME,
    DIGEST_TIMEZONE,
    DRY_RUN,
    get_log_file,
)

init(autoreset=True)

LOG_FILE = get_log_file("main.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

processes = {}
restart_history = {}

RESTART_LIMIT = 5
TIME_WINDOW = 600  # 10 минут
PYTHON = sys.executable or "python"


def start_process(name, command, restart: bool = True):
    try:
        proc = subprocess.Popen(command)
        processes[name] = {"process": proc, "restart": restart, "command": command}
        if restart:
            if name not in restart_history:
                restart_history[name] = deque(maxlen=RESTART_LIMIT)
            restart_history[name].append(time.time())
        logging.info(f"{name} запущен (PID {proc.pid})")
        print(Fore.GREEN + Style.BRIGHT + f"[MAIN] {name} запущен (PID {proc.pid})")
    except Exception as e:
        logging.error(f"Ошибка запуска {name}: {e}")
        print(Fore.RED + f"[MAIN] Ошибка запуска {name}: {e}")


def can_restart(name):
    if name not in restart_history:
        return True
    now = time.time()
    history = restart_history[name]
    while history and now - history[0] > TIME_WINDOW:
        history.popleft()
    return len(history) < RESTART_LIMIT


def check_processes():
    for name, state in list(processes.items()):
        proc = state["process"]
        retcode = proc.poll()
        if retcode is None:
            continue

        processes.pop(name, None)
        if not state["restart"]:
            level = logging.INFO if retcode == 0 else logging.ERROR
            logging.log(level, "%s завершился с кодом %s", name, retcode)
            color = Fore.GREEN if retcode == 0 else Fore.RED
            print(color + f"[MAIN] {name} завершился с кодом {retcode}")
            continue

        logging.warning(f"{name} упал с кодом {retcode}")
        print(Fore.RED + f"[MAIN] {name} упал с кодом {retcode}")
        if can_restart(name):
            print(Fore.YELLOW + f"[MAIN] Перезапускаем {name}...")
            start_process(name, state["command"], restart=True)
        else:
            logging.error(f"{name} превысил лимит рестартов")
            print(Fore.RED + f"[MAIN] {name} превысил лимит рестартов")


def run_heartbeat():
    start_process("heartbeat", [PYTHON, "heartbeat.py"], restart=True)


def run_breaking():
    start_process("breaking", [PYTHON, "breaking.py"], restart=True)


def run_digest_with_label(label: str):
    start_process(f"digest:{label}", [PYTHON, "digest.py", label], restart=False)


def schedule_digest(label: str, at_time: str):
    job = schedule.every().day.at(at_time, DIGEST_TIMEZONE).do(run_digest_with_label, label=label)
    logging.info("Запланирован %s дайджест на %s %s", label, at_time, DIGEST_TIMEZONE)
    return job


if __name__ == "__main__":
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(Fore.YELLOW + Style.BRIGHT + f"[MAIN] Менеджер запущен ({mode})")

    run_heartbeat()
    run_breaking()

    schedule_digest("утреннего", DIGEST_MORNING_TIME)
    schedule_digest("дневного", DIGEST_DAY_TIME)
    schedule_digest("вечернего", DIGEST_EVENING_TIME)

    print(
        Fore.CYAN
        + f"[MAIN] Дайджесты: {DIGEST_MORNING_TIME}, {DIGEST_DAY_TIME}, "
        + f"{DIGEST_EVENING_TIME} ({DIGEST_TIMEZONE})"
    )

    while True:
        schedule.run_pending()
        check_processes()
        time.sleep(5)
