import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta
from html import unescape
from pathlib import Path
from typing import Any

import requests

from feed_utils import parse_feed_url
from match_calendar import Match, local_now
from runtime_config import (
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_KEY,
    API_FOOTBALL_REQUEST_TIMEOUT_SECONDS,
    API_FOOTBALL_TEAM_ID,
    CALENDAR_REFRESH_SEASON,
    MATCHDAY_FULLTIME_MINUTES,
    MATCHDAY_LIVE_AFTER_MINUTES,
    MATCHDAY_LIVE_ENABLED,
    MATCHDAY_LIVE_EVENT_TYPES,
    MATCHDAY_LIVE_PROVIDER,
    MATCHDAY_LIVE_SUBSTITUTIONS_ENABLED,
    MATCHDAY_LIVE_SUBSTITUTIONS_REAL_ONLY,
    MATCHDAY_RSS_CONFIRMATION_CACHE_SECONDS,
    MATCHDAY_RSS_CONFIRMATION_ENABLED,
    MATCHDAY_RSS_CONFIRMATION_ENTRY_SCAN_LIMIT,
    MATCHDAY_LINEUP_BEFORE_MINUTES,
    MATCHDAY_LINEUP_ENABLED,
    MATCHDAY_RESULT_AFTER_MINUTES,
    MATCHDAY_RESULT_ENABLED,
    SPORTS_LIVE_RSS_URL,
    get_state_file,
)
from sources_international import X_SOURCES

CANCELLED_STATUSES = {"NS", "TBD", "PST", "CANC", "ABD", "AWD", "WO"}
FINISHED_STATUSES = {"FT", "AET", "PEN"}
HTML_TAG_RE = re.compile(r"<[^>]+>")
SCORE_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[-:]\s*(\d{1,2})(?!\d)")
MINUTE_RE = re.compile("(?<!\\d)(\\d{1,3})\\s*(?:['\u2019\u2032]|min\\.?|\u043c\u0438\u043d\\.?)(?!\\w)", re.IGNORECASE)
GOAL_RE = re.compile("\\b(?:go+l+|goal|\u0433\u043e\u043b+)\\b", re.IGNORECASE)
LIVE_MARKERS = ("\u043c\u0430\u0442\u0447", "live", "\u043e\u043d\u043b\u0430\u0439\u043d", "\u043f\u0435\u0440\u0435\u0440\u044b\u0432", "\u0442\u0440\u0430\u043d\u0441\u043b\u044f\u0446", "\u0441\u0447\u0451\u0442", "\u0441\u0447\u0435\u0442", "goal", "\u0433\u043e\u043b")
REAL_MADRID_SIGNAL_NAMES = ("real madrid", "\u043c\u0430\u0434\u0440\u0438\u0434\u0441\u043a\u0438\u0439 \u0440\u0435\u0430\u043b", "\u0440\u0435\u0430\u043b \u043c\u0430\u0434\u0440\u0438\u0434", "\u0440\u0435\u0430\u043b")
REAL_NAME_RE = re.compile(r"\breal\s+madrid\b|\bреал\s+мадрид\b", re.IGNORECASE)
LIVE_FIXTURES_FILE = get_state_file("live_fixtures.json")

