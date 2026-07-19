import json

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
