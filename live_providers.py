import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import requests

from match_calendar import Match, local_now
from runtime_config import (
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_KEY,
    API_FOOTBALL_LEAGUE_IDS,
    API_FOOTBALL_REQUEST_TIMEOUT_SECONDS,
    API_FOOTBALL_TEAM_ID,
    MATCHDAY_FULLTIME_MINUTES,
    MATCHDAY_LIVE_AFTER_MINUTES,
    MATCHDAY_LIVE_BEFORE_MINUTES,
    MATCHDAY_LIVE_ENABLED,
    MATCHDAY_LIVE_EVENT_TYPES,
    MATCHDAY_LIVE_PROVIDER,
    MATCHDAY_LINEUP_BEFORE_MINUTES,
    MATCHDAY_LINEUP_ENABLED,
    MATCHDAY_RESULT_ENABLED,
)

CANCELLED_STATUSES = {"NS", "TBD", "PST", "CANC", "ABD", "AWD", "WO"}
FINISHED_STATUSES = {"FT", "AET", "PEN"}
REAL_NAME_RE = re.compile(r"\breal\s+madrid\b|\bреал\s+мадрид\b", re.IGNORECASE)


@dataclass(frozen=True)
class LiveEvent:
    key: str
    match: Match
    minute: str
    kind: str
    score: str
    text: str


@dataclass(frozen=True)
class ConfirmedLineup:
    key: str
    match: Match
    formation: str
    starters: list[str]


@dataclass(frozen=True)
class FinalResult:
    key: str
    match: Match
    score: str
    status: str


class ApiFootballClient:
    def __init__(self) -> None:
        self.base_url = API_FOOTBALL_BASE_URL.rstrip("/")
        self.headers = {"x-apisports-key": API_FOOTBALL_KEY or ""}

    def get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=API_FOOTBALL_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if errors:
            logging.warning("API-FOOTBALL вернул errors=%s для %s", errors, path)
        data = payload.get("response", []) if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []

    def live_fixtures(self) -> list[dict[str, Any]]:
        return self.get("fixtures", {"live": "all", "team": API_FOOTBALL_TEAM_ID})

    def fixture_by_id(self, fixture_id: str) -> dict[str, Any] | None:
        rows = self.get("fixtures", {"id": fixture_id})
        return rows[0] if rows else None

    def fixture_events(self, fixture_id: str) -> list[dict[str, Any]]:
        return self.get("fixtures/events", {"fixture": fixture_id})

    def fixture_lineups(self, fixture_id: str) -> list[dict[str, Any]]:
        return self.get("fixtures/lineups", {"fixture": fixture_id})


def live_provider_status() -> str:
    if not MATCHDAY_LIVE_ENABLED:
        return "disabled"
    if MATCHDAY_LIVE_PROVIDER != "api-football":
        return f"unsupported provider: {MATCHDAY_LIVE_PROVIDER}"
    if not API_FOOTBALL_KEY:
        return "API_FOOTBALL_KEY is missing"
    return "api-football ready"


def provider_ready() -> bool:
    return live_provider_status() == "api-football ready"


def matches_in_live_window(matches: list[Match]) -> list[Match]:
    now = local_now()
    active = []
    for match in matches:
        kickoff = match.kickoff.astimezone(now.tzinfo)
        start = kickoff - timedelta(minutes=MATCHDAY_LIVE_BEFORE_MINUTES)
        end = kickoff + timedelta(minutes=MATCHDAY_FULLTIME_MINUTES + MATCHDAY_LIVE_AFTER_MINUTES)
        if start <= now <= end:
            active.append(match)
    return active


def matches_in_lineup_window(matches: list[Match]) -> list[Match]:
    now = local_now()
    active = []
    for match in matches:
        kickoff = match.kickoff.astimezone(now.tzinfo)
        start = kickoff - timedelta(minutes=MATCHDAY_LINEUP_BEFORE_MINUTES)
        end = kickoff + timedelta(minutes=30)
        if start <= now <= end:
            active.append(match)
    return active


def matches_in_result_window(matches: list[Match]) -> list[Match]:
    now = local_now()
    active = []
    for match in matches:
        kickoff = match.kickoff.astimezone(now.tzinfo)
        start = kickoff + timedelta(minutes=max(MATCHDAY_FULLTIME_MINUTES - 20, 90))
        end = kickoff + timedelta(minutes=MATCHDAY_FULLTIME_MINUTES + MATCHDAY_LIVE_AFTER_MINUTES)
        if start <= now <= end:
            active.append(match)
    return active


def fixture_id(fixture: dict[str, Any]) -> str:
    return str((fixture.get("fixture") or {}).get("id") or "")


def fixture_status(fixture: dict[str, Any]) -> str:
    status = (fixture.get("fixture") or {}).get("status") or {}
    return str(status.get("short") or "")


def fixture_allowed(fixture: dict[str, Any]) -> bool:
    if not API_FOOTBALL_LEAGUE_IDS:
        return True
    try:
        league_id = int((fixture.get("league") or {}).get("id"))
    except (TypeError, ValueError):
        return False
    return league_id in API_FOOTBALL_LEAGUE_IDS


