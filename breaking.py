#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import signal
import time
import logging
import random
import re
import threading
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

import requests
from colorama import init, Fore, Style

from article_media import fetch_article_image
from breaking_confirmation import observe_breaking_candidate
from editorial_archive import record_story
from text_cleaner import clean_text
from filters import passes_filters
from fabrizio_source import fetch_fabrizio_telegram_entries
from feed_utils import entry_media_url, is_repost_entry, parse_feed_url, source_is_x
from news_fingerprint import load_news_keys, save_news_keys, semantic_news_key, ucl_draw_event_key
from post_utils import append_hashtags
from llm_editor import llm_editor_enabled, review_breaking_items
from status_manager import record_error, record_status
from translator import translate_text
from sources_international import HERE_WE_GO_SOURCES, SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from source_quality import source_quality_policy, source_trust_tier
from story_lifecycle import lifecycle_decision, record_lifecycle
from visual_cards import render_news_card, render_x_post_card
from runtime_config import (
    BREAKING_HASHTAGS,
    BREAKING_INTERVAL_SECONDS,
    DIGEST_TIMEZONE,
    DRY_RUN,
    HERE_WE_GO_ENABLED,
    HERE_WE_GO_ENTRY_SCAN_LIMIT,
    HERE_WE_GO_HASHTAGS,
    HERE_WE_GO_MAX_AGE_MINUTES,
    LLM_EDITOR_BREAKING_BUFFER_SECONDS,
    LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS,
    LLM_EDITOR_MAX_BREAKING_ITEMS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    UCL_DRAW_ALERT_ENABLED,
    UCL_DRAW_DATE,
    get_log_file,
    get_state_file,
    telegram_configured,
)

init(autoreset=True)

LOG_FILE = get_log_file("breaking.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

SENT_FILE = get_state_file("sent_breaking.txt")
SENT_FINGERPRINT_FILE = get_state_file("sent_breaking_fingerprints.txt")
LLM_PENDING_FILE = get_state_file("breaking_llm_pending.json")
LLM_REJECTED_FILE = get_state_file("breaking_llm_rejected.txt")
HERE_WE_GO_BOOTSTRAP_FILE = get_state_file("here_we_go_bootstrap.txt")
X_RSS_BOOTSTRAP_FILE = get_state_file("x_rss_bootstrap.json")
stop_event = threading.Event()


def request_stop(signum=None, frame=None):
    stop_event.set()


def install_signal_handlers():
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)


def load_sent_links(path=SENT_FILE):
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_links(path, links):
    with path.open("w", encoding="utf-8") as f:
        for link in sorted(links):
            f.write(link + "\n")


def save_sent_links(links):
    save_links(SENT_FILE, links)


sent_breaking = load_sent_links()
llm_rejected_breaking = load_sent_links(LLM_REJECTED_FILE)
sent_breaking_fingerprints = load_news_keys(SENT_FINGERPRINT_FILE)


def refresh_sent_fingerprints() -> set[str]:
    global sent_breaking_fingerprints
    sent_breaking_fingerprints = load_news_keys(SENT_FINGERPRINT_FILE)
    return sent_breaking_fingerprints

STRONG_BREAKING_KEYWORDS = [
    "breaking",
    "official",
    "confirmed",
    "oficial",
    "confirmado",
    "comunicado oficial",
    "официально",
    "подтверждено",
]

PREFIX_BREAKING_KEYWORDS = [
    "urgent",
    "экстренно",
    "срочно",
]

