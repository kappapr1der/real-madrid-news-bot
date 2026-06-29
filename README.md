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
- Ранжирование дайджеста по важности: official, травмы, составы, матч-день, ЛЧ, трансферы, ключевые игроки.
- Антидубли по смыслу: похожие новости от разных источников схлопываются в один пункт.
- Настраиваемые хэштеги для дайджеста, breaking-постов, матч-дня и live-событий.
- Длинные Telegram-сообщения режутся на части до `TELEGRAM_MESSAGE_LIMIT`.
- RSS читается через HTTP timeout и `HTTP_USER_AGENT`, чтобы плохой источник не подвешивал процесс.
- Свежие дайджесты: бот берет дату публикации из RSS, отбрасывает старые новости и сортирует новые сверху внутри редакторского ранжирования.
- Автоматический тип дайджеста по времени: утренний, дневной, вечерний или ночной.
- Расписание дайджестов настраивается через `.env` и работает в `DIGEST_TIMEZONE`, а не в случайной таймзоне VPS.
- Если сервер был недоступен во время слота, `main.py` может догнать пропущенный дайджест при старте в пределах `DIGEST_MISSED_GRACE_MINUTES`.
- Матч-день для матчей Реала в Ла Лиге, Лиге чемпионов и любых других турнирах из `config/matches.json`.
- Автопосты матча: превью, старт, перерыв, финальный свист.
- Опциональные автоматические live-события через API-FOOTBALL: голы, карточки, замены и VAR.
- Дайджесты автоматически пропускаются в матчевое окно, чтобы не перекрывать матч.
- Breaking-мониторинг каждые 120 секунд.
- Safe dry-run режим: можно тестировать без отправки в Telegram.
- One-shot проверка breaking-цикла через `python breaking.py --once`.
- Проверка RSS-источников через `python scripts/check_sources.py`.
- `preflight.py` проверяет синтаксис, зависимости и базовую валидность `.env`.
- Статус-файл `state/status.json` и JSON heartbeat: `200`, если основные процессы свежие; `503`, если сервис устарел или упал.
- Логи в каталоге `logs/`, runtime-состояние в `state/`.

## Как выглядит дайджест

Вместо сырого URL и большого Telegram-превью бот отправляет компактный HTML-пост:

```text
Белое утро на Бернабеу
Свежие новости о «Реале» за ночь и утро.

1. «Реал» узнал диагноз по травме Трента Александер-Арнольда
Читать · Football España – Real Madrid · 14:23
Еще источники: Managing Madrid, Madrid Universal

2. «Арсенал» снова интересуется Ардой Гюлером
Читать · The Real Champs · 13:58

#RealMadrid #HalaMadrid #КофеСоСливками #Дайджест
```

Ссылки спрятаны в `Читать`, время берется из даты публикации RSS, а `disable_web_page_preview=True` отключает большую карточку под постом. Если несколько источников пишут об одном и том же, бот оставляет один основной пункт и показывает дополнительные источники строкой `Еще источники`.

## Качество Дайджеста

`content_quality.py` делает дайджест ближе к редакторской сводке:

- считает важность новости по теме, источнику, игрокам и свежести;
- поднимает выше официальные сообщения, травмы, составы, матчевые новости, ЛЧ и трансферы;
- группирует похожие заголовки от разных RSS, чтобы одна травма или один трансфер не занимали три пункта;
- сохраняет все ссылки из группы как отправленные, чтобы дубли не всплывали в следующем дайджесте.

Настройки:

```env
DIGEST_DEDUPE_ENABLED=true
DIGEST_PRIORITY_SORT_ENABLED=true
DIGEST_SHOW_RELATED_SOURCES=true
DIGEST_DEDUPE_SIMILARITY=42
```

`DIGEST_DEDUPE_SIMILARITY` задается от `0` до `100`: чем выше значение, тем строже бот считает новости дублями. Если бот склеивает лишнее, подними значение, например до `55`. Если пропускает очевидные повторы, опусти до `35`.

## Хэштеги

Все типы постов добавляют хэштеги через `post_utils.py`. По умолчанию используются фанатские теги канала, а в `.env` можно задать отдельный набор для каждого режима:

```env
POST_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками"
DIGEST_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #Дайджест"
BREAKING_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #СливочнаяМолния"
MATCHDAY_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #МатчДень"
LIVE_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #Live #МатчДень"
```

Можно разделять хэштеги пробелами или запятыми. `#` можно писать или не писать, бот нормализует сам. Если значение начинается с `#`, держи строку в кавычках, иначе `.env` может принять ее за комментарий.

## Матч-день

Матчевый режим использует локальный календарь `config/matches.json`. В него можно добавлять матчи Реала в Ла Лиге, Лиге чемпионов, Кубке, Суперкубке или товарищеских турнирах. Дайджесты блокируются вокруг любого матча из календаря.

Создать календарь на сервере:

```bash
cp config/matches.example.json config/matches.json
```

Формат матча:

