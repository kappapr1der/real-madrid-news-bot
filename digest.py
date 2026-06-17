#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import calendar
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
from translator import translate_text
from text_cleaner import clean_text
from runtime_config import (
    DIGEST_DAY_LOOKBACK_HOURS,
    DIGEST_DEFAULT_LOOKBACK_HOURS,
    DIGEST_ENTRY_SCAN_LIMIT,
    DIGEST_EVENING_LOOKBACK_HOURS,
    DIGEST_INCLUDE_UNDATED,
    DIGEST_LIMIT,
    DIGEST_MORNING_LOOKBACK_HOURS,
    DIGEST_NIGHT_LOOKBACK_HOURS,
    DIGEST_TIMEZONE,
    DRY_RUN,
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
TZ = ZoneInfo(DIGEST_TIMEZONE)


@dataclass
class DigestCandidate:
    title: str
    link: str
    source: str
    published_at: datetime | None


def load_sent_links():
    if not SENT_FILE.exists():
        return set()
    with SENT_FILE.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_sent_links(links):
    with SENT_FILE.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


sent_digest = load_sent_links()

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


def published_time_label(published_at: datetime | None) -> str:
    if not published_at:
        return ""
    return published_at.astimezone(TZ).strftime("%H:%M")


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


def format_news_entry(i: int, candidate: DigestCandidate) -> str:
    safe_text = escape(polish_title(candidate.title))
    safe_source = escape(candidate.source)
    safe_link = escape(candidate.link, quote=True)
    time_label = published_time_label(candidate.published_at)
    meta = f"{safe_source} · {time_label}" if time_label else safe_source
    return f"<b>{i}. {safe_text}</b>\n<a href=\"{safe_link}\">Читать</a> · {meta}"


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


def collect_candidates(sources, cutoff: datetime):
    seen_links = set(sent_digest)
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

                seen_links.add(link)
                candidates.append(
                    DigestCandidate(
                        title=title,
                        link=link,
                        source=label,
                        published_at=published_at,
                    )
                )
        except Exception as e:
            logging.error(f"Ошибка при парсинге {url}: {e}")

    return candidates


def fetch_digest(sources, label: str, limit=DIGEST_LIMIT):
    lookback_hours = lookback_hours_for_label(label)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    candidates = collect_candidates(sources, cutoff)
    candidates.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    selected = candidates[:limit]
    news_items = [format_news_entry(i, candidate) for i, candidate in enumerate(selected, start=1)]
    new_links = {candidate.link for candidate in selected}

    logging.info(
        "Digest label=%s lookback=%sh candidates=%s selected=%s",
        label,
        lookback_hours,
        len(candidates),
        len(selected),
    )
    return news_items, new_links


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
    block_reason = digest_block_reason()
    if block_reason:
        logging.info("Дайджест %s пропущен: %s", label, block_reason)
        print(f"[DIGEST] Пропущен: {block_reason}")
        return

    sources = SOURCES_INTERNATIONAL + SOURCES_RU
    news_items, new_links = fetch_digest(sources, label=label, limit=DIGEST_LIMIT)

    if not news_items:
        logging.info(f"Нет свежих новостей для {label} дайджеста")
        print(f"[DIGEST] Нет свежих новостей для {label} дайджеста")
        return

    joined_news = "\n\n".join(news_items)
    templates = TEMPLATES.get(label, TEMPLATES["default"])
    intro = random.choice(INTRO_LINES.get(label, INTRO_LINES["default"]))
    message = random.choice(templates).format(news=joined_news, intro=intro)
    chunks = split_message(message)

    if DRY_RUN:
        logging.info(f"DRY_RUN {label} дайджест: {len(news_items)} новостей, частей: {len(chunks)}")
        print(f"[DRY RUN DIGEST: {label}]")
        for index, chunk in enumerate(chunks, start=1):
            print(f"\n--- часть {index}/{len(chunks)} ---\n{chunk}")
        return

    if not telegram_configured():
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return

    for chunk in chunks:
        if not post_telegram_message(chunk):
            logging.error("Дайджест не сохранен как отправленный: часть сообщения не дошла")
            return

    sent_digest.update(new_links)
    save_sent_links(sent_digest)
    logging.info(f"Опубликован {label} дайджест")


if __name__ == "__main__":
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else "auto"
    send_digest(arg)