BREAKING_REAL_CONTEXT_TERMS = (
    "real madrid", "реал мадрид", "реал", "madrid", "bernabeu", "bernábeu",
    "florentino", "флорентино", "mbappe", "мбаппе", "vinicius", "винисиус",
    "bellingham", "беллингем", "valverde", "вальверде", "courtois", "куртуа",
    "rodrygo", "родриго", "arda", "гюлер", "trent", "трент", "mourinho", "моуринью",
    "xabi", "алонсо", "olise", "олисе", "enzo", "энцо",
)
BREAKING_FOOTBALL_TERMS = (
    "sign", "signed", "transfer", "fichaje", "contract", "contrato", "renewal",
    "injury", "lesion", "lesión", "squad", "lineup", "convocatoria", "match",
    "partido", "goal", "gol", "трансфер", "контракт", "травм", "состав",
    "матч", "гол", "переговор", "аренда", "уход", "подпис", "champions",
    "лига чемпионов", "жеребьев",
)
REAL_SOURCE_TERMS = (
    "real madrid", "madrid universal", "managing madrid", "marca", "defensa central",
    "bernabeu", "bernabéu", "sport - real madrid", "mundo deportivo - real madrid",
)
BREAKING_DENY_TERMS = (
    "basketball", "baloncesto", "liga endesa", "euroleague",
    "trey lyles", "scariolo", "баскетбол", "евролига", "трей лайлс", "скариоло",
    "jaime pradilla", "pradilla", "хайме прадилья", "прадилья",
    "brasil en mundial", "con brasil en mundial", "за сборную бразилии",
    "сборной бразилии", "ronaldo nazario", "rivaldo", "romario",
    "роналду назарио", "ривалдо", "ромарио",
    "minimum one player in final mundial", "menos jugador en final mundial",
    "минимум одного игрока в финале чемпионата мира",
)
BREAKING_RUMOUR_TERMS = (
    "rumour", "rumor", "could", "may", "might", "unlikely", "dream", "wish",
    "would like", "interested", "interest", "reportedly", "report says", "собирается",
    "может", "якобы", "слух", "интересуется", "мечтает", "возможн",
)
BREAKING_RELIABLE_TIERS = {"official", "reporter", "established_media"}
HERE_WE_GO_SOURCE = "fabrizio romano - telegram"
HERE_WE_GO_TERMS = ("here we go", "herewego")
HERE_WE_GO_DEAL_TERMS = (
    "deal", "sign", "signed", "signing", "joining", "transfer", "move", "agreement",
    "contract", "loan", "fichaje", "traspaso", "contrato", "cesion",
)

TEMPLATES = [
    "<b>Сливочная молния</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Экстра для мадридистов</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Срочно вокруг «Реала»</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Белая лента обновилась</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
    "<b>Из Мадрида пришло важное</b>\n{news}\n<a href=\"{link}\">Читать</a> · {source}",
]
UCL_DRAW_TEMPLATE = (
    "<b>Жеребьевка Лиги чемпионов</b>\n"
    "{news}\n"
    "<a href=\"{link}\">Читать</a> · {source}"
)
HERE_WE_GO_TEMPLATE = (
    "<b>Here we go</b>\n"
    "{news}\n"
    "<a href=\"{link}\">Источник: Fabrizio Romano</a>"
)

def source_url(source: Any) -> str | None:
    if isinstance(source, dict):
        return source.get("url")
    if isinstance(source, str):
        return source
    return None


def source_label(source: Any) -> str:
    if isinstance(source, dict):
        return source.get("label") or source.get("url") or "Неизвестный источник"
    if isinstance(source, str):
        return source
    return "Неизвестный источник"


def _breaking_normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def has_breaking_context(text: str, source: str = "", summary: str = "") -> bool:
    combined = _breaking_normalize(f"{text} {summary}")
    source_name = _breaking_normalize(source)

    if any(term in combined for term in BREAKING_DENY_TERMS):
        return False

    has_real_signal = any(term in combined for term in BREAKING_REAL_CONTEXT_TERMS)
    source_is_real = any(term in source_name for term in REAL_SOURCE_TERMS)
    has_football_signal = any(term in combined for term in BREAKING_FOOTBALL_TERMS)

    return has_real_signal and (has_football_signal or source_is_real)


def is_here_we_go(text: str, source: str = "", summary: str = "") -> bool:
    """Accept Romano's phrase only for a direct Real Madrid transfer confirmation."""
    if not HERE_WE_GO_ENABLED or _breaking_normalize(source) != HERE_WE_GO_SOURCE:
        return False

    combined = _breaking_normalize(f"{text} {summary}")
    return (
        any(term in combined for term in HERE_WE_GO_TERMS)
        and any(term in combined for term in HERE_WE_GO_DEAL_TERMS)
        and has_breaking_context(text, source=source, summary=summary)
    )


