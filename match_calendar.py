import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from runtime_config import (
    DIGEST_TIMEZONE,
    MATCH_SCHEDULE_FILE,
    MATCHDAY_BLOCK_AFTER_HOURS,
    MATCHDAY_BLOCK_ALL_DAY,
    MATCHDAY_BLOCK_BEFORE_HOURS,
    MATCHDAY_ENABLED,
)

TZ = ZoneInfo(DIGEST_TIMEZONE)


@dataclass(frozen=True)
class Match:
    id: str
    competition: str
    home: str
    away: str
    kickoff: datetime
    venue: str = ""
    round: str = ""
    broadcast: str = ""

    @property
    def title(self) -> str:
        return f"{self.home} - {self.away}"

    @property
    def is_home(self) -> bool:
        return "real madrid" in self.home.lower() or "реал" in self.home.lower()


def local_now() -> datetime:
    return datetime.now(TZ)


def parse_kickoff(value: str) -> datetime:
    raw = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def make_match_id(match: dict) -> str:
    base = "-".join(
        str(part)
        for part in (
            match.get("competition", "match"),
            match.get("kickoff", "unknown"),
            match.get("home", "home"),
            match.get("away", "away"),
        )
    )
    return re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()


def match_from_dict(raw: dict) -> Match:
    kickoff = parse_kickoff(str(raw["kickoff"]))
    return Match(
        id=str(raw.get("id") or make_match_id(raw)),
        competition=str(raw.get("competition") or "Матч"),
        home=str(raw.get("home") or "Real Madrid"),
        away=str(raw.get("away") or "Соперник"),
        kickoff=kickoff,
        venue=str(raw.get("venue") or ""),
        round=str(raw.get("round") or ""),
        broadcast=str(raw.get("broadcast") or ""),
    )


def load_matches(path: Path = MATCH_SCHEDULE_FILE) -> list[Match]:
    if not MATCHDAY_ENABLED:
        return []
    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.error("Не удалось прочитать календарь матчей %s: %s", path, exc)
        return []

    rows = payload.get("matches", []) if isinstance(payload, dict) else payload
    matches: list[Match] = []
    for raw in rows:
        if not isinstance(raw, dict) or not raw.get("kickoff"):
            continue
        try:
            matches.append(match_from_dict(raw))
        except (KeyError, ValueError, TypeError) as exc:
            logging.warning("Матч пропущен из-за ошибки в календаре: %s", exc)

    return sorted(matches, key=lambda item: item.kickoff)


def find_match(match_id: str) -> Match | None:
    for match in load_matches():
        if match.id == match_id:
            return match
    return None


def upcoming_matches(now: datetime | None = None, days: int = 14) -> list[Match]:
    current = (now or local_now()).astimezone(TZ)
    until = current + timedelta(days=days)
    return [match for match in load_matches() if current <= match.kickoff <= until]


def matchday_blocking_match(now: datetime | None = None) -> tuple[Match, str] | None:
    if not MATCHDAY_ENABLED:
        return None

    current = (now or local_now()).astimezone(TZ)
    for match in load_matches():
        kickoff = match.kickoff.astimezone(TZ)

        if MATCHDAY_BLOCK_ALL_DAY and kickoff.date() == current.date():
            return match, "matchday"

        start = kickoff - timedelta(hours=MATCHDAY_BLOCK_BEFORE_HOURS)
        end = kickoff + timedelta(hours=MATCHDAY_BLOCK_AFTER_HOURS)
        if start <= current <= end:
            return match, "window"

    return None


def digest_block_reason(now: datetime | None = None) -> str | None:
    blocked = matchday_blocking_match(now)
    if not blocked:
        return None

    match, mode = blocked
    kickoff = match.kickoff.astimezone(TZ).strftime("%d.%m %H:%M")
    if mode == "matchday":
        return f"матч-день: {match.title}, {match.competition}, начало {kickoff}"
    return f"матчевое окно: {match.title}, {match.competition}, начало {kickoff}"
