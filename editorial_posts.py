#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Scheduled visual editorial formats that deliberately stay out of digest flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from editorial_archive import record_story
from match_calendar import digest_block_reason
from paper_covers import PaperCover, fetch_latest_as_cover
from post_utils import append_hashtags
from runtime_config import (
    DRY_RUN,
    EDITORIAL_COVER_ENABLED,
    EDITORIAL_COVER_HASHTAGS,
    EDITORIAL_COVER_RESPECT_MATCHDAY_BLOCK,
    HISTORY_ENABLED,
    HISTORY_EVENTS_FILE,
    HISTORY_HASHTAGS,
    HISTORY_RESPECT_MATCHDAY_BLOCK,
    HISTORY_TIMEZONE,
    HTTP_USER_AGENT,
    RSS_TIMEOUT_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    get_log_file,
    get_state_file,
    telegram_configured,
)
from status_manager import record_error, record_status


LOG_FILE = get_log_file("editorial_posts.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)

COVER_HISTORY_FILE = get_state_file("editorial_cover_history.json")
HISTORY_POSTS_FILE = get_state_file("history_posts.json")
EDITORIAL_MEDIA_DIR = get_state_file("editorial_media")
TZ = ZoneInfo(HISTORY_TIMEZONE)
RUSSIAN_MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


@dataclass(frozen=True)
class HistoryEvent:
    id: str
    month: int
    day: int
    year: int
    title: str
    description: str
    source_name: str = ""
    source_url: str = ""
    image_url: str = ""
    priority: int = 0

    @property
    def date_label(self) -> str:
        return f"{self.day} {RUSSIAN_MONTHS[self.month - 1]} {self.year}"


def _load_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(value) for value in data if value} if isinstance(data, list) else set()


def _save_keys(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(keys)[-400:], ensure_ascii=False, indent=2), encoding="utf-8")


