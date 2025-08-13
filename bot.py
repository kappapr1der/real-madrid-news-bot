import os
import json
import feedparser
import requests
import schedule
import time
from dotenv import load_dotenv
from datetime import datetime

# Загружаем переменные окружения
if os.path.exists("config.env"):
    load_dotenv("config.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Пути
DATA_DIR = "data"
POSTED_FILE = os.path.join(DATA_DIR, "posted_links.json")

# Создаём папку и файл, если их нет
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

if not os.path.exists(POSTED_FILE):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

# Загружаем уже опубликованные ссылки
with open(POSTED_FILE, "r", encoding="utf-8") as f:
    try:
        posted_links = json.load(f)
    except json.JSONDecodeError:
        posted_links = []

# Источники новостей про Реал Мадрид
RSS_FEEDS = [
    "https://www.realmadrid.com/en/football/rss",
    "https://www.marca.com/en/football/real-madrid/rss",
    "https://as.com/rss/real-madrid/portada.xml",
    "https://www.uefa.com/rss/real-madrid.xml"
]

# Хэштеги для постов
HASHTAGS = "#RealMadrid #HalaMadrid #LaLiga #UCL #Football"

def get_latest_news():
    news_items = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            link = entry.link
            title = entry.title
            if link not in posted_links:
                news_items.append({
                    "title": title,
                    "link": link
                })
    return news_items

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "di
