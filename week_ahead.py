import argparse
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from zoneinfo import ZoneInfo

from match_calendar import match_rows, parse_kickoff, read_match_payload
from post_utils import append_hashtags
from runtime_config import (
    DRY_RUN,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_TIMEOUT_SECONDS,
    TARGET_CHAT_ID,
    WEEK_AHEAD_DAYS,
    WEEK_AHEAD_ENABLED,
    WEEK_AHEAD_HASHTAGS,
    WEEK_AHEAD_TIMEZONE,
    get_log_file,
    get_state_file,
    telegram_configured,
)
from status_manager import record_error, record_status


LOG_FILE = get_log_file("week_ahead.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
HISTORY_FILE = get_state_file("week_ahead_history.json")
TZ = ZoneInfo(WEEK_AHEAD_TIMEZONE)
WEEKDAY_NAMES = ("пн", "вт", "ср", "чт", "пт", "сб", "вс")
COMPETITION_NAMES = {
    "la liga": "Ла Лига",
    "uefa champions league": "Лига чемпионов",
    "champions league": "Лига чемпионов",
}


@dataclass(frozen=True)
class WeekFixture:
    id: str
    competition: str
    home: str
    away: str
    day: date
    kickoff: datetime | None = None
    round: str = ""
    date_hint_label: str = ""

    @property
    def title(self) -> str:
        return f"{display_team(self.home)} - {display_team(self.away)}"


def _week_key(now: datetime | None = None) -> str:
    current = now or datetime.now(TZ)
    year, week, _ = current.isocalendar()
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


def parse_date_hint(value: object) -> tuple[date, str] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw), ""
    except ValueError:
        pass

    match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})/(\d{2})", raw)
    if not match:
        return None
    year, month, first_day, last_day = (int(part) for part in match.groups())
    try:
        return date(year, month, first_day), f"{first_day}/{last_day}.{month:02d}"
    except ValueError:
        return None


def fixtures_from_rows(rows: list[object]) -> list[WeekFixture]:
    fixtures = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        kickoff = None
        if raw.get("kickoff"):
            try:
                kickoff = parse_kickoff(str(raw["kickoff"]))
            except (TypeError, ValueError):
                logging.warning("Некорректное время матча в календаре: %s", raw.get("id"))
        date_hint = parse_date_hint(raw.get("date_hint") or raw.get("date"))
        fixture_day = kickoff.date() if kickoff else (date_hint[0] if date_hint else None)
        if not fixture_day:
            continue
        fixtures.append(
            WeekFixture(
                id=str(raw.get("id") or f"{fixture_day}:{raw.get('home')}:{raw.get('away')}").strip(),
                competition=str(raw.get("competition") or "Матч").strip(),
                home=str(raw.get("home") or "Real Madrid").strip(),
                away=str(raw.get("away") or "Соперник").strip(),
                day=fixture_day,
                kickoff=kickoff,
                round=str(raw.get("round") or "").strip(),
                date_hint_label=date_hint[1] if date_hint and not kickoff else "",
            )
        )
    return sorted(fixtures, key=lambda fixture: (fixture.day, fixture.kickoff or datetime.max.replace(tzinfo=TZ), fixture.id))


def select_week_fixtures(
    fixtures: list[WeekFixture],
    now: datetime | None = None,
    days: int = WEEK_AHEAD_DAYS,
) -> list[WeekFixture]:
    current = (now or datetime.now(TZ)).astimezone(TZ).date()
    until = current + timedelta(days=max(days, 1))
    return [fixture for fixture in fixtures if current <= fixture.day <= until]


def display_team(name: str) -> str:
    value = (name or "").strip()
    if value.casefold() == "real madrid":
        return "«Реал»"
    return f"«{value}»" if value else "«Соперник»"


def display_competition(name: str) -> str:
    value = (name or "").strip()
    return COMPETITION_NAMES.get(value.casefold(), value or "Матч")


def fixture_date_label(fixture: WeekFixture) -> str:
    label = fixture.date_hint_label or f"{WEEKDAY_NAMES[fixture.day.weekday()]}, {fixture.day:%d.%m}"
    if fixture.kickoff:
        return f"{label} · {fixture.kickoff.astimezone(TZ):%H:%M}"
    return f"{label} · время уточняется"


def format_week_ahead(fixtures: list[WeekFixture]) -> str:
    lines = [
        "<b>Белый календарь недели</b>",
        "Ближайшие матчи «Реала» без лишнего шума.",
    ]
    for fixture in fixtures:
        details = display_competition(fixture.competition)
        if fixture.round:
            details = f"{details}, {fixture.round}"
        lines.extend(
            (
                "",
                f"<b>{escape(fixture_date_label(fixture))}</b>",
                escape(fixture.title),
                escape(details),
            )
        )
    return append_hashtags("\n".join(lines), WEEK_AHEAD_HASHTAGS)


def post_telegram_message(message: str) -> bool:
    if DRY_RUN:
        print("[DRY RUN WEEK AHEAD]\n" + message)
        return True
    if not telegram_configured():
        return False

    import requests

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
            logging.error("Telegram week-ahead response=%s body=%s", response.status_code, response.text)
        except requests.RequestException as exc:
            logging.error("Telegram week-ahead attempt=%s failed: %s", attempt, exc)
        if attempt < 3:
            time.sleep(attempt * 2)
    return False


def send_week_ahead(force: bool = False) -> bool:
    now = datetime.now(TZ)
    metrics = {"dry_run": DRY_RUN, "week": _week_key(now)}
    if not WEEK_AHEAD_ENABLED and not force:
        record_status("week_ahead", "disabled", "WEEK_AHEAD_ENABLED=false", metrics)
        return False

    history = _load_history()
    key = _week_key(now)
    if key in history and not force:
        record_status("week_ahead", "skipped", "week-ahead calendar already published", metrics)
        return False

    payload, error = read_match_payload()
    if error:
        record_error("week_ahead", error, metrics)
        return False
    fixtures = select_week_fixtures(fixtures_from_rows(match_rows(payload)), now=now)
    metrics["fixtures"] = len(fixtures)
    if not fixtures:
        record_status("week_ahead", "empty", "no fixtures in the upcoming window", metrics)
        return False

    if not post_telegram_message(format_week_ahead(fixtures)):
        record_error("week_ahead", "Telegram send failed", metrics)
        return False
    history.add(key)
    _save_history(history)
    record_status("week_ahead", "ok", "week-ahead calendar published", metrics)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot week-ahead calendar")
    parser.add_argument("--force", action="store_true", help="publish even if this week's calendar was already sent")
    args = parser.parse_args()
    send_week_ahead(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
