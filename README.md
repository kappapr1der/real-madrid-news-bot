# Coffee Bot (Кофе со сливками)

Телеграм-бот для канала о Real Madrid: собирает RSS-новости, фильтрует нерелевантное, переводит заголовки на русский и публикует breaking-новости, дайджесты и матчевые обновления.

Проект не требует OpenAI/GPT API. AI-редактор удален из рабочей схемы, чтобы бот оставался бесплатным и стабильным.

## Идея канала

`Кофе со сливками` — это не кофейная рубрика, а фанатский образ вокруг «сливочных»: белая форма, Мадрид, Бернабеу, мадридисты и новости о клубе без случайного футбольного шума.

Тон дайджестов поэтому ближе к болельщицкой сводке: `Утренние сливки Мадрида`, `Белое утро на Бернабеу`, `К этому часу у сливочных`, `Вечерняя белая хроника`.

## Возможности

- RSS-источники на русском, английском и испанском.
- Профильные Real Madrid RSS в приоритете: Managing Madrid, Madrid Universal, The Real Champs, Defensa Central, Bernabéu Digital, Marca, Mundo Deportivo, Sport и другие.
- Опциональные X/Twitter-источники через бесплатные Nitter-зеркала или внешний RSS-шлюз, чтобы ловить цитаты официальных аккаунтов и инсайдеров без платного X API.
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
- Если свежая лента тонкая, бот публикует короткий формат или пропускает слот вместо искусственного топ-10.
- Автоматический тип дайджеста по времени: утренний, дневной, вечерний или ночной.
- Расписание дайджестов настраивается через `.env` и работает в `DIGEST_TIMEZONE`, а не в случайной таймзоне VPS.
- Если сервер был недоступен во время слота, `main.py` может догнать последний актуальный дайджест при старте в пределах `DIGEST_MISSED_GRACE_MINUTES`.
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
- ведет статистику качества источников в `state/source_quality.json`: кандидаты, попадания в дайджест, карантин и тихие источники.

Настройки:

```env
DIGEST_MIN_ITEMS_TO_POST=3
DIGEST_SHORT_FORMAT_THRESHOLD=6
DIGEST_DEDUPE_ENABLED=true
DIGEST_PRIORITY_SORT_ENABLED=true
DIGEST_SHOW_RELATED_SOURCES=true
DIGEST_DEDUPE_SIMILARITY=42
```

`DIGEST_DEDUPE_SIMILARITY` задается от `0` до `100`: чем выше значение, тем строже бот считает новости дублями. Если бот склеивает лишнее, подними значение, например до `55`. Если пропускает очевидные повторы, опусти до `35`.

`DIGEST_MIN_ITEMS_TO_POST` задает нижнюю границу публикации. Если после фильтров осталось меньше пунктов, слот пропускается. `DIGEST_SHORT_FORMAT_THRESHOLD` включает короткий формат: по умолчанию 3-5 нормальных новостей публикуются как короткая сводка, а 6+ — как обычный дайджест.

## X-источники

Официальный X API требует Bearer token, поэтому бот не зависит от него напрямую. Вместо этого можно подключить любой RSS-шлюз, который превращает публичные X-аккаунты в RSS.

```env
X_NITTER_INSTANCES=https://nitter.poast.org,https://your-second-working-nitter.example
X_RSS_CACHE_SECONDS=300
X_RSS_BREAKING_ENTRY_SCAN_LIMIT=6
X_RSS_HANDLES=realmadrid,realmadriden,MarioCortegana,AranchaMOBILE,JLSanchez78,GuillermoRai_
```

`X_NITTER_INSTANCES` принимает несколько бесплатных Nitter-зеркал: бот проверяет их по порядку и переключается при сетевой ошибке, капче или невалидной RSS-ленте. Nitter читается через установленный на VPS `curl`, потому что часть публичных зеркал блокирует Python HTTP-клиенты. Для бережного отношения к инстансам X-лента кэшируется на пять минут, а ретвиты не выдают себя за прямые сообщения репортера. Обычный RSS-шлюз в `X_RSS_BASE_URL` поддерживается как запасной вариант; если оба параметра пусты, X-источники выключены.