# API-Football often returns abbreviated Latin names. Keep the feed readable
# without trying to machine-translate proper names at publication time.
PLAYER_DISPLAY_NAMES = {
    "aciria": "Алексис Чириа",
    "aguler": "Арда Гюлер",
    "alaba": "Давид Алаба",
    "alunin": "Андрей Лунин",
    "andriylunin": "Андрей Лунин",
    "arudiger": "Антонио Рюдигер",
    "atchouameni": "Орельен Тчуамени",
    "alexisciria": "Алексис Чириа",
    "antoniorudiger": "Антонио Рюдигер",
    "ardaguler": "Арда Гюлер",
    "aurelientchouameni": "Орельен Тчуамени",
    "bdiaz": "Браим Диас",
    "bsilva": "Бернарду Силва",
    "bernardosilva": "Бернарду Силва",
    "brahimdiaz": "Браим Диас",
    "cespi": "Карлос Эспи",
    "carlosespi": "Карлос Эспи",
    "ddumfries": "Дензел Думфрис",
    "deanhuijsen": "Дин Хёйсен",
    "dcarvajal": "Дани Карвахаль",
    "dhuijsen": "Дин Хёйсен",
    "dumfries": "Дензел Думфрис",
    "edermilitao": "Эдер Милитао",
    "emilitao": "Эдер Милитао",
    "ecamavinga": "Эдуарду Камавинга",
    "endrick": "Эндрик",
    "fcamavinga": "Эдуарду Камавинга",
    "fvalverde": "Феде Вальверде",
    "fmendy": "Ферлан Менди",
    "ferlandmendy": "Ферлан Менди",
    "francomastantuono": "Франко Мастантуоно",
    "gonzalogarcia": "Гонсало Гарсия",
    "ibrahimakonate": "Ибраима Конате",
    "ikonate": "Ибраима Конате",
    "jbellingham": "Джуд Беллингем",
    "jcesterosancho": "Х. Сестеро Санчо",
    "judebellingham": "Джуд Беллингем",
    "kmbappe": "Килиан Мбаппе",
    "kylianmbappe": "Килиан Мбаппе",
    "mcucurella": "Марк Кукурелья",
    "marccucurella": "Марк Кукурелья",
    "mrivas": "М. Ривас",
    "rodrygo": "Родриго",
    "rodrygogoes": "Родриго",
    "talexanderarnold": "Трент Александер-Арнольд",
    "tcourtois": "Тибо Куртуа",
    "trentalexanderarnold": "Трент Александер-Арнольд",
    "thibautcourtois": "Тибо Куртуа",
    "viniciusjr": "Винисиус Жуниор",
    "viniciusjunior": "Винисиус Жуниор",
    "vjunior": "Винисиус Жуниор",
}


@dataclass(frozen=True)
class LiveEvent:
    key: str
    match: Match
    minute: str
    kind: str
    score: str
    text: str


@dataclass(frozen=True)
class RssLiveSignal:
    match: Match
    source: str
    score: str
    minute: str
    event_kind: str


@dataclass(frozen=True)
class ConfirmedLineup:
    key: str
    match: Match
    formation: str
    starters: list[str]


@dataclass(frozen=True)
class GoalSummary:
    minute: str
    player: str
    team: str


@dataclass(frozen=True)
class FinalResult:
    key: str
    match: Match
    score: str
    status: str
    goals: list[GoalSummary] = field(default_factory=list)
    real_starters: list[str] = field(default_factory=list)


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
        start = kickoff
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
        end = kickoff + timedelta(minutes=MATCHDAY_FULLTIME_MINUTES + MATCHDAY_RESULT_AFTER_MINUTES)
        if start <= now <= end:
            active.append(match)
    return active


def fixture_id(fixture: dict[str, Any]) -> str:
    return str((fixture.get("fixture") or {}).get("id") or "")


def fixture_status(fixture: dict[str, Any]) -> str:
    status = (fixture.get("fixture") or {}).get("status") or {}
    return str(status.get("short") or "")


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


def similar_team_names(first: str, second: str) -> bool:
    normalized_first = normalize_name(first)
    normalized_second = normalize_name(second)
    if not normalized_first or not normalized_second:
        return False
    return normalized_first == normalized_second or (
        min(len(normalized_first), len(normalized_second)) >= 5
        and (normalized_first in normalized_second or normalized_second in normalized_first)
    )


def fixture_matches_match(fixture: dict[str, Any], match: Match) -> bool:
    home_name, away_name = fixture_team_names(fixture)
    direct = similar_team_names(home_name, match.home) and similar_team_names(away_name, match.away)
    reverse = similar_team_names(home_name, match.away) and similar_team_names(away_name, match.home)
    return direct or reverse


def match_for_fixture(fixture: dict[str, Any], active_matches: list[Match]) -> Match | None:
    current_fixture_id = fixture_id(fixture)
    for match in active_matches:
        if match.api_football_fixture_id and match.api_football_fixture_id == current_fixture_id:
            return match

    for match in active_matches:
        if fixture_matches_match(fixture, match):
            return match

    return None


