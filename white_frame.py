#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Occasional real-photo posts from Real Madrid's official X feeds."""

from __future__ import annotations

import argparse
import calendar
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from editorial_archive import record_story
from editorial_posts import cache_editorial_image, post_telegram_photo
from feed_utils import entry_media_url, is_repost_entry, parse_feed_url
from match_calendar import digest_block_reason
from post_utils import append_hashtags
from publication_registry import remember_editorial_link
from runtime_config import (
    WHITE_FRAME_ENABLED,
    WHITE_FRAME_ENTRY_SCAN_LIMIT,
    WHITE_FRAME_HASHTAGS,
    WHITE_FRAME_MAX_AGE_HOURS,
    WHITE_FRAME_RESPECT_MATCHDAY_BLOCK,
    WHITE_FRAME_TIMEZONE,
    get_log_file,
    get_state_file,
)
from sources_international import build_x_sources
from status_manager import record_error, record_status
from text_cleaner import clean_text
from translator import translate_text


LOG_FILE = get_log_file("white_frame.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
HISTORY_FILE = get_state_file("white_frame_history.json")
TZ = ZoneInfo(WHITE_FRAME_TIMEZONE)

PHOTO_TERMS = (
    "training",
    "entren",
    "valdebebas",
    "bernabeu",
    "pre-season",
    "preseason",
    "season",
    "madridismo",
    "matchday",
    "team",
    "squad",
    "players",
    "semana",
    "week",
    "vestuario",
    "dressing room",
)
PROMO_TERMS = ("shop", "buy now", "tickets", "merchandise", "jersey")


@dataclass(frozen=True)
class WhiteFrame:
    title: str
    link: str
    source: str
    image_url: str
    published_at: datetime | None = None


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
    HISTORY_FILE.write_text(json.dumps(sorted(values)[-120:], ensure_ascii=False, indent=2), encoding="utf-8")


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
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def official_x_sources() -> list[dict]:
    return [source for source in build_x_sources() if str(source.get("kind") or "") == "x_official"]


def suitable_frame_title(title: str) -> bool:
    normalized = (title or "").casefold()
    return bool(normalized and any(term in normalized for term in PHOTO_TERMS) and not any(term in normalized for term in PROMO_TERMS))


def find_white_frame(now: datetime | None = None, sources: list[dict] | None = None) -> WhiteFrame | None:
    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(hours=max(WHITE_FRAME_MAX_AGE_HOURS, 1))
    history = _load_history()
    candidates: list[WhiteFrame] = []
    for source in sources if sources is not None else official_x_sources():
        feed = parse_feed_url(source)
        if not feed:
            continue
        for entry in list(feed.entries or [])[:WHITE_FRAME_ENTRY_SCAN_LIMIT]:
            if is_repost_entry(entry):
                continue
            title = str(entry.get("title") or "").strip()
            link = str(entry.get("link") or "").strip()
            image_url = entry_media_url(entry)
            published_at = entry_published_at(entry)
            if not link or link in history or not image_url or not suitable_frame_title(title):
                continue
            if published_at and published_at < cutoff:
                continue
            candidates.append(
                WhiteFrame(
                    title=title,
                    link=link,
                    source=str(source.get("label") or "Real Madrid"),
                    image_url=image_url,
                    published_at=published_at,
                )
            )
    return max(candidates, key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc), default=None)


def short_caption(title: str) -> str:
    value = clean_text(translate_text(title))
    if re.fullmatch(r"(?:semana|week)\s*\d+\D*", value.casefold()):
        return "Клубная неделя в кадре."
    if len(value) <= 240:
        return value
    return f"{value[:237].rsplit(' ', 1)[0]}..."


def original_x_post_url(url: str) -> str:
    match = re.search(r"/([^/]+)/status/(\d+)", url or "")
    if not match:
        return url
    return f"https://x.com/{match.group(1)}/status/{match.group(2)}"


def format_white_frame(frame: WhiteFrame) -> str:
    post_url = original_x_post_url(frame.link)
    return append_hashtags(
        "\n".join(
            (
                "<b>Белый кадр</b>",
                escape(short_caption(frame.title)),
                f'<a href="{escape(post_url, quote=True)}">Открыть публикацию</a> · {escape(frame.source)}',
            )
        ),
        WHITE_FRAME_HASHTAGS,
    )


def send_white_frame(
    force: bool = False,
    now: datetime | None = None,
    finder: Callable[..., WhiteFrame | None] = find_white_frame,
    post_photo: Callable[[str, Path], bool] = post_telegram_photo,
) -> bool:
    current = (now or datetime.now(TZ)).astimezone(TZ)
    metrics = {"date": current.date().isoformat()}
    if not WHITE_FRAME_ENABLED and not force:
        record_status("white_frame", "disabled", "WHITE_FRAME_ENABLED=false", metrics)
        return False
    if WHITE_FRAME_RESPECT_MATCHDAY_BLOCK and not force:
        reason = digest_block_reason(current)
        if reason:
            record_status("white_frame", "skipped", reason, metrics)
            return False
    frame = finder(now=current.astimezone(timezone.utc))
    if not frame:
        record_status("white_frame", "empty", "no fresh official photo worth posting", metrics)
        return False
    photo_path = cache_editorial_image(frame.image_url)
    if not photo_path:
        record_status("white_frame", "empty", "official photo is unavailable", metrics)
        return False
    if not post_photo(format_white_frame(frame), photo_path):
        record_error("white_frame", "Telegram send failed", metrics)
        return False
    history = _load_history()
    history.add(frame.link)
    _save_history(history)
    remember_editorial_link(frame.link)
    record_story(
        kind="white_frame",
        title=short_caption(frame.title),
        source=frame.source,
        link=frame.link,
        fingerprint=f"white-frame:{frame.link}",
        category="editorial",
        metadata={"image_url": frame.image_url},
    )
    metrics["source"] = frame.source
    record_status("white_frame", "ok", "official photo published", metrics)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot White Frame")
    parser.add_argument("--force", action="store_true", help="ignore schedule guards")
    args = parser.parse_args()
    send_white_frame(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
