#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
from zoneinfo import ZoneInfo

import requests

from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from filters import passes_filters
from feed_utils import parse_feed_url
from match_calendar import digest_block_reason
from news_fingerprint import load_news_keys, save_news_keys, semantic_news_key
from post_utils import append_hashtags
from content_quality import RankedDigestItem, candidate_profile, rank_digest_candidates
from llm_editor import review_digest_items
from status_manager import record_error, record_status
from translator import translate_text
from text_cleaner import clean_text
from runtime_config import (
    DIGEST_DAY_LOOKBACK_HOURS,
    DIGEST_DEDUPE_ENABLED,
    DIGEST_DEDUPE_SIMILARITY,
    DIGEST_DEFAULT_LOOKBACK_HOURS,
    DIGEST_ENTRY_SCAN_LIMIT,
    DIGEST_EVENING_LOOKBACK_HOURS,
    DIGEST_HASHTAGS,
    DIGEST_INCLUDE_UNDATED,
    DIGEST_LIMIT,
    DIGEST_MORNING_LOOKBACK_HOURS,
    DIGEST_NIGHT_LOOKBACK_HOURS,
    DIGEST_PRIORITY_SORT_ENABLED,
    DIGEST_SHOW_RELATED_SOURCES,
    DIGEST_TIMEZONE,
    DRY_RUN,
    LLM_EDITOR_MAX_DIGEST_ITEMS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_MESSAGE_LIMIT,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)