def fixture_for_match(client: ApiFootballClient, match: Match) -> dict[str, Any] | None:
    if match.api_football_fixture_id:
        return client.fixture_by_id(match.api_football_fixture_id)

    observed_fixture_id = load_observed_fixture_ids().get(match.id, "")
    if observed_fixture_id:
        fixture = client.fixture_by_id(observed_fixture_id)
        if fixture:
            return fixture

    # A concrete entry in the calendar allows a friendly outside the league IDs.
    fixtures = client.get(
        "fixtures",
        {
            "team": API_FOOTBALL_TEAM_ID,
            "date": match.kickoff.date().isoformat(),
            "season": CALENDAR_REFRESH_SEASON,
        },
    )
    for fixture in fixtures:
        if fixture_matches_match(fixture, match):
            return fixture
    return None


def event_allowed(raw_event: dict[str, Any]) -> bool:
    event_type = str(raw_event.get("type") or "").casefold()
    if MATCHDAY_LIVE_EVENT_TYPES and event_type not in MATCHDAY_LIVE_EVENT_TYPES:
        return False
    if event_type == "subst":
        return MATCHDAY_LIVE_SUBSTITUTIONS_ENABLED and (
            not MATCHDAY_LIVE_SUBSTITUTIONS_REAL_ONLY or team_is_real(raw_event)
        )
    if event_type == "card":
        detail = str(raw_event.get("detail") or "").casefold()
        return "red" in detail or "second yellow" in detail
    return True


def event_minute(raw_event: dict[str, Any]) -> str:
    time_info = raw_event.get("time") or {}
    elapsed = time_info.get("elapsed")
    extra = time_info.get("extra")
    if elapsed is None:
        return ""
    return f"{elapsed}+{extra}" if extra else str(elapsed)


def player_name(raw_event: dict[str, Any], field: str) -> str:
    value = (raw_event.get(field) or {}).get("name")
    return display_player_name(str(value or ""))


def display_player_name(value: str) -> str:
    clean = value.strip()
    if not clean:
        return ""
    decomposed = unicodedata.normalize("NFKD", clean)
    ascii_name = "".join(char for char in decomposed if not unicodedata.combining(char))
    key = re.sub(r"[^a-z0-9]+", "", ascii_name.casefold())
    return PLAYER_DISPLAY_NAMES.get(key, clean)


def team_name(raw_event: dict[str, Any]) -> str:
    value = (raw_event.get("team") or {}).get("name")
    return str(value or "").strip()


def team_is_real(raw_event: dict[str, Any]) -> bool:
    team = raw_event.get("team") or {}
    if str(team.get("id") or "") == str(API_FOOTBALL_TEAM_ID):
        return True
    return bool(REAL_NAME_RE.search(str(team.get("name") or "")))


def load_observed_fixture_ids(path: Path | None = None) -> dict[str, str]:
    path = path or LIVE_FIXTURES_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(match_id): str(fixture_id)
        for match_id, fixture_id in raw.items()
        if str(match_id).strip() and str(fixture_id).strip()
    }


def remember_fixture_id(match: Match, fixture: dict[str, Any], path: Path | None = None) -> None:
    path = path or LIVE_FIXTURES_FILE
    fixture_ref = fixture_id(fixture)
    if not fixture_ref:
        return
    known = load_observed_fixture_ids(path)
    if known.get(match.id) == fixture_ref:
        return
    known[match.id] = fixture_ref
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(known, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logging.warning("Не удалось сохранить live fixture ID: %s", exc)


def live_team_label(match: Match, is_real: bool) -> str:
    if is_real:
        return "«Реал»"
    opponent = match.away if match.is_home else match.home
    names = {
        "ferencvaros": "«Ференцварош»",
        "ferencvarosi tc": "«Ференцварош»",
        "fiorentina": "«Фиорентина»",
        "schalke 04": "«Шальке 04»",
        "deportivo": "«Депортиво»",
    }
    return names.get(opponent.casefold(), opponent)


def fixture_score(fixture: dict[str, Any]) -> str:
    goals = fixture.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return ""
    return f"{home}:{away}"


def score_from_events(match: Match, raw_events: list[dict[str, Any]]) -> str:
    home_goals = 0
    away_goals = 0
    real_is_home = bool(REAL_NAME_RE.search(match.home))
    for raw_event in raw_events:
        if str(raw_event.get("type") or "").casefold() != "goal":
            continue
        scored_by_real = team_is_real(raw_event)
        if "own" in str(raw_event.get("detail") or "").casefold():
            scored_by_real = not scored_by_real
        if scored_by_real == real_is_home:
            home_goals += 1
        else:
            away_goals += 1
    return f"{home_goals}:{away_goals}" if home_goals or away_goals else ""


def observed_fixture_shell(match: Match, observed_fixture_id: str) -> dict[str, Any]:
    return {
        "fixture": {"id": observed_fixture_id},
        "teams": {"home": {"name": match.home}, "away": {"name": match.away}},
    }


def normalize_signal_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\u0430-\u044f\u0451:-]+", " ", without_accents.casefold())).strip()


