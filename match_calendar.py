import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
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
    api_football_fixture_id: str = ""

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


def fixture_id_from_dict(raw: dict) -> str:
    return str(
        raw.get("api_football_fixture_id")
        or raw.get("apiFootballFixtureId")
        or raw.get("fixture_id")
        or ""
    ).strip()


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
        api_football_fixture_id=fixture_id_from_dict(raw),
    )


def read_match_payload(path: Path = MATCH_SCHEDULE_FILE) -> tuple[object | None, str | None]:
    if not MATCHDAY_ENABLED or not path.exists():
        return None, None

    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Не удалось прочитать календарь матчей {path}: {exc}"


def calendar_read_error(path: Path = MATCH_SCHEDULE_FILE) -> str | None:
    _, error = read_match_payload(path)
    return error


def match_rows(payload: object | None) -> list[Any]:
    if isinstance(payload, dict):
        rows = payload.get("matches", [])
    else:
        rows = payload or []
    return rows if isinstance(rows, list) else []


def match_calendar_status(path: Path = MATCH_SCHEDULE_FILE) -> tuple[str, str, dict[str, Any]]:
    if not MATCHDAY_ENABLED:
        return "disabled", "matchday disabled", {"path": str(path)}
    if not path.exists():
        return "missing", f"календарь матчей не найден: {path}", {"path": str(path)}

    payload, error = read_match_payload(path)
    if error:
        return "error", error, {"path": str(path)}

    rows = match_rows(payload)
    metadata = payload if isinstance(payload, dict) else {}
    declared_status = str(metadata.get("status") or "").strip().lower()
    expected_publication = str(metadata.get("expected_publication") or "").strip()
    checked_at = str(metadata.get("checked_at") or "").strip()

    metrics: dict[str, Any] = {
        "path": str(path),
        "matches": len(rows),
        "status": declared_status or ("ready" if rows else "empty"),
    }
    if expected_publication:
        metrics["expected_publication"] = expected_publication
    if checked_at:
        metrics["checked_at"] = checked_at

    if declared_status in {"pending", "awaiting", "not_published"} and not rows:
        when = f", ожидается {expected_publication}" if expected_publication else ""
        return "pending", f"официальный календарь ещё не опубликован{when}", metrics
    if rows:
        return "ready", f"загружено матчей: {len(rows)}", metrics
    return "empty", "календарь валиден, но матчей пока нет", metrics


def load_matches(path: Path = MATCH_SCHEDULE_FILE) -> list[Match]:
    payload, error = read_match_payload(path)
    if error:
        logging.error(error)
        return []
    if payload is None:
        return []

    rows = match_rows(payload)
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
