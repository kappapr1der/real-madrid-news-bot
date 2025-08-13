import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN:
    raise ValueError("❌ TOKEN не найден. Укажи его в переменных окружения Render.")

app = Flask(__name__)

telegram_app = Application.builder().token(TOKEN).build()

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    telegram_app.update_queue.put_nowait(update)
    return "OK"

@app.route("/")
def home():
    return "Real Madrid Bot работает через webhook 🚀"

async def send_news():
    await telegram_app.bot.send_message(
        chat_id=CHAT_ID,
        text="⚽ Свежие новости Реал Мадрид!"
    )

if __name__ == "__main__":
    # Устанавливаем webhook
    import asyncio
    from telegram import Bot
    bot = Bot(TOKEN)
    asyncio.run(bot.set_webhook("https://YOUR-APP-NAME.onrender.com/" + TOKEN))
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