## Here We Go

Отдельная рубрика `Here we go` читает официальный публичный Telegram-канал Фабрицио Романо, а не случайное X-зеркало. Бот берёт только свежие посты с прямой формулировкой `Here we go`, относящиеся к «Реалу», и публикует их сразу: без второго источника и без ожидания LLM-очереди. Обычные сообщения Фабрицио в дайджесты не попадают.

```env
HERE_WE_GO_ENABLED=true
HERE_WE_GO_TELEGRAM_URL=https://t.me/s/fabrizioromanotg
HERE_WE_GO_ENTRY_SCAN_LIMIT=12
HERE_WE_GO_MAX_AGE_MINUTES=180
HERE_WE_GO_HASHTAGS="#RealMadrid #HalaMadrid #КофеСоСливками #HereWeGo"
```

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

Для уже опубликованной пары, у которой Ла Лига еще не назначила точный час, можно сохранить `date_hint` без `kickoff`. Такая запись видна в статусе календаря, но не запускает посты и не блокирует дайджесты. В репозитории лежит готовый маршрут сезона `config/laliga-2026-27.json`: в нем время назначено только там, где его уже подтвердили официально.

В день жеребьевки лиговой фазы ЛЧ бот включает одноразовый редакционный триггер: подтвержденная заметка о соперниках «Реала» получает отдельную шапку `Жеребьевка Лиги чемпионов` и единый отпечаток, поэтому несколько одинаковых публикаций не превратятся в серию молний и не попадут затем в дайджест. Дата задается через `UCL_DRAW_DATE`.

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
docs/failover.md                       # аварийный перенос на новый VPS
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

Для запуска тестов:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
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
HEARTBEAT_HOST=127.0.0.1
HEARTBEAT_PORT=8000
HEARTBEAT_TOKEN=
HEARTBEAT_MAIN_STALE_SECONDS=180
HEARTBEAT_BREAKING_STALE_SECONDS=420
HEARTBEAT_MATCHDAY_STALE_SECONDS=600
HEARTBEAT_LIVE_STALE_SECONDS=900
PREFLIGHT_STATUS_TTL_SECONDS=1800

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
DIGEST_MISSED_GRACE_MINUTES=360
DIGEST_LIMIT=10
DIGEST_MIN_ITEMS_TO_POST=3
DIGEST_SHORT_FORMAT_THRESHOLD=6
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
DIGEST_PREFLIGHT_ENABLED=true
DIGEST_PREFLIGHT_MINUTES=5
DIGEST_PREFLIGHT_WARN_MIN_CANDIDATES=6
BREAKING_PREFLIGHT_PENDING_WARN=10

# Опционально: X/Twitter через Nitter или внешний RSS-шлюз.
X_RSS_BASE_URL=
X_NITTER_INSTANCES=
X_RSS_CACHE_SECONDS=300
X_RSS_BREAKING_ENTRY_SCAN_LIMIT=6
X_RSS_HANDLES=realmadrid,realmadriden,MadridXtra,FabrizioRomano,MarioCortegana,AranchaMOBILE,melchorcope,JLSanchez78,Ramon_AlvarezMM,GuillermoRai_

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

Если `DIGEST_PREFLIGHT_ENABLED=true`, менеджер запускает `preflight.py digest <label>` за `DIGEST_PREFLIGHT_MINUTES` минут до каждого дайджеста. Preflight не публикует пост и не вызывает LLM-редактор: он собирает свежие кандидаты, проверяет дедупликацию, hard-deny, тонкие выпуски и очередь breaking, а затем пишет результат в `STATUS_FILE`. Свежие warning/error из preflight видны в heartbeat в течение `PREFLIGHT_STATUS_TTL_SECONDS`.