def entry_signal_text(entry: dict[str, Any]) -> str:
    raw = " ".join(
        str(entry.get(field) or "")
        for field in ("title", "summary", "description")
    )
    return normalize_signal_text(unescape(HTML_TAG_RE.sub(" ", raw)))


def text_score(text: str) -> str:
    match = SCORE_RE.search(text)
    if not match:
        return ""
    home, away = match.groups()
    if int(home) == 0 and int(away) == 0:
        return ""
    return f"{home}:{away}"


def text_minute(text: str) -> str:
    match = MINUTE_RE.search(text)
    return match.group(1) if match else ""


def text_event_kind(text: str) -> str:
    return "goal" if GOAL_RE.search(text) else ""


def text_has_phrase(text: str, phrase: str) -> bool:
    clean = normalize_signal_text(phrase)
    return bool(clean) and f" {clean} " in f" {text} "


def match_opponent(match: Match) -> str:
    home_is_real = bool(REAL_NAME_RE.search(match.home))
    away_is_real = bool(REAL_NAME_RE.search(match.away))
    return match.away if home_is_real else match.home if away_is_real else ""


def sports_entry_matches_match(text: str, match: Match) -> bool:
    mentions_real = any(text_has_phrase(text, name) for name in REAL_MADRID_SIGNAL_NAMES)
    if not mentions_real:
        return False
    opponent = match_opponent(match)
    mentions_opponent = text_has_phrase(text, opponent)
    has_live_context = any(marker in text for marker in LIVE_MARKERS)
    return mentions_opponent or has_live_context


def sports_live_source() -> dict[str, Any] | None:
    if not SPORTS_LIVE_RSS_URL:
        return None
    return {
        "url": SPORTS_LIVE_RSS_URL,
        "label": "Sports.ru live signal",
        "cache_seconds": MATCHDAY_RSS_CONFIRMATION_CACHE_SECONDS,
        "rss_require_entries": True,
    }


def official_x_live_sources() -> list[dict[str, Any]]:
    return [source for source in X_SOURCES if source.get("kind") == "x_official"]


def fetch_rss_live_signals(matches: list[Match]) -> list[RssLiveSignal]:
    """Read public RSS only as a signal. Nothing from it is publishable text."""
    if not MATCHDAY_RSS_CONFIRMATION_ENABLED or not matches:
        return []

    signals: list[RssLiveSignal] = []
    sports_source = sports_live_source()
    if sports_source:
        feed = parse_feed_url(sports_source)
        entries = list(getattr(feed, "entries", []) or [])[:MATCHDAY_RSS_CONFIRMATION_ENTRY_SCAN_LIMIT]
        for entry in entries:
            text = entry_signal_text(entry)
            score = text_score(text)
            if not score:
                continue
            for match in matches:
                if sports_entry_matches_match(text, match):
                    signals.append(
                        RssLiveSignal(
                            match=match,
                            source="sports",
                            score=score,
                            minute=text_minute(text),
                            event_kind=text_event_kind(text),
                        )
                    )

    # The official account supplies match context during the one active Real Madrid game.
    # It may not include the opponent or score in every post, so its text is never published.
    if len(matches) == 1:
        match = matches[0]
        for source in official_x_live_sources():
            feed = parse_feed_url(source)
            entries = list(getattr(feed, "entries", []) or [])[:MATCHDAY_RSS_CONFIRMATION_ENTRY_SCAN_LIMIT]
            for entry in entries:
                text = entry_signal_text(entry)
                score = text_score(text)
                event_kind = text_event_kind(text)
                if not score and not event_kind:
                    continue
                signals.append(
                    RssLiveSignal(
                        match=match,
                        source="official_x",
                        score=score,
                        minute=text_minute(text),
                        event_kind=event_kind,
                    )
                )
    return signals


