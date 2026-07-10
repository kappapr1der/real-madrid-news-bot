from datetime import datetime, timezone
from types import SimpleNamespace

import editorial_archive
import transfer_tracker
from breaking import is_breaking
from match_calendar import Match
from matchday import format_auto_message, format_lineup_message
from source_quality import source_quality_policy, source_trust_tier
from weekly_recap import format_weekly_recap, select_weekly_stories


def test_editorial_archive_merges_breaking_and_digest_story(monkeypatch, tmp_path):
    monkeypatch.setattr(editorial_archive, "ARCHIVE_FILE", tmp_path / "archive.json")
    monkeypatch.setattr(transfer_tracker, "TRACKER_FILE", tmp_path / "tracker.json")

    editorial_archive.record_story(
        kind="breaking",
        title="Real Madrid confirm Michael Olise signing",
        source="X – @realmadrid",
        link="https://example.test/official",
        fingerprint="transfer:olise-real",
        category="transfer",
    )
    second = editorial_archive.record_story(
        kind="digest",
        title="Real Madrid confirm Michael Olise signing",
        source="Marca – Real Madrid",
        link="https://example.test/marca",
        fingerprint="transfer:olise-real",
        category="transfer",
    )

    stories = editorial_archive.recent_stories(days=1)
    assert len(stories) == 1
    assert set(second["kinds"]) == {"breaking", "digest"}
    assert {"X – @realmadrid", "Marca – Real Madrid"} <= set(second["sources"])
    assert transfer_tracker.recent_updates(days=1)[0]["status"] == "официально"


def test_transfer_tracker_keeps_unverified_story_as_rumour(monkeypatch, tmp_path):
    monkeypatch.setattr(transfer_tracker, "TRACKER_FILE", tmp_path / "tracker.json")
    update = transfer_tracker.record_transfer_story(
        {
            "id": "transfer:olise-rumour",
            "title": "Real Madrid could make a move for Michael Olise",
            "source": "Bernabéu Digital",
            "link": "https://example.test/rumour",
            "category": "transfer",
        }
    )
    assert update is not None
    assert update["subject"] == "Майкл Олисе"
    assert update["status"] == "слух"
    assert update["changed"] is True


def test_breaking_requires_reliable_source_and_rejects_rumour():
    assert source_trust_tier("X – @realmadrid") == "official"
    assert is_breaking("Official: Real Madrid announce Michael Olise signing", "X – @realmadrid") is True
    assert is_breaking("Confirmed: Real Madrid could sign Michael Olise", "Bernabéu Digital") is False


def test_source_quality_autopilot_marks_only_very_noisy_sources_as_backup():
    data = {
        "sources": {
            "Noisy Feed": {"label": "Noisy Feed", "candidates": 60, "selected": 10, "quarantined": 42}
        }
    }
    assert source_quality_policy("Noisy Feed", data) == "backup"
    assert source_quality_policy("X – @realmadrid", data) == "normal"


def test_weekly_recap_renders_archived_stories_and_market_block():
    stories = select_weekly_stories(
        [
            {"title": "Official club statement", "link": "https://example.test/one", "source": "Real Madrid", "kinds": ["breaking"], "category": "official"},
            {"title": "Injury update", "link": "https://example.test/two", "source": "Marca", "kinds": ["digest"], "category": "injury"},
            {"title": "Transfer story", "link": "https://example.test/three", "source": "Reporter", "kinds": ["digest"], "category": "transfer"},
        ],
        limit=8,
    )
    message = format_weekly_recap(stories, [{"subject": "Майкл Олисе", "status": "слух"}])
    assert "Белая неделя" in message
    assert "Рынок за неделю" in message
    assert "#ИтогиНедели" in message


def test_match_center_adds_day_before_and_confirmed_lineup_formats():
    match = Match(
        id="test-match",
        competition="La Liga",
        home="Real Madrid",
        away="Opponent",
        kickoff=datetime(2026, 8, 23, 21, 0, tzinfo=timezone.utc),
    )
    day_before = format_auto_message(match, "day_before")
    lineup = format_lineup_message(
        SimpleNamespace(match=match, formation="4-3-3", starters=["Courtois", "Carvajal", "Militao"])
    )
    assert "Завтра матч" in day_before
    assert "Состав «Реала»" in lineup
    assert "4-3-3" in lineup