Если VPS был выключен или недоступен в момент запуска дайджеста, менеджер при старте проверяет пропущенные слоты. При `DIGEST_MISSED_CATCHUP_ENABLED=true` он догонит только последний актуальный выпуск дня, если с его планового времени прошло не больше `DIGEST_MISSED_GRACE_MINUTES` минут и этот дайджест сегодня ещё не завершался. Это защищает канал от пачки устаревших утренних/дневных выпусков после долгой аварии. По умолчанию окно — `360` минут.

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

`main.py`, `breaking.py`, `digest.py` и `matchday.py` пишут runtime-состояние в `STATUS_FILE` (`state/status.json` по умолчанию). `heartbeat.py` читает этот файл и отвечает JSON на `HEARTBEAT_HOST:HEARTBEAT_PORT` (`127.0.0.1:8000` по умолчанию).

### Визуальные рубрики

`editorial_posts.py` добавляет два самостоятельных формата, которые не смешиваются с обычными дайджестами:

- `history` в `HISTORY_TIME` публикуется только для проверенных дат из `config/history_events.json` и берет реальную архивную фотографию, заранее привязанную к событию;
- `cover` в `EDITORIAL_COVER_TIME` публикует фактическую первую полосу Diario AS.

Обе рубрики по умолчанию пропускают матч-дни. Их можно проверить без Telegram: `DRY_RUN=true python editorial_posts.py history --force` и `DRY_RUN=true python editorial_posts.py cover --force`.

Для `history` фотография задается вручную в `config/history_events.json` через `image_url`. Если у записи нет проверенной прямой ссылки на архивный кадр, пост не выйдет: бот не подставляет логотипы, случайные иллюстрации или сгенерированные карточки.

Проверить локально:

```bash
curl http://127.0.0.1:8000/
```

Heartbeat возвращает `200`, если обязательные сервисы свежие, и `503`, если сервис еще не отчитался, упал или давно не обновлялся. Если задан `HEARTBEAT_TOKEN`, запросы без токена в query-параметре `token` или заголовке `X-Heartbeat-Token` получат `403`.

- `main`;
- `breaking`;
- `matchday`, если `MATCHDAY_ENABLED=true`;
- `live`, если `MATCHDAY_LIVE_ENABLED=true`.

Свежие `preflight:*` статусы не считаются обязательными сервисами, но heartbeat добавляет их warning/error в общий ответ, пока они не старше `PREFLIGHT_STATUS_TTL_SECONDS`.

Пороги свежести настраиваются через `.env`:

```env
HEARTBEAT_HOST=127.0.0.1
HEARTBEAT_PORT=8000
HEARTBEAT_TOKEN=
HEARTBEAT_MAIN_STALE_SECONDS=180
HEARTBEAT_BREAKING_STALE_SECONDS=420
HEARTBEAT_MATCHDAY_STALE_SECONDS=600
HEARTBEAT_LIVE_STALE_SECONDS=900
```

Если запустить только `heartbeat.py` без `main.py`, он честно вернет `503`: это нормально, потому что менеджер и воркеры еще не записали статус.

Для UptimeRobot на VPS нужно открыть heartbeat наружу и задать токен:

```env
HEARTBEAT_HOST=0.0.0.0
HEARTBEAT_PORT=8000
HEARTBEAT_TOKEN=replace_with_long_random_string
```

Monitor URL:

```text
http://SERVER_IP:8000/health?token=replace_with_long_random_string
```

Тип монитора: HTTP(s). UptimeRobot будет видеть и полную сетевую недоступность сервера, и `503` от самого бота, если процесс жив, но сервисы устарели или упали.

`uptime_webhook.py` можно использовать для webhook-уведомлений от UptimeRobot, но не запускай его на том же VPS как единственный канал тревог: если этот VPS лежит, webhook тоже не примет уведомление. Для аварий ЦОДа надежнее alert contacts на стороне UptimeRobot.

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

## Календарь недели