```json
{
  "id": "ucl-2026-09-15-real-madrid-opponent",
  "competition": "UEFA Champions League",
  "round": "League phase",
  "home": "Real Madrid",
  "away": "Opponent",
  "kickoff": "2026-09-15T21:00:00+02:00",
  "venue": "Santiago Bernabeu",
  "broadcast": "",
  "api_football_fixture_id": ""
}
```

`api_football_fixture_id` можно оставить пустым. Если заполнить его fixture-id из API-FOOTBALL, live-провайдер будет точнее связывать события с матчем.

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
DRY_RUN=true python matchday.py --match-id ucl-2026-09-15-real-madrid-opponent --minute 23 --kind goal --score 1:0 --event-text "Беллингем открывает счет после передачи Винисиуса"
```

`main.py` запускает `matchday.py` отдельным процессом, если `MATCHDAY_ENABLED=true`. Автопосты сейчас такие:

- превью за `MATCHDAY_PREVIEW_MINUTES` минут до начала;
- старт матча в момент kickoff;
- перерыв примерно через `MATCHDAY_HALFTIME_MINUTES` минут;
- финальный свист примерно через `MATCHDAY_FULLTIME_MINUTES` минут.

Дайджесты не публикуются в матчевое окно: по умолчанию за `3` часа до kickoff и `2` часа после. Если нужен полный режим “в день матча без дайджестов”, включи `MATCHDAY_BLOCK_ALL_DAY=true`.

## Автоматический live

Автоматический live выключен по умолчанию. Без ключа API бот продолжит работать как раньше: автопосты матча плюс ручной `--event-text`.

Чтобы включить автоматические live-события через API-FOOTBALL:

```env
MATCHDAY_LIVE_ENABLED=true
MATCHDAY_LIVE_PROVIDER=api-football
API_FOOTBALL_KEY=replace_me
API_FOOTBALL_TEAM_ID=541
API_FOOTBALL_LEAGUE_IDS=140,2
MATCHDAY_LIVE_POLL_SECONDS=180
MATCHDAY_LIVE_EVENT_TYPES=Goal,Card,subst,Var
```

По умолчанию `API_FOOTBALL_LEAGUE_IDS=140,2`: Ла Лига и Лига чемпионов. Если позже нужны Кубок Испании или Суперкубок, добавь ID лиги через запятую.

Live-провайдер работает только в окне вокруг матчей из `config/matches.json`: за `MATCHDAY_LIVE_BEFORE_MINUTES` минут до kickoff и до `MATCHDAY_FULLTIME_MINUTES + MATCHDAY_LIVE_AFTER_MINUTES` минут после kickoff. Это экономит бесплатные запросы.

Проверить один live-полл:

```bash
DRY_RUN=true python matchday.py --live-once
```

Бот берет структурированные события провайдера и сам пишет короткий фанатский текст без GPT:

```text
<b>72' · Гол · 2:1 | Real Madrid - Opponent</b>
Винисиус забивает за Мадрид. Счет 2:1. Сливочные получают важный импульс.

