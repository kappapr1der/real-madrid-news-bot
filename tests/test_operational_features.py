from datetime import datetime, timezone

import breaking_confirmation
import story_lifecycle
from calendar_refresh import merge_api_football_fixtures
from editorial_report import format_editorial_report
from live_providers import FinalResult, GoalSummary
from match_calendar import Match
from matchday import format_final_result_message, player_of_match_options


def test_breaking_confirmation_waits_for_independent_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(breaking_confirmation, "CONFIRMATIONS_FILE", tmp_path / "confirmations.json")

    first = breaking_confirmation.observe_breaking_candidate(
        fingerprint="transfer:olise-real",
        source="Marca - Real Madrid",
        link="https://example.test/marca",
        title="Official: Real Madrid sign Michael Olise",
    )
    repeated = breaking_confirmation.observe_breaking_candidate(
        fingerprint="transfer:olise-real",
        source="Marca - Real Madrid",
        link="https://example.test/marca-update",
        title="Official: Real Madrid sign Michael Olise",
    )
    second = breaking_confirmation.observe_breaking_candidate(
        fingerprint="transfer:olise-real",
        source="Managing Madrid",
        link="https://example.test/managing",
        title="Official: Real Madrid sign Michael Olise",
    )

    assert first.ready is False
    assert repeated.sources == 1
    assert second.ready is True
    assert second.sources == 2


def test_official_source_bypasses_breaking_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(breaking_confirmation, "CONFIRMATIONS_FILE", tmp_path / "confirmations.json")
    result = breaking_confirmation.observe_breaking_candidate(
        fingerprint="official:contract",
        source="X - @realmadrid",
        title="Official: Real Madrid announce a contract extension",
    )
    assert result.ready is True
    assert result.reason == "official_source"


def test_story_lifecycle_only_changes_when_status_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(story_lifecycle, "LIFECYCLE_FILE", tmp_path / "lifecycle.json")
    first = story_lifecycle.record_lifecycle(
        "Real Madrid hold talks for Michael Olise",
        source="Marca - Real Madrid",
        fingerprint="transfer:olise-real",
    )
    repeated = story_lifecycle.record_lifecycle(
        "Real Madrid hold talks for Michael Olise",
        source="Managing Madrid",
        fingerprint="transfer:olise-real",
    )
    official = story_lifecycle.record_lifecycle(
        "Official: Real Madrid announce Michael Olise signing",
        source="X - @realmadrid",
        fingerprint="transfer:olise-real",
    )

    assert first.relevant and first.changed
    assert repeated.relevant and repeated.changed is False
    assert official.relevant and official.changed


def test_calendar_refresh_updates_only_known_fixture_in_its_date_window():
    payload = {
        "matches": [
            {
                "id": "betis-real",
                "home": "Real Betis",
                "away": "Real Madrid",
                "date_hint": "2026-09-05/06",
                "api_football_fixture_id": "",
            }
        ]
    }
    fixture = {
        "fixture": {"id": 123, "date": "2026-09-06T19:00:00+00:00"},
        "league": {"id": 140},
        "teams": {"home": {"name": "Real Betis"}, "away": {"name": "Real Madrid"}},
    }

    updated, ids = merge_api_football_fixtures(payload, [fixture])

    assert ids == ["betis-real"]
    assert updated["matches"][0]["api_football_fixture_id"] == "123"
    assert updated["matches"][0]["kickoff"].startswith("2026-09-06T22:00:00+03:00")


def test_final_result_includes_goal_details_and_poll_candidates():
    match = Match(
        id="result-test",
        competition="La Liga",
        home="Real Madrid",
        away="Opponent",
        kickoff=datetime(2026, 8, 22, 21, 0, tzinfo=timezone.utc),
    )
    result = FinalResult(
        key="result-test",
        match=match,
        score="2:1",
        status="FT",
        goals=[
            GoalSummary(minute="18", player="Kylian Mbappe", team="Real Madrid"),
            GoalSummary(minute="73", player="Opponent scorer", team="Opponent"),
        ],
        real_starters=["Courtois", "Kylian Mbappe", "Jude Bellingham"],
    )

    message = format_final_result_message(result)

    assert "Голы:" in message
    assert "Kylian Mbappe" in message
    assert player_of_match_options(result) == ["Kylian Mbappe", "Courtois", "Jude Bellingham"]


def test_internal_editorial_report_stays_operational_not_channel_copy():
    report = format_editorial_report(
        quality={
            "tracked_sources": 2,
            "productive": [{"source": "Marca", "selected": 8, "candidates": 10, "quarantined": 1, "policy": "normal"}],
            "noisy": [{"source": "Noisy", "selected": 0, "candidates": 8, "quarantined": 7, "policy": "backup"}],
        },
        confirmations={"waiting": 1, "verified": 2},
        lifecycle={"tracked": 4, "transfers": 2, "injuries": 1, "contracts": 1},
        calendar=("partial", "fixture time pending", {"scheduled_matches": 3, "pending_kickoff_times": 35}),
        now=datetime(2026, 7, 19, 12, 20, tzinfo=timezone.utc),
    )

    assert "Source quality" in report
    assert "Noisy" in report
    assert "Telegram" not in report
