import json
from datetime import datetime

import match_calendar

from match_calendar import load_matches, match_calendar_status


def test_partial_calendar_tracks_confirmed_and_pending_kickoff_times(tmp_path):
    path = tmp_path / "matches.json"
    path.write_text(
        json.dumps(
            {
                "status": "partial",
                "matches": [
                    {
                        "id": "confirmed",
                        "competition": "La Liga",
                        "home": "Real Madrid",
                        "away": "Espanyol",
                        "kickoff": "2026-08-22T21:30:00+02:00",
                    },
                    {
                        "id": "awaiting-time",
                        "competition": "La Liga",
                        "home": "Real Madrid",
                        "away": "Malaga",
                        "date_hint": "2026-08-30",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    state, _, metrics = match_calendar_status(path)

    assert state == "partial"
    assert metrics["matches"] == 2
    assert metrics["scheduled_matches"] == 1
    assert metrics["pending_kickoff_times"] == 1
    assert [match.id for match in load_matches(path)] == ["confirmed"]


def test_supplemental_calendar_adds_confirmed_friendlies(tmp_path):
    path = tmp_path / "matches.json"
    supplement_dir = tmp_path / "supplements"
    supplement_dir.mkdir()
    path.write_text(
        json.dumps(
            {
                "status": "partial",
                "matches": [
                    {
                        "id": "league-match",
                        "competition": "La Liga",
                        "home": "Real Madrid",
                        "away": "Espanyol",
                        "kickoff": "2026-08-22T21:30:00+02:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (supplement_dir / "preseason.json").write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "id": "friendly-match",
                        "competition": "Friendly",
                        "home": "Real Madrid",
                        "away": "Ferencvaros",
                        "kickoff": "2026-08-08T19:00:00+02:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    state, _, metrics = match_calendar_status(path)

    assert state == "ready"
    assert metrics["matches"] == 2
    assert metrics["supplement_files"] == 1
    assert metrics["supplement_matches"] == 1
    assert [match.id for match in load_matches(path)] == ["friendly-match", "league-match"]


def test_supplemental_friendly_blocks_digest_in_match_window(monkeypatch, tmp_path):
    path = tmp_path / "matches.json"
    supplement_dir = tmp_path / "supplements"
    supplement_dir.mkdir()
    path.write_text(json.dumps({"matches": []}), encoding="utf-8")
    (supplement_dir / "preseason.json").write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "id": "friendly-match",
                        "competition": "Friendly",
                        "home": "Real Madrid",
                        "away": "Fiorentina",
                        "kickoff": "2026-08-08T19:00:00+02:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(match_calendar, "load_matches", lambda: load_matches(path))

    reason = match_calendar.digest_block_reason(datetime.fromisoformat("2026-08-08T18:00:00+02:00"))

    assert reason is not None
    assert "Fiorentina" in reason
