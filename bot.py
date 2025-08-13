import os
import requests
import feedparser
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app = Flask(__name__)
bot = Bot(token=TOKEN)

# Получение новостей из нескольких RSS-источников
def get_latest_news(limit=5):
    sources = [
        "https://www.realmadrid.com/en/news/rss",
        "https://www.marca.com/rss/futbol/real-madrid.xml",
        "https://www.espn.com/espn/rss/football/news"
    ]
    
    news_list = []
    for url in sources:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                title = entry.title
                link = entry.link
                news_list.append(f"🔹 {title}\n{link}")
        except Exception as e:
            news_list.append(f"Ошибка при получении {url}: {e}")
    
    return "\n\n".join(news_list)

# /start
async def start(update, context):
    await update.message.reply_text("Привет! Я Real Madrid News Bot.")

# /news — постинг свежих новостей
async def news(update, context):
    latest = get_latest_news()
    await update.message.reply_text(f"📰 Последние новости:\n\n{latest}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    application.update_queue.put_nowait(update)
    return "OK", 200

if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("news", news))

    # Устанавливаем вебхук
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

    # Flask-приложение для Render
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