LOG_FILE = get_log_file("digest.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = get_state_file("sent_links.txt")
SENT_BREAKING_FILE = get_state_file("sent_breaking.txt")
SENT_BREAKING_FINGERPRINT_FILE = get_state_file("sent_breaking_fingerprints.txt")
QUARANTINE_FILE = get_state_file("digest_quarantine.json")
QUARANTINE_LIMIT = 200
TZ = ZoneInfo(DIGEST_TIMEZONE)

DIGEST_LLM_HARD_DENY_TERMS = (
    "francia gana",
    "france wins",
    "world cup",
    "2026 world cup",
    "world cup spotlight",
    "madrid world cup spotlight",
    "mundial",
    "чемпионат мира",
    "чемпионата мира",
    "сборная",
    "сборной",
    "сборную",
    "national team",
    "франция выигрывает",
    "франция выиграла",
    "hat-trick ousmane",
    "ousmane dembele",
    "усман дембеле",
    "дембеле",
    "mbappe solidario",
    "mbappé solidario",
    "solidario mejor mundial",
    "mejor del mundial",
    "мбаппе стал третьим",
    "самый поддерживающий мбаппе",
    "мбаппе уже стал лучшим",
    "лучшим в мире",
    "20+ результатив",
    "haaland",
    "хааланд",
    "эрлинг хааланд",
    "bonito reencuentro cristiano ronaldo rodrygo",
    "cristiano ronaldo rodrygo portugues preocupo lesion",
    "cristiano ronaldo y rodrygo",
    "reencuentro cristiano rodrygo",
    "reencuentro cristiano-rodrygo",
    "cristiano-rodrygo",
    "криштиану роналду и родриго",
    "возвращение криштиану и родриго",
    "португалец беспокоился о своей травме",
    "ronaldo nazario",
    "ronaldo nazário",
    "ronaldo-nazario-mbappe",
    "ronaldo-nazario-mbappe-me-recuerda",
    "mbappe recuerda mi prime",
    "mbappé recuerda mi prime",
    "mbappe me recuerda",
    "mbappé me recuerda",
    "мбаппе напоминает мне меня",
    "роналду назарио: мбаппе",
    "роналду забыл о винисиусе",
    "забыл о винисиусе",
    "я не вижу другого такого, как неймар",
    "другого такого, как неймар",
    "me encanta venir",
    "estas vistas",
    "cuando marco gol",
    "виды",
    "забиваю гол",
    "bielsa",
    "бьелса",
    "valverde y estrellas uruguay",
    "вальверде и звезды уругвая",
    "carlo ancelotti refuses engage japan mind games",
    "brazil manager carlo ancelotti refuses",
    "brazil-manager-carlo-ancelotti",
    "japan mind games",
    "japan-mind-games",
    "round 32 clash world cup",
    "японских интеллектуальных играх",
    "анчелотти отказывается участвовать",
    "интеллектуальных играх",
    "как формируется новая бразилия",
    "new brazil taking shape",
    "new brazil is taking shape",
    "how new brazil is taking shape",
    "cunha plays key role",
    "кунья играет ключевую роль",
    "fede valverde's uruguay eliminated",
    "valverde's uruguay",
    "uruguay eliminated",
    "сборная уругвая",
    "вылетела с чемпионата мира",
    "spain clinch first place",
    "marc cucurella features",
    "win over uruguay",
    "bellingham became tuchel",
    "bellingham has become tuchel",
    "tuchel's most important player",
    "tuchel most important player",
    "most important player for tuchel",
    "important player tuchel",
    "беллингем стал важнейшим игроком тухеля",
    "важнейшим игроком тухеля",
    "real madrid players still going strong at the world cup",
    "players still going strong at the world cup",
    "world cup for the round of 32",
    "round of 32",
    "по-прежнему сильны на чемпионате мира",
    "игроков мадридского \"реала\" по-прежнему сильны",
    "испания завоевала первое место",
    "голу марка кукуреллы",
    "победу над уругваем",
    "courtois belgica",
    "courtois belgium",
    "belgica siguen adelante",
    "france vs norway",
    "france against norway",
    "francia contra noruega",
    "francia noruega",
    "flipped the narrative",
    "during france vs norway",
    "куртуа и бельгия",
    "бельгия продолжа",
    "первое место в группе",
    "center of controversy",
    "centre of controversy",
    "controversy again",
    "controversia",
    "polémica",
    "polemica",
    "снова в центре скандала",
    "juancho hernangomez",
    "juancho hernangómez",
    "хуанчо эрнангомес",
    "baloncesto",
    "баскетбол",
    "entra historia belgica",
    "historia belgica",
    "historia de belgica",
    "belgium history",
    "history of belgium",
    "agustin canobbio",
    "canobbio",
    "apellido verdugo real madrid",
    "expulsion contra espana",
    "channing tatum",
    "actor channing",
    "actor chenning",
    "norway and france",
    "noruega y francia",
    "uruguay vuelve firmar",
    "dolorosa eliminacion fase grupos",
    "dolorosa eliminacion",
    "fase de grupos",
    "bernardo silva stays on the bench",
    "portugal's 0-0 draw with colombia",
    "portugals 0-0 draw with colombia",
    "portugal 0-0 draw with colombia",
    "portugal colombia",
    "rodrygo appears in miami",
    "rodrygo aparece en miami",
    "saca primera foto de equipo",
    "saca la primera foto de equipo",
    "primera foto equipo",
    "first team photo with bernardo",
    "first photo with summer signing",
    "shares first photo with summer signing",
    "image real madrid winger shares first photo",
    "real madrid winger shares first photo",
    "bienvenida rodrygo bernardo silva",
    "bienvenida rodrygo",
    "welcomes bernardo silva",
    "bienvenida de rodrygo",
    "la bienvenida de rodrygo",
    "bienvenida a bernardo silva",
    "rodrygo a bernardo silva",
    "familia cule cucurella",
    "familia culé cucurella",
    "familia cule de cucurella",
    "familia culé de cucurella",
    "семья куле кукурельи",
    "dani carvajal 34 anos sobre futbol",
    "jovenes deben disfrutar deporte",
    "redes sociales ya quieren ser futbolistas",
    "young people should enjoy sport",
    "micah richards told it like it is",
    "trent alexander-arnold controversy",
    "addressing trent alexander-arnold controversy",
    "toni kroos said what liverpool and bayern",
    "fans are terrified to confess",
    "gary neville affirmed",
    "real madrid fans have been saying for weeks",
    "fans have been saying for weeks about trent",
    "gary neville exfutbolista",
    "tuchel no ha querido en mundial",
    "alexander-arnold es clase mundial",
    "alexander arnold es clase mundial",
    "laterales propensos lesionarse",
    "giro mundial brahim",
    "lider con marruecos",
    "líder con marruecos",
    "lГ­der con marruecos",
    "marruecos real madrid mourinho",
    "leader with morocco",
    "messi mbappe",
    "messi, mbappe",
    "vozinha",
    "opta",
    "СЃРёРјРІРѕР»РёС‡РµСЃРєРѕР№ СЃР±РѕСЂРЅРѕР№ РіСЂСѓРїРїРѕРІРѕРіРѕ СЌС‚Р°РїР°",
    "СЃР±РѕСЂРЅРѕР№ РіСЂСѓРїРїРѕРІРѕРіРѕ СЌС‚Р°РїР° С‡Рј",
    "rincon madrid en bellingham",
    "rincón madrid en bellingham",
    "rincГіn madrid en bellingham",
    "bellingham tiene dos casas",
    "antiguo coto caza",
    "zonas verdes",
    "10 minutos santiago bernabeu",
    "СѓРіРѕР»РѕРє РјР°РґСЂРёРґР°",
    "Р±РµР»Р»РёРЅРіРµРјР° РµСЃС‚СЊ РґРІР° РґРѕРјР°",
    "РѕС…РѕС‚РЅРёС‡СЊРµ СѓРіРѕРґСЊРµ",
    "Р·РµР»РµРЅС‹Рµ РЅР°СЃР°Р¶РґРµРЅРёСЏ",
    "laporta contra cuerdas",
    "barcelona debe este ano",
    "barcelona debe este año",
    "barcelona debe este aГ±o",
    "goldman sachs",
    "camp nou",
    "Р»Р°РїРѕСЂС‚Р°",
    "РіРѕР»РґРјР°РЅ СЃР°РєСЃ",
    "antonio rudiger 33 anos futbolista real madrid infancia pobreza",
    "antonio rüdiger 33 anos futbolista real madrid infancia pobreza",
    "infancia pobreza",
    "infancia estuvo marcada",
    "pobreza",
    "si habia pollo en la mesa",
    "si había pollo en la mesa",
    "если на столе была курица",
    "детство было отмечено бедностью",
)

DIGEST_LLM_ABSOLUTE_DENY_TERMS = (
    "juancho hernangomez",
    "juancho hernangómez",
    "хуанчо эрнангомес",
    "baloncesto",
    "баскетбол",
    "agustin canobbio",
    "canobbio",
    "apellido verdugo real madrid",
    "expulsion contra espana",
    "first photo with summer signing",
    "shares first photo with summer signing",
    "bienvenida rodrygo",
    "bienvenida de rodrygo",
    "la bienvenida de rodrygo",
    "welcomes bernardo silva",
    "familia cule cucurella",
    "familia culé cucurella",
    "gary neville affirmed",
    "real madrid fans have been saying for weeks",
    "gary neville exfutbolista",
    "tuchel no ha querido en mundial",
    "manolo lama",
    "lesion raphinha ha venido bien",
    "lesión raphinha ha venido bien",
    "no brasil ahora se siente superestrella",
    "todos van jugar el",
    "todos van a jugar el",
    "hora juegan madridistas mundial",
    "cuando juegan madridistas mundial",
    "madridistas mundial",
    "reranking europe top clubs player performance world cup",
    "top clubs player performance world cup",
    "reranking europe's top clubs",
    "player performance at the world cup",
    "player performance world cup",
    "tuchel's most important player",
    "беллингем стал важнейшим игроком тухеля",
    "bonito reencuentro cristiano ronaldo rodrygo",
    "cristiano ronaldo y rodrygo",
    "reencuentro cristiano-rodrygo",
    "возвращение криштиану и родриго",
    "ronaldo nazario",
    "ronaldo nazário",
    "ronaldo-nazario-mbappe",
    "мбаппе напоминает мне меня",
    "роналду забыл о винисиусе",
    "забыл о винисиусе",
    "japan mind games",
    "japan-mind-games",
    "анчелотти отказывается участвовать",
    "интеллектуальных играх",
    "new brazil taking shape",
    "new brazil is taking shape",
    "how new brazil is taking shape",
    "cunha plays key role",
    "infancia pobreza",
    "infancia estuvo marcada",
    "pobreza",
    "si habia pollo en la mesa",
    "players still going strong at the world cup",
    "round of 32",
    "alexander-arnold es clase mundial",
    "alexander arnold es clase mundial",
    "laterales propensos lesionarse",
    "does carlo ancelotti hate endrick",
    "carlo ancelotti hate endrick",
    "hate endrick",
    "ненавидит эндрика",
    "так ли это на самом деле",
    "divertido momento marcelo linda caicedo",
    "divertido momento entre marcelo",
    "marcelo linda caicedo",
    "забавный момент между марсело и линдой кайседо",
    "giro mundial brahim",
    "lider con marruecos",
    "messi mbappe",
    "vozinha",
    "opta",
    "rincon madrid en bellingham",
    "bellingham tiene dos casas",
    "antiguo coto caza",
    "zonas verdes",
    "fallece padre ricardo carvalho",
    "padre de ricardo carvalho",
    "ricardo carvalho father",
    "father of ricardo carvalho",
    "скончался отец рикарду карвалью",
    "laporta contra cuerdas",
    "barcelona debe este ano",
    "barcelona debe este año",
    "barcelona debe este aГ±o",
    "goldman sachs",
    "camp nou",
    "4 champions eclipsan",
    "eclipsan eliminatoria seleccion",
    "ni 4 campeones",
    "ни 4 чемпиона",
    "so much for the endrick breakout",
    "endrick breakout under carlo ancelotti",
    "прорыв эндрика под руководством карло анчелотти",
    "real madrid c mantener plaza segunda rfef",
    "real madrid c mantener",
    "segunda rfef",
    "втором дивизионе рфпл",
    "втором дивизионе rfef",
    "реал c может",
    "george weah",
    "weah said what",
    "fans have been whispering",
    "lamine yamal",
    "джордж веа",
    "ямаля",
    "liga f",
    "grupo pau gasol",
    "pau gasol",
    "chelsea sign italian defender",
    "chelsea signs italian defender",
    "palestra",
    "juanma rodriguez filtros mbappe francia",
    "juanma rodriguez without filters",
    "sin filtros sobre mbappe en francia",
    "mbappe in france",
    "мбаппе в сборной франции",
    "комментарии родригеса",
    "toni kroos got brutally honest",
    "florian wirtz and jamal musiala",
    "wirtz and musiala",
    "jamal musiala stack up with jude bellingham",
    "флориан виртц и джамал музиала",
    "виртц и джамал мусиала",
    "david alaba claro jugar espana",
    "jugar espana especial mi",
    "jugar en espana es especial",
    "jugar en españa es especial",
    "alaba claro: jugar",
    "alaba claro jugar espana",
    "играть в испании особенно",
)

DIGEST_LLM_CLUB_IMPACT_TERMS = (
    "real madrid",
    "official",
    "confirmed",
    "transfer",
    "signing",
    "sign",
    "departure",
    "contract",
    "injury",
    "lineup",
    "squad",
    "fichaje",
    "fichajes",
    "fichar",
    "salida",
    "contrato",
    "lesion",
    "lesión",
    "convocatoria",
    "реал",
    "официально",
    "подтвержден",
    "трансфер",
    "подписание",
    "подписать",
    "подпишет",
    "уход",
    "контракт",
    "травм",
    "состав",
    "заявка",
)


@dataclass
class DigestCandidate:
    title: str
    link: str
    source: str
    published_at: datetime | None
    summary: str = ""


def load_sent_links(path=SENT_FILE):
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with SENT_FILE.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


sent_digest = load_sent_links(SENT_FILE)

TEMPLATES = {
    "утреннего": [
        "<b>Утренние сливки Мадрида</b>\n{intro}\n\n{news}",
        "<b>Белое утро на Бернабеу</b>\n{intro}\n\n{news}",
    ],
    "дневного": [
        "<b>К этому часу у сливочных</b>\n{intro}\n\n{news}",
        "<b>Дневная белая сводка</b>\n{intro}\n\n{news}",
    ],
    "вечернего": [
        "<b>Вечерняя белая хроника</b>\n{intro}\n\n{news}",
        "<b>Сливочные итоги дня</b>\n{intro}\n\n{news}",
    ],
    "ночного": [
        "<b>Ночная смена мадридистов</b>\n{intro}\n\n{news}",
        "<b>Пока Бернабеу спит</b>\n{intro}\n\n{news}",
    ],
    "default": [
        "<b>Белая сводка «Кофе со сливками»</b>\n{intro}\n\n{news}",
        "<b>Главное о сливочных</b>\n{intro}\n\n{news}",
    ],
}

INTRO_LINES = {
    "утреннего": [
        "Свежие новости о «Реале» за ночь и утро.",
        "Что произошло вокруг Мадрида, пока город просыпался.",
    ],
    "дневного": [
        "Главное вокруг клуба к этому часу.",
        "Свежая лента для мадридистов без лишнего шума.",
    ],
    "вечернего": [
        "Собрал главное вокруг Мадрида к вечеру.",
        "Все, что стоит знать о сливочных перед концом дня.",
    ],
    "ночного": [
        "Коротко о том, что не хочется пропустить до утра.",
        "Поздняя белая сводка для тех, кто еще в игре.",
    ],
    "default": [
        "Главное вокруг «Реала» из свежей ленты.",
        "Сливочная подборка без случайного футбольного шума.",
    ],
}

LABEL_ALIASES = {
    "morning": "утреннего",
    "утро": "утреннего",
    "утренний": "утреннего",
    "утреннего": "утреннего",
    "day": "дневного",
    "день": "дневного",
    "дневной": "дневного",
    "дневного": "дневного",
    "evening": "вечернего",
    "вечер": "вечернего",
    "вечерний": "вечернего",
    "вечернего": "вечернего",
    "night": "ночного",
    "ночь": "ночного",
    "ночной": "ночного",
    "ночного": "ночного",
    "auto": "auto",
    "default": "default",
}

LOOKBACK_BY_LABEL = {
    "утреннего": DIGEST_MORNING_LOOKBACK_HOURS,
    "дневного": DIGEST_DAY_LOOKBACK_HOURS,
    "вечернего": DIGEST_EVENING_LOOKBACK_HOURS,
    "ночного": DIGEST_NIGHT_LOOKBACK_HOURS,
    "default": DIGEST_DEFAULT_LOOKBACK_HOURS,
}


def auto_digest_label(now: datetime | None = None) -> str:
    dt = now.astimezone(TZ) if now else datetime.now(TZ)
    hour = dt.hour
    if 5 <= hour < 11:
        return "утреннего"
    if 11 <= hour < 17:
        return "дневного"
    if 17 <= hour <= 23:
        return "вечернего"
    return "ночного"


def normalize_label(label: str | None) -> str:
    if not label:
        return auto_digest_label()
    value = label.strip().lower()
    normalized = LABEL_ALIASES.get(value, value)
    if normalized == "auto":
        return auto_digest_label()
    return normalized


def lookback_hours_for_label(label: str) -> int:
    return LOOKBACK_BY_LABEL.get(label, DIGEST_DEFAULT_LOOKBACK_HOURS)


def entry_published_at(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)

    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    return None


def is_fresh(published_at: datetime | None, cutoff: datetime) -> bool:
    if published_at is None:
        return DIGEST_INCLUDE_UNDATED
    return published_at >= cutoff


def polish_title(title: str) -> str:
    title = clean_text(translate_text(title))

    replacements = {
        "получает диагноз травмы": "узнал диагноз по травме",
        "получил диагноз травмы": "узнал диагноз по травме",
        "диагноз травмы": "диагноз по травме",
        "снова обратился к новой заинтересованности": "снова получил интерес",
        "рекордной плате": "рекордной сумме",
        "новой заинтересованности": "новому интересу",
        "получает новости обратно": "получил новости",
    }
    for bad, good in replacements.items():
        title = title.replace(bad, good)

    return title.strip()


def related_sources_line(item: RankedDigestItem) -> str:
    if not DIGEST_SHOW_RELATED_SOURCES or not item.related_sources:
        return ""

    visible_sources = [escape(source) for source in item.related_sources[:3]]
    extra_count = len(item.related_sources) - len(visible_sources)
    suffix = f" +{extra_count}" if extra_count > 0 else ""
    return f"\nЕще источники: {', '.join(visible_sources)}{suffix}"


def format_news_entry(i: int, item: RankedDigestItem, title_override: str | None = None) -> str:
    candidate = item.candidate
    safe_text = escape(title_override or polish_title(candidate.title))
    safe_source = escape(candidate.source)
    safe_link = escape(candidate.link, quote=True)
    related = related_sources_line(item)
    return f"<b>{i}. {safe_text}</b>\n<a href=\"{safe_link}\">Читать</a> · {safe_source}{related}"


def split_message(message: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    if len(message) <= limit:
        return [message]

    chunks: list[str] = []
    current = ""
    for block in message.split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        while len(block) > limit:
            chunks.append(block[:limit])
            block = block[limit:]
        current = block

    if current:
        chunks.append(current)
    return chunks


def already_posted_links() -> set[str]:
    return set(sent_digest) | load_sent_links(SENT_BREAKING_FILE)


def digest_semantic_keys(items: list[RankedDigestItem]) -> set[str]:
    keys: set[str] = set()
    for item in items:
        candidate = item.candidate
        key = semantic_news_key(candidate.title, candidate.summary)
        if key:
            keys.add(key)
    return keys


def collect_candidates(sources, cutoff: datetime):
    seen_links = already_posted_links()
    seen_breaking_fingerprints = load_news_keys(SENT_BREAKING_FINGERPRINT_FILE)
    candidates: list[DigestCandidate] = []

    for src in sources:
        url = src.get("url")
        label = src.get("label", url or "Неизвестный источник")
        if not url:
            logging.warning(f"Источник без URL пропущен: {src!r}")
            continue

        try:
            feed = parse_feed_url(url)
            if not feed or not feed.entries:
                continue

            for entry in feed.entries[:DIGEST_ENTRY_SCAN_LIMIT]:
                link = entry.get("link")
                if not link or link in seen_links:
                    continue

                published_at = entry_published_at(entry)
                if not is_fresh(published_at, cutoff):
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                if not title or not passes_filters(title, summary=summary, source=label):
                    continue

                fingerprint = semantic_news_key(title, summary)
                if fingerprint in seen_breaking_fingerprints:
                    logging.info("[DIGEST SKIPPED: BREAKING SEMANTIC DUPLICATE] %s: %s", fingerprint, title)
                    continue

                seen_links.add(link)
                candidates.append(
                    DigestCandidate(
                        title=title,
                        link=link,
                        source=label,
                        published_at=published_at,
                        summary=summary,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return candidates


def normalized_similarity_threshold() -> float:
    return min(max(DIGEST_DEDUPE_SIMILARITY, 0), 100) / 100


def load_quarantine() -> list[dict]:
    if not QUARANTINE_FILE.exists():
        return []
    try:
        data = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_quarantine(rows: list[dict]) -> None:
    QUARANTINE_FILE.write_text(
        json.dumps(rows[-QUARANTINE_LIMIT:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_digest_quarantine(candidates: list[DigestCandidate], selected: list[RankedDigestItem], label: str) -> int:
    selected_links = {item.candidate.link for item in selected}
    now = datetime.now(timezone.utc)
    rows = load_quarantine()
    existing = {row.get("link") for row in rows}
    added = 0

    for candidate in candidates:
        if candidate.link in selected_links or candidate.link in existing:
            continue
        profile = candidate_profile(candidate, now)
        if profile.score >= 78 and "clickbait" not in profile.reason:
            continue
        rows.append(
            {
                "captured_at": now.isoformat(),
                "label": label,
                "title": candidate.title,
                "link": candidate.link,
                "source": candidate.source,
                "score": profile.score,
                "reason": profile.reason,
            }
        )
        existing.add(candidate.link)
        added += 1

    if added:
        save_quarantine(rows)
    return added


def digest_llm_hard_deny(item: RankedDigestItem, headline: str = "") -> bool:
    candidate = item.candidate
    text = " ".join(
        [
            str(candidate.title or ""),
            str(getattr(candidate, "summary", "") or ""),
            str(getattr(candidate, "link", "") or ""),
            str(getattr(candidate, "source", "") or ""),
            str(headline or ""),
        ]
    ).casefold()
    if any(term in text for term in DIGEST_LLM_ABSOLUTE_DENY_TERMS):
        return True
    if not any(term in text for term in DIGEST_LLM_HARD_DENY_TERMS):
        return False
    return not any(term in text for term in DIGEST_LLM_CLUB_IMPACT_TERMS)


def apply_digest_hard_deny(selected: list[RankedDigestItem]) -> tuple[list[RankedDigestItem], int]:
    filtered: list[RankedDigestItem] = []
    dropped = 0
    for item in selected:
        if digest_llm_hard_deny(item):
            dropped += 1
            logging.info("[DIGEST HARD DENY] %s | %s", item.candidate.source, item.candidate.title)
            continue
        filtered.append(item)
    if dropped and not filtered:
        logging.warning("[DIGEST HARD DENY] all items were dropped, keeping original selection")
        return selected, 0
    return filtered, dropped


def apply_llm_digest_editor(selected: list[RankedDigestItem], label: str) -> tuple[list[RankedDigestItem], dict[str, str], dict]:
    review_items = []
    for item in selected:
        candidate = item.candidate
        review_items.append(
            {
                "title": candidate.title,
                "source": candidate.source,
                "summary": getattr(candidate, "summary", ""),
                "score": item.score,
                "reason": item.reason,
            }
        )

    result = review_digest_items(review_items, label=label)
    metrics = {
        "llm_editor_used": result.used,
        "llm_editor_reason": result.reason,
        **{f"llm_{key}": value for key, value in result.metrics.items() if key != "error"},
    }
    if not result.used:
        if result.reason not in {"disabled", "empty"}:
            logging.info("[LLM DIGEST] skipped: %s", result.reason)
        selected, hard_dropped = apply_digest_hard_deny(selected)
        metrics["digest_hard_dropped"] = hard_dropped
        return selected, {}, metrics

    filtered: list[RankedDigestItem] = []
    title_overrides: dict[str, str] = {}
    dropped = 0
    for index, item in enumerate(selected, start=1):
        decision = result.decisions.get(index, {})
        if decision.get("keep") is False:
            dropped += 1
            logging.info("[LLM DIGEST] dropped: %s | %s", item.candidate.source, item.candidate.title)
            continue

        headline = str(decision.get("headline_ru") or "").strip()
        cleaned_headline = clean_text(headline) if headline else ""
        if digest_llm_hard_deny(item, headline) or (
            cleaned_headline and digest_llm_hard_deny(item, cleaned_headline)
        ):
            dropped += 1
            logging.info("[LLM DIGEST] hard dropped: %s | %s", item.candidate.source, item.candidate.title)
            continue
        if cleaned_headline:
            title_overrides[item.candidate.link] = cleaned_headline
        filtered.append(item)

    if not filtered:
        logging.warning("[LLM DIGEST] all items were dropped, keeping original selection")
        metrics["llm_editor_all_dropped"] = True
        return selected, {}, metrics

    metrics["llm_editor_dropped"] = dropped
    metrics["llm_editor_titles"] = len(title_overrides)
    return filtered, title_overrides, metrics


def fetch_digest(sources, label: str, limit=DIGEST_LIMIT):
    lookback_hours = lookback_hours_for_label(label)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    candidates = collect_candidates(sources, cutoff)
    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    review_limit = max(limit, LLM_EDITOR_MAX_DIGEST_ITEMS)
    selected = rank_digest_candidates(
        candidates,
        limit=review_limit,
        dedupe_enabled=DIGEST_DEDUPE_ENABLED,
        priority_sort_enabled=DIGEST_PRIORITY_SORT_ENABLED,
        similarity_threshold=normalized_similarity_threshold(),
    )
    selected, title_overrides, editor_metrics = apply_llm_digest_editor(selected, label)
    selected = selected[:limit]
    quarantined = update_digest_quarantine(candidates, selected, label)
    news_items = [
        format_news_entry(i, item, title_overrides.get(item.candidate.link))
        for i, item in enumerate(selected, start=1)
    ]
    new_links = set()
    grouped_links = 0
    for item in selected:
        new_links.update(item.grouped_links)
        grouped_links += max(len(item.grouped_links) - 1, 0)
    new_fingerprints = digest_semantic_keys(selected)

    logging.info(
        "Digest label=%s lookback=%sh candidates=%s selected=%s grouped=%s priority_sort=%s dedupe=%s",
        label,
        lookback_hours,
        len(candidates),
        len(selected),
        grouped_links,
        DIGEST_PRIORITY_SORT_ENABLED,
        DIGEST_DEDUPE_ENABLED,
    )
    metrics = {
        "label": label,
        "lookback_hours": lookback_hours,
        "candidates": len(candidates),
        "selected": len(selected),
        "review_limit": review_limit,
        "grouped_links": grouped_links,
        "dedupe": DIGEST_DEDUPE_ENABLED,
        "priority_sort": DIGEST_PRIORITY_SORT_ENABLED,
        "quarantined": quarantined,
        "semantic_keys": len(new_fingerprints),
        **editor_metrics,
    }
    return news_items, new_links, new_fingerprints, metrics


def post_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, 4):
        try:
            response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return True
            logging.error("Ошибка Telegram API: %s %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Ошибка при отправке дайджеста, попытка %s: %s", attempt, exc)

        if attempt < 3:
            time.sleep(attempt * 2)

    return False


def send_digest(label: str = "auto"):
    global sent_digest

    label = normalize_label(label)
    record_status("digest", "starting", "digest run started", {"label": label, "dry_run": DRY_RUN})
    block_reason = digest_block_reason()
    if block_reason:
        metrics = {"label": label, "reason": block_reason}
        record_status("digest", "skipped", block_reason, metrics)
        logging.info("Дайджест %s пропущен: %s", label, block_reason)
        print(f"[DIGEST] Пропущен: {block_reason}")
        return

    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items, new_links, new_fingerprints, metrics = fetch_digest(sources, label=label, limit=DIGEST_LIMIT)
    metrics["dry_run"] = DRY_RUN

    if not news_items:
        record_status("digest", "empty", f"Нет свежих новостей для {label} дайджеста", metrics)
        logging.info(f"Нет свежих новостей для {label} дайджеста")
        print(f"[DIGEST] Нет свежих новостей для {label} дайджеста")
        return

    joined_news = "\n\n".join(news_items)
    templates = TEMPLATES.get(label, TEMPLATES["default"])
    intro = random.choice(INTRO_LINES.get(label, INTRO_LINES["default"]))
    message = random.choice(templates).format(news=joined_news, intro=intro)
    message = append_hashtags(message, DIGEST_HASHTAGS)
    chunks = split_message(message)
    metrics["chunks"] = len(chunks)
    metrics["new_links"] = len(new_links)

    if DRY_RUN:
        record_status("digest", "dry_run", f"{label} digest rendered", metrics)
        logging.info(f"DRY_RUN {label} дайджест: {len(news_items)} новостей, частей: {len(chunks)}")
        print(f"[DRY RUN DIGEST: {label}]")
        for index, chunk in enumerate(chunks, start=1):
            print(f"\n--- часть {index}/{len(chunks)} ---\n{chunk}")
        return

    if not telegram_configured():
        record_error("digest", "TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы", metrics)
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    for chunk in chunks:
        if not post_telegram_message(chunk):
            record_error("digest", "Дайджест не сохранен как отправленный: часть сообщения не дошла", metrics)
            logging.error("Дайджест не сохранен как отправленный: часть сообщения не дошла")
            return

    sent_digest.update(new_links)
    save_sent_links(sent_digest)
    if new_fingerprints:
        sent_fingerprints = load_news_keys(SENT_BREAKING_FINGERPRINT_FILE)
        sent_fingerprints.update(new_fingerprints)
        save_news_keys(SENT_BREAKING_FINGERPRINT_FILE, sent_fingerprints)
    record_status("digest", "ok", f"Опубликован {label} дайджест", metrics)
    logging.info(f"Опубликован {label} дайджест")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "auto"
    send_digest(arg)
