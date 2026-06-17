# Coffee Bot (Кофе со сливками)

Телеграм-бот для канала о Real Madrid: собирает RSS-новости, фильтрует нерелевантное, переводит заголовки на русский и публикует breaking-новости, дайджесты и матчевые обновления.

Проект не требует OpenAI/GPT API. AI-редактор удален из рабочей схемы, чтобы бот оставался бесплатным и стабильным.

## Идея канала

`Кофе со сливками` — это не кофейная рубрика, а фанатский образ вокруг «сливочных»: белая форма, Мадрид, Бернабеу, мадридисты и новости о клубе без случайного футбольного шума.

Тон дайджестов поэтому ближе к болельщицкой сводке: `Утренние сливки Мадрида`, `Белое утро на Бернабеу`, `К этому часу у сливочных`, `Вечерняя белая хроника`.

## Возможности

- RSS-источники на русском, английском и испанском.
- Профильные Real Madrid RSS в приоритете: Managing Madrid, Madrid Universal, The Real Champs, Defensa Central, Bernabéu Digital, Marca, Mundo Deportivo, Sport и другие.
- Фильтр релевантности по Real Madrid, игрокам, турнирам, профильным источникам и стоп-словам.
- Перевод через DeepL API Free, если задан `DEEPL_API_KEY`; иначе fallback на `deep-translator` / MyMemory.
- Словари и правки терминов через `terms_by_theme.yaml` и `additions.yaml`.
- Компактные HTML-дайджесты и breaking-посты без сырых URL и без огромных link preview.
- Длинные Telegram-сообщения режутся на части до `TELEGRAM_MESSAGE_LIMIT`.
- RSS читается через HTTP timeout и `HTTP_USER_AGENT`, чтобы плохой источник не подвешивал процесс.
- Свежие дайджесты: бот берет дату публикации из RSS, отбрасывает старые новости и сортирует новые сверху.
- Автоматический тип дайджеста по времени: утренний, дневной, вечерний или ночной.
- Расписание дайджестов настраивается через `.env` и работает в `DIGEST_TIMEZONE`, а не в случайной таймзоне VPS.
- Матч-день: отдельный процесс для превью/старта/перерыва/финального свистка и будущих live-событий.
- Дайджесты автоматически пропускаются в матчевое окно, чтобы не перекрывать матч.
- Breaking-мониторинг каждые 120 секунд.
- Safe dry-run режим: можно тестировать без отправки в Telegram.
- One-shot проверка breaking-цикла через `python breaking.py --once`.
- Проверка RSS-источников через `python scripts/check_sources.py`.
- `preflight.py` проверяет синтаксис, зависимости и базовую валидность `.env`.
- Heartbeat HTTP-сервис для мониторинга.
- Логи в каталоге `logs/`, runtime-состояние в `state/`.

## Как выглядит дайджест

Вместо сырого URL и большого Telegram-превью бот отправляет компактный HTML-пост:

```text
Белое утро на Бернабеу
Свежие новости о «Реале» за ночь и утро.

1. «Реал» узнал диагноз по травме Трента Александер-Арнольда
Читать · Football España – Real Madrid · 14:23

2. «Арсенал» снова интересуется Ардой Гюлером
Читать · The Real Champs · 13:58
```

Ссылки спрятаны в `Читать`, время берется из даты публикации RSS, а `disable_web_page_preview=True` отключает большую карточку под постом.

## Матч-день

Матчевый режим пока не привязан к платному live API. Он использует локальный календарь `config/matches.json` и готов к подключению внешнего провайдера событий позже.

Создать календарь на сервере:

```bash
cp config/matches.example.json config/matches.json
```

Формат матча:

```json
{
  "id": "laliga-2026-08-23-real-madrid-opponent",
  "competition": "La Liga",
  "round": "Matchday 1",
  "home": "Real Madrid",
  "away": "Opponent",
  "kickoff": "2026-08-23T21:00:00+02:00",
  "venue": "Santiago Bernabeu",
  "broadcast": ""
}
```

