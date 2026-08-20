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
from llm_editor import review_digest_items
from match_calendar import digest_block_reason
from news_fingerprint import semantic_news_key
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
    if weekly_story_is_official(story):
        score += 18
    return score, str(story.get("last_archived_at") or "")


def weekly_source_title(story: dict) -> str:
    metadata = story.get("metadata") if isinstance(story.get("metadata"), dict) else {}
    return str(metadata.get("raw_title") or story.get("title") or "").strip()


def weekly_story_identity(story: dict) -> str:
    return str(story.get("id") or story.get("link") or weekly_story_key(story))


def _letter_counts(value: str) -> tuple[int, int]:
    return len(re.findall(r"[\u0410-\u042f\u0430-\u044f\u0401\u0451]", value)), len(re.findall(r"[A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff]", value))


def weekly_story_title(story: dict) -> str:
    archived_title = clean_text(str(story.get("title") or ""))
    raw_title = clean_text(weekly_source_title(story))

    # The archive stores the editor's Russian copy from the original digest.
    # Reusing it is safer than translating the same foreign headline again.
    archived_cyrillic, archived_latin = _letter_counts(archived_title)
    if archived_title and archived_cyrillic and archived_cyrillic >= archived_latin:
        return archived_title

    title = raw_title or archived_title
    if not title:
        return ""

    cyrillic_count, latin_count = _letter_counts(title)
    if latin_count > cyrillic_count:
        translated = clean_text(translate_text(title))
        translated_cyrillic, translated_latin = _letter_counts(translated)
        if translated_latin > translated_cyrillic:
            if archived_title and archived_cyrillic >= archived_latin:
                return archived_title
        return translated
    return title


def weekly_story_key(story: dict) -> str:
    combined = " ".join(
        (
            weekly_source_title(story),
            str(story.get("title") or ""),
            str(story.get("link") or ""),
        )
    ).casefold()
    # A weekly recap needs broader grouping than a live feed: a first injury
    # report and its official confirmation are still one weekly story.
    is_asencio = "asencio" in combined or "\u0430\u0441\u0435\u043d\u0441\u0438\u043e" in combined
    injury_markers = ("injur", "lesion", "lesiona", "seman", "pretemporada", "\u0442\u0440\u0430\u0432\u043c", "\u0432\u044b\u0431\u044b\u043b", "\u0441\u043b\u043e\u043c")
    if is_asencio and any(marker in combined for marker in injury_markers):
        return "injury:raul-asencio"
    is_carlos_espi = (
        ("carlos" in combined and "espi" in combined)
        or ("\u043a\u0430\u0440\u043b\u043e\u0441" in combined and "\u044d\u0441\u043f\u0438" in combined)
    )
    if is_carlos_espi:
        return "transfer:carlos-espi-real-madrid"
    if "schalke" in combined and ("friendly" in combined or "amistoso" in combined):
        return "schedule:preseason-schalke-04-friendly"

    for title in (weekly_source_title(story), str(story.get("title") or "")):
        key = semantic_news_key(title)
        if key.startswith("injury:raul-asencio"):
            return "injury:raul-asencio"
        if not key.startswith("generic:"):
            return key

    key = semantic_news_key(combined)
    return str(story.get("link") or key) if key.startswith("generic:") else key


def weekly_story_is_official(story: dict) -> bool:
    text = " ".join((weekly_source_title(story), str(story.get("title") or ""))).casefold()
    return any(marker in text for marker in ("official", "oficial", "confirmed", "confirmado", "\u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u043e"))