#RealMadrid #HalaMadrid #КофеСоСливками #Live #МатчДень
```

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
- найденные новости ранжируются по важности, а внутри близких по важности случаев учитывается свежесть;
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
post_utils.py                          # общий формат хэштегов для Telegram-постов
status_manager.py                      # runtime-статус сервисов и JSON health snapshot
content_quality.py                     # ранжирование и антидубли дайджеста
live_providers.py                      # API-FOOTBALL live-события для матчей Реала
match_calendar.py                      # календарь матчей и guard для дайджеста
matchday.py                            # матчевые автопосты, ручные и автоматические live-события
config/matches.example.json            # пример календаря матчей Ла Лиги и ЛЧ
heartbeat.py                           # HTTP JSON heartbeat
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
STATUS_FILE=state/status.json
BREAKING_INTERVAL_SECONDS=120
HEARTBEAT_PORT=8000
HEARTBEAT_MAIN_STALE_SECONDS=180
HEARTBEAT_BREAKING_STALE_SECONDS=420
HEARTBEAT_MATCHDAY_STALE_SECONDS=600
HEARTBEAT_LIVE_STALE_SECONDS=900

# HTTP и Telegram-лимиты.
HTTP_USER_AGENT=CoffeeBot/1.0 (+https://t.me/slivochniyfootball)
RSS_TIMEOUT_SECONDS=15
TELEGRAM_TIMEOUT_SECONDS=10
TELEGRAM_MESSAGE_LIMIT=3900

# Хэштеги для Telegram. Значения с # держи в кавычках.
POST_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками"
DIGEST_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #Дайджест"
BREAKING_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #СливочнаяМолния"
MATCHDAY_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #МатчДень"
LIVE_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #Live #МатчДень"

# Свежесть, расписание, ранжирование и формат дайджестов.
DIGEST_TIMEZONE=Europe/Moscow
DIGEST_MORNING_TIME=09:00
DIGEST_DAY_TIME=15:00
DIGEST_EVENING_TIME=21:00
DIGEST_MISSED_CATCHUP_ENABLED=true
DIGEST_MISSED_GRACE_MINUTES=120
DIGEST_LIMIT=10
DIGEST_ENTRY_SCAN_LIMIT=5
DIGEST_DEFAULT_LOOKBACK_HOURS=8
DIGEST_MORNING_LOOKBACK_HOURS=14
DIGEST_DAY_LOOKBACK_HOURS=8
DIGEST_EVENING_LOOKBACK_HOURS=8
DIGEST_NIGHT_LOOKBACK_HOURS=8
DIGEST_INCLUDE_UNDATED=false
DIGEST_DEDUPE_ENABLED=true
DIGEST_PRIORITY_SORT_ENABLED=true
DIGEST_SHOW_RELATED_SOURCES=true
DIGEST_DEDUPE_SIMILARITY=42

# Матч-день и текстовые трансляции.
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
MATCHDAY_LIVE_ENABLED=false
MATCHDAY_LIVE_PROVIDER=api-football
MATCHDAY_LIVE_POLL_SECONDS=180
MATCHDAY_LIVE_BEFORE_MINUTES=15
MATCHDAY_LIVE_AFTER_MINUTES=30
MATCHDAY_LIVE_EVENT_TYPES=Goal,Card,subst,Var

# API-FOOTBALL / API-SPORTS. По умолчанию: Real Madrid, La Liga, Champions League.
API_FOOTBALL_KEY=
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
API_FOOTBALL_TEAM_ID=541
API_FOOTBALL_LEAGUE_IDS=140,2
API_FOOTBALL_REQUEST_TIMEOUT_SECONDS=10
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
DRY_RUN=true python matchday.py --live-once
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

Если VPS был выключен или недоступен в момент запуска дайджеста, менеджер при старте проверяет пропущенные слоты. При `DIGEST_MISSED_CATCHUP_ENABLED=true` он догонит выпуск, если с планового времени прошло не больше `DIGEST_MISSED_GRACE_MINUTES` минут и этот дайджест сегодня ещё не завершался. По умолчанию окно — `120` минут.

## Live-режим

На сервере, когда все проверено, явно выключи dry-run:

```env
DRY_RUN=false
```

Без этого бот не будет публиковать сообщения в Telegram. Это сделано специально, чтобы случайный локальный запуск не стрелял в канал.

Автоматический live отдельно включается через `MATCHDAY_LIVE_ENABLED=true` и требует `API_FOOTBALL_KEY`. Если live выключен, ручные события через `--event-text` остаются доступными.

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

`main.py`, `breaking.py`, `digest.py` и `matchday.py` пишут runtime-состояние в `STATUS_FILE` (`state/status.json` по умолчанию). `heartbeat.py` читает этот файл и отвечает JSON по порту из `HEARTBEAT_PORT` (`8000` по умолчанию).

Проверить локально:

```bash
curl http://127.0.0.1:8000/
```

Heartbeat возвращает `200`, если обязательные сервисы свежие, и `503`, если сервис еще не отчитался, упал или давно не обновлялся. Обязательные сервисы:

- `main`;
- `breaking`;
- `matchday`, если `MATCHDAY_ENABLED=true`;
- `live`, если `MATCHDAY_LIVE_ENABLED=true`.

Пороги свежести настраиваются через `.env`:

```env
HEARTBEAT_MAIN_STALE_SECONDS=180
HEARTBEAT_BREAKING_STALE_SECONDS=420
HEARTBEAT_MATCHDAY_STALE_SECONDS=600
HEARTBEAT_LIVE_STALE_SECONDS=900
```

Если запустить только `heartbeat.py` без `main.py`, он честно вернет `503`: это нормально, потому что менеджер и воркеры еще не записали статус.

`uptime_webhook.py` можно использовать для webhook-уведомлений от UptimeRobot. Он берет Telegram-токен и канал из `.env`, а не из кода.

## Runtime-файлы

Не коммить:

- `.env`
- `logs/`
- `state/`
- `config/matches.json`
- `sent_links.txt`
- `sent_breaking.txt`

`sent_links.txt`, `sent_breaking.txt`, `matchday_posts.json` и `status.json` теперь живут в `STATE_DIR`, чтобы runtime-состояние не попадало в git.

## Примечания

- Для бесплатного режима не нужны `OPENAI_API_KEY`, `OPENROUTER_API_KEY` или другие LLM-ключи.
- Для лучшего перевода можно добавить бесплатный `DEEPL_API_KEY`; без него бот продолжит работать через текущие fallback-переводчики.
- Если RSS-источник часто не отдает дату публикации, можно временно поставить `DIGEST_INCLUDE_UNDATED=true`, но для настоящего “свежака” лучше держать `false`.
- Если антидубли склеивают слишком много, подними `DIGEST_DEDUPE_SIMILARITY`; если пропускает повторы, опусти значение.
- API-FOOTBALL free plan ограничен по запросам в день, поэтому `MATCHDAY_LIVE_POLL_SECONDS=180` лучше не снижать без необходимости.
