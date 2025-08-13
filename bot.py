import os
import feedparser
import requests
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # например @my_channel или -100123456789
RSS_FEEDS = [
    "https://www.realmadrid.com/en/rss/news",
    "https://www.marca.com/en/rss/futbol/real-madrid.xml",
    "https://as.com/rss/futbol/real_madrid.xml"
]
POSTED_FILE = "posted.txt"

# Загружаем список уже отправленных новостей
if os.path.exists(POSTED_FILE):
    with open(POSTED_FILE, "r", encoding="utf-8") as f:
        posted_links = set(f.read().splitlines())
else:
    posted_links = set()

def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def check_news():
    global posted_links
    new_posts = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            if entry.link not in posted_links:
                post_text = f"<b>{entry.title}</b>\n{entry.link}\n\n#RealMadrid #Новости"
                send_message(post_text)
                posted_links.add(entry.link)
                new_posts.append(entry.link)
    if new_posts:
        with open(POSTED_FILE, "a", encoding="utf-8") as f:
            for link in new_posts:
                f.write(link + "\n")
        print(f"[{datetime.now()}] Отправлено {len(new_posts)} новостей.")
    else:
        print(f"[{datetime.now()}] Новостей нет.")

# Запуск в 10:00 по UTC (можно поменять)
schedule.every().day.at("10:00").do(check_news)

print("Бот запущен. Ожидаю расписания...")
while True:
    schedule.run_pending()
    time.sleep(30)
