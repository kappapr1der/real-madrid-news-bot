import os
import feedparser
import requests
import schedule
import time
from dotenv import load_dotenv
from telegram import Bot
from openai import OpenAI

# Загружаем переменные окружения из .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

RSS_URL = "https://www.realmadrid.com/en/football/rss"

def fetch_news():
    """Получаем последние новости из RSS"""
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        print("Новостей нет")
        return None

    latest = feed.entries[0]
    title = latest.title
    link = latest.link

    return f"{title}\n{link}"

def summarize_text(text):
    """Делаем краткое резюме через OpenAI"""
    try:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты футбольный новостной редактор."},
                {"role": "user", "content": f"Сделай краткое резюме новости: {text}"}
            ],
            max_tokens=100
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Ошибка OpenAI: {e}")
        return text

def send_news():
    news = fetch_news()
    if news:
        summary = summarize_text(news)
        bot.send_message(chat_id=CHAT_ID, text=summary)
        print("Новость отправлена!")

# Запускаем проверку каждые 60 минут
schedule.every(60).minutes.do(send_news)

if __name__ == "__main__":
    print("Бот запущен...")
    send_news()  # сразу отправим при старте
    while True:
        schedule.run_pending()
        time.sleep(1)