def fixture_active_enough(fixture: dict[str, Any]) -> bool:
    status = fixture_status(fixture)
    return bool(status and status not in CANCELLED_STATUSES)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def fixture_team_names(fixture: dict[str, Any]) -> tuple[str, str]:
    teams = fixture.get("teams") or {}
    home = (teams.get("home") or {}).get("name") or ""
    away = (teams.get("away") or {}).get("name") or ""
    return str(home), str(away)


def match_for_fixture(fixture: dict[str, Any], active_matches: list[Match]) -> Match | None:
    current_fixture_id = fixture_id(fixture)
    for match in active_matches:
        if match.api_football_fixture_id and match.api_football_fixture_id == current_fixture_id:
            return match

    if len(active_matches) == 1:
        return active_matches[0]

    home_name, away_name = fixture_team_names(fixture)
    fixture_names = {normalize_name(home_name), normalize_name(away_name)}
    for match in active_matches:
        match_names = {normalize_name(match.home), normalize_name(match.away)}
        if fixture_names & match_names:
            return match

    return None


def event_allowed(raw_event: dict[str, Any]) -> bool:
    event_type = str(raw_event.get("type") or "").casefold()
    return not MATCHDAY_LIVE_EVENT_TYPES or event_type in MATCHDAY_LIVE_EVENT_TYPES


def event_minute(raw_event: dict[str, Any]) -> str:
    time_info = raw_event.get("time") or {}
    elapsed = time_info.get("elapsed")
    extra = time_info.get("extra")
    if elapsed is None:
        return ""
    return f"{elapsed}+{extra}" if extra else str(elapsed)


def player_name(raw_event: dict[str, Any], field: str) -> str:
    value = (raw_event.get(field) or {}).get("name")
    return str(value or "").strip()


def team_name(raw_event: dict[str, Any]) -> str:
    value = (raw_event.get("team") or {}).get("name")
    return str(value or "").strip()


def team_is_real(raw_event: dict[str, Any]) -> bool:
    team = raw_event.get("team") or {}
    if str(team.get("id") or "") == str(API_FOOTBALL_TEAM_ID):
        return True
    return bool(REAL_NAME_RE.search(str(team.get("name") or "")))


def fixture_score(fixture: dict[str, Any]) -> str:
    goals = fixture.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return ""
    return f"{home}:{away}"


def score_sentence(score: str) -> str:
    return f" Счет {score}." if score else ""


def event_kind(raw_event: dict[str, Any]) -> str:
    event_type = str(raw_event.get("type") or "")
    event_type_lower = event_type.casefold()
    if event_type_lower == "goal":
        return "Гол"
    if event_type_lower == "card":
        return "Карточка"
    if event_type_lower == "subst":
        return "Замена"
    if event_type_lower == "var":
        return "VAR"
    return event_type or "Live"


def render_event_text(match: Match, raw_event: dict[str, Any], score: str) -> str:
    event_type = str(raw_event.get("type") or "").casefold()
    detail = str(raw_event.get("detail") or "")
    detail_lower = detail.casefold()
    player = player_name(raw_event, "player")
    assist = player_name(raw_event, "assist")
    event_team = team_name(raw_event)
    is_real = team_is_real(raw_event)
    score_text = score_sentence(score)

    if event_type == "goal":
        scorer = player or ("Игрок Реала" if is_real else event_team or "Соперник")
        if "own" in detail_lower:
            if is_real:
                return f"Автогол у Мадрида: {scorer}.{score_text} Нужно быстро возвращать контроль."
            return f"Автогол соперника, Мадрид получает подарок.{score_text} Сливочные снова ближе к своему."
        if "penalty" in detail_lower:
            action = "реализует пенальти" if is_real else "забивает с пенальти"
        else:
            action = "забивает за Мадрид" if is_real else "забивает"
        if is_real:
            extra = f" Передача: {assist}." if assist else ""
            return f"{scorer} {action}.{score_text}{extra} Сливочные получают важный импульс."
        return f"{event_team or 'Соперник'} отвечает: {scorer} {action}.{score_text} Мадриду нужно прибавлять."

    if event_type == "card":
        card = detail or "карточка"
        target = player or event_team or "участник эпизода"
        if is_real:
            return f"{card} для Мадрида: {target}.{score_text} Теперь аккуратнее в единоборствах."
        return f"{card} у соперника: {target}.{score_text} Можно давить на этот фланг сильнее."

    if event_type == "subst":
        out_player = player or "игрок"
        in_player = assist or "свежий игрок"
        side = "Мадрид" if is_real else event_team or "соперник"
        return f"Замена у команды {side}: {in_player} вместо {out_player}.{score_text}"

    if event_type == "var":
        subject = player or event_team or match.title
        detail_text = f": {detail}" if detail else ""
        return f"VAR проверяет эпизод с участием {subject}{detail_text}.{score_text} Ждем решения арбитра."

    subject = player or event_team or match.title
    detail_text = f" ({detail})" if detail else ""
    return f"Событие матча: {subject}{detail_text}.{score_text}"


