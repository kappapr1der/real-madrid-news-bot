from datetime import datetime, timezone

import live_providers
from live_providers import (
    LiveEvent,
    event_allowed,
    fetch_confirmed_rss_live_events,
    fixture_for_match,
    fixture_matches_match,
    load_observed_fixture_ids,
    normalize_event,
    remember_fixture_id,
)
from match_calendar import Match


def _friendly_match():
    return Match(
        id="friendly-ferencvaros",
        competition="Friendly",
        home="Ferencvaros",
        away="Real Madrid",
        kickoff=datetime(2026, 8, 8, 17, 0, tzinfo=timezone.utc),
    )


def test_fixture_for_scheduled_friendly_uses_calendar_allow_list():
    fixture = {
        "fixture": {"id": 667001},
        "league": {"id": 667, "name": "Club Friendlies"},
        "teams": {"home": {"name": "Ferencvarosi TC"}, "away": {"name": "Real Madrid"}},
    }

    class Client:
        def __init__(self):
            self.calls = []

        def fixture_by_id(self, _fixture_id):
            return None

        def get(self, path, params):
            self.calls.append((path, params))
            return [fixture]

    client = Client()

    assert fixture_matches_match(fixture, _friendly_match()) is True
    assert fixture_for_match(client, _friendly_match()) == fixture
    assert client.calls == [
        (
            "fixtures",
            {"team": 541, "date": "2026-08-08", "season": 2026},
        )
    ]


def test_fixture_for_match_reuses_live_fixture_id_for_final_result(monkeypatch, tmp_path):
    match = _friendly_match()
    fixture = {
        "fixture": {"id": 1604780},
        "league": {"id": 667, "name": "Club Friendlies"},
        "teams": {"home": {"name": "Ferencvarosi TC"}, "away": {"name": "Real Madrid"}},
    }
    fixture_state = tmp_path / "live-fixtures.json"
    monkeypatch.setattr(live_providers, "LIVE_FIXTURES_FILE", fixture_state)
    remember_fixture_id(match, fixture)

    class Client:
        def fixture_by_id(self, fixture_id):
            assert fixture_id == "1604780"
            return fixture

        def get(self, *_args, **_kwargs):
            raise AssertionError("season lookup must not run after a live fixture was observed")

    assert load_observed_fixture_ids() == {match.id: "1604780"}
    assert fixture_for_match(Client(), match) == fixture


def test_live_events_skip_substitutions_yellows_and_incomplete_goals(monkeypatch):
    monkeypatch.setattr(live_providers, "MATCHDAY_LIVE_EVENT_TYPES", {"goal", "card", "subst", "var"})
    monkeypatch.setattr(live_providers, "MATCHDAY_LIVE_SUBSTITUTIONS_ENABLED", False)

    assert event_allowed({"type": "subst"}) is False
    assert event_allowed({"type": "Card", "detail": "Yellow Card"}) is False
    assert event_allowed({"type": "Card", "detail": "Red Card"}) is True

    fixture = {"fixture": {"id": 1604780}, "goals": {"home": 0, "away": 2}}
    raw_goal = {
        "type": "Goal",
        "detail": "Normal Goal",
        "time": {"elapsed": 49},
        "team": {"name": "Real Madrid"},
        "player": {"name": ""},
    }
    assert normalize_event(_friendly_match(), fixture, raw_goal) is None


class Feed:
    def __init__(self, entries):
        self.entries = entries


def _live_match():
    return Match(
        id="friendly-fiorentina",
        competition="Friendly",
        home="Real Madrid",
        away="Fiorentina",
        kickoff=datetime(2026, 8, 1, 16, 0, tzinfo=timezone.utc),
    )


def _configure_rss_live(monkeypatch, sports_entries, official_entries=()):
    monkeypatch.setattr(live_providers, "MATCHDAY_RSS_CONFIRMATION_ENABLED", True)
    monkeypatch.setattr(live_providers, "SPORTS_LIVE_RSS_URL", "https://sports.example/live.xml")
    monkeypatch.setattr(live_providers, "MATCHDAY_RSS_CONFIRMATION_ENTRY_SCAN_LIMIT", 12)
    monkeypatch.setattr(
        live_providers,
        "X_SOURCES",
        [{"url": "https://x.example/realmadrid/rss", "label": "X - @realmadrid", "kind": "x_official"}],
    )
    monkeypatch.setattr(live_providers, "matches_in_live_window", lambda matches: matches)

    def fake_parse(source):
        if source["label"] == "Sports.ru live signal":
            return Feed(sports_entries)
        return Feed(official_entries)

    monkeypatch.setattr(live_providers, "parse_feed_url", fake_parse)


def test_sports_live_score_needs_official_or_api_confirmation(monkeypatch):
    _configure_rss_live(
        monkeypatch,
        [{"title": "\u0420\u0435\u0430\u043b \u041c\u0430\u0434\u0440\u0438\u0434: \u0433\u043e\u043b, 1:0"}],
    )

    assert fetch_confirmed_rss_live_events([_live_match()], []) == []


def test_sports_live_score_posts_own_copy_after_official_x_goal(monkeypatch):
    _configure_rss_live(
        monkeypatch,
        [{"title": "\u0420\u0435\u0430\u043b \u041c\u0430\u0434\u0440\u0438\u0434: \u0433\u043e\u043b, 1:0 \u043d\u0430 17 \u043c\u0438\u043d."}],
        [{"title": "GOOOOOL! 17'"}],
    )

    events = fetch_confirmed_rss_live_events([_live_match()], [])

    assert len(events) == 1
    assert events[0].key == "rss-confirmed:friendly-fiorentina:1:0"
    assert events[0].minute == "17"
    assert events[0].text == "\u041d\u0430 \u0442\u0430\u0431\u043b\u043e: Real Madrid 1 \u2013 0 Fiorentina."
    assert "GOOOOOL" not in events[0].text


def test_sports_live_score_can_be_confirmed_by_api_without_duplicate_goal(monkeypatch):
    match = _live_match()
    _configure_rss_live(
        monkeypatch,
        [{"title": "\u0420\u0435\u0430\u043b \u041c\u0430\u0434\u0440\u0438\u0434: \u0433\u043e\u043b, 2:1"}],
    )

    card_event = LiveEvent(
        key="api-card",
        match=match,
        minute="61",
        kind="\u041a\u0430\u0440\u0442\u043e\u0447\u043a\u0430",
        score="2:1",
        text="card",
    )
    assert len(fetch_confirmed_rss_live_events([match], [card_event])) == 1

    goal_event = LiveEvent(
        key="api-goal",
        match=match,
        minute="60",
        kind="\u0413\u043e\u043b",
        score="2:1",
        text="goal",
    )
    assert fetch_confirmed_rss_live_events([match], [goal_event]) == []
