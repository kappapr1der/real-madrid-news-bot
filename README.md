# ⚽ Real Madrid News Bot

Бот, который автоматически собирает свежие новости о **Реал Мадрид**, переводит их (если нужно), добавляет хэштеги и публикует в Telegram-канал.

---

## 🚀 Запуск

### 1. Локально
1. Установите [Python 3.10+](https://www.python.org/downloads/).
2. Склонируйте репозиторий:
   ```bash
   git clone https://github.com/username/real-madrid-news-bot.git
   cd real-madrid-news-bot
3. Установите зависимости:

bash

pip install -r requirements.txt

4. Создайте файл config.env на основе config.env.example и заполните переменные.

5. Запустите бота:
python bot.py
Запустите бота:
bash
python bot.py

2. На Render (бесплатно)
1.Сделайте fork репозитория.

2. Зайдите на render.com → New Web Service.

3. Подключите репозиторий.

4. Укажите:

- Build Command:
pip install -r requirements.txt

- Start Command:
python bot.py

5. Добавьте переменные окружения из config.env.example.

6. Нажмите Deploy.

3. В Docker
docker build -t real-madrid-bot .
docker run --env-file config.env real-madrid-bot


⚙️ Переменные окружения
| Переменная         | Описание                              |
| ------------------ | ------------------------------------- |
| TELEGRAM\_TOKEN    | Токен бота от @BotFather              |
| TELEGRAM\_CHAT\_ID | ID канала или чата                    |
| OPENAI\_API\_KEY   | API-ключ OpenAI (для перевода текста) |


📂 Структура проекта

real-madrid-news-bot/
├── bot.py

├── requirements.txt

├── Procfile

├── Dockerfile

├── README.md

├── config.env.example

└── data/
    └── posted_links.json


🏆 Автор kappapr1der
Разработано с ❤️ для болельщиков Реал Мадрид.





