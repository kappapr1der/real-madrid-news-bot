# Coffee Bot (Кофе со сливками)

Телеграм-бот для канала о Real Madrid: собирает RSS-новости, фильтрует нерелевантное, переводит заголовки на русский и публикует breaking-новости и дайджесты.

Проект не требует OpenAI/GPT API. AI-редактор удален из рабочей схемы, чтобы бот оставался бесплатным и стабильным.

## Возможности

- RSS-источники на русском, английском и испанском.
- Фильтр релевантности по Real Madrid, игрокам, турнирам и стоп-словам.
- Перевод через `deep-translator` с fallback на MyMemory.
- Словари и правки терминов через `terms_by_theme.yaml` и `additions.yaml`.
- Breaking-мониторинг каждые 120 секунд.
- Дайджесты по расписанию: утро, день, вечер.
- Heartbeat HTTP-сервис для мониторинга.
- Логи в каталоге `logs/`.

## Структура

```text
main.py                  # менеджер процессов
heartbeat.py             # HTTP heartbeat на порту 8000
breaking.py              # breaking-мониторинг RSS
digest.py                # разовый запуск дайджеста
filters.py               # фильтр релевантности
text_cleaner.py          # очистка текста после перевода
translator.py            # перевод + словарные замены
sources_international.py # международные источники
sources_ru.py            # русскоязычные источники
utils/                   # вспомогательные функции
requirements.txt         # зависимости
```

## Настройка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` нужно указать:

```env
TELEGRAM_BOT_TOKEN=123456789:replace_me
TARGET_CHAT_ID=@your_channel_username
```

Если настоящий Telegram-токен когда-либо попадал в репозиторий, перевыпусти его в BotFather перед деплоем.

## Запуск

Полный менеджер:

```bash
python main.py
```

Отдельные сервисы:

```bash
python heartbeat.py
python breaking.py
python digest.py утреннего
python digest.py дневного
python digest.py вечернего
```

`main.py` запускает `heartbeat.py` и `breaking.py`, а также планирует дайджесты на `08:00`, `14:00` и `20:00` по локальному времени сервера.

## Мониторинг

`heartbeat.py` отвечает `Bernabeu Heartbeat OK` на HTTP-запросы по порту `8000`.

`uptime_webhook.py` можно использовать для webhook-уведомлений от UptimeRobot. Он берет Telegram-токен и канал из `.env`, а не из кода.

## Примечания

- Не коммить `.env`, логи и файлы `sent_links.txt` / `sent_breaking.txt`.
- Для бесплатного режима не нужны `OPENAI_API_KEY`, `OPENROUTER_API_KEY` или другие LLM-ключи.
- Если когда-нибудь понадобится улучшить перевод, самый простой опциональный следующий слой - DeepL API Free, но базовая версия уже работает без него.