Проверить ближайшие матчи:

```bash
python matchday.py --list
```

Проверить автопосты матча без отправки в Telegram:

```bash
DRY_RUN=true python matchday.py --once
```

Отправить ручное или будущее live-событие:

```bash
DRY_RUN=true python matchday.py --match-id laliga-2026-08-23-real-madrid-opponent --minute 23 --kind goal --score 1:0 --event-text "Беллингем открывает счет после передачи Винисиуса"
```

`main.py` запускает `matchday.py` отдельным процессом, если `MATCHDAY_ENABLED=true`. Автопосты сейчас такие:

- превью за `MATCHDAY_PREVIEW_MINUTES` минут до начала;
- старт матча в момент kickoff;
- перерыв примерно через `MATCHDAY_HALFTIME_MINUTES` минут;
- финальный свист примерно через `MATCHDAY_FULLTIME_MINUTES` минут.

Дайджесты не публикуются в матчевое окно: по умолчанию за `3` часа до kickoff и `2` часа после. Если нужен полный режим “в день матча без дайджестов”, включи `MATCHDAY_BLOCK_ALL_DAY=true`.

## Источники

Источники разделены на два слоя:

- профильные Real Madrid RSS — проходят более мягко после blacklist-проверки, потому что сам источник уже про клуб;
- общие футбольные RSS — проходят только при явных маркерах «Реала», игроков, турниров или матчапов.

Перед деплоем полезно проверить живость всех RSS:

```bash
python scripts/check_sources.py
```

Если один из сайтов временно недоступен, скрипт покажет `FAIL` или `WARN`; такой источник можно заменить или оставить, если это разовая проблема сайта.

## Свежесть дайджеста

`digest.py` смотрит только свежие записи относительно текущего времени:

- утренний дайджест: последние `14` часов по умолчанию;
- дневной, вечерний и ночной дайджесты: последние `8` часов по умолчанию;
- если RSS-запись без даты, она пропускается при `DIGEST_INCLUDE_UNDATED=false`;
- найденные новости сортируются от самых новых к более старым;
- уже отправленные ссылки сохраняются в `STATE_DIR/sent_links.txt` и не повторяются.

Если запустить `python digest.py` без аргумента, бот сам выберет тип дайджеста по `DIGEST_TIMEZONE`:

- `05:00-10:59` — утренний;
- `11:00-16:59` — дневной;
- `17:00-23:59` — вечерний;
- `00:00-04:59` — ночной.

Явно можно запускать так:

```bash
DRY_RUN=true python digest.py утреннего
DRY_RUN=true python digest.py дневного
DRY_RUN=true python digest.py вечернего
DRY_RUN=true python digest.py ночного
```

## Структура

```text
main.py                                # менеджер процессов
runtime_config.py                      # env, dry-run, пути logs/state, настройки дайджеста и матч-дня
feed_utils.py                          # общий RSS fetch helper с timeout/User-Agent
match_calendar.py                      # календарь матчей и guard для дайджеста
matchday.py                            # матчевые автопосты и заготовка live-событий
config/matches.example.json            # пример календаря матчей
heartbeat.py                           # HTTP heartbeat
breaking.py                            # breaking-мониторинг RSS
digest.py                              # разовый запуск дайджеста
filters.py                             # фильтр релевантности
text_cleaner.py                        # очистка текста после перевода
translator.py                          # перевод + словарные замены
sources_international.py               # международные источники
sources_ru.py                          # русскоязычные источники
scripts/preflight.py                   # проверка синтаксиса, зависимостей и .env
scripts/check_sources.py               # проверка доступности RSS-источников
deploy/systemd/coffee-bot.service.example # systemd-шаблон для VPS
requirements.txt                       # зависимости
```

## Настройка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config/matches.example.json config/matches.json
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

