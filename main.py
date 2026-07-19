import os
import signal
import subprocess
import logging
import sys
import time
import threading
import schedule
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo
from colorama import init, Fore, Style

from runtime_config import (
    DIGEST_DAY_TIME,
    DIGEST_EVENING_TIME,
    DIGEST_MISSED_CATCHUP_ENABLED,
    DIGEST_MISSED_GRACE_MINUTES,
    DIGEST_MORNING_TIME,
    DIGEST_PREFLIGHT_ENABLED,
    DIGEST_PREFLIGHT_MINUTES,
    DIGEST_TIMEZONE,
    DRY_RUN,
    MATCHDAY_ENABLED,
    WEEK_AHEAD_DAY,
    WEEK_AHEAD_ENABLED,
    WEEK_AHEAD_TIME,
    WEEK_AHEAD_TIMEZONE,
    WEEKLY_RECAP_DAY,
    WEEKLY_RECAP_ENABLED,
    WEEKLY_RECAP_TIME,
    WEEKLY_RECAP_TIMEZONE,
    get_log_file,
)
from status_manager import load_status, parse_iso, record_error, record_status

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
stop_event = threading.Event()


def request_stop(signum=None, frame=None):
    stop_event.set()


def install_signal_handlers():
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)


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


def run_weekly_recap():
    start_process("weekly_recap", [PYTHON, "weekly_recap.py"], restart=False)


def run_week_ahead():
    start_process("week_ahead", [PYTHON, "week_ahead.py"], restart=False)


def run_preflight_with_label(label: str):
    start_process(f"preflight:{label}", [PYTHON, "preflight.py", "digest", label], restart=False)


