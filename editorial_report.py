import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from breaking_confirmation import confirmation_summary
from match_calendar import match_calendar_status
from runtime_config import (
    DIGEST_TIMEZONE,
    EDITORIAL_REPORT_ENABLED,
    get_state_file,
)
from source_quality import load_source_quality, summarize_source_quality
from status_manager import record_status
from story_lifecycle import lifecycle_summary


REPORT_DIR = get_state_file("reports")


def _source_lines(rows: list[dict]) -> list[str]:
    if not rows:
        return ["- no data"]
    return [
        "- {source}: selected {selected}/{candidates}, quarantined {quarantined}, policy {policy}".format(**row)
        for row in rows[:6]
    ]


def format_editorial_report(
    *,
    quality: dict,
    confirmations: dict[str, int],
    lifecycle: dict[str, int],
    calendar: tuple[str, str, dict],
    now: datetime,
) -> str:
    state, calendar_message, calendar_metrics = calendar
    lines = [
        f"# Coffee Bot editorial report - {now:%Y-%m-%d}",
        "",
        "## Source quality",
        f"Tracked sources: {quality.get('tracked_sources', 0)}",
        "",
        "### Productive",
        *_source_lines(quality.get("productive", [])),
        "",
        "### Noisy",
        *_source_lines(quality.get("noisy", [])),
        "",
        "## Breaking confirmation",
        f"Waiting stories: {confirmations.get('waiting', 0)}",
        f"Corroborated stories: {confirmations.get('verified', 0)}",
        "",
        "## Story lifecycle",
        f"Tracked: {lifecycle.get('tracked', 0)}",
        f"Transfers: {lifecycle.get('transfers', 0)}",
        f"Injuries: {lifecycle.get('injuries', 0)}",
        f"Contracts: {lifecycle.get('contracts', 0)}",
        "",
        "## Calendar",
        f"State: {state}",
        f"Details: {calendar_message}",
        f"Confirmed kickoff times: {calendar_metrics.get('scheduled_matches', 0)}",
        f"Pending kickoff times: {calendar_metrics.get('pending_kickoff_times', 0)}",
        "",
    ]
    return "\n".join(lines)


def write_editorial_report(force: bool = False) -> Path | None:
    if not EDITORIAL_REPORT_ENABLED and not force:
        record_status("editorial_report", "disabled", "EDITORIAL_REPORT_ENABLED=false")
        return None
    now = datetime.now(ZoneInfo(DIGEST_TIMEZONE))
    report = format_editorial_report(
        quality=summarize_source_quality(load_source_quality()),
        confirmations=confirmation_summary(),
        lifecycle=lifecycle_summary(),
        calendar=match_calendar_status(),
        now=now,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    year, week, _ = now.isocalendar()
    path = REPORT_DIR / f"editorial-{year}-W{week:02d}.md"
    path.write_text(report, encoding="utf-8")
    record_status("editorial_report", "ok", "internal editorial report written", {"path": str(path), "week": f"{year}-W{week:02d}"})
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Coffee Bot internal editorial report")
    parser.add_argument("--force", action="store_true", help="write report even when disabled")
    args = parser.parse_args()
    path = write_editorial_report(force=args.force)
    if path:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