def load_history_events(path: Path = HISTORY_EVENTS_FILE) -> list[HistoryEvent]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("events", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    events: list[HistoryEvent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            event = HistoryEvent(
                id=str(row["id"]).strip(),
                month=int(row["month"]),
                day=int(row["day"]),
                year=int(row["year"]),
                title=str(row["title"]).strip(),
                description=str(row["description"]).strip(),
                source_name=str(row.get("source_name") or "").strip(),
                source_url=str(row.get("source_url") or "").strip(),
                image_url=str(row.get("image_url") or "").strip(),
                priority=int(row.get("priority") or 0),
            )
            date(event.year, event.month, event.day)
        except (KeyError, TypeError, ValueError):
            continue
        if event.id and event.title and event.description:
            events.append(event)
    return events


def history_events_for_day(events: list[HistoryEvent], now: datetime) -> list[HistoryEvent]:
    return sorted(
        (event for event in events if event.month == now.month and event.day == now.day),
        key=lambda event: (-event.priority, event.year, event.id),
    )


def _history_key(event: HistoryEvent, now: datetime) -> str:
    return f"{now.date().isoformat()}:{event.id}"


def _cover_key(now: datetime) -> str:
    return now.date().isoformat()


def cache_editorial_image(url: str) -> Path | None:
    if not url:
        return None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": HTTP_USER_AGENT},
            timeout=RSS_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    content_type = str(response.headers.get("content-type") or "").casefold()
    if "image" not in content_type or not response.content:
        return None
    suffix = ".png" if "png" in content_type else ".jpg"
    path = EDITORIAL_MEDIA_DIR / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()[:20]}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    return path


def post_telegram_photo(caption: str, photo_path: Path) -> bool:
    if DRY_RUN:
        print(f"[DRY RUN EDITORIAL PHOTO] {photo_path}\n{caption}")
        return True
    if not telegram_configured() or not photo_path.exists():
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    for attempt in range(1, 4):
        try:
            with photo_path.open("rb") as photo:
                response = requests.post(
                    url,
                    data={"chat_id": TARGET_CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                    files={"photo": photo},
                    timeout=TELEGRAM_TIMEOUT_SECONDS,
                )
            if response.status_code == 200:
                return True
            logging.error("Telegram editorial photo response=%s body=%s", response.status_code, response.text)
        except (OSError, requests.RequestException) as exc:
            logging.error("Telegram editorial photo attempt=%s failed: %s", attempt, exc)
        if attempt < 3:
            time.sleep(attempt * 2)
    return False


def format_history_caption(event: HistoryEvent) -> str:
    lines = [
        "<b>День в истории</b>",
        f"<b>{escape(event.date_label)}</b>",
        escape(event.description),
    ]
    if event.source_url:
        label = escape(event.source_name or "Источник")
        lines.append(f'<a href="{escape(event.source_url, quote=True)}">{label}</a>')
    return append_hashtags("\n\n".join(lines), HISTORY_HASHTAGS)


def format_cover_caption(cover: PaperCover) -> str:
    safe_link = escape(cover.page_url, quote=True)
    safe_source = escape(cover.source_name)
    return append_hashtags(
        f"<b>Обложка дня</b>\nСвежая первая полоса {safe_source}.\n\n<a href=\"{safe_link}\">Открыть архив</a>",
        EDITORIAL_COVER_HASHTAGS,
    )


def send_history_post(
    force: bool = False,
    now: datetime | None = None,
    post_photo: Callable[[str, Path], bool] = post_telegram_photo,
) -> bool:
    current = (now or datetime.now(TZ)).astimezone(TZ)
    metrics: dict[str, Any] = {"dry_run": DRY_RUN, "date": current.date().isoformat()}
    if not HISTORY_ENABLED and not force:
        record_status("history", "disabled", "HISTORY_ENABLED=false", metrics)
        return False
    if HISTORY_RESPECT_MATCHDAY_BLOCK and not force:
        reason = digest_block_reason()
        if reason:
            record_status("history", "skipped", reason, metrics)
            return False

    events = history_events_for_day(load_history_events(), current)
    metrics["events_today"] = len(events)
    if not events:
        record_status("history", "empty", "no verified event for today", metrics)
        return False
    event = events[0]
    key = _history_key(event, current)
    published = _load_keys(HISTORY_POSTS_FILE)
    if key in published and not force:
        record_status("history", "skipped", "history post already published", metrics)
        return False

    caption = format_history_caption(event)
    if not event.image_url:
        record_status("history", "empty", "history event has no vetted archival image", metrics)
        return False
    photo_path = cache_editorial_image(event.image_url)
    if not photo_path:
        record_status("history", "empty", "history event has no vetted archival image", metrics)
        return False
    delivered = post_photo(caption, photo_path)
    if not delivered:
        record_error("history", "Telegram send failed", metrics)
        return False

    published.add(key)
    _save_keys(HISTORY_POSTS_FILE, published)
    record_story(
        kind="history",
        title=event.title,
        source=event.source_name,
        link=event.source_url,
        fingerprint=f"history:{event.id}",
        category="history",
        metadata={"event_date": event.date_label},
    )
    metrics["event"] = event.id
    record_status("history", "ok", "history post published", metrics)
    return True


def send_editorial_cover(
    force: bool = False,
    now: datetime | None = None,
    cover_fetcher: Callable[[], PaperCover | None] = fetch_latest_as_cover,
    post_photo: Callable[[str, Path], bool] = post_telegram_photo,
) -> bool:
    current = (now or datetime.now(TZ)).astimezone(TZ)
    metrics: dict[str, Any] = {"dry_run": DRY_RUN, "date": current.date().isoformat()}
    if not EDITORIAL_COVER_ENABLED and not force:
        record_status("editorial_cover", "disabled", "EDITORIAL_COVER_ENABLED=false", metrics)
        return False
    if EDITORIAL_COVER_RESPECT_MATCHDAY_BLOCK and not force:
        reason = digest_block_reason()
        if reason:
            record_status("editorial_cover", "skipped", reason, metrics)
            return False

    key = _cover_key(current)
    published = _load_keys(COVER_HISTORY_FILE)
    if key in published and not force:
        record_status("editorial_cover", "skipped", "daily cover already published", metrics)
        return False

    cover = cover_fetcher()
    if not cover:
        record_status("editorial_cover", "empty", "front page source is unavailable", metrics)
        return False
    photo_path = cache_editorial_image(cover.image_url)
    if not photo_path:
        record_status("editorial_cover", "empty", "front page image is unavailable", metrics)
        return False
    caption = format_cover_caption(cover)
    delivered = post_photo(caption, photo_path)
    if not delivered:
        record_error("editorial_cover", "Telegram send failed", metrics)
        return False

    published.add(key)
    _save_keys(COVER_HISTORY_FILE, published)
    record_story(
        kind="cover",
        title=f"Обложка дня: {cover.source_name}",
        source=cover.source_name,
        link=cover.page_url,
        fingerprint=f"cover:{cover.image_url}",
        category="cover",
        metadata={"image_url": cover.image_url},
    )
    metrics["source"] = cover.source_name
    record_status("editorial_cover", "ok", "editorial cover published", metrics)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot visual editorial posts")
    parser.add_argument("kind", choices=("cover", "history", "all"))
    parser.add_argument("--force", action="store_true", help="ignore schedule guards and prior publication")
    args = parser.parse_args()
    if args.kind == "cover":
        send_editorial_cover(force=args.force)
    elif args.kind == "history":
        send_history_post(force=args.force)
    else:
        send_history_post(force=args.force)
        send_editorial_cover(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
