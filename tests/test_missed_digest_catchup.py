from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from main import (
    digest_completed_today,
    mark_digest_slot_completed,
    preflight_time_for_digest,
    select_missed_digest_candidate,
)


TZ = ZoneInfo("Europe/Moscow")
DIGEST_SLOTS = [
    ("утреннего", "09:00"),
    ("дневного", "15:00"),
    ("вечернего", "21:00"),
]


def test_missed_catchup_uses_latest_past_slot_only():
    now = datetime(2026, 6, 30, 17, 10, tzinfo=TZ)

    candidate = select_missed_digest_candidate(DIGEST_SLOTS, now)

    assert candidate["label"] == "дневного"
    assert candidate["at_time"] == "15:00"
    assert candidate["late_minutes"] == 130


def test_missed_catchup_can_still_pick_morning_before_day_slot():
    now = datetime(2026, 6, 30, 10, 30, tzinfo=TZ)

    candidate = select_missed_digest_candidate(DIGEST_SLOTS, now)

    assert candidate["label"] == "утреннего"
    assert candidate["at_time"] == "09:00"
    assert candidate["late_minutes"] == 90


def test_missed_catchup_waits_before_first_slot():
    now = datetime(2026, 6, 30, 8, 30, tzinfo=TZ)

    assert select_missed_digest_candidate(DIGEST_SLOTS, now) is None


def test_preflight_time_is_before_digest_slot():
    assert preflight_time_for_digest("15:00", 5) == "14:55"
    assert preflight_time_for_digest("09:00", 15) == "08:45"


def test_preflight_time_wraps_previous_day():
    assert preflight_time_for_digest("00:03", 5) == "23:58"


def test_digest_completed_today_reads_label_status():
    now = datetime(2026, 7, 2, 13, 43, tzinfo=TZ)
    status = {
        "services": {
            "digest:утреннего": {
                "state": "completed",
                "updated_at": "2026-07-02T06:00:17+00:00",
                "metrics": {"label": "утреннего"},
            }
        }
    }

    with patch("main.load_status", return_value=status):
        assert digest_completed_today("утреннего", now) is True


def test_digest_completed_today_reads_aggregate_digest_status():
    now = datetime(2026, 7, 2, 13, 43, tzinfo=TZ)
    status = {
        "services": {
            "digest": {
                "state": "ok",
                "updated_at": "2026-07-02T06:00:14+00:00",
                "metrics": {"label": "утреннего"},
            }
        }
    }

    with patch("main.load_status", return_value=status):
        assert digest_completed_today("утреннего", now) is True
        assert digest_completed_today("дневного", now) is False


def test_digest_completed_today_uses_slot_ledger_when_status_is_missing(tmp_path):
    now = datetime(2026, 7, 2, 21, 28, tzinfo=TZ)

    with patch("main.DIGEST_SLOT_RUNS_FILE", tmp_path / "digest_slot_runs.json"):
        mark_digest_slot_completed("вечернего", now)
        with patch("main.load_status", return_value={"services": {}}):
            assert digest_completed_today("вечернего", now) is True
