#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import logging
import signal
import threading
import time
from datetime import timedelta
from html import escape

import requests
from colorama import Fore, Style, init

from live_providers import fetch_live_events, live_provider_status
from match_calendar import Match, calendar_read_error, find_match, load_matches, local_now, upcoming_matches
from post_utils import append_hashtags
from status_manager import record_error, record_status
from runtime_config import (
    DRY_RUN,
    LIVE_HASHTAGS,
    MATCHDAY_FULLTIME_MINUTES,
    MATCHDAY_HALFTIME_MINUTES,
    MATCHDAY_HASHTAGS,
    MATCHDAY_LIVE_ENABLED,
    MATCHDAY_LIVE_POLL_SECONDS,
    MATCHDAY_POLL_SECONDS,
    MATCHDAY_POST_TOLERANCE_MINUTES,
    MATCHDAY_PREVIEW_MINUTES,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)

init(autoreset=True)

LOG_FILE = get_log_file("matchday.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

STATE_FILE = get_state_file("matchday_posts.json")
AUTO_PHASES = {
    "preview": -MATCHDAY_PREVIEW_MINUTES,
    "kickoff": 0,
    "halftime": MATCHDAY_HALFTIME_MINUTES,
    "fulltime": MATCHDAY_FULLTIME_MINUTES,
}
last_live_check = 0.0
stop_event = threading.Event()


def request_stop(signum=None, frame=None):
    stop_event.set()


def install_signal_handlers():
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)


def load_state() -> set[str]:
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return set(str(item) for item in data if item)


def save_state(state: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(state), ensure_ascii=False, indent=2), encoding="utf-8")


posted_keys = load_state()


def match_meta(match: Match) -> str:
    details = [match.competition]
    if match.round:
        details.append(match.round)
    if match.venue:
        details.append(match.venue)
    return " · ".join(details)


def kickoff_label(match: Match) -> str:
    return match.kickoff.strftime("%d.%m %H:%M")


def format_auto_message(match: Match, phase: str) -> str:
    safe_title = escape(match.title)
    safe_meta = escape(match_meta(match))
    safe_kickoff = escape(kickoff_label(match))

    if phase == "preview":
        lines = [
            f"<b>Матч-день: {safe_title}</b>",
            safe_meta,
            f"Начало: {safe_kickoff}",
            "На время матча обычные дайджесты приглушены.",
        ]
        if match.broadcast:
            lines.append(f"Трансляция: {escape(match.broadcast)}")
        message = "\n".join(lines)
        return append_hashtags(message, MATCHDAY_HASHTAGS)

    if phase == "kickoff":
        message = "\n".join([
            f"<b>Матч начался: {safe_title}</b>",
            safe_meta,
            "Следим за сливочными.",
        ])
        return append_hashtags(message, MATCHDAY_HASHTAGS)

    if phase == "halftime":
        message = "\n".join([
            f"<b>Перерыв: {safe_title}</b>",
            "Пауза в матче. Продолжаем следить за Мадридом.",
        ])
        return append_hashtags(message, MATCHDAY_HASHTAGS)

    message = "\n".join([
        f"<b>Финальный свист: {safe_title}</b>",
        "Ждем подтвержденные итоги и детали после матча.",
    ])
    return append_hashtags(message, MATCHDAY_HASHTAGS)


def format_event_message(match: Match, minute: str, text: str, kind: str = "update", score: str = "") -> str:
    safe_title = escape(match.title)
    safe_text = escape(text.strip())
    safe_kind = escape(kind.strip() or "update")
    safe_minute = escape(minute.strip()) if minute else ""
    safe_score = escape(score.strip()) if score else ""

    header_parts = []
    if safe_minute:
        header_parts.append(f"{safe_minute}'")
    header_parts.append(safe_kind)
    if safe_score:
        header_parts.append(safe_score)

    header = " · ".join(header_parts)
    message = f"<b>{header} | {safe_title}</b>\n{safe_text}"
    return append_hashtags(message, LIVE_HASHTAGS)


