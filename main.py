import subprocess
import logging
import sys
import time
import schedule
from collections import deque
from colorama import init, Fore, Style

from runtime_config import DRY_RUN, get_log_file

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


def start_process(name, command):
    try:
        proc = subprocess.Popen(command)
        processes[name] = proc
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
    for name, proc in list(processes.items()):
        retcode = proc.poll()
        if retcode is not None:
            logging.warning(f"{name} упал с кодом {retcode}")
            print(Fore.RED + f"[MAIN] {name} упал с кодом {retcode}")
            if can_restart(name):
                print(Fore.YELLOW + f"[MAIN] Перезапускаем {name}...")
                start_process(name, proc.args)
            else:
                logging.error(f"{name} превысил лимит рестартов")
                print(Fore.RED + f"[MAIN] {name} превысил лимит рестартов")


def run_heartbeat():
    start_process("heartbeat", [PYTHON, "heartbeat.py"])


def run_breaking():
    start_process("breaking", [PYTHON, "breaking.py"])


def run_digest_with_label(label: str):
    start_process(f"digest:{label}", [PYTHON, "digest.py", label])


if __name__ == "__main__":
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(Fore.YELLOW + Style.BRIGHT + f"[MAIN] Менеджер запущен ({mode})")

    run_heartbeat()
    run_breaking()

    # Три фиксированных слота дайджеста (локальное время сервера)
    schedule.every().day.at("08:00").do(run_digest_with_label, label="утреннего")
    schedule.every().day.at("14:00").do(run_digest_with_label, label="дневного")
    schedule.every().day.at("20:00").do(run_digest_with_label, label="вечернего")

    while True:
        schedule.run_pending()
        check_processes()
        time.sleep(5)