def render_confirmed_score_text(match: Match, score: str) -> str:
    return f"\u041d\u0430 \u0442\u0430\u0431\u043b\u043e: {match.home} {score.replace(':', ' \u2013 ')} {match.away}."


def fetch_confirmed_rss_live_events(matches: list[Match], api_events: list[LiveEvent]) -> list[LiveEvent]:
    """Turn a Sports.ru score into a post only after API-Football or @realmadrid confirms it."""
    if not MATCHDAY_RSS_CONFIRMATION_ENABLED:
        return []

    active_matches = matches_in_live_window(matches)
    if not active_matches:
        return []

    signals = fetch_rss_live_signals(active_matches)
    sports_signals = [signal for signal in signals if signal.source == "sports"]
    if not sports_signals:
        return []

    api_scores = {(event.match.id, event.score) for event in api_events if event.score}
    api_goal_scores = {
        (event.match.id, event.score)
        for event in api_events
        if event.score and event.kind.casefold() == "\u0433\u043e\u043b"
    }
    official_signals = [signal for signal in signals if signal.source == "official_x"]
    confirmed: list[LiveEvent] = []
    seen: set[tuple[str, str]] = set()
    for signal in sports_signals:
        pair = (signal.match.id, signal.score)
        if pair in seen or pair in api_goal_scores:
            continue
        official_match_signals = [item for item in official_signals if item.match.id == signal.match.id]
        official_confirms = any(
            item.score == signal.score or item.event_kind == "goal"
            for item in official_match_signals
        )
        if pair not in api_scores and not official_confirms:
            continue
        minute = signal.minute or next(
            (item.minute for item in official_match_signals if item.minute),
            "",
        )
        confirmed.append(
            LiveEvent(
                key=f"rss-confirmed:{signal.match.id}:{signal.score}",
                match=signal.match,
                minute=minute,
                kind="\u0421\u0447\u0451\u0442",
                score=signal.score,
                text=render_confirmed_score_text(signal.match, signal.score),
            )
        )
        seen.add(pair)
    return confirmed


def event_kind(raw_event: dict[str, Any]) -> str:
    event_type = str(raw_event.get("type") or "")
    event_type_lower = event_type.casefold()
    if event_type_lower == "goal":
        return "Гол «Реала»" if team_is_real(raw_event) else "Гол соперника"
    if event_type_lower == "card":
        return "Удаление «Реала»" if team_is_real(raw_event) else "Удаление соперника"
    if event_type_lower == "subst":
        return "Белая ротация" if team_is_real(raw_event) else "Ротация соперника"
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
    side = live_team_label(match, is_real)

    if event_type == "goal":
        scorer = player or ("игрок «Реала»" if is_real else event_team or "соперник")
        if "own" in detail_lower:
            if is_real:
                return f"Автогол «Реала»: {scorer}."
            return "Автогол соперника. «Реал» получает преимущество."
        if "penalty" in detail_lower:
            action = "точен с пенальти" if is_real else "забивает с пенальти"
        else:
            action = "завершает атаку «Реала»" if is_real else "забивает"
        if is_real:
            extra = f" Голевой пас: {assist}." if assist else ""
            return f"ГОЛ! {scorer} {action}.{extra}"
        return f"{side} отвечает: {scorer} {action}."

    if event_type == "card":
        target = player or event_team or "участник эпизода"
        if is_real:
            return f"Удаление у «Реала»: {target}. Впереди игра в меньшинстве."
        return f"Удаление у {side}: {target}. «Реал» получает численное преимущество."

    if event_type == "subst":
        out_player = player or "игрок"
        in_player = assist or "свежий игрок"
        return f"{side} меняет состав: {in_player} вместо {out_player}."

    if event_type == "var":
        subject = player or side
        return f"VAR в деле: проверяют эпизод с участием {subject}. Ждём решения."

    subject = player or side
    detail_text = f" ({detail})" if detail else ""
    return f"Эпизод у {subject}{detail_text}."


