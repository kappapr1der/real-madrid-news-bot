import os
import json
import feedparser
import logging
import requests
import schedule
import time
from datetime import datetime
from telegram import Bot
from telegram.ext import Updater, CommandHandler

# ------------------ НАСТРОЙКА ЛОГОВ ------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ------------------ ЧТЕНИЕ ТОКЕНОВ ------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)

# ------------------ НАСТРОЙКА БОТА ------------------
bot = Bot(token=TELEGRAM_TOKEN)

# ------------------ ФАЙЛ ДЛЯ ССЫЛОК ------------------
DATA_FILE = "data/posted_links.json"

if not os.path.exists("data"):
    os.makedirs("data")

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# ------------------ СПИСОК RSS-ЛЕНТ ------------------
RSS_FEEDS = [
    "https://www.realmadrid.com/StaticFiles/RealMadrid/Feeds/es/Rss/News_rss.xml",
    "https://www.marca.com/en/rss/real-madrid.xml",
    "https://as.com/rss/futbol/real_madrid.xml"
]

# ------------------ КОМАНДА /id ------------------
def get_chat_id(update, context):
    update.message.reply_text(f"Твой Chat ID: {update.effective_chat.id}")

# ------------------ ЗАГРУЗКА ПРОЧИТАННЫХ ССЫЛОК ------------------
def load_posted_links():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ------------------ СОХРАНЕНИЕ ССЫЛОК ------------------
def save_posted_links(links):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

# ------------------ ПОЛУЧЕНИЕ НОВОСТЕЙ ------------------
def get_latest_news():
    posted_links = load_posted_links()
    new_posts = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if entry.link not in posted_links:
                new_posts.append({
                    "title": entry.title,
                    "link": entry.link
                })
                posted_links.append(entry.link)

    save_posted_links(posted_links)
    return new_posts

# ------------------ ОТПРАВКА НОВОСТЕЙ ------------------
def send_news():
    news_items = get_latest_news()
    if new
