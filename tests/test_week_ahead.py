from datetime import datetime
from zoneinfo import ZoneInfo

from week_ahead import fixtures_from_rows, format_week_ahead, select_week_fixtures


TZ = ZoneInfo("Europe/Moscow")


def test_week_ahead_keeps_date_only_fixture_but_does_not_invent_kickoff_time():
    fixtures = fixtures_from_rows(
        [
            {
                "id": "known",
                "competition": "La Liga",
                "round": "Matchday 2",
                "home": "Espanyol",
                "away": "Real Madrid",
                "kickoff": "2026-08-22T22:30:00+03:00",
            },
            {
                "id": "pending",
                "competition": "UEFA Champions League",
                "round": "League phase",
                "home": "Real Madrid",
                "away": "Opponent",
                "date_hint": "2026-08-25",
            },
        ]
    )

    selected = select_week_fixtures(fixtures, now=datetime(2026, 8, 20, 10, tzinfo=TZ), days=8)
    message = format_week_ahead(selected)

    assert len(selected) == 2
    assert "сб, 22.08 · 22:30" in message
    assert "вт, 25.08 · время уточняется" in message
    assert "«Espanyol» - «Реал»" in message
    assert "#Календарь" in message


def test_week_ahead_ignores_fixture_outside_the_upcoming_window():
    fixtures = fixtures_from_rows(
        [
            {
                "id": "later",
                "competition": "La Liga",
                "home": "Real Madrid",
                "away": "Opponent",
                "date_hint": "2026-09-10",
            }
        ]
    )

    assert select_week_fixtures(fixtures, now=datetime(2026, 8, 20, tzinfo=TZ), days=8) == []


def test_week_ahead_does_not_present_a_weekend_range_as_a_confirmed_match_date():
    fixtures = fixtures_from_rows(
        [
            {
                "id": "weekend",
                "competition": "La Liga",
                "home": "Real Madrid",
                "away": "Real Betis",
                "date_hint": "2026-09-05/06",
            }
        ]
    )

    message = format_week_ahead(fixtures)

    assert "5/6.09 · время уточняется" in message
    assert "сб, 05.09" not in message