def post_telegram_message(message: str) -> bool:
    if DRY_RUN:
        print(Fore.MAGENTA + Style.BRIGHT + "[DRY RUN MATCHDAY]\n" + message)
        return True

    if not telegram_configured():
        record_error("matchday", "TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        print(Fore.RED + "[MATCHDAY] TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, 4):
        if stop_event.is_set():
            return False
        try:
            response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return True
            logging.error("Ошибка Telegram API: %s %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Ошибка при отправке matchday, попытка %s: %s", attempt, exc)

        if attempt < 3:
            stop_event.wait(attempt * 2)

    return False


def mark_posted(key: str) -> None:
    posted_keys.add(key)
    save_state(posted_keys)


def phase_due(match: Match, phase: str, now) -> bool:
    offset = AUTO_PHASES[phase]
    due_at = match.kickoff + timedelta(minutes=offset)
    expires_at = due_at + timedelta(minutes=MATCHDAY_POST_TOLERANCE_MINUTES)
    return due_at <= now <= expires_at


def calendar_ready() -> bool:
    calendar_error = calendar_read_error()
    if not calendar_error:
        return True

    record_error("matchday", calendar_error, {"dry_run": DRY_RUN})
    logging.error(calendar_error)
    print(Fore.RED + f"[MATCHDAY] {calendar_error}")
    return False


def run_auto_once() -> int:
    now = local_now()
    sent = 0
    matches = load_matches()

    for match in matches:
        if stop_event.is_set():
            break
        for phase in AUTO_PHASES:
            if stop_event.is_set():
                break
            key = f"auto:{match.id}:{phase}"
            if key in posted_keys or not phase_due(match, phase, now):
                continue

            message = format_auto_message(match, phase)
            if post_telegram_message(message):
                mark_posted(key)
                sent += 1
                logging.info("Опубликован matchday phase=%s match=%s", phase, match.id)

    record_status(
        "matchday",
        "ok",
        "auto check complete",
        {"matches": len(matches), "sent": sent, "dry_run": DRY_RUN},
    )
    print(Fore.CYAN + f"[MATCHDAY] Проверка автопостов завершена, опубликовано: {sent}")
    return sent


def run_live_once() -> int:
    status = live_provider_status()
    if status != "api-football ready":
        if MATCHDAY_LIVE_ENABLED:
            record_error("live", status)
            logging.warning("Live-провайдер не готов: %s", status)
        else:
            record_status("live", "disabled", status)
        print(Fore.YELLOW + f"[MATCHDAY LIVE] Live-провайдер не готов: {status}")
        return 0

    if not calendar_ready():
        return 0

    sent = 0
    events = fetch_live_events(load_matches())
    for event in events:
        if stop_event.is_set():
            break
        key = f"live:{event.key}"
        if key in posted_keys:
            continue

        message = format_event_message(
            event.match,
            minute=event.minute,
            text=event.text,
            kind=event.kind,
            score=event.score,
        )
        if post_telegram_message(message):
            mark_posted(key)
            sent += 1
            logging.info("Опубликовано live event key=%s match=%s", event.key, event.match.id)

    record_status(
        "live",
        "ok",
        "live check complete",
        {"events": len(events), "sent": sent, "dry_run": DRY_RUN},
    )
    print(Fore.CYAN + f"[MATCHDAY LIVE] Проверка live-событий завершена, опубликовано: {sent}")
    return sent


def live_due(force: bool = False) -> bool:
    global last_live_check
    if not MATCHDAY_LIVE_ENABLED:
        return False
    if force:
        last_live_check = time.monotonic()
        return True

    now = time.monotonic()
    if now - last_live_check >= MATCHDAY_LIVE_POLL_SECONDS:
        last_live_check = now
        return True
    return False


