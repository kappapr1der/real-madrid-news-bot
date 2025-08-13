import os
import requests
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

# Получение новостей (здесь несколько источников)
def get_latest_news():
    sources = [
        "https://onefootball.com/ru/team/real-madrid-26/news",
        "https://www.realmadrid.com/en/news/rss",
        "https://www.marca.com/rss/futbol/real-madrid.xml"
    ]
    news_list = []
    for url in sources:
        try:
            r = requests.get(url, timeout=5)
            news_list.append(f"{url} — {len(r.text)} символов получено")
        except:
            news_list.append(f"Ошибка получения {url}")
    return "\n".join(news_list)

# /start
async def start(update, context):
    await update.message.reply_text("Привет! Я Real Madrid News Bot.")

# /news — постинг свежих новостей
async def news(update, context):
    latest = get_latest_news()
    await update.message.reply_text(f"Последние новости:\n{latest}")

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
