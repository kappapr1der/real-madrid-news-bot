import os
import time
import logging
import random
import requests
import feedparser
from dotenv import load_dotenv
from deep_translator import GoogleTranslator, MyMemoryTranslator
from colorama import init, Fore, Style
from text_cleaner import clean_text
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from anti_spam_unified import AntiSpamUnified

# Colorama
init(autoreset=True)

# .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TARGET_CHAT_ID")

# Лог
LOG_FILE = "logs/breaking.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s", encoding="utf-8")

# Антиспам
antispam = AntiSpamUnified()

BREAKING_KEYWORDS = ["breaking", "urgent", "official", "confirmed", "экстренно", "срочно", "официально", "подтверждено"]

TEMPLATES = [
    "☕️ Сливочная молния\n{news}\nИсточник: {source}\n🔗 {link}",
    "⚪️ Экстра от «Кофе со сливками»\n{news}\nИсточник: {source}\n🔗 {link}",
    "🚨 Горячо из чашки сливочного кофе\n{news}\nИсточник: {source}\n🔗 {link}"
]

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
            print(Fore.RED + Style.BRIGHT + f"[BREAKING DETECTED] {word} → {text}")
            logging.info(f"Обнаружено ключевое слово: {word} → {text}")
            return True
    return False

def send_breaking(news: str, link: str, source: str = "Неизвестный источник"):
    template = random.choice(TEMPLATES)
    message = template.format(news=news, link=link, source=source)
    if antispam.is_duplicate_link(link) or antispam.is_duplicate_text(news):
        logging.info(f"Дубликат breaking пропущен: {news}")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": False}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info(f"Опубликовано breaking: {news} | Источник: {source}")
            print(Fore.RED + Style.BRIGHT + f"[SENT BREAKING] {news}")
            antispam.mark_sent(link=link, text=news)
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке breaking: {e}")

def fetch_breaking(sources):
    found = 0
    checked = 0
    for url in sources:
        checked += 1
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            entry = feed.entries[0]
            link = entry.get("link")
            title = entry.get("title", "").strip()
            if not link or not title:
                continue
            if is_breaking(title):
                news = translate_text(title)
                clean_news = clean_text(news)
                send_breaking(clean_news, link, source=url)
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