def run_cycle(force_live: bool = False) -> int:
    if not calendar_ready():
        return 0

    sent = run_auto_once()
    if live_due(force=force_live):
        sent += run_live_once()
    elif not MATCHDAY_LIVE_ENABLED:
        record_status("live", "disabled", "MATCHDAY_LIVE_ENABLED=false")
    return sent


def post_manual_event(match_id: str, minute: str, text: str, kind: str, score: str) -> int:
    match = find_match(match_id)
    if not match:
        record_error("matchday", f"Матч не найден: {match_id}")
        print(Fore.RED + f"[MATCHDAY] Матч не найден: {match_id}")
        return 1

    fingerprint = hashlib.sha1(f"{match_id}|{minute}|{kind}|{score}|{text}".encode("utf-8")).hexdigest()[:16]
    key = f"event:{match_id}:{fingerprint}"
    if key in posted_keys:
        print(Fore.YELLOW + "[MATCHDAY] Такое событие уже публиковалось")
        return 0

    message = format_event_message(match, minute=minute, text=text, kind=kind, score=score)
    if post_telegram_message(message):
        mark_posted(key)
        record_status("live", "ok", "manual event posted", {"match_id": match_id, "kind": kind, "minute": minute})
        logging.info("Опубликовано matchday event match=%s kind=%s minute=%s", match_id, kind, minute)
        return 0
    record_error("live", "manual event send failed", {"match_id": match_id, "kind": kind, "minute": minute})
    return 1


def print_matches() -> None:
    matches = upcoming_matches(days=30)
    if not matches:
        print("Ближайших матчей в календаре нет. Проверь config/matches.json")
        return

    for match in matches:
        fixture = f" | api_football_fixture_id={match.api_football_fixture_id}" if match.api_football_fixture_id else ""
        print(f"{match.id} | {kickoff_label(match)} | {match.title} | {match_meta(match)}{fixture}")


def parse_args():
    parser = argparse.ArgumentParser(description="Coffee Bot matchday broadcaster")
    parser.add_argument("--once", action="store_true", help="run one matchday check and exit")
    parser.add_argument("--live-once", action="store_true", help="poll configured live provider once and exit")
    parser.add_argument("--list", action="store_true", help="print upcoming matches from config/matches.json")
    parser.add_argument("--match-id", help="match id for a manual/future live event")
    parser.add_argument("--event-text", help="text for a manual/future live event")
    parser.add_argument("--minute", default="", help="match minute for the event, for example 23")
    parser.add_argument("--kind", default="update", help="event kind: update, goal, card, substitution, var")
    parser.add_argument("--score", default="", help="optional score label, for example 1:0")
    return parser.parse_args()


def main() -> int:
    install_signal_handlers()
    args = parse_args()
    record_status("matchday", "starting", f"matchday started; live={live_provider_status()}")

    if args.list:
        print_matches()
        return 0

    if args.event_text:
        if not args.match_id:
            record_error("matchday", "Для --event-text нужен --match-id")
            print(Fore.RED + "[MATCHDAY] Для --event-text нужен --match-id")
            return 1
        return post_manual_event(
            match_id=args.match_id,
            minute=args.minute,
            text=args.event_text,
            kind=args.kind,
            score=args.score,
        )

    if args.live_once:
        run_live_once()
        return 0

    if args.once:
        run_cycle(force_live=True)
        return 0

    print(Fore.YELLOW + f"[MATCHDAY] Matchday broadcaster started; live={live_provider_status()}")
    try:
        while not stop_event.is_set():
            run_cycle()
            stop_event.wait(MATCHDAY_POLL_SECONDS)
    except KeyboardInterrupt:
        request_stop(signal.SIGINT, None)

    if stop_event.is_set():
        record_status("matchday", "stopping", "matchday stopped by signal", {"dry_run": DRY_RUN})
        logging.info("Matchday-воркер остановлен сигналом")
        print(Fore.YELLOW + "[MATCHDAY] Остановка по сигналу")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
