import os
import requests
import schedule
import time
from dotenv import load_dotenv
from telegram import Bot

# Загружаем переменные окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

# Функция для получения новостей
def get_news():
    url = "https://api.sportsdata.io/v4/soccer/scores/json/NewsByTeam/REA"  # пример API
    headers = {"Ocp-Apim-Subscription-Key": os.getenv("SPORTS_API_KEY")}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        if data:
            latest = data[0]
            title = latest.get("Title", "")
            content = latest.get("Content", "")
            message = f"⚽ {title}\n\n{content}\n\n#RealMadrid #Новости"
            bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print(f"Ошибка получения новостей: {e}")

# Планировщик
schedule.every(30).minutes.do(get_news)

if __name__ == "__main__":
    get_news()  # отправим сразу при старте
    while True:
        schedule.run_pending()
        time.sleep(60)