# HTTP и Telegram-лимиты.
HTTP_USER_AGENT=CoffeeBot/1.0 (+https://t.me/slivochniyfootball)
RSS_TIMEOUT_SECONDS=15
TELEGRAM_TIMEOUT_SECONDS=10
TELEGRAM_MESSAGE_LIMIT=3900

# Свежесть, расписание и формат дайджестов.
DIGEST_TIMEZONE=Europe/Moscow
DIGEST_MORNING_TIME=09:00
DIGEST_DAY_TIME=15:00
DIGEST_EVENING_TIME=21:00
DIGEST_LIMIT=10
DIGEST_ENTRY_SCAN_LIMIT=5
DIGEST_DEFAULT_LOOKBACK_HOURS=8
DIGEST_MORNING_LOOKBACK_HOURS=14
DIGEST_DAY_LOOKBACK_HOURS=8
DIGEST_EVENING_LOOKBACK_HOURS=8
DIGEST_NIGHT_LOOKBACK_HOURS=8
DIGEST_INCLUDE_UNDATED=false

# Матч-день и заготовка текстовых трансляций.
MATCHDAY_ENABLED=true
MATCH_SCHEDULE_FILE=config/matches.json
MATCHDAY_BLOCK_BEFORE_HOURS=3
MATCHDAY_BLOCK_AFTER_HOURS=2
MATCHDAY_BLOCK_ALL_DAY=false
MATCHDAY_PREVIEW_MINUTES=60
MATCHDAY_HALFTIME_MINUTES=50
MATCHDAY_FULLTIME_MINUTES=125
MATCHDAY_POST_TOLERANCE_MINUTES=20
MATCHDAY_POLL_SECONDS=60
```

Если настоящий Telegram-токен когда-либо попадал в репозиторий, перевыпусти его в BotFather перед деплоем.

## Проверка до сервера

Проверить синтаксис основных модулей, зависимости и `.env`:

```bash
python scripts/preflight.py
```

Проверить RSS-источники:

```bash
python scripts/check_sources.py
```

Проверить календарь матчей:

```bash
python matchday.py --list
DRY_RUN=true python matchday.py --once
```

Собрать дайджест без отправки в Telegram. Без аргумента бот сам выберет утро, день, вечер или ночь по текущему времени:

```bash
DRY_RUN=true python digest.py
```

Проверить конкретный тип дайджеста:

```bash
DRY_RUN=true python digest.py утреннего
DRY_RUN=true python digest.py дневного
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
python matchday.py
python digest.py
python digest.py утреннего
python digest.py дневного
python digest.py вечернего
```

`main.py` запускает `heartbeat.py`, `breaking.py` и `matchday.py` как процессы с рестартом, а `digest.py` — как одноразовую задачу без автоперезапуска после успешного завершения. Дайджесты планируются по настройкам `DIGEST_MORNING_TIME`, `DIGEST_DAY_TIME`, `DIGEST_EVENING_TIME` в таймзоне `DIGEST_TIMEZONE`. По умолчанию это `09:00`, `15:00`, `21:00` по Москве.

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
- `config/matches.json`
- `sent_links.txt`
- `sent_breaking.txt`

`sent_links.txt`, `sent_breaking.txt` и `matchday_posts.json` теперь живут в `STATE_DIR`, чтобы runtime-состояние не попадало в git.

## Примечания

- Для бесплатного режима не нужны `OPENAI_API_KEY`, `OPENROUTER_API_KEY` или другие LLM-ключи.
- Для лучшего перевода можно добавить бесплатный `DEEPL_API_KEY`; без него бот продолжит работать через текущие fallback-переводчики.
- Если RSS-источник часто не отдает дату публикации, можно временно поставить `DIGEST_INCLUDE_UNDATED=true`, но для настоящего “свежака” лучше держать `false`.
- Для настоящей автоматической текстовой трансляции нужен live-events provider; текущий `matchday.py` уже дает место, куда его подключить.
