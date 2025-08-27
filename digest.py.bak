#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import random
import requests
import feedparser
from dotenv import load_dotenv

from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from text_cleaner import clean_text
from filters import passes_filters
from translator import translate_text  # ✅ наш словарный переводчик

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TARGET_CHAT_ID")

LOG_FILE = "logs/digest.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

SENT_FILE = "sent_links.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_links(links):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")

sent_digest = load_sent_links()

TEMPLATES = {
    "утреннего": [
        "☕️ Утренний сливочный дайджест\n\n{news}",
        "🌅 Доброе утро, мадридисты!\n\n{news}"
    ],
    "дневного": [
        "⚪️ Дневная подборка от «Кофе со сливками»\n\n{news}",
        "📋 Всё самое важное днём:\n\n{news}"
    ],
    "вечернего": [
        "🌙 Вечерние сливки дня\n\n{news}",
        "📰 Вечерний дайджест Реала:\n\n{news}"
    ],
    "ночного": [
        "🌌 Ночной сливочный дайджест\n\n{news}",
        "💤 Пока вы спите, у нас новости:\n\n{news}"
    ],
    "default": [
        "📋 Дайджест Реала:\n\n{news}",
        "📰 Всё самое важное:\n\n{news}"
    ]
}

def format_news_entry(i: int, text: str, link: str, source: str) -> str:
    return f"{i}️⃣ {text}\n🔗 {link}\nИсточник: {source}"

def fetch_digest(sources, limit=10):
    global sent_digest
    news_items = []

    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            if not feed.entries:
                continue

            for entry in feed.entries[:3]:
                link = entry.get("link")
                if not link or link in sent_digest:
                    continue

                title = entry.get("title", "").strip()
                if not title or not passes_filters(title):
                    continue

                cleaned = translate_text(title)  # ✅ словарный перевод
                formatted = format_news_entry(len(news_items) + 1, cleaned, link, src["label"])
                news_items.append(formatted)
                sent_digest.add(link)

                if len(news_items) >= limit:
                    break

            if len(news_items) >= limit:
                break

        except Exception as e:
            logging.error(f"Ошибка при парсинге {src['url']}: {e}")

    save_sent_links(sent_digest)
    return news_items

def send_digest(label: str = "default"):
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items = fetch_digest(sources, limit=10)

    if not news_items:
        logging.info(f"Нет новостей для {label} дайджеста")
        return

    joined_news = "\n━━━━━━━━━━━━━━\n".join(news_items) if len(news_items) > 3 else "\n\n".join(news_items)
    templates = TEMPLATES.get(label, TEMPLATES["default"])
    message = random.choice(templates).format(news=joined_news)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info(f"Опубликован {label} дайджест")
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке дайджеста: {e}")

if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "default"
    send_digest(arg)