def weekly_story_is_low_signal(story: dict) -> bool:
    text = " ".join((weekly_source_title(story), str(story.get("title") or ""))).casefold()
    # The live feed may cover a developing rumour. A once-a-week recap should
    # only preserve facts that held up, not analysis pieces or negotiations.
    markers = (
        " theory",
        "\u0442\u0435\u043e\u0440\u0438\u044f",
        "rumou",
        "speculat",
        "negoci",
        "\u043f\u0435\u0440\u0435\u0433\u043e\u0432\u043e\u0440",
        "cl\u00e1usula",
        "clause",
        "psycholog",
        "psic\u00f3log",
        "\u043f\u0441\u0438\u0445\u043e\u043b\u043e\u0433",
    )
    if any(marker in text for marker in markers) and not weekly_story_is_official(story):
        return True

    kinds = set(story.get("kinds") or [])
    is_unconfirmed_transfer = weekly_story_key(story).startswith("transfer:") and "breaking" not in kinds
    if is_unconfirmed_transfer and not weekly_story_is_official(story):
        return True

    is_uefa_or_fifa = "uefa" in text or "fifa" in text
    mentions_real_madrid = "real madrid" in text or "\u0440\u0435\u0430\u043b" in text
    return is_uefa_or_fifa and not mentions_real_madrid


def select_weekly_stories(stories: list[dict], limit: int) -> list[dict]:
    selected = []
    category_counts: dict[str, int] = {}
    selected_keys: set[str] = set()
    for story in sorted(stories, key=_story_score, reverse=True):
        title = weekly_source_title(story)
        if not title or not passes_filters(
            title,
            source=str(story.get("source") or ""),
            link=str(story.get("link") or ""),
        ):
            continue
        if weekly_story_is_low_signal(story):
            continue
        category = str(story.get("category") or "general")
        if category_counts.get(category, 0) >= 3:
            continue
        key = weekly_story_key(story)
        if key in selected_keys:
            continue
        selected.append(story)
        selected_keys.add(key)
        category_counts[category] = category_counts.get(category, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def review_weekly_stories(stories: list[dict]) -> tuple[list[dict], dict[str, str], dict[str, object]]:
    review_items = [
        {
            "title": weekly_source_title(story),
            "summary": weekly_story_title(story),
            "source": str(story.get("source") or ""),
            "score": _story_score(story)[0],
            "reason": str(story.get("category") or "weekly archive"),
        }
        for story in stories
    ]
    result = review_digest_items(review_items, label="weekly")
    metrics: dict[str, object] = {
        "llm_editor_used": result.used,
        "llm_editor_reason": result.reason,
        **result.metrics,
    }
    if not result.used:
        return stories, {}, metrics

    approved: list[dict] = []
    title_overrides: dict[str, str] = {}
    for index, story in enumerate(stories, start=1):
        decision = result.decisions.get(index, {})
        if decision and not decision.get("keep", True):
            continue
        approved.append(story)
        headline = clean_text(str(decision.get("headline_ru") or ""))
        if headline:
            title_overrides[weekly_story_identity(story)] = headline

    # A temporary LLM problem must not make the recap disappear altogether.
    if not approved:
        metrics["llm_editor_fallback"] = "all stories rejected"
        return stories, {}, metrics
    metrics["llm_editor_kept"] = len(approved)
    return approved, title_overrides, metrics


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
    metrics["stories_before_editor"] = len(stories)
    if len(stories) < WEEKLY_RECAP_MIN_ITEMS:
        record_status("weekly_recap", "empty", "not enough archived stories", metrics)
        return False
    stories, title_overrides, editor_metrics = review_weekly_stories(stories)
    metrics.update(editor_metrics)
    metrics["stories"] = len(stories)
    if len(stories) < WEEKLY_RECAP_MIN_ITEMS:
        record_status("weekly_recap", "empty", "not enough approved archived stories", metrics)
        return False
    # A block made only of rumours reads as filler, not as a useful market summary.
    transfers = recent_updates(days=WEEKLY_RECAP_DAYS, limit=4, include_rumours=False)
    message = format_weekly_recap(
        stories,
        transfers,
        title_formatter=lambda story: title_overrides.get(weekly_story_identity(story), weekly_story_title(story)),
    )
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
