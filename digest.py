#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import random

import requests
import feedparser

from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from filters import passes_filters
from translator import translate_text
from runtime_config import (
    DRY_RUN,
    TELEGRAM_BOT_TOKEN,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)

LOG_FILE = get_log_file("digest.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = get_state_file("sent_links.txt")


def load_sent_links():
    if not SENT_FILE.exists():
        return set()
    with SENT_FILE.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with SENT_FILE.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


sent_digest = load_sent_links()

TEMPLATES = {
    "утреннего": [
        "☕️ Утренний сливочный дайджест\n\n{news}",
        "🌅 Доброе утро, мадридисты!\n\n{news}",
    ],
    "дневного": [
        "⚪️ Дневная подборка от «Кофе со сливками»\n\n{news}",
        "📋 Всё самое важное днём:\n\n{news}",
    ],
    "вечернего": [
        "🌙 Вечерние сливки дня\n\n{news}",
        "📰 Вечерний дайджест Реала:\n\n{news}",
    ],
    "ночного": [
        "🌌 Ночной сливочный дайджест\n\n{news}",
        "💤 Пока вы спите, у нас новости:\n\n{news}",
    ],
    "default": [
        "📋 Дайджест Реала:\n\n{news}",
        "📰 Всё самое важное:\n\n{news}",
    ],
}


def format_news_entry(i: int, text: str, link: str, source: str) -> str:
    return f"{i}️⃣ {text}\n🔗 {link}\nИсточник: {source}"


def fetch_digest(sources, limit=10):
    seen_links = set(sent_digest)
    new_links = set()
    news_items = []

    for src in sources:
        url = src.get("url")
        label = src.get("label", url or "Неизвестный источник")
        if not url:
            logging.warning(f"Источник без URL пропущен: {src!r}")
            continue

        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            for entry in feed.entries[:3]:
                link = entry.get("link")
                if not link or link in seen_links:
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                if not title or not passes_filters(title, summary=summary, source=label):
                    continue

                cleaned = translate_text(title)
                formatted = format_news_entry(len(news_items) + 1, cleaned, link, label)
                news_items.append(formatted)
                seen_links.add(link)
                new_links.add(link)

                if len(news_items) >= limit:
                    break

            if len(news_items) >= limit:
                break

        except Exception as e:
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return news_items, new_links


def send_digest(label: str = "default"):
    global sent_digest

    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items, new_links = fetch_digest(sources, limit=10)

    if not news_items:
        logging.info(f"Нет новостей для {label} дайджеста")
        return

    joined_news = "\n━━━━━━━━━━━━━━\n".join(news_items) if len(news_items) > 3 else "\n\n".join(news_items)
    templates = TEMPLATES.get(label, TEMPLATES["default"])
    message = random.choice(templates).format(news=joined_news)

    if DRY_RUN:
        logging.info(f"DRY_RUN {label} дайджест: {len(news_items)} новостей")
        print(f"[DRY RUN DIGEST: {label}]\n{message}")
        return

    if not telegram_configured():
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            sent_digest.update(new_links)
            save_sent_links(sent_digest)
            logging.info(f"Опубликован {label} дайджест")
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке дайджеста: {e}")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "default"
    send_digest(arg)