def event_key(fixture: dict[str, Any], raw_event: dict[str, Any]) -> str:
    event_type = str(raw_event.get("type") or "").casefold()
    payload = {
        "fixture": fixture_id(fixture),
        "time": raw_event.get("time"),
        "team": raw_event.get("team"),
        "type": event_type,
    }
    if event_type == "goal":
        payload["score"] = fixture_score(fixture)
    else:
        payload.update(
            {
                "player": raw_event.get("player"),
                "assist": raw_event.get("assist"),
                "detail": raw_event.get("detail"),
                "comments": raw_event.get("comments"),
            }
        )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"api-football:{fixture_id(fixture)}:{digest}"


def normalize_event(
    match: Match,
    fixture: dict[str, Any],
    raw_event: dict[str, Any],
    score: str | None = None,
) -> LiveEvent | None:
    if not event_allowed(raw_event):
        return None
    event_type = str(raw_event.get("type") or "").casefold()
    if event_type == "subst":
        return None
    if event_type == "goal" and not player_name(raw_event, "player"):
        return None
    score = score if score is not None else fixture_score(fixture)
    return LiveEvent(
        key=event_key(fixture, raw_event),
        match=match,
        minute=event_minute(raw_event),
        kind=event_kind(raw_event),
        score=score,
        text=render_event_text(match, raw_event, score),
    )


