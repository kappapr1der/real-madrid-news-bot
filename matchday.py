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

from editorial_archive import archive_matchday_story
from live_providers import fetch_confirmed_lineups, fetch_final_results, fetch_live_events, live_provider_status
from matchday_editorial import bernabeu_voice_copy, pre_whistle_copy
from match_calendar import Match, calendar_read_error, find_match, load_matches, local_now, match_calendar_status, upcoming_matches
from post_utils import append_hashtags
from status_manager import record_error, record_status
from visual_cards import render_match_card
from runtime_config import (
    DRY_RUN,
    LIVE_HASHTAGS,
    MATCHDAY_FULLTIME_MINUTES,
    MATCHDAY_DAY_BEFORE_MINUTES,
    MATCHDAY_HALFTIME_MINUTES,
    MATCHDAY_HASHTAGS,
    MATCHDAY_LIVE_ENABLED,
    MATCHDAY_LIVE_POLL_SECONDS,
    MATCHDAY_POLL_SECONDS,
    MATCHDAY_POST_TOLERANCE_MINUTES,
    MATCHDAY_PREVIEW_MINUTES,
    MATCHDAY_LINEUP_ENABLED,
    MATCHDAY_POSTMATCH_POLL_ENABLED,
    MATCHDAY_POSTMATCH_POLL_QUESTION,
    MATCHDAY_RESULT_ENABLED,
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
    "day_before": -MATCHDAY_DAY_BEFORE_MINUTES,
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

    if phase == "day_before":
        pre_whistle = pre_whistle_copy(match)
        lines = [
            f"<b>{'Перед свистком' if pre_whistle else 'Завтра матч'}: {safe_title}</b>",
            safe_meta,
            f"Начало: {safe_kickoff}",
            pre_whistle or "Заранее собираем всё важное к матчу и оставляем день без лишнего шума.",
        ]
        if match.broadcast:
            lines.append(f"Трансляция: {escape(match.broadcast)}")
        hashtags = f"{MATCHDAY_HASHTAGS} #ПередСвистком" if pre_whistle else MATCHDAY_HASHTAGS
        return append_hashtags("\n".join(lines), hashtags)

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


def format_lineup_message(lineup) -> str:
    formation = f" · {escape(lineup.formation)}" if lineup.formation else ""
    names = ", ".join(escape(name) for name in lineup.starters)
    message = "\n".join(
        [
            f"<b>Состав «Реала» на матч с {escape(lineup.match.away if lineup.match.is_home else lineup.match.home)}{formation}</b>",
            names,
        ]
    )
    return append_hashtags(message, MATCHDAY_HASHTAGS)


def format_final_result_message(result) -> str:
    lines = [
        f"<b>Финальный свист: {escape(result.match.title)}</b>",
        f"Счёт: <b>{escape(result.score)}</b>",
    ]
    goals = []
    for goal in list(getattr(result, "goals", []) or [])[:8]:
        minute = f"{escape(str(goal.minute))}' " if getattr(goal, "minute", "") else ""
        player = escape(str(getattr(goal, "player", "") or ""))
        if player:
            goals.append(f"{minute}{player}")
    if goals:
        lines.append(f"Голы: {', '.join(goals)}")
    bernabeu_voice = bernabeu_voice_copy(result)
    if bernabeu_voice:
        lines.extend(("", bernabeu_voice))
    message = "\n".join(lines)
    hashtags = f"{MATCHDAY_HASHTAGS} #ГолосБернабеу" if bernabeu_voice else MATCHDAY_HASHTAGS
    return append_hashtags(message, hashtags)


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


def player_of_match_options(result) -> list[str]:
    options = []
    seen = set()

    def add(name: str) -> None:
        clean_name = (name or "").strip()
        key = clean_name.casefold()
        if clean_name and key not in seen and len(options) < 4:
            options.append(clean_name)
            seen.add(key)

    for goal in list(getattr(result, "goals", []) or []):
        team = str(getattr(goal, "team", "") or "").casefold()
        if "real madrid" in team or "реал мадрид" in team:
            add(str(getattr(goal, "player", "") or ""))
    for starter in list(getattr(result, "real_starters", []) or []):
        add(str(starter))
    return options if len(options) >= 2 else []


def post_player_of_match_poll(result) -> bool:
    options = player_of_match_options(result)
    if not MATCHDAY_POSTMATCH_POLL_ENABLED or not options:
        return False
    if DRY_RUN:
        print(Fore.MAGENTA + Style.BRIGHT + f"[DRY RUN MATCHDAY POLL] {MATCHDAY_POSTMATCH_POLL_QUESTION}: {options}")
        return True
    if not telegram_configured():
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "question": MATCHDAY_POSTMATCH_POLL_QUESTION,
        "options": json.dumps(options, ensure_ascii=False),
        "is_anonymous": True,
    }
    try:
        response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
        if response.status_code == 200:
            return True
        logging.warning("Telegram player-of-match poll response=%s body=%s", response.status_code, response.text)
    except requests.RequestException as exc:
        logging.warning("Telegram player-of-match poll failed: %s", exc)
    return False


