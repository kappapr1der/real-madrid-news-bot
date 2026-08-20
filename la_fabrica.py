#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""A low-volume academy format that only posts concrete La Fabrica news."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import requests

from article_media import fetch_article_image
from content_quality import candidate_profile
from digest import DigestCandidate, collect_candidates
from editorial_archive import record_story
from editorial_posts import cache_editorial_image, post_telegram_photo
from match_calendar import digest_block_reason
from post_utils import append_hashtags
from publication_registry import remember_editorial_link
from runtime_config import (
    LA_FABRICA_ENABLED,
    LA_FABRICA_HASHTAGS,
    LA_FABRICA_LOOKBACK_DAYS,
    LA_FABRICA_RESPECT_MATCHDAY_BLOCK,
    LA_FABRICA_TIMEZONE,
    RSS_TIMEOUT_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)
from sources_international import SOURCES_INTERNATIONAL
from sources_ru import SOURCES_RU
from status_manager import record_error, record_status
from text_cleaner import clean_text
from translator import translate_text


LOG_FILE = get_log_file("la_fabrica.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
HISTORY_FILE = get_state_file("la_fabrica_history.json")
TZ = ZoneInfo(LA_FABRICA_TIMEZONE)

ACADEMY_TERMS = (
    "la fabrica",
    "la fábrica",
    "castilla",
    "cantera",
    "academy",
    "juvenil",
    "u19",
    "u-19",
    "under-19",
    "youth prospect",
)
CONCRETE_TERMS = (
    "sign",
    "signing",
    "contract",
    "renew",
    "debut",
    "call-up",
    "called up",
    "promoted",
    "promotion",
    "loan",
    "sale",
    "sold",
    "joins",
    "won",
    "title",
    "ficha",
    "contrato",
    "renueva",
    "debut",
    "convocado",
    "asciende",
    "cesion",
    "cesión",
    "venta",
    "gana",
    "titulo",
    "título",
)


def _load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    try:
        values = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(value) for value in values if value} if isinstance(values, list) else set()


def _save_history(values: set[str]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(sorted(values)[-240:], ensure_ascii=False, indent=2), encoding="utf-8")


def is_concrete_la_fabrica_story(candidate: DigestCandidate) -> bool:
    text = f"{candidate.title} {candidate.summary}".casefold()
    return any(term in text for term in ACADEMY_TERMS) and any(term in text for term in CONCRETE_TERMS)


def select_la_fabrica_story(candidates: list[DigestCandidate], now: datetime | None = None) -> DigestCandidate | None:
    history = _load_history()
    current = now or datetime.now(timezone.utc)
    eligible = [candidate for candidate in candidates if candidate.link not in history and is_concrete_la_fabrica_story(candidate)]
    if not eligible:
        return None
    return max(eligible, key=lambda candidate: candidate_profile(candidate, current).score)


def story_title(candidate: DigestCandidate) -> str:
    return clean_text(translate_text(candidate.title))


def format_la_fabrica(candidate: DigestCandidate) -> str:
    safe_link = escape(candidate.link, quote=True)
    return append_hashtags(
        f"<b>Ла Фабрика</b>\n{escape(story_title(candidate))}\n<a href=\"{safe_link}\">Читать</a> · {escape(candidate.source)}",
        LA_FABRICA_HASHTAGS,
    )


def post_message(message: str) -> bool:
    if not telegram_configured():
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for attempt in range(1, 4):
        try:
            response = requests.post(
                url,
                data={"chat_id": TARGET_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=TELEGRAM_TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                return True
            logging.error("Telegram La Fabrica response=%s body=%s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Telegram La Fabrica attempt=%s failed: %s", attempt, exc)
        if attempt < 3:
            time.sleep(attempt * 2)
    return False


def send_la_fabrica(
    force: bool = False,
    now: datetime | None = None,
    candidate_fetcher: Callable[[datetime], list[DigestCandidate]] | None = None,
    send_text: Callable[[str], bool] = post_message,
    send_photo: Callable[[str, Path], bool] = post_telegram_photo,
) -> bool:
    current = (now or datetime.now(TZ)).astimezone(TZ)
    metrics = {"date": current.date().isoformat()}
    if not LA_FABRICA_ENABLED and not force:
        record_status("la_fabrica", "disabled", "LA_FABRICA_ENABLED=false", metrics)
        return False
    if LA_FABRICA_RESPECT_MATCHDAY_BLOCK and not force:
        reason = digest_block_reason(current)
        if reason:
            record_status("la_fabrica", "skipped", reason, metrics)
            return False
    cutoff = current.astimezone(timezone.utc) - timedelta(days=max(LA_FABRICA_LOOKBACK_DAYS, 1))
    candidates = candidate_fetcher(cutoff) if candidate_fetcher else collect_candidates(SOURCES_INTERNATIONAL + SOURCES_RU, cutoff)
    story = select_la_fabrica_story(candidates, now=current.astimezone(timezone.utc))
    metrics["candidates"] = len(candidates)
    if not story:
        record_status("la_fabrica", "empty", "no concrete academy update", metrics)
        return False
    caption = format_la_fabrica(story)
    image_url = fetch_article_image(story.link)
    photo_path = cache_editorial_image(image_url) if image_url else None
    delivered = send_photo(caption, photo_path) if photo_path else send_text(caption)
    if not delivered:
        record_error("la_fabrica", "Telegram send failed", metrics)
        return False
    history = _load_history()
    history.add(story.link)
    _save_history(history)
    remember_editorial_link(story.link)
    record_story(
        kind="la_fabrica",
        title=story_title(story),
        source=story.source,
        link=story.link,
        category="academy",
        metadata={"raw_title": story.title},
    )
    metrics["source"] = story.source
    record_status("la_fabrica", "ok", "academy story published", metrics)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot La Fabrica")
    parser.add_argument("--force", action="store_true", help="ignore schedule guards")
    args = parser.parse_args()
    send_la_fabrica(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
