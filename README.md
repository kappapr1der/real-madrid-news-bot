# ⚽ Real Madrid News Bot

# Real Madrid News Bot

Бот для Telegram, который каждую пятницу публикует новости о Реал Мадрид.

## 🚀 Запуск на Render (бесплатно)
1. Сделайте fork репозитория.
2. Зайдите на [Render](https://render.com) → **New Web Service**.
3. Подключите свой репозиторий.
4. Настройки:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Instance Type: Free
5. В **Environment Variables** добавьте:
   - `TELEGRAM_TOKEN` — токен вашего бота
   - `CHAT_ID` — ID чата для отправки новостей
6. Запустите сервис. Готово!

## 📅 Расписание

Бот отправляет 3 свежие новости с каждого RSS-источника каждую пятницу в 12:00.

## 🏷️ Хэштеги
Каждая новость содержит:

#RealMadrid #HalaMadrid

🏆 Автор kappapr1der

Разработано с ❤️ для болельщиков Реал Мадрид.