def here_we_go_is_fresh(entry: dict[str, Any]) -> bool:
    published_at = entry.get("published_at")
    if not isinstance(published_at, datetime):
        return False
    return published_at >= datetime.now(timezone.utc) - timedelta(minutes=max(HERE_WE_GO_MAX_AGE_MINUTES, 15))


def bootstrap_here_we_go(entries: list[dict[str, Any]]) -> bool:
    """Remember the current channel page once, so deployment never republishes old deals."""
    if HERE_WE_GO_BOOTSTRAP_FILE.exists():
        return False

    known_links = {str(entry.get("link") or "").strip() for entry in entries}
    known_links.discard("")
    save_links(HERE_WE_GO_BOOTSTRAP_FILE, known_links)
    logging.info("[HERE WE GO] bootstrap complete, remembered=%s", len(known_links))
    return True


def load_x_rss_bootstrap() -> dict[str, list[str]]:
    if not X_RSS_BOOTSTRAP_FILE.exists():
        return {}
    try:
        data = json.loads(X_RSS_BOOTSTRAP_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(label): [str(link) for link in links if str(link)]
        for label, links in data.items()
        if isinstance(links, list)
    }


def save_x_rss_bootstrap(data: dict[str, list[str]]) -> None:
    X_RSS_BOOTSTRAP_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def bootstrap_x_source(source: Any, entries: list[dict[str, Any]]) -> set[str] | None:
    """Remember the first visible page of each newly enabled X source.

    ``None`` means the source was just initialized and should not be processed
    in this cycle. It prevents old posts from turning into new breakings after
    X is enabled or a handle is added later.
    """
    if not source_is_x(source):
        return set()

    label = source_label(source)
    data = load_x_rss_bootstrap()
    if label in data:
        return set(data[label])

    known_links = {str(entry.get("link") or "").strip() for entry in entries}
    known_links.discard("")
    if not known_links:
        return set()

    data[label] = sorted(known_links)
    save_x_rss_bootstrap(data)
    logging.info("[X RSS] bootstrap complete for %s, remembered=%s", label, len(known_links))
    return None


def is_ucl_draw_result(text: str, summary: str = "", now: datetime | None = None) -> bool:
    if not UCL_DRAW_ALERT_ENABLED or not UCL_DRAW_DATE:
        return False

    current = (now or datetime.now(ZoneInfo(DIGEST_TIMEZONE))).astimezone(ZoneInfo(DIGEST_TIMEZONE))
    if current.date().isoformat() != UCL_DRAW_DATE:
        return False

    return bool(ucl_draw_event_key(text, summary, UCL_DRAW_DATE))


def is_breaking(text: str, source: str = "", summary: str = "", now: datetime | None = None) -> bool:
    lower_text = _breaking_normalize(text)
    if is_here_we_go(text, source=source, summary=summary):
        logging.info("[BREAKING DETECTED: HERE WE GO] %s", text)
        return True
    if not has_breaking_context(text, source=source, summary=summary):
        logging.info("[BREAKING SKIPPED: LOW CONTEXT] %s: %s", source, text)
        return False

    tier = source_trust_tier(source)
    source_policy = source_quality_policy(source)
    if source_policy in {"backup", "blocked"}:
        logging.info("[BREAKING SKIPPED: SOURCE POLICY %s] %s: %s", source_policy, source, text)
        return False
    if tier not in BREAKING_RELIABLE_TIERS:
        logging.info("[BREAKING SKIPPED: UNVERIFIED SOURCE] %s: %s", source, text)
        return False
    if tier != "official" and any(term in lower_text for term in BREAKING_RUMOUR_TERMS):
        logging.info("[BREAKING SKIPPED: RUMOUR] %s: %s", source, text)
        return False

    if is_ucl_draw_result(text, summary=summary, now=now):
        logging.info("[BREAKING DETECTED: UCL DRAW] %s", text)
        return True

    for word in STRONG_BREAKING_KEYWORDS:
        if word in lower_text:
            print(Fore.RED + Style.BRIGHT + f"[BREAKING DETECTED] {word} -> {text}")
            logging.info(f"Обнаружено ключевое слово: {word} -> {text}")
            return True

    for word in PREFIX_BREAKING_KEYWORDS:
        if lower_text == word or lower_text.startswith(f"{word} ") or lower_text.startswith(f"{word}:"):
            print(Fore.RED + Style.BRIGHT + f"[BREAKING DETECTED] {word} -> {text}")
            logging.info(f"Обнаружено ключевое слово: {word} -> {text}")
            return True

    return False