def parse_digest_clock(at_time: str) -> tuple[int, int] | None:
    try:
        hour_raw, minute_raw = at_time.split(":", 1)
        hour = int(hour_raw)
        minute = int(minute_raw)
    except (ValueError, AttributeError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def preflight_time_for_digest(at_time: str, lead_minutes: int) -> str | None:
    clock = parse_digest_clock(at_time)
    if not clock:
        return None
    hour, minute = clock
    total_minutes = (hour * 60 + minute - max(lead_minutes, 0)) % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def digest_completed_today(label: str, now: datetime) -> bool:
    services = load_status().get("services", {})
    entries = [
        services.get(f"digest:{label}", {}),
        services.get("digest", {}),
    ]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        state = entry.get("state")
        metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
        if state not in {"completed", "ok"}:
            continue
        if entry is services.get("digest") and metrics.get("label") != label:
            continue
        completed_at = parse_iso(str(entry.get("updated_at") or ""))
        if completed_at and completed_at.astimezone(now.tzinfo).date() == now.date():
            return True
    return False


def missed_digest_candidate(label: str, at_time: str, now: datetime) -> dict | None:
    clock = parse_digest_clock(at_time)
    if not clock:
        logging.warning("Невозможно проверить пропущенный %s дайджест: некорректное время %s", label, at_time)
        return None

    hour, minute = clock
    scheduled_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now < scheduled_at:
        return None

    late_minutes = int((now - scheduled_at).total_seconds() // 60)
    return {
        "label": label,
        "at_time": at_time,
        "scheduled_at": scheduled_at,
        "late_minutes": late_minutes,
    }


def select_missed_digest_candidate(slots: list[tuple[str, str]], now: datetime) -> dict | None:
    candidates = [
        candidate
        for label, at_time in slots
        if (candidate := missed_digest_candidate(label, at_time, now)) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate["scheduled_at"])


def run_missed_digest_if_needed(slots: list[tuple[str, str]]):
    if not DIGEST_MISSED_CATCHUP_ENABLED:
        return

    tz = ZoneInfo(DIGEST_TIMEZONE)
    now = datetime.now(tz)
    candidate = select_missed_digest_candidate(slots, now)
    if not candidate:
        return

    label = candidate["label"]
    at_time = candidate["at_time"]
    late_minutes = candidate["late_minutes"]
    if late_minutes > DIGEST_MISSED_GRACE_MINUTES:
        logging.info(
            "Пропущенный %s дайджест не догоняем: прошло %s мин, лимит %s мин",
            label,
            late_minutes,
            DIGEST_MISSED_GRACE_MINUTES,
        )
        return

    if f"digest:{label}" in processes or digest_completed_today(label, now):
        return

    logging.warning(
        "Догоняем пропущенный %s дайджест: план %s %s, опоздание %s мин",
        label,
        at_time,
        DIGEST_TIMEZONE,
        late_minutes,
    )
    print(Fore.YELLOW + f"[MAIN] Догоняем пропущенный {label} дайджест ({late_minutes} мин)")
    run_digest_with_label(label)


def schedule_digest(label: str, at_time: str):
    job = schedule.every().day.at(at_time, DIGEST_TIMEZONE).do(run_digest_with_label, label=label)
    logging.info("Запланирован %s дайджест на %s %s", label, at_time, DIGEST_TIMEZONE)
    return job


def schedule_digest_preflight(label: str, at_time: str):
    if not DIGEST_PREFLIGHT_ENABLED or DIGEST_PREFLIGHT_MINUTES <= 0:
        return None
    preflight_time = preflight_time_for_digest(at_time, DIGEST_PREFLIGHT_MINUTES)
    if not preflight_time:
        logging.warning("Не удалось запланировать preflight для %s: некорректное время %s", label, at_time)
        return None
    job = schedule.every().day.at(preflight_time, DIGEST_TIMEZONE).do(run_preflight_with_label, label=label)
    logging.info(
        "Запланирован preflight %s дайджеста на %s %s (%s мин до выпуска)",
        label,
        preflight_time,
        DIGEST_TIMEZONE,
        DIGEST_PREFLIGHT_MINUTES,
    )
    return job


def schedule_weekly_recap():
    if not WEEKLY_RECAP_ENABLED:
        record_status("weekly_recap", "disabled", "WEEKLY_RECAP_ENABLED=false")
        return None
    days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    day = WEEKLY_RECAP_DAY if WEEKLY_RECAP_DAY in days else "sunday"
    weekly_job = getattr(schedule.every(), day)
    job = weekly_job.at(WEEKLY_RECAP_TIME, WEEKLY_RECAP_TIMEZONE).do(run_weekly_recap)
    logging.info("Scheduled weekly recap on %s %s %s", day, WEEKLY_RECAP_TIME, WEEKLY_RECAP_TIMEZONE)
    return job


def schedule_week_ahead():
    if not WEEK_AHEAD_ENABLED:
        record_status("week_ahead", "disabled", "WEEK_AHEAD_ENABLED=false")
        return None
    days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    day = WEEK_AHEAD_DAY if WEEK_AHEAD_DAY in days else "monday"
    weekly_job = getattr(schedule.every(), day)
    job = weekly_job.at(WEEK_AHEAD_TIME, WEEK_AHEAD_TIMEZONE).do(run_week_ahead)
    logging.info("Scheduled week-ahead calendar on %s %s %s", day, WEEK_AHEAD_TIME, WEEK_AHEAD_TIMEZONE)
    return job


def main():
    install_signal_handlers()
    try:
        mode = "DRY RUN" if DRY_RUN else "LIVE"
        print(Fore.YELLOW + Style.BRIGHT + f"[MAIN] Менеджер запущен ({mode})")
        update_manager_status(force=True)

        run_heartbeat()
        run_breaking()
        run_matchday()

        digest_slots = [
            ("утреннего", DIGEST_MORNING_TIME),
            ("дневного", DIGEST_DAY_TIME),
            ("вечернего", DIGEST_EVENING_TIME),
        ]
        for label, at_time in digest_slots:
            schedule_digest_preflight(label, at_time)
            schedule_digest(label, at_time)
        schedule_week_ahead()
        schedule_weekly_recap()
        run_missed_digest_if_needed(digest_slots)

        print(
            Fore.CYAN
            + f"[MAIN] Дайджесты: {DIGEST_MORNING_TIME}, {DIGEST_DAY_TIME}, "
            + f"{DIGEST_EVENING_TIME} ({DIGEST_TIMEZONE})"
        )
        if DIGEST_PREFLIGHT_ENABLED:
            print(Fore.CYAN + f"[MAIN] Preflight: за {DIGEST_PREFLIGHT_MINUTES} мин до дайджеста")

        while not stop_event.is_set():
            schedule.run_pending()
            check_processes()
            update_manager_status()
            stop_event.wait(5)
    except KeyboardInterrupt:
        request_stop(signal.SIGINT, None)
    finally:
        if stop_event.is_set():
            record_status("main", "stopping", "manager stopped by signal", {"pid": os.getpid()})
            logging.info("Менеджер остановлен сигналом")
            print(Fore.YELLOW + "[MAIN] Остановка по сигналу")
        shutdown_processes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
