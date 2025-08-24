import os
import logging
import random
import requests
import feedparser
from dotenv import load_dotenv
from deep_translator import GoogleTranslator, MyMemoryTranslator

from text_cleaner import clean_text
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from anti_spam_unified import AntiSpamUnified

# Загрузка .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TARGET_CHAT_ID")

# Лог
LOG_FILE = "logs/digest.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

# Инициализация антиспам
antispam = AntiSpamUnified()

TEMPLATES = {
    "утреннего": ["☕️ Утренний сливочный дайджест\n{news}", "🌅 Доброе утро, мадридисты!\n{news}"],
    "дневного": ["⚪️ Дневная подборка от «Кофе со сливками»\n{news}", "📋 Всё самое важное днём:\n{news}"],
    "вечернего": ["🌙 Вечерние сливки дня\n{news}", "📰 Вечерний дайджест Реала:\n{news}"],
    "ночного": ["🌌 Ночной сливочный дайджест\n{news}", "💤 Пока вы спите, у нас новости:\n{news}"],
    "default": ["📋 Дайджест Реала:\n{news}", "📰 Всё самое важное:\n{news}"]
}

def translate_text(text: str) -> str:
    try:
        translated = GoogleTranslator(source="auto", target="ru").translate(text)
    except Exception:
        try:
            translated = MyMemoryTranslator(source="auto", target="ru").translate(text)
        except Exception:
            translated = text
    return clean_text(translated)

def fetch_digest(sources, limit=10):
    news_items = []
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
            if not feed.entries:
                continue
            for entry in feed.entries[:2]:
                link = entry.get("link")
                title = entry.get("title", "").strip()
                if not link or not title:
                    continue
                if antispam.is_duplicate_link(link) or antispam.is_duplicate_text(title):
                    continue
                translated = translate_text(title)
                news = f"{translated}\n🔗 {link}\nИсточник: {src['label']}"
                news_items.append(news)
                antispam.mark_sent(link=link, text=title)
                if len(news_items) >= limit:
                    break
            if len(news_items) >= limit:
                break
        except Exception as e:
            logging.error(f"Ошибка при парсинге {src['url']}: {e}")
    return news_items

def send_digest(label: str = "default"):
    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items = fetch_digest(sources, limit=10)
    if not news_items:
        logging.info(f"Нет новостей для {label} дайджеста")
        return
    joined_news = "\n━━━━━━━━━━━━━━\n".join(news_items) if len(news_items) > 3 else "\n\n".join(news_items)
    template = random.choice(TEMPLATES.get(label, TEMPLATES["default"]))
    message = template.format(news=joined_news)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": False}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info(f"Опубликован {label} дайджест")
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке дайджеста: {e}")

if __name__ == "__main__":
    send_digest("default")
