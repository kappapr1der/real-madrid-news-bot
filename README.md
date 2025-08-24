# ☕ Coffee Bot (Кофе со сливками)

Телеграм-бот, который собирает новости о **Real Madrid**  
с англоязычных, испанских и русскоязычных источников.  
Публикует переводы в канал 👉 [Кофе со сливками](https://t.me/slivochniyfootball)

---

## 🚀 Возможности
- Сбор новостей с более чем 40 источников (RSS, сайты, Twitter-зеркала)
- Автоматический перевод на русский язык
- Умный фильтр (убирает тизеры, дубли и спам)
- Постинг в Telegram-канал
- 💓 Heartbeat-сервис для мониторинга активности
- Логирование в консоль для удобного отслеживания работы

---

## 📂 Структура проекта
coffee-bot/
├── main.py # основной код бота
├── heartbeat_service.py # отдельный heartbeat
├── sources_int.py # иностранные источники (английские, испанские, международные)
├── sources_ru.py # русскоязычные источники
├── requirements.txt # зависимости
└── README.md # документация

yaml
Копировать
Редактировать

---

## ⚡ Автозапуск
Оба сервиса запускаются через systemd:
- `coffee-bot.service` — бот
- `heartbeat.service` — мониторинг

Примеры команд:
```bash
sudo systemctl start coffee-bot.service
sudo systemctl stop coffee-bot.service
sudo systemctl restart coffee-bot.service
sudo systemctl status coffee-bot.service
🔗 Канал
Новости публикуются здесь: t.me/slivochniyfootball

🛠️ Технологии
Python 3.10

Aiogram 3.x

Loguru

Deep Translator / MyMemory API

Systemd (VPS)

GitHub для синхронизации
