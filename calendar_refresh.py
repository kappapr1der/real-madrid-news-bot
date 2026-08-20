import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from match_calendar import MATCH_SCHEDULE_FILE, match_rows, parse_kickoff, read_match_payload
from runtime_config import (
    API_FOOTBALL_BASE_URL,
    API_FOOTBALL_KEY,
    API_FOOTBALL_LEAGUE_IDS,
    API_FOOTBALL_REQUEST_TIMEOUT_SECONDS,
    API_FOOTBALL_TEAM_ID,
    CALENDAR_REFRESH_ENABLED,
    CALENDAR_REFRESH_SEASON,
    get_log_file,
)
from status_manager import record_error, record_status


LOG_FILE = get_log_file("calendar_refresh.log")
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)


def _normal(value: str) -> str:
    return "".join(character for character in (value or "").casefold() if character.isalnum())


def _fixture_team_names(fixture: dict[str, Any]) -> tuple[str, str]:
    teams = fixture.get("teams") or {}
    home = str((teams.get("home") or {}).get("name") or "")
    away = str((teams.get("away") or {}).get("name") or "")
    return home, away


def _fixture_kickoff(fixture: dict[str, Any]):
    raw = str((fixture.get("fixture") or {}).get("date") or "")
    if not raw:
        return None
    try:
        return parse_kickoff(raw)
    except (TypeError, ValueError):
        return None


def _fixture_id(fixture: dict[str, Any]) -> str:
    return str((fixture.get("fixture") or {}).get("id") or "")


def _fixture_allowed(fixture: dict[str, Any]) -> bool:
    if not API_FOOTBALL_LEAGUE_IDS:
        return True
    try:
        return int((fixture.get("league") or {}).get("id")) in API_FOOTBALL_LEAGUE_IDS
    except (TypeError, ValueError):
        return False


def _same_fixture(row: dict[str, Any], fixture: dict[str, Any]) -> bool:
    home, away = _fixture_team_names(fixture)
    if {_normal(row.get("home", "")), _normal(row.get("away", ""))} != {_normal(home), _normal(away)}:
        return False
    kickoff = _fixture_kickoff(fixture)
    if not kickoff:
        return False
    existing = row.get("kickoff")
    if existing:
        try:
            return parse_kickoff(str(existing)).date() == kickoff.date()
        except (TypeError, ValueError):
            return False
    hint = str(row.get("date_hint") or row.get("date") or "")
    if "/" in hint:
        first, last = hint.split("/", 1)
        try:
            start = datetime.fromisoformat(first).date()
            end = datetime.fromisoformat(f"{first[:8]}{last}").date()
        except ValueError:
            return kickoff.date().isoformat() == first
        return start <= kickoff.date() <= end
    return kickoff.date().isoformat() == hint


def merge_api_football_fixtures(payload: dict[str, Any], fixtures: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Only enrich known Real Madrid fixtures, never create speculative rows."""
    rows = match_rows(payload)
    if not isinstance(rows, list):
        return payload, []
    updated: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for fixture in fixtures:
            if not isinstance(fixture, dict) or not _fixture_allowed(fixture) or not _same_fixture(row, fixture):
                continue
            kickoff = _fixture_kickoff(fixture)
            fixture_id = _fixture_id(fixture)
            if not kickoff:
                continue
            next_kickoff = kickoff.isoformat()
            changed = row.get("kickoff") != next_kickoff
            changed = changed or (fixture_id and row.get("api_football_fixture_id") != fixture_id)
            row["kickoff"] = next_kickoff
            if fixture_id:
                row["api_football_fixture_id"] = fixture_id
            if changed:
                updated.append(str(row.get("id") or row.get("home") or "match"))
            break
    return payload, updated


def fetch_api_football_fixtures() -> list[dict[str, Any]]:
    if not API_FOOTBALL_KEY:
        return []
    url = f"{API_FOOTBALL_BASE_URL.rstrip('/')}/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    fixtures: list[dict[str, Any]] = []
    for league in API_FOOTBALL_LEAGUE_IDS or [None]:
        params: dict[str, Any] = {"team": API_FOOTBALL_TEAM_ID, "season": CALENDAR_REFRESH_SEASON}
        if league is not None:
            params["league"] = league
        response = requests.get(url, headers=headers, params=params, timeout=API_FOOTBALL_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("response", []) if isinstance(payload, dict) else []
        fixtures.extend(row for row in rows if isinstance(row, dict))
    return fixtures


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def refresh_calendar(force: bool = False, path: Path = MATCH_SCHEDULE_FILE) -> bool:
    metrics: dict[str, Any] = {"season": CALENDAR_REFRESH_SEASON, "force": force}
    if not CALENDAR_REFRESH_ENABLED and not force:
        record_status("calendar_refresh", "disabled", "CALENDAR_REFRESH_ENABLED=false", metrics)
        return False
    if not API_FOOTBALL_KEY:
        record_status("calendar_refresh", "waiting", "API_FOOTBALL_KEY is missing", metrics)
        return False
    payload, error = read_match_payload(path)
    if error or not isinstance(payload, dict):
        record_error("calendar_refresh", error or "calendar payload is invalid", metrics)
        return False
    try:
        fixtures = fetch_api_football_fixtures()
        updated_payload, updated = merge_api_football_fixtures(payload, fixtures)
    except (requests.RequestException, ValueError, TypeError) as exc:
        record_error("calendar_refresh", f"API-FOOTBALL refresh failed: {exc}", metrics)
        return False

    metrics.update({"provider_fixtures": len(fixtures), "updated_matches": len(updated), "updated_ids": updated})
    if updated:
        updated_payload["updated_at"] = datetime.now().astimezone().isoformat()
        updated_payload["refresh_source"] = "api-football"
        _write_payload(path, updated_payload)
        record_status("calendar_refresh", "ok", "calendar kickoff times refreshed", metrics)
        return True
    record_status("calendar_refresh", "ok", "calendar already up to date", metrics)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot calendar refresh")
    parser.add_argument("--force", action="store_true", help="run even when calendar refresh is disabled")
    args = parser.parse_args()
    refresh_calendar(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