`week_ahead.py` публикует отдельный короткий пост с ближайшими матчами «Реала». По умолчанию он выходит по понедельникам в `11:00` по Москве и охватывает следующие восемь дней.

Календарь использует тот же `config/matches.json`, что и матч-день. Время начала выводится только при наличии `kickoff`; запись только с `date_hint` честно получает пометку «время уточняется» и не запускает матчевые автопосты.

```bash
DRY_RUN=true python week_ahead.py --force
```

Настройки: `WEEK_AHEAD_ENABLED`, `WEEK_AHEAD_DAY`, `WEEK_AHEAD_TIME`, `WEEK_AHEAD_TIMEZONE`, `WEEK_AHEAD_DAYS`, `WEEK_AHEAD_HASHTAGS`.

## Визуальная айдентика

Молнии публикуются с фирменной бело-синей карточкой и эмблемой «Реала». Ключевые матчевые посты, составы и подтверждённый результат получают карточки с эмблемами обеих команд. Значки соперников находятся по названию, кэшируются в `STATE_DIR/club_badges` и не мешают публикации: если внешний каталог недоступен, бот отправит карточку с нейтральным знаком.

Короткий дайджест, который помещается в Telegram-caption, тоже выходит на фирменной карточке. Длинный дайджест остаётся одним текстовым сообщением: Telegram ограничивает подпись к изображению 1024 символами, а разбивать выпуск на два равноправных поста ради обложки бот не будет.

Настройки: `VISUAL_CARDS_ENABLED`, `VISUAL_NEWS_CARDS_ENABLED`, `VISUAL_MATCH_CARDS_ENABLED`, `VISUAL_X_POST_CARDS_ENABLED`, `CLUB_BADGE_LOOKUP_URL`, `CLUB_BADGE_LOOKUP_TIMEOUT_SECONDS`. X/Nitter-breaking получает отдельную карточку с автором, русской сутью и медиа из исходного поста, когда оно доступно.

## Редакционная надежность

Неофициальная молния теперь ждёт подтверждения из второго независимого источника. Официальные каналы «Реала» проходят без задержки. Проверка живёт только внутри бота: в опубликованных постах не появляются служебные статусы или квадратные скобки.

Для трансферов, травм и контрактов бот ведёт состояние сюжета. Повторная заметка с тем же статусом не становится новой молнией; новый этап, например официальный переход после переговоров, проходит как отдельное обновление.

Настройки: `BREAKING_CONFIRMATION_ENABLED`, `BREAKING_CONFIRMATION_MIN_SOURCES`, `BREAKING_CONFIRMATION_TTL_MINUTES`, `STORY_LIFECYCLE_ENABLED`.

## Итог Матча И Операционный Отчет

Когда подключен API-FOOTBALL, итог матча получает подтверждённый счёт, авторов голов и карточку с эмблемами. После такого итога бот открывает анонимное голосование за игрока матча только при наличии подтверждённых кандидатов из состава или списка авторов голов.

`calendar_refresh.py` раз в день сверяет уже известные пары с API-FOOTBALL и дописывает только подтверждённые время kickoff и fixture id. Без `API_FOOTBALL_KEY` календарь не меняется и сервис остаётся в состоянии ожидания.

`editorial_report.py` раз в неделю сохраняет внутренний Markdown-отчёт в `STATE_DIR/reports/`: полезные и шумные источники, ожидающие подтверждения сюжеты, жизненный цикл новостей и готовность календаря. В Telegram он ничего не отправляет.

Настройки: `MATCHDAY_POSTMATCH_POLL_ENABLED`, `MATCHDAY_POSTMATCH_POLL_QUESTION`, `CALENDAR_REFRESH_ENABLED`, `CALENDAR_REFRESH_TIME`, `CALENDAR_REFRESH_SEASON`, `EDITORIAL_REPORT_ENABLED`, `EDITORIAL_REPORT_DAY`, `EDITORIAL_REPORT_TIME`.
