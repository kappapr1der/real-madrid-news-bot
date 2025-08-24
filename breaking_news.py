import logging
import random
import requests
import os

# Лог
LOG_FILE = "logs/breaking.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8"
)

# Шаблоны для breaking news
TEMPLATES = [
    "☕️ Сливочная молния\n{news}\n🔗 {link}",
    "⚪️ Экстра от «Кофе со сливками»\n{news}\n🔗 {link}",
    "🚨 Горячо из чашки сливочного кофе\n{news}\n🔗 {link}",
    "🔥 Срочно! Новости Реала:\n{news}\n🔗 {link}",
    "🏰 Новости замка Мадрида:\n{news}\n🔗 {link}",
    "✨ В центре внимания:\n{news}\n🔗 {link}",
    "💥 Брызги на поле:\n{news}\n🔗 {link}",
    "📣 Эй, фанаты Реала:\n{news}\n🔗 {link}",
    "⚡️ Breaking из Мадрида:\n{news}\n🔗 {link}",
    "🏃 Быстрое обновление:\n{news}\n🔗 {link}",
    "📰 Горячие новости:\n{news}\n🔗 {link}",
    "🌟 Эксклюзив от «Кофе со сливками»:\n{news}\n🔗 {link}"
]

# Токен и чат
BOT_TOKEN = "***REMOVED***"
CHAT_ID = "@slivochniyfootball"

def send_breaking(news: str, link: str):
    """Отправляет breaking news в Telegram + лог"""
    template = random.choice(TEMPLATES)
    message = template.format(news=news, link=link)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            logging.info(f"Опубликовано breaking: {message}")
        else:
            logging.error(f"Ошибка Telegram API: {r.status_code} {r.text}")
    except Exception as e:
        logging.error(f"Ошибка при отправке breaking: {e}")

# Пример использования (тест)
if __name__ == "__main__":
    test_news = "Важная трансферная новость!"
    test_link = "https://example.com/news1"
    send_breaking(test_news, test_link)