def post_match_card_or_message(message: str, match: Match, phase: str, score: str = "") -> bool:
    if DRY_RUN:
        return post_telegram_message(message)
    card_path = render_match_card(match, phase=phase, score=score)
    if card_path and len(message) <= 1024:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        payload = {
            "chat_id": TARGET_CHAT_ID,
            "caption": message,
            "parse_mode": "HTML",
        }
        for attempt in range(1, 3):
            if stop_event.is_set():
                return False
            try:
                with open(card_path, "rb") as image_file:
                    response = requests.post(
                        url,
                        data=payload,
                        files={"photo": (card_path.name, image_file, "image/jpeg")},
                        timeout=TELEGRAM_TIMEOUT_SECONDS,
                    )
                if response.status_code == 200:
                    return True
                logging.warning("Карточка матча не отправилась: %s %s", response.status_code, response.text)
            except (OSError, requests.RequestException) as exc:
                logging.warning("Ошибка карточки матча, попытка %s: %s", attempt, exc)
            if attempt < 2:
                stop_event.wait(attempt * 2)
    return post_telegram_message(message)


def mark_posted(key: str) -> None:
    posted_keys.add(key)
    save_state(posted_keys)


def phase_due(match: Match, phase: str, now) -> bool:
    offset = AUTO_PHASES[phase]
    due_at = match.kickoff + timedelta(minutes=offset)
    expires_at = due_at + timedelta(minutes=MATCHDAY_POST_TOLERANCE_MINUTES)
    return due_at <= now <= expires_at


def calendar_ready() -> bool:
    state, message, metrics = match_calendar_status()
    metrics["dry_run"] = DRY_RUN
    record_state = "error" if state == "error" else state
    record_status("calendar", record_state, message, metrics)
    if state != "error":
        return True

    record_error("matchday", message, metrics)
    logging.error(message)
    print(Fore.RED + f"[MATCHDAY] {message}")
    return False


def run_auto_once() -> int:
    now = local_now()
    sent = 0
    calendar_state, calendar_message, calendar_metrics = match_calendar_status()
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
            if phase == "fulltime" and MATCHDAY_RESULT_ENABLED and MATCHDAY_LIVE_ENABLED:
                continue

            message = format_auto_message(match, phase)
            if post_match_card_or_message(message, match, phase):
                mark_posted(key)
                archive_matchday_story(match, phase)
                sent += 1
                logging.info("Опубликован matchday phase=%s match=%s", phase, match.id)

    status_state = "waiting_calendar" if not matches and calendar_state in {"pending", "missing", "empty"} else "ok"
    metrics = {"matches": len(matches), "sent": sent, "dry_run": DRY_RUN, "calendar_state": calendar_state}
    if calendar_message:
        metrics["calendar_message"] = calendar_message
    metrics.update({f"calendar_{key}": value for key, value in calendar_metrics.items() if key not in metrics})
    record_status(
        "matchday",
        status_state,
        "auto check complete" if matches else calendar_message,
        metrics,
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
            archive_matchday_story(event.match, "live_event", text=event.text, score=event.score)
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


def run_lineup_once() -> int:
    if not MATCHDAY_LINEUP_ENABLED or live_provider_status() != "api-football ready":
        return 0
    sent = 0
    for lineup in fetch_confirmed_lineups(load_matches()):
        key = f"lineup:{lineup.key}"
        if key in posted_keys:
            continue
        if post_match_card_or_message(format_lineup_message(lineup), lineup.match, "lineup"):
            mark_posted(key)
            archive_matchday_story(lineup.match, "lineup", text=", ".join(lineup.starters))
            sent += 1
    return sent


def run_result_once() -> int:
    if not MATCHDAY_RESULT_ENABLED or live_provider_status() != "api-football ready":
        return 0
    sent = 0
    for result in fetch_final_results(load_matches()):
        key = f"result:{result.key}"
        if key not in posted_keys:
            if post_match_card_or_message(
                format_final_result_message(result),
                result.match,
                "result",
                score=result.score,
            ):
                mark_posted(key)
                archive_matchday_story(result.match, "final_result", score=result.score)
                sent += 1
        poll_key = f"poll:{result.key}"
        if key in posted_keys and poll_key not in posted_keys and post_player_of_match_poll(result):
            mark_posted(poll_key)
            sent += 1
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
        sent += run_lineup_once()
        sent += run_result_once()
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


def print_calendar_status() -> None:
    state, message, metrics = match_calendar_status()
    print(f"calendar_state={state}")
    print(message)
    for key, value in metrics.items():
        print(f"{key}={value}")


def print_matches() -> None:
    matches = upcoming_matches(days=30)
    if not matches:
        print_calendar_status()
        return

    for match in matches:
        fixture = f" | api_football_fixture_id={match.api_football_fixture_id}" if match.api_football_fixture_id else ""
        print(f"{match.id} | {kickoff_label(match)} | {match.title} | {match_meta(match)}{fixture}")


def parse_args():
    parser = argparse.ArgumentParser(description="Coffee Bot matchday broadcaster")
    parser.add_argument("--once", action="store_true", help="run one matchday check and exit")
    parser.add_argument("--live-once", action="store_true", help="poll configured live provider once and exit")
    parser.add_argument("--list", action="store_true", help="print upcoming matches from config/matches.json")
    parser.add_argument("--calendar-status", action="store_true", help="print calendar publication/load status")
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

    if args.calendar_status:
        print_calendar_status()
        return 0

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
