import os
import threading
import time
import feedparser
import schedule
from telegram import Bot
from flask import Flask

# Загружаем переменные
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

# Новости о Реал Мадрид
RSS_FEEDS = [
    "https://www.realmadrid.com/en/rss",
    "https://www.marca.com/en/football/real-madrid/rss.html",
    "https://www.managingmadrid.com/rss/index.xml"
]

# Функция отправки новостей
def send_news():
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            message = f"{entry.title}\n{entry.link}\n#RealMadrid #HalaMadrid"
            bot.send_message(chat_id=CHAT_ID, text=message)
    print("Новости отправлены!")

# Планировщик — каждую пятницу в 12:00
schedule.every().friday.at("12:00").do(send_news)

# Фоновая задача для планировщика
def scheduler_thread():
    while True:
        schedule.run_pending()
        time.sleep(30)

# Flask для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "Real Madrid bot is running!"

if __name__ == "__main__":
    # Запускаем планировщик в отдельном потоке
    t = threading.Thread(target=scheduler_thread)
    t.start()

    # Запускаем веб-сервер (Render будет проверять этот порт)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
