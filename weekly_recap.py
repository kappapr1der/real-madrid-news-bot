import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

import requests

from editorial_archive import recent_stories
from filters import passes_filters
from match_calendar import digest_block_reason
from post_utils import append_hashtags
from runtime_config import (
    DRY_RUN,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    WEEKLY_RECAP_DAYS,
    WEEKLY_RECAP_ENABLED,
    WEEKLY_RECAP_HASHTAGS,
    WEEKLY_RECAP_LIMIT,
    WEEKLY_RECAP_MIN_ITEMS,
    WEEKLY_RECAP_RESPECT_MATCHDAY_BLOCK,
    WEEKLY_RECAP_TIMEZONE,
    get_log_file,
    get_state_file,
    telegram_configured,
)
from status_manager import record_error, record_status
from transfer_tracker import recent_updates
from text_cleaner import clean_text
from translator import translate_text


LOG_FILE = get_log_file("weekly_recap.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
HISTORY_FILE = get_state_file("weekly_recap_history.json")
TZ = ZoneInfo(WEEKLY_RECAP_TIMEZONE)


def _week_key(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week:02d}"


def _load_history() -> set[str]:
    if not HISTORY_FILE.exists():
        return set()
    try:
        rows = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(row) for row in rows if row}


def _save_history(keys: set[str]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(sorted(keys)[-104:], ensure_ascii=False, indent=2), encoding="utf-8")


def _story_score(story: dict) -> tuple[int, str]:
    kinds = set(story.get("kinds") or [])
    category = str(story.get("category") or "")
    score = 0
    if "breaking" in kinds:
        score += 30
    if "digest" in kinds:
        score += 15
    if category in {"official", "injury", "lineup", "matchday"}:
        score += 12
    if category == "transfer":
        score += 8
    return score, str(story.get("last_archived_at") or "")


def weekly_source_title(story: dict) -> str:
    metadata = story.get("metadata") if isinstance(story.get("metadata"), dict) else {}
    return str(metadata.get("raw_title") or story.get("title") or "").strip()


def weekly_story_title(story: dict) -> str:
    title = clean_text(weekly_source_title(story))
    if not title:
        return ""

    cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", title))
    latin_count = len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", title))
    if latin_count > cyrillic_count:
        return clean_text(translate_text(title))
    return title


def select_weekly_stories(stories: list[dict], limit: int) -> list[dict]:
    selected = []
    category_counts: dict[str, int] = {}
    for story in sorted(stories, key=_story_score, reverse=True):
        title = weekly_source_title(story)
        if not title or not passes_filters(title, source=str(story.get("source") or "")):
            continue
        category = str(story.get("category") or "general")
        if category_counts.get(category, 0) >= 3:
            continue
        selected.append(story)
        category_counts[category] = category_counts.get(category, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def format_weekly_recap(stories: list[dict], transfers: list[dict], title_formatter=weekly_story_title) -> str:
    lines = ["<b>Белая неделя: главное</b>", "Собрали сюжеты, которые действительно двигали ленту последние семь дней."]
    for index, story in enumerate(stories, start=1):
        title = escape(title_formatter(story))
        link = str(story.get("link") or "").strip()
        source = escape(str(story.get("source") or ""))
        suffix = f"\n<a href=\"{escape(link, quote=True)}\">Читать</a> · {source}" if link else (f"\n{source}" if source else "")
        lines.append(f"\n{index}. {title}{suffix}")

    if transfers:
        lines.append("\n<b>Рынок за неделю</b>")
        for row in transfers[:4]:
            subject = escape(str(row.get("subject") or ""))
            status = escape(str(row.get("status") or ""))
            lines.append(f"• {subject}: {status}")
    return append_hashtags("\n".join(lines), WEEKLY_RECAP_HASHTAGS)


def post_telegram_message(message: str) -> bool:
    if DRY_RUN:
        print("[DRY RUN WEEKLY]\n" + message)
        return True
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
            logging.error("Telegram weekly recap response=%s body=%s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Telegram weekly recap attempt=%s failed: %s", attempt, exc)
        if attempt < 3:
            time.sleep(attempt * 2)
    return False


def send_weekly_recap(force: bool = False) -> bool:
    metrics = {"dry_run": DRY_RUN, "week": _week_key()}
    if not WEEKLY_RECAP_ENABLED and not force:
        record_status("weekly_recap", "disabled", "WEEKLY_RECAP_ENABLED=false", metrics)
        return False
    if WEEKLY_RECAP_RESPECT_MATCHDAY_BLOCK and not force:
        reason = digest_block_reason()
        if reason:
            record_status("weekly_recap", "skipped", reason, metrics)
            return False
    history = _load_history()
    key = _week_key()
    if key in history and not force:
        record_status("weekly_recap", "skipped", "weekly recap already published", metrics)
        return False

    stories = select_weekly_stories(recent_stories(days=WEEKLY_RECAP_DAYS), WEEKLY_RECAP_LIMIT)
    metrics["stories"] = len(stories)
    if len(stories) < WEEKLY_RECAP_MIN_ITEMS:
        record_status("weekly_recap", "empty", "not enough archived stories", metrics)
        return False
    # A block made only of rumours reads as filler, not as a useful market summary.
    transfers = recent_updates(days=WEEKLY_RECAP_DAYS, limit=4, include_rumours=False)
    message = format_weekly_recap(stories, transfers)
    if not post_telegram_message(message):
        record_error("weekly_recap", "Telegram send failed", metrics)
        return False
    history.add(key)
    _save_history(history)
    metrics["transfer_updates"] = len(transfers)
    record_status("weekly_recap", "ok", "weekly recap published", metrics)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot weekly recap")
    parser.add_argument("--force", action="store_true", help="ignore schedule/day and prior weekly publication")
    args = parser.parse_args()
    send_weekly_recap(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