def load_llm_pending() -> list[dict[str, Any]]:
    if not LLM_PENDING_FILE.exists():
        return []
    try:
        data = json.loads(LLM_PENDING_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_llm_pending(rows: list[dict[str, Any]]) -> None:
    LLM_PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    LLM_PENDING_FILE.write_text(
        json.dumps(rows[-100:], ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def pending_llm_links() -> set[str]:
    return {row.get("link", "") for row in load_llm_pending() if row.get("link")}


def queue_llm_breaking(
    title: str,
    summary: str,
    link: str,
    source: str,
    fingerprint: str,
    media_image_url: str = "",
) -> None:
    now = int(time.time())
    rows = load_llm_pending()
    by_link = {row.get("link"): row for row in rows if row.get("link")}
    row = by_link.get(link)
    if row:
        row["last_seen_at"] = now
        row["seen_count"] = int(row.get("seen_count", 1)) + 1
    else:
        rows.append(
            {
                "title": title,
                "summary": summary,
                "link": link,
                "source": source,
                "fingerprint": fingerprint,
                "media_image_url": media_image_url,
                "first_seen_at": now,
                "last_seen_at": now,
                "seen_count": 1,
            }
        )
    save_llm_pending(rows)


def _post_breaking_row(row: dict[str, Any], decision: dict[str, Any] | None = None) -> bool:
    fingerprint = str(row.get("fingerprint") or "")
    link = str(row.get("link") or "")
    if not link or link in sent_breaking:
        return False
    if fingerprint and fingerprint in refresh_sent_fingerprints():
        logging.info("[BREAKING SKIPPED: SEMANTIC DUPLICATE AFTER LLM] %s: %s", fingerprint, row.get("title"))
        return False

    headline = ""
    if decision:
        headline = str(decision.get("headline_ru") or "").strip()
    if not headline:
        headline = translate_text(str(row.get("title") or ""))
    clean_news = clean_text(headline)
    lifecycle = lifecycle_decision(
        str(row.get("title") or ""),
        source=str(row.get("source") or ""),
        category="breaking",
        fingerprint=fingerprint,
    )
    if lifecycle.relevant and not lifecycle.changed:
        logging.info("[BREAKING SKIPPED: STORY STATUS UNCHANGED] %s", lifecycle.key)
        return False
    event_type = "ucl_draw" if is_ucl_draw_result(str(row.get("title") or ""), str(row.get("summary") or "")) else ""
    sent = send_breaking(
        clean_news,
        link,
        source=str(row.get("source") or ""),
        fingerprint=fingerprint,
        event_type=event_type,
        media_image_url=str(row.get("media_image_url") or ""),
    )
    if sent and lifecycle.relevant:
        record_lifecycle(
            str(row.get("title") or ""),
            source=str(row.get("source") or ""),
            link=link,
            category="breaking",
            fingerprint=fingerprint,
        )
    return sent


def flush_llm_breaking_queue() -> tuple[int, int]:
    global llm_rejected_breaking

    if not llm_editor_enabled("breaking"):
        return 0, 0

    rows = load_llm_pending()
    if not rows:
        return 0, 0

    now = int(time.time())
    ready = [
        row for row in rows
        if now - int(row.get("first_seen_at", now)) >= LLM_EDITOR_BREAKING_BUFFER_SECONDS
    ]
    if not ready:
        return 0, 0

    ready = ready[:LLM_EDITOR_MAX_BREAKING_ITEMS]
    result = review_breaking_items(ready)
    if not result.used:
        if result.reason == "breaking_min_interval":
            logging.info("[LLM BREAKING] waiting for min interval, pending=%s", len(rows))
            return 0, 0

        fallback_ready = [
            row for row in ready
            if now - int(row.get("first_seen_at", now)) >= LLM_EDITOR_BREAKING_FALLBACK_AFTER_SECONDS
        ]
        if not fallback_ready:
            logging.info("[LLM BREAKING] skipped: %s, pending=%s", result.reason, len(rows))
            return 0, 0

        posted = 0
        ready_links = {row.get("link") for row in fallback_ready}
        for row in fallback_ready:
            if _post_breaking_row(row):
                posted += 1
        save_llm_pending([row for row in rows if row.get("link") not in ready_links])
        return posted, 0

    posted = 0
    rejected = 0
    processed_links: set[str] = set()
    for index, row in enumerate(ready, start=1):
        decision = result.decisions.get(index, {})
        should_post = decision.get("post") is True
        link = str(row.get("link") or "")
        if should_post:
            if _post_breaking_row(row, decision):
                posted += 1
        else:
            rejected += 1
            if link:
                llm_rejected_breaking.add(link)
            logging.info("[LLM BREAKING] rejected: %s | %s", decision.get("reason"), row.get("title"))
        if link:
            processed_links.add(link)

    if processed_links:
        save_llm_pending([row for row in rows if row.get("link") not in processed_links])
        save_links(LLM_REJECTED_FILE, llm_rejected_breaking)

    logging.info("[LLM BREAKING] posted=%s rejected=%s pending=%s", posted, rejected, len(rows) - len(processed_links))
    return posted, rejected


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
            logging.error("Ошибка при отправке breaking, попытка %s: %s", attempt, exc)

        if attempt < 3:
            time.sleep(attempt * 2)

    return False


def post_telegram_photo(caption: str, photo_url: str = "", photo_path=None) -> bool:
    if len(caption) > 1024 or (not photo_url and not photo_path):
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": TARGET_CHAT_ID,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML",
    }

    for attempt in range(1, 3):
        try:
            if photo_path:
                with open(photo_path, "rb") as image_file:
                    response = requests.post(
                        url,
                        data=payload,
                        files={"photo": (photo_path.name, image_file, "image/jpeg")},
                        timeout=TELEGRAM_TIMEOUT_SECONDS,
                    )
            else:
                payload["photo"] = photo_url
                response = requests.post(url, data=payload, timeout=TELEGRAM_TIMEOUT_SECONDS)
            if response.status_code == 200:
                return True
            logging.warning("Фото для breaking не отправилось: %s %s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.warning("Ошибка при отправке фото breaking, попытка %s: %s", attempt, exc)

        if attempt < 2:
            time.sleep(attempt * 2)

    return False


def send_breaking(
    news: str,
    link: str,
    source: str = "Неизвестный источник",
    fingerprint: str = "",
    event_type: str = "",
    media_image_url: str = "",
):
    if event_type == "ucl_draw":
        template = UCL_DRAW_TEMPLATE
        hashtags = BREAKING_HASHTAGS
    elif event_type == "here_we_go":
        template = HERE_WE_GO_TEMPLATE
        hashtags = HERE_WE_GO_HASHTAGS
    else:
        template = random.choice(TEMPLATES)
        hashtags = BREAKING_HASHTAGS
    message = template.format(
        news=escape(news),
        link=escape(link, quote=True),
        source=escape(source),
    )
    message = append_hashtags(message, hashtags)

    if DRY_RUN:
        logging.info(f"DRY_RUN breaking: {news} | Источник: {source}")
        print(Fore.MAGENTA + Style.BRIGHT + "[DRY RUN BREAKING]\n" + message)
        return True

    if not telegram_configured():
        record_error("breaking", "TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        logging.error("TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        print(Fore.RED + "[BREAKING] TELEGRAM_BOT_TOKEN или TARGET_CHAT_ID не заданы")
        return False

    x_source = bool(re.match(r"^x\s*[-–]\s*@", source.strip(), flags=re.IGNORECASE))
    image_url = "" if x_source else fetch_article_image(link)
    branded_card = render_x_post_card(source, news, media_image_url) if x_source else render_news_card(image_url)
    sent = False
    if branded_card:
        sent = post_telegram_photo(message, photo_path=branded_card)
        if sent:
            logging.info("Опубликовано breaking с фирменной карточкой: %s | Источник: %s", news, source)
    elif image_url:
        sent = post_telegram_photo(message, photo_url=image_url)
        if sent:
            logging.info("Опубликовано breaking с фото: %s | Источник: %s", news, source)

    if not sent:
        sent = post_telegram_message(message)

    if sent:
        logging.info(f"Опубликовано breaking: {news} | Источник: {source}")
        print(Fore.RED + Style.BRIGHT + f"[SENT BREAKING] {news}")
        sent_breaking.add(link)
        save_sent_links(sent_breaking)
        if fingerprint:
            sent_breaking_fingerprints.add(fingerprint)
            save_news_keys(SENT_FINGERPRINT_FILE, sent_breaking_fingerprints)
        record_story(
            kind="breaking",
            title=news,
            source=source,
            link=link,
            fingerprint=fingerprint,
            category="breaking",
        )
    else:
        record_error("breaking", "Telegram send failed for breaking post", {"source": source})
    return sent


def fetch_breaking(sources):
    found = 0
    queued = 0
    rejected = 0
    awaiting_confirmation = 0
    checked = 0
    errors = 0
    use_llm_editor = llm_editor_enabled("breaking")
    pending_links = pending_llm_links() if use_llm_editor else set()
    seen_fingerprints = refresh_sent_fingerprints()

    for source in sources:
        if stop_event.is_set():
            break

        url = source_url(source)
        label = source_label(source)
        if not url:
            logging.warning(f"Источник без URL пропущен: {source!r}")
            continue

        checked += 1
        try:
            here_we_go_source = isinstance(source, dict) and source.get("kind") == "fabrizio_telegram"
            bootstrap_links: set[str] = set()
            if here_we_go_source:
                entries = fetch_fabrizio_telegram_entries(url)[:HERE_WE_GO_ENTRY_SCAN_LIMIT]
                if bootstrap_here_we_go(entries):
                    continue
                bootstrap_links = load_sent_links(HERE_WE_GO_BOOTSTRAP_FILE)
            else:
                feed = parse_feed_url(source)
                entry_limit = source.get("breaking_entry_scan_limit", 1) if isinstance(source, dict) else 1
                entries = list(feed.entries[:entry_limit]) if feed and feed.entries else []
                x_bootstrap_links = bootstrap_x_source(source, entries)
                if x_bootstrap_links is None:
                    continue
                bootstrap_links.update(x_bootstrap_links)

            for entry in entries:
                if source_is_x(source) and is_repost_entry(entry):
                    continue
                if here_we_go_source and not here_we_go_is_fresh(entry):
                    continue
                link = entry.get("link")
                if not link or link in bootstrap_links or link in sent_breaking or link in llm_rejected_breaking or link in pending_links:
                    continue

                title = entry.get("title", "").strip()
                summary = entry.get("summary", "")
                if not title or not passes_filters(title, summary=summary, source=label):
                    continue

                here_we_go = is_here_we_go(title, source=label, summary=summary)
                if not is_breaking(title, source=label, summary=summary):
                    continue

                is_draw_alert = is_ucl_draw_result(title, summary)
                fingerprint = ucl_draw_event_key(title, summary, UCL_DRAW_DATE) or semantic_news_key(title, summary)
                if fingerprint in seen_fingerprints:
                    logging.info("[BREAKING SKIPPED: SEMANTIC DUPLICATE] %s: %s", fingerprint, title)
                    continue
                confirmation = observe_breaking_candidate(
                    fingerprint=fingerprint,
                    source=label,
                    link=link,
                    title=title,
                    trusted_reporter=here_we_go,
                )
                if not confirmation.ready:
                    awaiting_confirmation += 1
                    logging.info(
                        "[BREAKING AWAITING CONFIRMATION] sources=%s fingerprint=%s title=%s",
                        confirmation.sources,
                        fingerprint,
                        title,
                    )
                    continue
                if use_llm_editor and not is_draw_alert and not here_we_go:
                    queue_llm_breaking(
                        title,
                        summary,
                        link,
                        label,
                        fingerprint,
                        media_image_url=entry_media_url(entry) if source_is_x(source) else "",
                    )
                    pending_links.add(link)
                    seen_fingerprints.add(fingerprint)
                    queued += 1
                    logging.info("[LLM BREAKING] queued: %s | %s", label, title)
                    continue
                news = translate_text(title)
                clean_news = clean_text(news)
                event_type = "here_we_go" if here_we_go else "ucl_draw" if is_draw_alert else ""
                lifecycle = lifecycle_decision(title, source=label, category="breaking", fingerprint=fingerprint)
                if lifecycle.relevant and not lifecycle.changed:
                    logging.info("[BREAKING SKIPPED: STORY STATUS UNCHANGED] %s", lifecycle.key)
                    continue
                if send_breaking(
                    clean_news,
                    link,
                    source=label,
                    fingerprint=fingerprint,
                    event_type=event_type,
                    media_image_url=entry_media_url(entry) if source_is_x(source) else "",
                ):
                    if lifecycle.relevant:
                        record_lifecycle(title, source=label, link=link, category="breaking", fingerprint=fingerprint)
                    seen_fingerprints.add(fingerprint)
                    found += 1
        except Exception as e:
            errors += 1
            logging.error(f"Ошибка при парсинге {url}: {e}")

    if use_llm_editor:
        posted, rejected_now = flush_llm_breaking_queue()
        found += posted
        rejected += rejected_now

    return checked, found, errors, queued, rejected, len(load_llm_pending()) if use_llm_editor else 0, awaiting_confirmation


def run_cycle(sources):
    checked, found, errors, queued, rejected, pending, awaiting_confirmation = fetch_breaking(sources)
    state = "degraded" if errors and errors == checked else "ok"
    record_status(
        "breaking",
        state,
        "cycle complete",
        {
            "checked": checked,
            "found": found,
            "queued": queued,
            "rejected": rejected,
            "pending": pending,
            "errors": errors,
            "awaiting_confirmation": awaiting_confirmation,
            "dry_run": DRY_RUN,
        },
    )
    print(Fore.CYAN + f"[CYCLE DONE] Проверено {checked} источников, найдено {found} breaking, queued {queued}, pending {pending}, ошибок {errors}.")
    return checked, found


def parse_args():
    parser = argparse.ArgumentParser(description="Coffee Bot breaking news monitor")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one cycle and exit; useful for dry-run checks before deployment",
    )
    return parser.parse_args()


def main() -> int:
    install_signal_handlers()
    args = parse_args()
    sources = SOURCES_INTERNATIONAL + SOURCES_RU + HERE_WE_GO_SOURCES
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    record_status("breaking", "starting", f"monitor started ({mode})")
    print(Fore.YELLOW + f"[BREAKING BOT STARTED] Запущен мониторинг breaking news ({mode}).")

    if args.once:
        run_cycle(sources)
        return 0

    try:
        while not stop_event.is_set():
            run_cycle(sources)
            stop_event.wait(BREAKING_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        request_stop(signal.SIGINT, None)

    if stop_event.is_set():
        record_status("breaking", "stopping", "monitor stopped by signal", {"dry_run": DRY_RUN})
        logging.info("Breaking-монитор остановлен сигналом")
        print(Fore.YELLOW + "[BREAKING] Остановка по сигналу")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