def event_key(fixture: dict[str, Any], raw_event: dict[str, Any]) -> str:
    payload = {
        "fixture": fixture_id(fixture),
        "time": raw_event.get("time"),
        "team": raw_event.get("team"),
        "player": raw_event.get("player"),
        "assist": raw_event.get("assist"),
        "type": raw_event.get("type"),
        "detail": raw_event.get("detail"),
        "comments": raw_event.get("comments"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"api-football:{fixture_id(fixture)}:{digest}"


def normalize_event(match: Match, fixture: dict[str, Any], raw_event: dict[str, Any]) -> LiveEvent | None:
    if not event_allowed(raw_event):
        return None
    score = fixture_score(fixture)
    return LiveEvent(
        key=event_key(fixture, raw_event),
        match=match,
        minute=event_minute(raw_event),
        kind=event_kind(raw_event),
        score=score,
        text=render_event_text(match, raw_event, score),
    )


def fetch_live_events(matches: list[Match]) -> list[LiveEvent]:
    if not provider_ready():
        return []

    active_matches = matches_in_live_window(matches)
    if not active_matches:
        return []

    client = ApiFootballClient()
    fixtures_by_id: dict[str, dict[str, Any]] = {}

    try:
        for fixture in client.live_fixtures():
            current_fixture_id = fixture_id(fixture)
            if current_fixture_id and fixture_allowed(fixture):
                fixtures_by_id[current_fixture_id] = fixture

        for match in active_matches:
            configured_id = match.api_football_fixture_id
            if not configured_id or configured_id in fixtures_by_id:
                continue
            fixture = client.fixture_by_id(configured_id)
            if fixture and fixture_allowed(fixture) and fixture_active_enough(fixture):
                fixtures_by_id[configured_id] = fixture

        events: list[LiveEvent] = []
        for fixture in fixtures_by_id.values():
            match = match_for_fixture(fixture, active_matches)
            if not match:
                continue
            current_fixture_id = fixture_id(fixture)
            if not current_fixture_id:
                continue
            for raw_event in client.fixture_events(current_fixture_id):
                event = normalize_event(match, fixture, raw_event)
                if event:
                    events.append(event)
        return events
    except (requests.RequestException, ValueError, TypeError) as exc:
        logging.warning("Не удалось получить live-события API-FOOTBALL: %s", exc)
        return []


def fetch_confirmed_lineups(matches: list[Match]) -> list[ConfirmedLineup]:
    if not MATCHDAY_LINEUP_ENABLED or not provider_ready():
        return []
    active_matches = matches_in_lineup_window(matches)
    if not active_matches:
        return []

    client = ApiFootballClient()
    lineups: list[ConfirmedLineup] = []
    try:
        for match in active_matches:
            fixture_ref = match.api_football_fixture_id
            if not fixture_ref:
                continue
            fixture = client.fixture_by_id(fixture_ref)
            if not fixture or not fixture_allowed(fixture):
                continue
            for row in client.fixture_lineups(fixture_ref):
                team = row.get("team") or {}
                team_id = str(team.get("id") or "")
                team_label = str(team.get("name") or "")
                if team_id != str(API_FOOTBALL_TEAM_ID) and not REAL_NAME_RE.search(team_label):
                    continue
                starters = [
                    str((entry.get("player") or {}).get("name") or "").strip()
                    for entry in (row.get("startXI") or [])
                ]
                starters = [name for name in starters if name]
                if len(starters) < 8:
                    continue
                formation = str(row.get("formation") or "")
                lineups.append(
                    ConfirmedLineup(
                        key=f"api-football:{fixture_ref}:real-madrid-lineup",
                        match=match,
                        formation=formation,
                        starters=starters[:11],
                    )
                )
        return lineups
    except (requests.RequestException, ValueError, TypeError) as exc:
        logging.warning("Не удалось получить состав API-FOOTBALL: %s", exc)
        return []


def fetch_final_results(matches: list[Match]) -> list[FinalResult]:
    if not MATCHDAY_RESULT_ENABLED or not provider_ready():
        return []
    active_matches = matches_in_result_window(matches)
    if not active_matches:
        return []

    client = ApiFootballClient()
    results: list[FinalResult] = []
    try:
        for match in active_matches:
            fixture_ref = match.api_football_fixture_id
            if not fixture_ref:
                continue
            fixture = client.fixture_by_id(fixture_ref)
            if not fixture or not fixture_allowed(fixture) or fixture_status(fixture) not in FINISHED_STATUSES:
                continue
            score = fixture_score(fixture)
            if not score:
                continue
            results.append(
                FinalResult(
                    key=f"api-football:{fixture_ref}:final:{score}",
                    match=match,
                    score=score,
                    status=fixture_status(fixture),
                )
            )
        return results
    except (requests.RequestException, ValueError, TypeError) as exc:
        logging.warning("Не удалось получить итог матча API-FOOTBALL: %s", exc)
        return []