def substitution_group_key(fixture: dict[str, Any], events: list[dict[str, Any]]) -> str:
    first = events[0]
    payload = {
        "fixture": fixture_id(fixture),
        "minute": event_minute(first),
        "team": first.get("team"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"api-football:{fixture_id(fixture)}:subst:{digest}"


def compact_player_names(names: list[str], limit: int = 5) -> str:
    visible = [name for name in names if name][:limit]
    suffix = f" и ещё {len(names) - len(visible)}" if len(names) > len(visible) else ""
    return ", ".join(visible) + suffix


def render_substitution_group_text(match: Match, events: list[dict[str, Any]]) -> str:
    first = events[0]
    side = live_team_label(match, team_is_real(first))
    incoming = compact_player_names([player_name(event, "assist") for event in events])
    outgoing = compact_player_names([player_name(event, "player") for event in events])
    if len(events) == 1:
        incoming_name = incoming or "свежий игрок"
        outgoing_name = outgoing or "игрок"
        owner = "«Реала»" if team_is_real(first) else side
        return f"Замена у {owner}: {incoming_name} вместо {outgoing_name}."
    return "\n".join(
        [
            f"{side} освежает состав.",
            f"На поле: {incoming or 'свежие игроки'}.",
            f"Покидают поле: {outgoing or 'игроки стартового состава'}.",
        ]
    )


def normalize_live_events(
    match: Match,
    fixture: dict[str, Any],
    raw_events: list[dict[str, Any]],
    score: str | None = None,
) -> list[LiveEvent]:
    indexed_events: list[tuple[int, LiveEvent]] = []
    substitution_groups: dict[tuple[str, str], tuple[int, list[dict[str, Any]]]] = {}
    for index, raw_event in enumerate(raw_events):
        if str(raw_event.get("type") or "").casefold() == "subst":
            if not event_allowed(raw_event):
                continue
            group = (event_minute(raw_event), json.dumps(raw_event.get("team") or {}, sort_keys=True))
            if group not in substitution_groups:
                substitution_groups[group] = (index, [])
            substitution_groups[group][1].append(raw_event)
            continue
        event = normalize_event(match, fixture, raw_event, score=score)
        if event:
            indexed_events.append((index, event))

    score = score if score is not None else fixture_score(fixture)
    for first_index, events in substitution_groups.values():
        if not events:
            continue
        indexed_events.append(
            (
                first_index,
                LiveEvent(
                    key=substitution_group_key(fixture, events),
                    match=match,
                    minute=event_minute(events[0]),
                    kind=event_kind(events[0]),
                    score=score,
                    text=render_substitution_group_text(match, events),
                ),
            )
        )
    return [event for _, event in sorted(indexed_events, key=lambda item: item[0])]


def fetch_live_events(matches: list[Match]) -> list[LiveEvent]:
    if not provider_ready():
        return []

    active_matches = matches_in_live_window(matches)
    if not active_matches:
        return []

    client = ApiFootballClient()
    fixtures_by_match: dict[str, dict[str, Any]] = {}
    observed_fixtures = load_observed_fixture_ids()

    try:
        for match in active_matches:
            observed_fixture_id = match.api_football_fixture_id or observed_fixtures.get(match.id, "")
            if observed_fixture_id:
                fixtures_by_match[match.id] = observed_fixture_shell(match, observed_fixture_id)

        unresolved_matches = [match for match in active_matches if match.id not in fixtures_by_match]
        if unresolved_matches:
            for fixture in client.live_fixtures():
                matched = match_for_fixture(fixture, unresolved_matches)
                current_fixture_id = fixture_id(fixture)
                if matched and current_fixture_id:
                    fixtures_by_match[matched.id] = fixture

        for match in unresolved_matches:
            if match.id in fixtures_by_match:
                continue
            fixture = fixture_for_match(client, match)
            current_fixture_id = fixture_id(fixture) if fixture else ""
            if fixture and current_fixture_id and fixture_active_enough(fixture):
                fixtures_by_match[match.id] = fixture

        events: list[LiveEvent] = []
        for match in active_matches:
            fixture = fixtures_by_match.get(match.id)
            if not fixture:
                continue
            current_fixture_id = fixture_id(fixture)
            if not current_fixture_id:
                continue
            remember_fixture_id(match, fixture)
            raw_events = client.fixture_events(current_fixture_id)
            score = fixture_score(fixture) or score_from_events(match, raw_events)
            events.extend(normalize_live_events(match, fixture, raw_events, score=score))
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
            fixture = fixture_for_match(client, match)
            fixture_ref = fixture_id(fixture) if fixture else ""
            if not fixture or not fixture_ref:
                continue
            for row in client.fixture_lineups(fixture_ref):
                team = row.get("team") or {}
                team_id = str(team.get("id") or "")
                team_label = str(team.get("name") or "")
                if team_id != str(API_FOOTBALL_TEAM_ID) and not REAL_NAME_RE.search(team_label):
                    continue
                starters = [
                    display_player_name(str((entry.get("player") or {}).get("name") or ""))
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
            fixture = fixture_for_match(client, match)
            fixture_ref = fixture_id(fixture) if fixture else ""
            if not fixture or not fixture_ref or fixture_status(fixture) not in FINISHED_STATUSES:
                continue
            score = fixture_score(fixture)
            if not score:
                continue
            goal_events = []
            for raw_event in client.fixture_events(fixture_ref):
                if str(raw_event.get("type") or "").casefold() != "goal":
                    continue
                scorer = player_name(raw_event, "player")
                if not scorer:
                    continue
                goal_events.append(
                    GoalSummary(
                        minute=event_minute(raw_event),
                        player=scorer,
                        team=team_name(raw_event),
                    )
                )
            real_starters = []
            for lineup in client.fixture_lineups(fixture_ref):
                team = lineup.get("team") or {}
                team_id = str(team.get("id") or "")
                team_label = str(team.get("name") or "")
                if team_id != str(API_FOOTBALL_TEAM_ID) and not REAL_NAME_RE.search(team_label):
                    continue
                real_starters = [
                    display_player_name(str((entry.get("player") or {}).get("name") or ""))
                    for entry in (lineup.get("startXI") or [])
                ]
                real_starters = [name for name in real_starters if name]
                break
            results.append(
                FinalResult(
                    key=f"api-football:{fixture_ref}:final:{score}",
                    match=match,
                    score=score,
                    status=fixture_status(fixture),
                    goals=goal_events,
                    real_starters=real_starters[:11],
                )
            )
        return results
    except (requests.RequestException, ValueError, TypeError) as exc:
        logging.warning("Не удалось получить итог матча API-FOOTBALL: %s", exc)
        return []
