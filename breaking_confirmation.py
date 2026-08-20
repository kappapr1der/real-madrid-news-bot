import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from runtime_config import (
    BREAKING_CONFIRMATION_ENABLED,
    BREAKING_CONFIRMATION_MIN_SOURCES,
    BREAKING_CONFIRMATION_TTL_MINUTES,
    get_state_file,
)
from source_quality import normalized_source_name, source_trust_tier


CONFIRMATIONS_FILE = get_state_file("breaking_confirmations.json")


@dataclass(frozen=True)
class ConfirmationDecision:
    ready: bool
    reason: str
    sources: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load() -> dict[str, Any]:
    if not CONFIRMATIONS_FILE.exists():
        return {"version": 1, "entries": {}}
    try:
        data = json.loads(CONFIRMATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": {}}
    if not isinstance(data, dict):
        return {"version": 1, "entries": {}}
    data["version"] = 1
    data["entries"] = data.get("entries") if isinstance(data.get("entries"), dict) else {}
    return data


def _save(data: dict[str, Any]) -> None:
    CONFIRMATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMATIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _prune(entries: dict[str, Any], now: datetime) -> None:
    cutoff = now - timedelta(minutes=max(BREAKING_CONFIRMATION_TTL_MINUTES, 5))
    for key, row in list(entries.items()):
        try:
            last_seen = datetime.fromisoformat(str(row.get("last_seen_at") or "").replace("Z", "+00:00"))
        except (AttributeError, TypeError, ValueError):
            entries.pop(key, None)
            continue
        if last_seen < cutoff:
            entries.pop(key, None)


def observe_breaking_candidate(
    *,
    fingerprint: str,
    source: str,
    link: str = "",
    title: str = "",
    trusted_reporter: bool = False,
    now: datetime | None = None,
) -> ConfirmationDecision:
    """Require two independent sources, while never delaying vetted direct confirmations."""
    tier = source_trust_tier(source)
    if tier == "official":
        return ConfirmationDecision(True, "official_source", 1)
    if trusted_reporter:
        return ConfirmationDecision(True, "trusted_reporter", 1)
    if not BREAKING_CONFIRMATION_ENABLED:
        return ConfirmationDecision(True, "confirmation_disabled", 1)
    if not fingerprint:
        return ConfirmationDecision(False, "missing_fingerprint", 0)

    current = now or _now()
    data = _load()
    entries = data["entries"]
    _prune(entries, current)

    row = entries.setdefault(
        fingerprint,
        {
            "first_seen_at": current.isoformat(),
            "last_seen_at": current.isoformat(),
            "sources": [],
            "links": [],
            "title": title,
        },
    )
    source_key = normalized_source_name(source)
    sources = row.setdefault("sources", [])
    if source_key and source_key not in {normalized_source_name(value) for value in sources}:
        sources.append(source)
    if link and link not in row.setdefault("links", []):
        row["links"].append(link)
    row["last_seen_at"] = current.isoformat()
    row["title"] = title or row.get("title", "")
    row["sources"] = row["sources"][-12:]
    row["links"] = row["links"][-20:]
    _save(data)

    source_count = len(row["sources"])
    required = max(BREAKING_CONFIRMATION_MIN_SOURCES, 2)
    if source_count >= required:
        return ConfirmationDecision(True, "independent_sources", source_count)
    return ConfirmationDecision(False, "awaiting_independent_source", source_count)


def confirmation_summary() -> dict[str, int]:
    data = _load()
    now = _now()
    entries = data["entries"]
    _prune(entries, now)
    _save(data)
    waiting = sum(1 for row in entries.values() if isinstance(row, dict))
    verified = sum(
        1
        for row in entries.values()
        if isinstance(row, dict) and len(row.get("sources") or []) >= max(BREAKING_CONFIRMATION_MIN_SOURCES, 2)
    )
    return {"waiting": waiting, "verified": verified}
