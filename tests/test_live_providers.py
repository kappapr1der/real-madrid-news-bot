from datetime import datetime, timezone

from live_providers import fixture_for_match, fixture_matches_match
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
