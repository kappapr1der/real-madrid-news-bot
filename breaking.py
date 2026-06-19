#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import time
import logging
import random
from html import escape
from typing import Any

import requests
from colorama import init, Fore, Style

from text_cleaner import clean_text
from filters import passes_filters
from feed_utils import parse_feed_url
from post_utils import append_hashtags
from status_manager import record_error, record_status
from translator import translate_text
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from runtime_config import (
    BREAKING_HASHTAGS,
    BREAKING_INTERVAL_SECONDS,
    DRY_RUN,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)

init(autoreset=True)

LOG_FILE = get_log_file("breaking.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = get_state_file("sent_breaking.txt")


def load_sent_links():
    if not SENT_FILE.exists():
        return set()
    with SENT_FILE.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with SENT_FILE.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


sent_breaking = load_sent_links()

BREAKING_KEYWORDS = [
    "breaking",
    "urgent",
    "official",
    "confirmed",
    "экстренно",
    "срочно",
    "официально",
    "подтверждено",
]

TEMPLATES = [
    "<b>Сливочная молния</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Экстра для мадридистов</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Срочно вокруг «Реала»</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Белая лента обновилась</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Из Мадрида пришло важное</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
]


def source_url(source: Any) -> str | None:
    if isinstance(source, dict):
        return source.get("url")
    if isinstance(source, str):
        return source
    return None


def source_label(source: Any) -> str:
    if isinstance(source, dict):
        return source.get("label") or source.get("url") or "Неизвестный источник"
    if isinstance(source, str):
        return source
    return "Неизвестный источник"


def is_breaking(text: str) -> bool:
    lower_text = text.lower()
    for word in BREAKING_KEYWORDS:
        if word in lower_text:
            print(Fore.RED + Style.BRIGHT + f"[BREAKING DETECTED] {word} -> {text}")
            logging.info(f"Обнаружено ключевое слово: {word} -> {text}")
            return True
    return False


def post_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return True
            logging.error("Ошибка Telegram API: %s %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Ошибка при отправке breaking, попытка %s: %s", attempt, exc)

        if attempt < 3:
            time.sleep(attempt * 2)

    return False


def send_breaking(news: str, link: str, source: str = "Неизвестный источник"):
    template = random.choice(TEMPLATES)
    message = template.format(
        news=escape(news),
        link=escape(link, quote=True),
        source=escape(source),
    )
    message = append_hashtags(message, BREAKING_HASHTAGS)

    if DRY_RUN:
        logging.info(f"DRY_RUN breaking: {news} | Источник: {source}")
        print(Fore.MAGENTA + Style.BRIGHT + "[DRY RUN BREAKING]\n" + message)
        return

    if not telegram_configured():
        record_error("breaking", "TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        print(Fore.RED + "[BREAKING] TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    if post_telegram_message(message):
        logging.info(f"Опубликовано breaking: {news} | Источник: {source}")
        print(Fore.RED + Style.BRIGHT + f"[SENT BREAKING] {news}")
        sent_breaking.add(link)
        save_sent_links(sent_breaking)
    else:
        record_error("breaking", "Telegram send failed for breaking post", {"source": source})


def fetch_breaking(sources):
    found = 0
    checked = 0
    errors = 0

    for source in sources:
        url = source_url(source)
        label = source_label(source)
        if not url:
            logging.warning(f"Источник без URL пропущен: {source!r}")
            continue

        checked += 1
        try:
            feed = parse_feed_url(url)
            if not feed or not feed.entries:
                continue

            entry = feed.entries[0]
            link = entry.get("link")
            if not link or link in sent_breaking:
                continue

            title = entry.get("title", "").strip()
            summary = entry.get("summary", "")
            if not title or not passes_filters(title, summary=summary, source=label):
                continue

            if is_breaking(title):
                news = translate_text(title)
                clean_news = clean_text(news)
                send_breaking(clean_news, link, source=label)
                found += 1
        except Exception as e:
            errors += 1
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return checked, found, errors


def run_cycle(sources):
    checked, found, errors = fetch_breaking(sources)
    state = "degraded" if errors and errors == checked else "ok"
    record_status(
        "breaking",
        state,
        "cycle complete",
        {"checked": checked, "found": found, "errors": errors, "dry_run": DRY_RUN},
    )
    print(Fore.CYAN + f"[CYCLE DONE] Проверено {checked} источников, найдено {found} breaking, ошибок {errors}.")
    return checked, found


def parse_args():
    parser = argparse.ArgumentParser(description="Coffee Bot breaking news monitor")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one cycle and exit; useful for dry-run checks before deployment",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    record_status("breaking", "starting", f"monitor started ({mode})")
    print(Fore.YELLOW + f"[BREAKING BOT STARTED] Запущен мониторинг breaking news ({mode}).")

    if args.once:
        run_cycle(sources)
    else:
        try:
            while True:
                run_cycle(sources)
                time.sleep(BREAKING_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            record_status("breaking", "stopping", "monitor stopped by signal", {"dry_run": DRY_RUN})
            logging.info("Breaking-монитор остановлен сигналом")
            print(Fore.YELLOW + "[BREAKING] Остановка по сигналу")
