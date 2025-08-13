import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv
import schedule
import time

# Загружаем переменные
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

# RSS-ленты
RSS_FEEDS = [
    "https://www.realmadrid.com/en/football/news/rss",
    "https://www.marca.com/en/football/real-madrid/rss.xml"
]

# Файл с уже отправленными ссылками
SENT_FILE = "sent_news.txt"
if not os.path.exists(SENT_FILE):
    open(SENT_FILE, "w").close()

def get_sent_links():
    with open(SENT_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_sent_link(link):
    with open(SENT_FILE, "a") as f:
        f.write(link + "\n")

def fetch_rss(url):
    resp = requests.get(url)
    root = ET.fromstring(resp.content)
    for item in root.findall("./channel/item"):
        title = item.find("title").text
        link = item.find("link").text
        yield {"title": title, "link": link}

def send_news():
    sent_links = get_sent_links()
    for feed in RSS_FEEDS:
        for news in fetch_rss(feed):
            if news["link"] not in sent_links:
                hashtags = "#RealMadrid #HalaMadrid #LaLiga"
                message = f"{news['title']}\n{news['link']}\n\n{hashtags}"
                bot.send_message(chat_id=CHAT_ID, text=message)
                save_sent_link(news["link"])

# Запускаем каждую пятницу в 10:00
schedule.every().friday.at("10:00").do(send_news)

print("Бот запущен...")
while True:
    schedule.run_pending()
    time.sleep(60)
