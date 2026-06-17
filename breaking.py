#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import logging
import random
from typing import Any

import requests
import feedparser
from dotenv import load_dotenv
from deep_translator import GoogleTranslator, MyMemoryTranslator
from colorama import init, Fore, Style

from text_cleaner import clean_text
from filters import passes_filters
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU

init(autoreset=True)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TARGET_CHAT_ID")

LOG_FILE = "logs/breaking.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = "sent_breaking.txt"


def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
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
    "☕️ Сливочная молния\n{news}\nИсточник: {source}\n🔗 {link}",
    "⚪️ Экстра от «Кофе со сливками»\n{news}\nИсточник: {source}\n🔗 {link}",
    "🚨 Горячо из чашки сливочного кофе\n{news}\nИсточник: {source}\n🔗 {link}",
    "🔥 Срочно! Новости Реала:\n{news}\nИсточник: {source}\n🔗 {link}",
    "🏰 Новости замка Мадрида:\n{news}\nИсточник: {source}\n🔗 {link}",
    "✨ В центре внимания:\n{news}\nИсточник: {source}\n🔗 {link}",
    "💥 Брызги на поле:\n{news}\nИсточник: {source}\n🔗 {link}",
    "📣 Эй, фанаты Реала:\n{news}\nИсточник: {source}\n🔗 {link}",
    "⚡️ Breaking из Мадрида:\n{news}\nИсточник: {source}\n🔗 {link}",
    "🏃 Быстрое обновление:\n{news}\nИсточник: {source}\n🔗 {link}",
    "📰 Горячие новости:\n{news}\nИсточник: {source}\n🔗 {link}",
    "🌟 Эксклюзив от «Кофе со сливками»:\n{news}\nИсточник: {source}\n🔗 {link}",
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


def translate_text(text: str) -> str:
    try:
        return GoogleTranslator(source="auto", target="ru").translate(text)
    except Exception:
        try:
            return MyMemoryTranslator(source="auto", target="ru").translate(text)
        except Exception:
            return text


def is_breaking(text: str) -> bool:
    lower_text = text.lower()
    for word in BREAKING_KEYWORDS:
        if word in lower_text:
            print(Fore.RED + Style.BRIGHT + f"[BREAKING DETECTED] {word} -> {text}")
            logging.info(f"Обнаружено ключевое слово: {word} -> {text}")
            return True
    return False


def send_breaking(news: str, link: str, source: str = "Неизвестный источник"):
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        print(Fore.RED + "[BREAKING] TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    template = random.choice(TEMPLATES)
    message = template.format(news=news, link=link, source=source)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info(f"Опубликовано breaking: {news} | Источник: {source}")
            print(Fore.RED + Style.BRIGHT + f"[SENT BREAKING] {news}")
            sent_breaking.add(link)
            save_sent_links(sent_breaking)
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке breaking: {e}")


def fetch_breaking(sources):
    found = 0
    checked = 0

    for source in sources:
        url = source_url(source)
        label = source_label(source)
        if not url:
            logging.warning(f"Источник без URL пропущен: {source!r}")
            continue

        checked += 1
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
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
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return checked, found


if __name__ == "__main__":
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    print(Fore.YELLOW + "[BREAKING BOT STARTED] Запущен мониторинг breaking news.")
    while True:
        checked, found = fetch_breaking(sources)
        print(Fore.CYAN + f"[CYCLE DONE] Проверено {checked} источников, найдено {found} breaking.")
        time.sleep(120)
