import os
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
    MATCHDAY_ENABLED,
    get_log_file,
)
from status_manager import record_error, record_status

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
MANAGER_STATUS_INTERVAL = 60
last_manager_status = 0.0


def status_metrics(name, command, restart: bool, pid: int | None = None):
    metrics = {
        "command": " ".join(command),
        "restart": restart,
    }
    if pid is not None:
        metrics["pid"] = pid
    return metrics


def start_process(name, command, restart: bool = True):
    try:
        proc = subprocess.Popen(command)
        processes[name] = {"process": proc, "restart": restart, "command": command}
        if restart:
            if name not in restart_history:
                restart_history[name] = deque(maxlen=RESTART_LIMIT)
            restart_history[name].append(time.time())
        record_status(name, "starting", "process started", status_metrics(name, command, restart, proc.pid))
        logging.info(f"{name} запущен (PID {proc.pid})")
        print(Fore.GREEN + Style.BRIGHT + f"[MAIN] {name} запущен (PID {proc.pid})")
    except Exception as e:
        record_error(name, f"Ошибка запуска: {e}", status_metrics(name, command, restart))
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


def update_manager_status(force: bool = False):
    global last_manager_status
    now = time.time()
    if not force and now - last_manager_status < MANAGER_STATUS_INTERVAL:
        return
    last_manager_status = now
    record_status(
        "main",
        "running",
        "manager loop active",
        {
            "pid": os.getpid(),
            "processes": sorted(processes.keys()),
            "mode": "dry_run" if DRY_RUN else "live",
        },
    )


def check_processes():
    for name, state in list(processes.items()):
        proc = state["process"]
        retcode = proc.poll()
        if retcode is None:
            continue

        processes.pop(name, None)
        metrics = status_metrics(name, state["command"], state["restart"], proc.pid)
        metrics["retcode"] = retcode
        if not state["restart"]:
            level = logging.INFO if retcode == 0 else logging.ERROR
            status_state = "completed" if retcode == 0 else "error"
            record_status(name, status_state, f"process exited with code {retcode}", metrics)
            logging.log(level, "%s завершился с кодом %s", name, retcode)
            color = Fore.GREEN if retcode == 0 else Fore.RED
            print(color + f"[MAIN] {name} завершился с кодом {retcode}")
            continue

        record_error(name, f"process crashed with code {retcode}", metrics)
        logging.warning(f"{name} упал с кодом {retcode}")
        print(Fore.RED + f"[MAIN] {name} упал с кодом {retcode}")
        if can_restart(name):
            print(Fore.YELLOW + f"[MAIN] Перезапускаем {name}...")
            start_process(name, state["command"], restart=True)
        else:
            record_status(name, "restart_limit", "restart limit exceeded", metrics)
            logging.error(f"{name} превысил лимит рестартов")
            print(Fore.RED + f"[MAIN] {name} превысил лимит рестартов")


def shutdown_processes(timeout: float = 10.0):
    if not processes:
        return

    logging.info("Останавливаем дочерние процессы: %s", ", ".join(sorted(processes.keys())))
    for name, state in list(processes.items()):
        proc = state["process"]
        if proc.poll() is None:
            logging.info("Остановка %s (PID %s)", name, proc.pid)
            proc.terminate()

    deadline = time.time() + timeout
    for name, state in list(processes.items()):
        proc = state["process"]
        remaining = max(deadline - time.time(), 0.1)
        try:
            proc.wait(timeout=remaining)
            logging.info("%s остановлен с кодом %s", name, proc.returncode)
        except subprocess.TimeoutExpired:
            logging.warning("%s не остановился вовремя, завершаем принудительно", name)
            proc.kill()


def run_heartbeat():
    start_process("heartbeat", [PYTHON, "heartbeat.py"], restart=True)


def run_breaking():
    start_process("breaking", [PYTHON, "breaking.py"], restart=True)


def run_matchday():
    if MATCHDAY_ENABLED:
        start_process("matchday", [PYTHON, "matchday.py"], restart=True)
    else:
        record_status("matchday", "disabled", "MATCHDAY_ENABLED=false")


def run_digest_with_label(label: str):
    start_process(f"digest:{label}", [PYTHON, "digest.py", label], restart=False)


def schedule_digest(label: str, at_time: str):
    job = schedule.every().day.at(at_time, DIGEST_TIMEZONE).do(run_digest_with_label, label=label)
    logging.info("Запланирован %s дайджест на %s %s", label, at_time, DIGEST_TIMEZONE)
    return job


if __name__ == "__main__":
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(Fore.YELLOW + Style.BRIGHT + f"[MAIN] Менеджер запущен ({mode})")
    update_manager_status(force=True)

    run_heartbeat()
    run_breaking()
    run_matchday()

    schedule_digest("утреннего", DIGEST_MORNING_TIME)
    schedule_digest("дневного", DIGEST_DAY_TIME)
    schedule_digest("вечернего", DIGEST_EVENING_TIME)

    print(
        Fore.CYAN
        + f"[MAIN] Дайджесты: {DIGEST_MORNING_TIME}, {DIGEST_DAY_TIME}, "
        + f"{DIGEST_EVENING_TIME} ({DIGEST_TIMEZONE})"
    )

    try:
        while True:
            schedule.run_pending()
            check_processes()
            update_manager_status()
            time.sleep(5)
    except KeyboardInterrupt:
        record_status("main", "stopping", "manager stopped by signal", {"pid": os.getpid()})
        logging.info("Менеджер остановлен сигналом")
        print(Fore.YELLOW + "[MAIN] Остановка по сигналу")
        shutdown_processes()
