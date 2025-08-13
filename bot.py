import os
import requests
import schedule
import time
from telegram import Bot
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("❌ Ошибка: Нет TOKEN или CHAT_ID. Проверь переменные окружения.")
    exit()

bot = Bot(token=TOKEN)

# Функция получения новостей (пример с Google News RSS)
def get_real_madrid_news():
    url = "https://news.google.com/rss/search?q=Real+Madrid&hl=ru&gl=RU&ceid=RU:ru"
    try:
        response = requests.get(url)
        response.raise_for_status()
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        news_list = []
        for item in items[:3]:  # последние 3 новости
            title = item.find("title").text
            link = item.find("link").text
            news_list.append(f"⚽ {title}\n{link}")
        return "\n\n".join(news_list)
    except Exception as e:
        return f"Ошибка получения новостей: {e}"

# Функция отправки новости
def send_news():
    news = get_real_madrid_news()
    bot.send_message(chat_id=CHAT_ID, text=news)
    print("✅ Новости отправлены")

# Запускаем каждые 6 часов
schedule.every(6).hours.do(send_news)

print("🤖 Бот запущен и ждет следующей отправки...")
send_news()  # отправляем сразу при старте

while True:
    schedule.run_pending()
    time.sleep(60)
