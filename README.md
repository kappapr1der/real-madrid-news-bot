# Coffee Bot (Кофе со сливками)

Телеграм-бот для канала о Real Madrid: собирает RSS-новости, фильтрует нерелевантное, переводит заголовки на русский и публикует breaking-новости и дайджесты.

Проект не требует OpenAI/GPT API. AI-редактор удален из рабочей схемы, чтобы бот оставался бесплатным и стабильным.

## Возможности

- RSS-источники на русском, английском и испанском.
- Фильтр релевантности по Real Madrid, игрокам, турнирам и стоп-словам.
- Перевод через DeepL API Free, если задан `DEEPL_API_KEY`; иначе fallback на `deep-translator` / MyMemory.
- Словари и правки терминов через `terms_by_theme.yaml` и `additions.yaml`.
- Компактные HTML-дайджесты без сырых URL и без огромных link preview.
- Breaking-мониторинг каждые 120 секунд.
- Дайджесты по расписанию: утро, день, вечер.
- Safe dry-run режим: можно тестировать без отправки в Telegram.
- One-shot проверка breaking-цикла через `python breaking.py --once`.
- Heartbeat HTTP-сервис для мониторинга.
- Логи в каталоге `logs/`, runtime-состояние в `state/`.

## Как выглядит дайджест

Вместо сырого URL и большого Telegram-превью бот отправляет компактный HTML-пост:

```text
Вечерний дайджест «Реала»

1. «Реал» узнал диагноз по травме Трента Александер-Арнольда
Читать · Football España

2. «Арсенал» снова интересуется Ардой Гюлером
Читать · FourFourTwo
```

Ссылки спрятаны в `Читать`, а `disable_web_page_preview=True` отключает большую карточку под постом.

## Структура

```text
main.py                                # менеджер процессов
runtime_config.py                      # env, dry-run, пути logs/state
heartbeat.py                           # HTTP heartbeat
breaking.py                            # breaking-мониторинг RSS
digest.py                              # разовый запуск дайджеста
filters.py                             # фильтр релевантности
text_cleaner.py                        # очистка текста после перевода
translator.py                          # перевод + словарные замены
sources_international.py               # международные источники
sources_ru.py                          # русскоязычные источники
scripts/preflight.py                   # проверка синтаксиса и зависимостей
deploy/systemd/coffee-bot.service.example # systemd-шаблон для VPS
requirements.txt                       # зависимости
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

# Безопасный режим по умолчанию: бот печатает сообщения, но не отправляет их.
DRY_RUN=true

# Опционально: улучшает русский перевод без GPT/OpenAI.
DEEPL_API_KEY=
DEEPL_API_URL=https://api-free.deepl.com/v2/translate

STATE_DIR=state
LOG_DIR=logs
BREAKING_INTERVAL_SECONDS=120
HEARTBEAT_PORT=8000
```

Если настоящий Telegram-токен когда-либо попадал в репозиторий, перевыпусти его в BotFather перед деплоем.

## Проверка до сервера

Проверить синтаксис основных модулей и наличие зависимостей:

```bash
python scripts/preflight.py
```

Собрать дайджест без отправки в Telegram:

```bash
DRY_RUN=true python digest.py утреннего
```

Проверить один цикл breaking-мониторинга без бесконечного процесса:

```bash
DRY_RUN=true python breaking.py --once
```

Запустить breaking-мониторинг в безопасном режиме:

```bash
DRY_RUN=true python breaking.py
```

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

## Live-режим

На сервере, когда все проверено, явно выключи dry-run:

```env
DRY_RUN=false
```

Без этого бот не будет публиковать сообщения в Telegram. Это сделано специально, чтобы случайный локальный запуск не стрелял в канал.

## Systemd на VPS

В репозитории есть шаблон:

```text
deploy/systemd/coffee-bot.service.example
```

Перед установкой проверь `User`, `Group`, `WorkingDirectory`, `EnvironmentFile` и `ExecStart` под реальный путь на сервере. Пример для `/opt/coffee-bot`:

```bash
sudo cp deploy/systemd/coffee-bot.service.example /etc/systemd/system/coffee-bot.service
sudo systemctl daemon-reload
sudo systemctl enable coffee-bot.service
sudo systemctl start coffee-bot.service
sudo systemctl status coffee-bot.service
```

## Мониторинг

`heartbeat.py` отвечает `Bernabeu Heartbeat OK` на HTTP-запросы по порту из `HEARTBEAT_PORT` (`8000` по умолчанию).

`uptime_webhook.py` можно использовать для webhook-уведомлений от UptimeRobot. Он берет Telegram-токен и канал из `.env`, а не из кода.

## Runtime-файлы

Не коммить:

- `.env`
- `logs/`
- `state/`
- `sent_links.txt`
- `sent_breaking.txt`

`sent_links.txt` и `sent_breaking.txt` теперь живут в `STATE_DIR`, чтобы история отправленных ссылок не попадала в git.

## Примечания

- Для бесплатного режима не нужны `OPENAI_API_KEY`, `OPENROUTER_API_KEY` или другие LLM-ключи.
- Для лучшего перевода можно добавить бесплатный `DEEPL_API_KEY`; без него бот продолжит работать через текущие fallback-переводчики.
